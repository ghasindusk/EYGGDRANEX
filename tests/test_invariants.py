# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Invariant and characterization tests for simulation contract 1.

These tests pin mechanisms and bookkeeping, never desired outcomes: extinction is a
valid result and no test requires a population to survive.
"""

import json
import math
from pathlib import Path
import platform
import random
import sys
import unittest
from unittest import mock

from eyggnx.genome import Genome
from eyggnx.organism import Organism
from eyggnx.simulation import Simulation
from eyggnx.world import ResourcePatch, World

GENE_BOUNDS = {
    "speed": (0.15, 4.0),
    "sensor_range": (1.0, 30.0),
    "metabolism": (0.05, 2.5),
    "movement_cost": (0.005, 0.8),
    "reproduction_threshold": (12.0, 120.0),
    "offspring_fraction": (0.20, 0.70),
    "mutation_scale": (0.005, 0.25),
    "max_age": (80, 2000),
}


def controlled_sim(organisms, patches):
    """A simulation with hand-placed organisms and resource patches (no founders)."""
    sim = Simulation(seed=0, population=0)
    sim.world.resources = patches
    sim.organisms = organisms
    sim.next_id = max((o.oid for o in organisms), default=-1) + 1
    return sim


class GenomeInvariantTests(unittest.TestCase):
    def test_all_genes_stay_within_bounds(self):
        rng = random.Random(72)
        g = Genome(mutation_scale=0.25)
        for _ in range(2000):
            g = g.mutate(rng)
            for name, (lo, hi) in GENE_BOUNDS.items():
                value = getattr(g, name)
                self.assertGreaterEqual(value, lo, name)
                self.assertLessEqual(value, hi, name)
            self.assertIsInstance(g.max_age, int)


class DeterminismTests(unittest.TestCase):
    def test_same_seed_gives_identical_full_state(self):
        a = Simulation(seed=123, population=40)
        b = Simulation(seed=123, population=40)
        a.run(300)
        b.run(300)
        self.assertEqual(a.state_digest(), b.state_digest())

    def test_chunked_run_equals_single_run(self):
        a = Simulation(seed=5, population=40)
        b = Simulation(seed=5, population=40)
        a.run(300)
        b.run(100)
        b.run(200)
        self.assertEqual(a.state_digest(), b.state_digest())

    def test_golden_digest_for_this_platform(self):
        data = json.loads(Path(__file__).with_name("golden_digests.json").read_text(encoding="utf-8"))
        key = f"{sys.platform}-{platform.machine().lower()}"
        for name, case in data["cases"].items():
            expected = case["digests"].get(key)
            if expected is None:
                self.skipTest(f"no golden digest recorded for {key}; run tests/record_golden.py")
            sim = Simulation(seed=case["seed"], population=case["population"])
            sim.run(case["ticks"])
            self.assertEqual(sim.state_digest(), expected, f"{name}: simulation contract 1 trajectory changed")


class WorldGeometryTests(unittest.TestCase):
    def setUp(self):
        self.world = World(100.0, 50.0, random.Random(0), patches=0)

    def test_wrap_both_directions(self):
        self.assertEqual(self.world.wrap(-1.0, 51.0), (99.0, 1.0))
        self.assertEqual(self.world.wrap(100.0, 0.0), (0.0, 0.0))

    def test_delta_takes_shortest_path_across_seam(self):
        dx, dy = self.world.delta(99.0, 49.0, 1.0, 1.0)
        self.assertAlmostEqual(dx, 2.0)
        self.assertAlmostEqual(dy, 2.0)
        self.assertAlmostEqual(self.world.distance(99.0, 49.0, 1.0, 1.0), math.hypot(2.0, 2.0))

    def test_depleted_patches_are_not_perceived(self):
        self.world.resources = [ResourcePatch(1.0, 1.0, 0.2, 10.0, 0.0), ResourcePatch(3.0, 1.0, 0.21, 10.0, 0.0)]
        self.assertIs(self.world.nearest_resource(1.0, 1.0, 5.0), self.world.resources[1])

    def test_nearest_resource_tie_prefers_first_patch(self):
        self.world.resources = [ResourcePatch(2.0, 1.0, 5.0, 10.0, 0.0), ResourcePatch(0.0, 1.0, 5.0, 10.0, 0.0)]
        self.assertIs(self.world.nearest_resource(1.0, 1.0, 5.0), self.world.resources[0])


class EnergyLedgerTests(unittest.TestCase):
    def test_reproduction_splits_energy_exactly(self):
        world = World(100.0, 100.0, random.Random(0), patches=0)
        parent = Organism(oid=7, x=10.0, y=10.0, energy=50.0, genome=Genome(), generation=3)
        before = parent.energy
        child = parent.reproduce(99, random.Random(1), world)
        self.assertEqual(parent.energy + child.energy, before)
        self.assertEqual(child.energy, before * Genome().offspring_fraction)
        self.assertEqual((child.oid, child.parent_id, child.generation, child.age), (99, 7, 4, 0))
        self.assertEqual(parent.genome, Genome())

    def test_patch_energy_lost_equals_energy_eaten(self):
        sim = Simulation(seed=11, population=60)
        eaten_total = [0.0]
        original_step = Organism.step

        def recording_step(self, world, rng):
            eaten = original_step(self, world, rng)
            eaten_total[0] += eaten
            return eaten

        original_world_tick = World.tick
        after_regen = [0.0]

        def recording_world_tick(self):
            original_world_tick(self)
            after_regen[0] = sum(r.energy for r in self.resources)

        with mock.patch.object(Organism, "step", recording_step), \
                mock.patch.object(World, "tick", recording_world_tick):
            for _ in range(200):
                eaten_total[0] = 0.0
                sim.tick()
                remaining = sum(r.energy for r in sim.world.resources)
                self.assertAlmostEqual(after_regen[0] - remaining, eaten_total[0], places=9)

    def test_population_accounting_and_state_sanity(self):
        for seed in range(3):
            sim = Simulation(seed=seed, population=50)
            for _ in range(300):
                sim.tick()
                self.assertEqual(len(sim.organisms), 50 + sim.births_total - sim.deaths_total)
                ids = [o.oid for o in sim.organisms]
                self.assertEqual(len(ids), len(set(ids)))
                for o in sim.organisms:
                    self.assertTrue(0.0 <= o.x < sim.world.width and 0.0 <= o.y < sim.world.height)
                    self.assertTrue(math.isfinite(o.energy))
                for r in sim.world.resources:
                    self.assertTrue(0.0 <= r.energy <= r.capacity)
                if not sim.organisms:
                    break


class LifecycleCharacterizationTests(unittest.TestCase):
    """Pin the documented tick semantics of contract 1 (see docs/specifications/ORGANISM_SPEC.md)."""

    def test_feeding_after_costs_can_rescue_an_organism(self):
        o = Organism(oid=0, x=5.0, y=5.0, energy=0.1, genome=Genome())
        sim = controlled_sim([o], [ResourcePatch(5.0, 5.0, 10.0, 10.0, 0.0)])
        sim.tick()
        self.assertEqual(sim.organisms, [o])
        self.assertAlmostEqual(o.energy, 0.1 - Genome().metabolism + 3.0)

    def test_organism_at_age_limit_eats_but_cannot_reproduce(self):
        g = Genome(max_age=100, reproduction_threshold=12.0)
        o = Organism(oid=0, x=5.0, y=5.0, energy=40.0, genome=g, age=99)
        patch = ResourcePatch(5.0, 5.0, 10.0, 10.0, 0.0)
        sim = controlled_sim([o], [patch])
        sim.tick()
        self.assertEqual(patch.energy, 7.0)
        self.assertEqual((sim.births_total, sim.deaths_total, sim.organisms), (0, 1, []))

    def test_newborns_do_not_act_on_their_birth_tick(self):
        o = Organism(oid=0, x=5.0, y=5.0, energy=100.0, genome=Genome())
        sim = controlled_sim([o], [])
        sim.tick()
        self.assertEqual(sim.births_total, 1)
        child = sim.organisms[-1]
        self.assertEqual((child.parent_id, child.age), (0, 0))

    def test_list_order_decides_feeding_priority(self):
        # Contract 1: organisms act in list order, so the earlier one takes the full bite.
        def run(order):
            a = Organism(oid=0, x=5.0, y=5.0, energy=10.0, genome=Genome())
            b = Organism(oid=1, x=5.0, y=5.0, energy=10.0, genome=Genome())
            patch = ResourcePatch(5.0, 5.0, 4.0, 10.0, 0.0)
            sim = controlled_sim([a, b] if order == "ab" else [b, a], [patch])
            sim.tick()
            return a.energy, b.energy

        a_first = run("ab")
        b_first = run("ba")
        self.assertGreater(a_first[0], a_first[1])
        self.assertGreater(b_first[1], b_first[0])
        self.assertAlmostEqual(a_first[0], b_first[1])


if __name__ == "__main__":
    unittest.main()
