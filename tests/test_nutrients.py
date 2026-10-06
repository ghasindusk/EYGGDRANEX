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
from unittest import mock
import zlib

from eyggnx import cli
from eyggnx.config import SimulationConfig
from eyggnx.nutrients import load_nutrients, nutrient_energy
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
        self.assertEqual(nutrient_energy(os.urandom(100_000), cfg), cfg.nutrient_max_energy)
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
        patches, _ = load_nutrients(self.config(width=30.0, height=20.0))
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
        self.assertTrue(all(r.energy > 0.0 or r.regen > 0.0 for r in a.world.resources))

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
        patches, manifest = load_nutrients(self.config(nutrient_chunk_bytes=4000))
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


class ReleaseTests(NutrientDirTestCase):
    def test_release_exposes_a_capacity_and_keeps_the_rest_in_reserve(self):
        self.write("a", os.urandom(5_000))
        total = load_nutrients(self.config())[0][0].energy
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

    def test_negative_release_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            SimulationConfig(nutrient_release_rate=-0.1)


if __name__ == "__main__":
    unittest.main()
