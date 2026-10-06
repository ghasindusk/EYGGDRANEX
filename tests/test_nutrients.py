# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""External data nutrients: files in a directory become food (eyggnx.nutrients)."""

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
import zlib

from eyggnx import cli
from eyggnx.config import SimulationConfig
from eyggnx.nutrients import load_nutrients, nutrient_category, nutrient_energy
from eyggnx.recorder import population_metrics
from eyggnx.simulation import Simulation
from eyggnx.world import ResourcePatch


class NutrientDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, data):
        (self.dir / name).write_bytes(data)

    def config(self, **kw):
        return SimulationConfig(nutrient_dir=str(self.dir), **kw)


class LoadingTests(NutrientDirTestCase):
    def test_off_by_default(self):
        patches, manifest = load_nutrients(SimulationConfig())
        self.assertEqual((patches, manifest["files"], manifest["digest"]), ([], [], None))

    def test_only_regular_files_directly_in_the_directory(self):
        self.write("b.txt", b"beta " * 50)
        self.write("a.bin", os.urandom(300))
        (self.dir / "sub").mkdir()
        (self.dir / "sub" / "deep.txt").write_bytes(b"not read" * 100)
        try:
            os.symlink(self.dir / "b.txt", self.dir / "link.txt")
        except (OSError, NotImplementedError):
            pass
        patches, manifest = load_nutrients(self.config())
        self.assertEqual([f["name"] for f in manifest["files"]], ["a.bin", "b.txt"])
        self.assertEqual(len(patches), 2)

    def test_energy_is_compressed_size_and_capped(self):
        cfg = SimulationConfig()
        repetitive, noisy = b"a" * 10_000, os.urandom(10_000)
        self.assertLess(nutrient_energy(repetitive, cfg), nutrient_energy(noisy, cfg))
        self.assertAlmostEqual(nutrient_energy(repetitive, cfg), len(zlib.compress(repetitive, 9)) * 0.01)
        self.assertEqual(nutrient_energy(os.urandom(100_000), SimulationConfig(nutrient_max_energy=200.0)), 200.0)
        self.assertLess(nutrient_energy(os.urandom(100_000), cfg), cfg.nutrient_max_energy)
        self.assertEqual(nutrient_energy(b"", cfg), 0.0)

    def test_names_and_extensions_do_not_matter(self):
        data = b"identical content " * 40
        self.write("x.py", data)
        self.write("y.jpg", data)
        patches, _ = load_nutrients(self.config())
        self.assertEqual((patches[0].x, patches[0].y, patches[0].energy),
                         (patches[1].x, patches[1].y, patches[1].energy))

    def test_patches_are_finite_and_inside_the_world(self):
        for i in range(20):
            self.write(f"f{i}", os.urandom(50 + i))
        patches, _ = load_nutrients(self.config(width=30.0, height=20.0, nutrient_release_rate=0.0))
        for p in patches:
            self.assertTrue(0.0 <= p.x < 30.0 and 0.0 <= p.y < 20.0)
            self.assertEqual((p.regen, p.capacity), (0.0, p.energy))

    def test_limits_on_files_and_bytes(self):
        for i in range(5):
            self.write(f"f{i}", os.urandom(1000))
        patches, manifest = load_nutrients(self.config(nutrient_max_files=3, nutrient_max_bytes=100))
        self.assertEqual(len(patches), 3)
        self.assertEqual(manifest["skipped_over_limit"], 2)
        self.assertTrue(all(f["bytes_read"] == 100 and f["size"] == 1000 for f in manifest["files"]))

    def test_manifest_digest_tracks_content(self):
        self.write("a", b"one" * 30)
        first = load_nutrients(self.config())[1]["digest"]
        self.assertEqual(first, load_nutrients(self.config())[1]["digest"])
        self.write("a", b"two" * 30)
        self.assertNotEqual(first, load_nutrients(self.config())[1]["digest"])

    def test_unreadable_files_are_skipped_and_listed(self):
        self.write("good", b"some text " * 20)
        self.write("placeholder.gdoc", b"x")
        real_open = open

        def fake_open(path, *args, **kwargs):
            if str(path).endswith("placeholder.gdoc"):
                raise OSError(22, "Invalid argument")
            return real_open(path, *args, **kwargs)

        with mock.patch("builtins.open", fake_open):
            patches, manifest = load_nutrients(self.config())
        self.assertEqual([f["name"] for f in manifest["files"]], ["good"])
        self.assertEqual(manifest["unreadable"], ["placeholder.gdoc"])
        self.assertEqual(len(patches), 1)

    def test_missing_directory_is_rejected(self):
        with self.assertRaises(ValueError):
            load_nutrients(SimulationConfig(nutrient_dir=str(self.dir / "missing")))


class SimulationTests(NutrientDirTestCase):
    def test_nutrients_do_not_shift_other_mechanisms(self):
        self.write("data", os.urandom(400))
        plain = Simulation(seed=3, population=20)
        fed = Simulation(seed=3, population=20, config=self.config())
        self.assertEqual(fed.world.resources[: len(plain.world.resources)], plain.world.resources)
        self.assertEqual(len(fed.world.resources), len(plain.world.resources) + 1)
        self.assertEqual([(o.x, o.y, o.genome) for o in fed.organisms],
                         [(o.x, o.y, o.genome) for o in plain.organisms])

    def test_eaten_nutrients_disappear_and_runs_are_deterministic(self):
        for i in range(10):
            self.write(f"f{i}", os.urandom(300))
        a = Simulation(seed=5, population=60, config=self.config(resource_patches=5))
        b = Simulation(seed=5, population=60, config=self.config(resource_patches=5))
        a.run(1500)
        b.run(1500)
        self.assertEqual(a.state_digest(), b.state_digest())
        self.assertTrue(all(not r.exhausted for r in a.world.resources))

    def test_run_record_contains_manifest(self):
        self.write("a", b"hello world " * 20)
        out = io.StringIO()
        argv = ["eyggnx", "--steps", "5", "--format", "record", "--nutrient-dir", str(self.dir)]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
            cli.main()
        record = json.loads(out.getvalue())
        self.assertEqual(record["experiment"]["config"]["nutrient_dir"], str(self.dir))
        self.assertEqual([f["name"] for f in record["nutrients"]["files"]], ["a"])
        self.assertEqual(len(record["nutrients"]["digest"]), 64)


class ChunkTests(NutrientDirTestCase):
    def test_large_file_is_spread_over_chunks(self):
        data = os.urandom(10_000)
        self.write("big", data)
        patches, manifest = load_nutrients(self.config(nutrient_chunk_bytes=4000, nutrient_release_rate=0.0))
        self.assertEqual(len(patches), 3)
        self.assertEqual(manifest["files"][0]["chunks"], 3)
        cfg = SimulationConfig()
        expected = [nutrient_energy(data[i:i + 4000], cfg) for i in (0, 4000, 8000)]
        self.assertEqual([p.energy for p in patches], expected)
        self.assertAlmostEqual(manifest["files"][0]["energy"], sum(expected))
        self.assertEqual(len({(p.x, p.y) for p in patches}), 3)

    def test_chunking_off_keeps_one_patch_per_file(self):
        self.write("big", os.urandom(10_000))
        patches, manifest = load_nutrients(self.config())
        self.assertEqual(len(patches), 1)
        self.assertNotIn("chunks", manifest["files"][0])


    def test_split_energy_splits_only_large_files(self):
        self.write("big", os.urandom(30_000))   # about 300 energy as one patch
        self.write("small", os.urandom(5_000))  # about 50
        cfg = self.config(nutrient_split_energy=100.0, nutrient_release_rate=0.0)
        patches, manifest = load_nutrients(cfg)
        by_name = {f["name"]: f for f in manifest["files"]}
        self.assertNotIn("chunks", by_name["small"])
        self.assertGreaterEqual(by_name["big"]["chunks"], 3)
        self.assertEqual(len(patches), by_name["big"]["chunks"] + 1)
        self.assertTrue(all(p.energy <= 110.0 for p in patches))
        whole = load_nutrients(self.config(nutrient_release_rate=0.0))[1]["files"]
        self.assertAlmostEqual(sum(f["energy"] for f in manifest["files"]), sum(f["energy"] for f in whole), delta=10.0)

    def test_split_energy_rejects_negative(self):
        with self.assertRaises(ValueError):
            SimulationConfig(nutrient_split_energy=-1.0)


class ReleaseTests(NutrientDirTestCase):
    def test_release_exposes_a_capacity_and_keeps_the_rest_in_reserve(self):
        self.write("a", os.urandom(2_500).hex().encode())  # text: digestibility 1
        total = load_nutrients(self.config(nutrient_release_rate=0.0))[0][0].energy
        (p,), _ = load_nutrients(self.config(nutrient_release_rate=0.5, nutrient_release_capacity=10.0))
        self.assertEqual((p.energy, p.capacity, p.regen), (10.0, 10.0, 0.5))
        self.assertAlmostEqual(p.energy + p.reservoir, total)

    def test_reservoir_refills_until_empty_without_creating_energy(self):
        p = ResourcePatch(0.0, 0.0, 0.0, 2.0, 0.5, 1.2)
        seen = []
        for _ in range(5):
            p.tick()
            seen.append((p.energy, p.reservoir))
        self.assertEqual(seen[:3], [(0.5, 0.7), (1.0, 0.19999999999999996), (1.2, 0.0)])
        self.assertEqual(seen[-1], (1.2, 0.0))
        self.assertFalse(p.exhausted)
        p.energy = 0.0
        self.assertTrue(p.exhausted)

    def test_reservoir_respects_capacity(self):
        p = ResourcePatch(0.0, 0.0, 1.9, 2.0, 0.5, 5.0)
        p.tick()
        self.assertEqual((p.energy, p.reservoir), (2.0, 4.9))

    def test_released_nutrients_are_eaten_up_and_removed_deterministically(self):
        for i in range(6):
            self.write(f"f{i}", os.urandom(800))
        cfg = self.config(resource_patches=3, nutrient_release_rate=0.3, nutrient_release_capacity=3.0)
        a, b = (Simulation(seed=8, population=40, config=cfg) for _ in range(2))
        start = population_metrics(a)["finite_substrate_energy"]
        self.assertGreater(start, 0.0)
        a.run(800)
        b.run(800)
        self.assertEqual(a.state_digest(), b.state_digest())
        self.assertLess(population_metrics(a)["finite_substrate_energy"], start)
        self.assertTrue(all(not r.exhausted for r in a.world.resources))

    def test_slow_release_is_the_default_and_immediate_release_remains_available(self):
        self.write("a", os.urandom(2_500).hex().encode())  # text: digestibility 1
        (slow,), _ = load_nutrients(self.config())
        (fast,), _ = load_nutrients(self.config(nutrient_release_rate=0.0))
        self.assertEqual((slow.regen, slow.capacity), (0.4, 30.0))
        self.assertAlmostEqual(slow.energy + slow.reservoir, fast.energy)
        self.assertEqual((fast.regen, fast.reservoir), (0.0, None))

    def test_negative_release_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            SimulationConfig(nutrient_release_rate=-0.1)


class CategoryTests(NutrientDirTestCase):
    def test_category_comes_from_content_signatures(self):
        cases = {
            b"PK\x03\x04" + os.urandom(50): "archive",
            b"\x1f\x8b\x08" + os.urandom(50): "archive",
            b"\x89PNG\r\n\x1a\n" + os.urandom(50): "image",
            b"\xff\xd8\xff\xe0" + os.urandom(50): "image",
            b"RIFF\x00\x00\x00\x00WEBPVP8 ": "image",
            b"RIFF\x00\x00\x00\x00WAVEfmt ": "media",
            b"\x00\x00\x00\x18ftypmp42": "media",
            b"%PDF-1.7\n": "document",
            b"\x7fELF\x02\x01": "executable",
            "日本語のテキスト\n".encode(): "text",
            b"plain ascii": "text",
            b"\xff\xfe\x00\x01 not utf-8": "binary",
            b"abc\x00def": "binary",
        }
        for data, expected in cases.items():
            with self.subTest(data=data[:12]):
                self.assertEqual(nutrient_category(data), expected)

    def test_utf8_cut_by_the_byte_limit_is_still_text(self):
        self.assertEqual(nutrient_category("あいう".encode()[:-1]), "text")

    def test_extension_does_not_change_the_category(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("inner.txt", "hello " * 200)
        self.write("archive.txt", buf.getvalue())
        self.write("notes.zip", b"just some text " * 30)
        _, manifest = load_nutrients(self.config())
        cats = {f["name"]: f["category"] for f in manifest["files"]}
        self.assertEqual(cats, {"archive.txt": "archive", "notes.zip": "text"})

    def test_attributes_scale_energy_and_release(self):
        payload = os.urandom(2_000)
        self.write("a.bin", b"PK\x03\x04" + payload)
        (patch,), manifest = load_nutrients(self.config())
        info = manifest["files"][0]
        self.assertEqual((info["category"], info["energy_factor"], info["digestibility"]), ("archive", 1.25, 0.5))
        cfg = SimulationConfig()
        self.assertAlmostEqual(info["energy"], nutrient_energy(b"PK\x03\x04" + payload, cfg, 1.25))
        self.assertAlmostEqual(patch.regen, cfg.nutrient_release_rate * 0.5)

    def test_attributes_can_be_overridden(self):
        self.write("a.bin", b"PK\x03\x04" + os.urandom(500))
        cfg = self.config(nutrient_attributes={"archive": {"energy": 2.0}})
        (patch,), manifest = load_nutrients(cfg)
        self.assertEqual((manifest["files"][0]["energy_factor"], manifest["files"][0]["digestibility"]), (2.0, 0.5))
        for bad in ({"zip": {"energy": 1.0}}, {"archive": {"speed": 1.0}}, {"archive": {"energy": 0.0}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                SimulationConfig(nutrient_attributes=bad)

    def test_attributes_round_trip_through_experiment_json(self):
        from eyggnx.config import ExperimentSpec
        spec = ExperimentSpec.from_dict({"model": {"nutrient_attributes": {"text": {"digestibility": 0.25}}}})
        self.assertEqual(spec.config.nutrient_attributes_for("text"), {"energy": 1.0, "digestibility": 0.25})
        self.assertEqual(ExperimentSpec.from_dict(json.loads(json.dumps(spec.to_dict()))), spec)


class RegrowthTests(NutrientDirTestCase):
    def test_eaten_nutrients_come_back_at_the_interval(self):
        self.write("a", os.urandom(2_000).hex().encode())
        sim = Simulation(seed=1, population=0, config=self.config(resource_patches=0, nutrient_regrow_interval=5))
        (patch,) = sim.world.resources
        loaded = (patch.energy, patch.reservoir)
        patch.energy, patch.reservoir = 0.0, 0.0
        sim.tick()
        self.assertEqual(sim.world.resources, [])  # exhausted and removed
        for _ in range(4):
            sim.tick()
        self.assertEqual(sim.tick_index, 5)
        self.assertEqual(len(sim.world.resources), 1)
        self.assertIs(sim.world.resources[0], patch)
        self.assertEqual((patch.energy, patch.reservoir), loaded)

    def test_partly_eaten_nutrients_are_refilled_in_place(self):
        self.write("a", os.urandom(2_000).hex().encode())
        sim = Simulation(seed=1, population=0, config=self.config(resource_patches=0, nutrient_regrow_interval=3))
        (patch,) = sim.world.resources
        total = patch.energy + patch.reservoir
        patch.reservoir -= 5.0
        for _ in range(3):
            sim.tick()
        self.assertEqual(len(sim.world.resources), 1)
        self.assertAlmostEqual(patch.energy + patch.reservoir, total)

    def test_regrowth_is_deterministic_and_off_by_default(self):
        for i in range(5):
            self.write(f"f{i}", os.urandom(600))
        self.assertEqual(SimulationConfig().nutrient_regrow_interval, 0)
        cfg = self.config(resource_patches=0, nutrient_regrow_interval=50)
        a, b = (Simulation(seed=4, population=30, config=cfg) for _ in range(2))
        a.run(400)
        b.run(400)
        self.assertEqual(a.state_digest(), b.state_digest())
        with self.assertRaises(ValueError):
            SimulationConfig(nutrient_regrow_interval=-1)


class RespawnTests(NutrientDirTestCase):
    def eat_up(self, patch):
        patch.energy = 0.0
        if patch.reservoir is not None:
            patch.reservoir = 0.0

    def test_eaten_nutrient_returns_half_in_place_and_half_far_away(self):
        self.write("a", os.urandom(8_000).hex().encode())
        sim = Simulation(seed=1, population=0, config=self.config(resource_patches=0, nutrient_respawn_delay=5))
        (patch,) = sim.world.resources
        total = patch.energy + patch.reservoir
        self.eat_up(patch)
        sim.tick()  # removed; respawn scheduled for tick 1 + 5
        self.assertEqual(sim.world.resources, [])
        for _ in range(4):
            sim.tick()
        self.assertEqual(sim.world.resources, [])
        sim.tick()
        same, far = sim.world.resources
        self.assertEqual((same.x, same.y), (patch.x, patch.y))
        for p in (same, far):
            self.assertAlmostEqual(p.energy + p.reservoir, total / 2.0)
            self.assertEqual((p.capacity, p.regen), (patch.capacity, patch.regen))
        # Far: at least a quarter of the world away on each axis (half minus an eighth jitter).
        dx, dy = sim.world.delta(patch.x, patch.y, far.x, far.y)
        self.assertGreaterEqual(abs(dx), sim.world.width * 3 / 8 - 1e-9)
        self.assertGreaterEqual(abs(dy), sim.world.height * 3 / 8 - 1e-9)

    def test_respawned_nutrients_split_again_until_the_minimum(self):
        self.write("a", os.urandom(8_000).hex().encode())
        cfg = self.config(resource_patches=0, nutrient_respawn_delay=1, nutrient_respawn_min_energy=1e9)
        sim = Simulation(seed=1, population=0, config=cfg)
        (patch,) = sim.world.resources
        total = patch.energy + patch.reservoir
        self.eat_up(patch)
        sim.tick()
        sim.tick()
        (back,) = sim.world.resources  # half below the minimum: everything in place
        self.assertEqual((back.x, back.y), (patch.x, patch.y))
        self.assertAlmostEqual(back.energy + back.reservoir, total)

    def test_immediate_release_nutrients_respawn_without_reservoir(self):
        self.write("a", os.urandom(8_000).hex().encode())
        cfg = self.config(resource_patches=0, nutrient_respawn_delay=1, nutrient_release_rate=0.0)
        sim = Simulation(seed=1, population=0, config=cfg)
        (patch,) = sim.world.resources
        total = patch.energy
        self.eat_up(patch)
        sim.tick()
        sim.tick()
        self.assertEqual(len(sim.world.resources), 2)
        for p in sim.world.resources:
            self.assertIsNone(p.reservoir)
            self.assertEqual((p.energy, p.capacity, p.regen), (total / 2.0, total / 2.0, 0.0))

    def test_respawn_is_deterministic_off_by_default_and_exclusive_with_regrowth(self):
        for i in range(5):
            self.write(f"f{i}", os.urandom(600))
        self.assertEqual(SimulationConfig().nutrient_respawn_delay, 0)
        cfg = self.config(resource_patches=0, nutrient_respawn_delay=50)
        a, b = (Simulation(seed=4, population=30, config=cfg) for _ in range(2))
        a.run(400)
        b.run(400)
        self.assertEqual(a.state_digest(), b.state_digest())
        with self.assertRaises(ValueError):
            SimulationConfig(nutrient_respawn_delay=-1)
        with self.assertRaises(ValueError):
            SimulationConfig(nutrient_respawn_delay=10, nutrient_regrow_interval=10)

    def test_pending_respawns_enter_the_digest(self):
        self.write("a", os.urandom(8_000).hex().encode())
        cfg = self.config(resource_patches=0, nutrient_respawn_delay=10)
        a, b = (Simulation(seed=1, population=0, config=cfg) for _ in range(2))
        self.eat_up(a.world.resources[0])
        self.eat_up(b.world.resources[0])
        a.tick()
        b.tick()
        self.assertEqual(a.state_digest(), b.state_digest())
        b._respawn_pending[0][1].energy += 1.0
        self.assertNotEqual(a.state_digest(), b.state_digest())


if __name__ == "__main__":
    unittest.main()
