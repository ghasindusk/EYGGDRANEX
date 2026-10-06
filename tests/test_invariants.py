# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Invariant and characterization tests for simulation contract 2.

These tests pin mechanisms and bookkeeping, never desired outcomes: extinction is a
valid result and no test requires a population to survive. The invariants are listed
in docs/architecture/INVARIANTS.md.
"""

from dataclasses import fields, replace
import json
import math
from pathlib import Path
import platform
import random
from statistics import median
import sys
import unittest
from unittest import mock

from eyggnx.config import SimulationConfig
from eyggnx.controller import ForagingController
from eyggnx.genome import GENE_BOUNDS, GENES, Genome, reflect
from eyggnx.organism import Organism, basal_metabolism
from eyggnx.simulation import RNG_STREAMS, Simulation, derive_stream
from eyggnx.world import ResourcePatch, World


def controlled_sim(organisms, patches, config=None):
    """A simulation with hand-placed organisms and resource patches (no founders)."""
    sim = Simulation(seed=0, population=0, config=config)
    sim.world.resources = patches
    sim.organisms = organisms
    sim.next_id = max((o.oid for o in organisms), default=-1) + 1
    return sim


class GenomeInvariantTests(unittest.TestCase):
    def test_registry_matches_genome(self):
        self.assertEqual([f.name for f in fields(Genome)], [g.name for g in GENES])
        for g in GENES:
            self.assertEqual(getattr(Genome(), g.name), g.default)
            self.assertTrue(0.0 < g.lo <= g.default <= g.hi, g.name)

    def test_all_genes_stay_within_bounds(self):
        rng = random.Random(72)
        g = Genome(mutation_scale=0.25)
        for _ in range(2000):
            g = g.mutate(rng)
            for name, (lo, hi) in GENE_BOUNDS.items():
                value = getattr(g, name)
                self.assertGreaterEqual(value, lo, name)
                self.assertLessEqual(value, hi, name)

    def test_reflect_folds_into_range(self):
        self.assertEqual(reflect(0.5, 0.0, 1.0), 0.5)
        self.assertAlmostEqual(reflect(1.25, 0.0, 1.0), 0.75)
        self.assertAlmostEqual(reflect(-0.25, 0.0, 1.0), 0.25)
        self.assertAlmostEqual(reflect(2.25, 0.0, 1.0), 0.25)

    def test_mutation_is_unbiased_in_log_space(self):
        # One mutation from the default genome: the median log change is ~0 for every gene.
        rng = random.Random(3)
        base = Genome()
        children = [base.mutate(rng) for _ in range(4000)]
        for name in GENE_BOUNDS:
            change = median(math.log(getattr(c, name) / getattr(base, name)) for c in children)
            self.assertLess(abs(change), 0.01, name)

    def test_max_age_is_continuous(self):
        rng = random.Random(0)
        g = Genome(max_age=80.0, mutation_scale=0.005)
        self.assertNotEqual(g.mutate(rng).max_age, 80.0)
        self.assertIsInstance(g.mutate(rng).max_age, float)


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
        self.assertEqual(data["simulation_contract"], 2)
        key = f"{sys.platform}-{platform.machine().lower()}"
        for name, case in data["cases"].items():
            sim = Simulation(seed=case["seed"], population=case["population"])
            sim.run(case["ticks"])
            expected = case["digests"].get(key)
            if expected is None:
                self.skipTest(f"no golden digest recorded for {key} ({name}: {sim.state_digest()}); "
                              "record it with tests/record_golden.py --write")
            self.assertEqual(sim.state_digest(), expected, f"{name}: simulation contract 2 trajectory changed")


class StreamIsolationTests(unittest.TestCase):
    def test_streams_are_distinct_and_reproducible(self):
        first = {name: derive_stream(9, name).random() for name in RNG_STREAMS}
        self.assertEqual(len(set(first.values())), len(RNG_STREAMS))
        self.assertEqual(first, {name: derive_stream(9, name).random() for name in RNG_STREAMS})

    def test_world_layout_does_not_shift_founders(self):
        a = Simulation(seed=4, population=20, config=SimulationConfig(resource_patches=55))
        b = Simulation(seed=4, population=20, config=SimulationConfig(resource_patches=10))
        self.assertEqual([(o.x, o.y, o.energy, o.genome) for o in a.organisms],
                         [(o.x, o.y, o.energy, o.genome) for o in b.organisms])

    def test_founder_count_does_not_shift_world(self):
        a = Simulation(seed=4, population=5)
        b = Simulation(seed=4, population=80)
        self.assertEqual(a.world.resources, b.world.resources)

    def test_mutation_switch_does_not_shift_birth_placement(self):
        # The first birth happens before any genome difference can change behaviour.
        def first_birth(mutate):
            o = Organism(oid=0, x=5.0, y=5.0, energy=100.0, genome=Genome())
            sim = controlled_sim([o], [], SimulationConfig(mutate_offspring=mutate))
            sim.tick()
            child = sim.organisms[-1]
            return child.x, child.y

        self.assertEqual(first_birth(True), first_birth(False))


class OrderNeutralityTests(unittest.TestCase):
    def test_list_order_does_not_change_the_trajectory(self):
        a = Simulation(seed=31, population=40)
        b = Simulation(seed=31, population=40)
        for _ in range(200):
            b.organisms.reverse()
            a.tick()
            b.tick()
        self.assertEqual(a.state_digest(), b.state_digest())

    def test_contested_patch_is_shared_equally(self):
        def run(order):
            a = Organism(oid=0, x=5.0, y=5.0, energy=10.0, genome=Genome())
            b = Organism(oid=1, x=5.0, y=5.0, energy=10.0, genome=Genome())
            patch = ResourcePatch(5.0, 5.0, 4.0, 10.0, 0.0)
            sim = controlled_sim([a, b] if order == "ab" else [b, a], [patch])
            sim.tick()
            return a.energy, b.energy, patch.energy

        self.assertEqual(run("ab"), run("ba"))
        a_energy, b_energy, left = run("ab")
        self.assertEqual(a_energy, b_energy)
        self.assertEqual(left, 0.0)
        self.assertAlmostEqual(a_energy, 10.0 - basal_metabolism(Genome(), SimulationConfig()) + 2.0)

    def test_uncontested_bites_are_full(self):
        a = Organism(oid=0, x=5.0, y=5.0, energy=10.0, genome=Genome())
        b = Organism(oid=1, x=5.0, y=5.0, energy=10.0, genome=Genome())
        patch = ResourcePatch(5.0, 5.0, 20.0, 20.0, 0.0)
        controlled_sim([a, b], [patch]).tick()
        self.assertEqual(patch.energy, 14.0)
        self.assertEqual(a.energy, b.energy)


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

    def test_initial_resource_energy_never_exceeds_capacity(self):
        for seed in range(200):
            for r in Simulation(seed=seed, population=0).world.resources:
                self.assertLessEqual(r.energy, r.capacity)

    def test_nearest_resource_tie_prefers_first_patch(self):
        self.world.resources = [ResourcePatch(2.0, 1.0, 5.0, 10.0, 0.0), ResourcePatch(0.0, 1.0, 5.0, 10.0, 0.0)]
        self.assertIs(self.world.nearest_resource(1.0, 1.0, 5.0), self.world.resources[0])

    def test_spatial_grid_matches_full_scan(self):
        rng = random.Random(8)
        world = World(100.0, 70.0, rng, patches=120)
        for _ in range(500):
            x, y, radius = rng.random() * 100.0, rng.random() * 70.0, rng.uniform(0.5, 45.0)
            brute = sorted(
                (world.distance(x, y, r.x, r.y), i) for i, r in enumerate(world.resources)
                if r.energy > world.config.perception_threshold and world.distance(x, y, r.x, r.y) <= radius
            )
            got = sorted((d, i) for d, i, _ in world.perceive(x, y, radius))
            self.assertEqual(got, brute)


class EnergyLedgerTests(unittest.TestCase):
    def test_reproduction_splits_energy_exactly(self):
        world = World(100.0, 100.0, random.Random(0), patches=0)
        parent = Organism(oid=7, x=10.0, y=10.0, energy=50.0, genome=Genome(), generation=3)
        before = parent.energy
        child = parent.reproduce(99, world, random.Random(1), random.Random(2))
        self.assertEqual(parent.energy + child.energy, before)
        self.assertEqual(child.energy, before * Genome().offspring_fraction)
        self.assertEqual((child.oid, child.parent_id, child.generation, child.age), (99, 7, 4, 0))
        self.assertEqual(parent.genome, Genome())

    def test_patch_energy_lost_equals_energy_eaten(self):
        sim = Simulation(seed=11, population=60)
        original_world_tick = World.tick
        after_regen = [0.0]

        def recording_world_tick(self):
            original_world_tick(self)
            after_regen[0] = math.fsum(r.energy for r in self.resources)

        with mock.patch.object(World, "tick", recording_world_tick):
            for _ in range(200):
                sim.tick()
                remaining = math.fsum(r.energy for r in sim.world.resources)
                self.assertAlmostEqual(after_regen[0] - remaining, sim.eaten_last_tick, places=9)

    def test_organism_energy_ledger(self):
        # Energy after a tick = before - basal metabolism - movement cost + eaten.
        g = Genome(speed=2.0, wander_step=0.5)
        o = Organism(oid=0, x=50.0, y=50.0, energy=10.0, genome=g)
        sim = controlled_sim([o], [])
        sim.tick()
        cfg = SimulationConfig()
        moved = g.speed * g.wander_step
        self.assertAlmostEqual(o.energy, 10.0 - basal_metabolism(g, cfg) - moved * cfg.movement_cost * g.speed)

    def test_population_accounting_and_state_sanity(self):
        for seed in range(3):
            sim = Simulation(seed=seed, population=50, config=SimulationConfig(detritus_fraction=0.5))
            for _ in range(300):
                sim.tick()
                self.assertEqual(len(sim.organisms), 50 + sim.births_total - sim.deaths_total)
                ids = [o.oid for o in sim.organisms]
                self.assertEqual(ids, sorted(set(ids)))
                for o in sim.organisms:
                    self.assertTrue(0.0 <= o.x < sim.world.width and 0.0 <= o.y < sim.world.height)
                    self.assertTrue(math.isfinite(o.energy))
                for r in sim.world.resources:
                    self.assertTrue(0.0 <= r.energy <= r.capacity)
                if not sim.organisms:
                    break


class TradeOffTests(unittest.TestCase):
    """Invariant 5: every gene that helps survival costs energy."""

    def test_sensor_range_and_longevity_raise_basal_metabolism(self):
        cfg = SimulationConfig()
        base = basal_metabolism(Genome(), cfg)
        self.assertGreater(basal_metabolism(Genome(sensor_range=20.0), cfg), base)
        self.assertGreater(basal_metabolism(Genome(max_age=1000.0), cfg), base)
        self.assertAlmostEqual(base, 0.10 + 0.006 * 8.0 + 0.00017 * 420.0)

    def test_movement_cost_scales_with_speed(self):
        def cost(speed):
            g = Genome(speed=speed, wander_step=1.0)
            o = Organism(oid=0, x=50.0, y=50.0, energy=10.0, genome=g)
            controlled_sim([o], []).tick()
            return 10.0 - o.energy - basal_metabolism(g, SimulationConfig())

        self.assertAlmostEqual(cost(2.0) / cost(1.0), 4.0)  # twice the distance at twice the drag


class ControllerTests(unittest.TestCase):
    def decide(self, genome, patches):
        world = World(100.0, 100.0, random.Random(0), patches=0)
        world.resources = patches
        o = Organism(oid=0, x=50.0, y=50.0, energy=10.0, genome=genome)
        return ForagingController().decide(o, world, random.Random(0))

    def test_aversion_trades_distance_against_patch_energy(self):
        near_poor = ResourcePatch(52.0, 50.0, 15.0, 40.0, 0.0)
        far_rich = ResourcePatch(44.0, 50.0, 40.0, 40.0, 0.0)
        self.assertGreater(self.decide(Genome(distance_aversion=50.0), [near_poor, far_rich]).dx, 0.0)
        self.assertLess(self.decide(Genome(distance_aversion=0.05), [near_poor, far_rich]).dx, 0.0)

    def test_wander_step_is_heritable_step_length(self):
        intent = self.decide(Genome(speed=2.0, wander_step=0.3), [])
        self.assertAlmostEqual(math.hypot(intent.dx, intent.dy), 0.6)

    def test_decisions_use_the_world_before_anyone_eats(self):
        # Both see the same patch; neither sees it emptied by the other first.
        patch = ResourcePatch(51.0, 50.0, 2.0, 10.0, 0.0)
        a = Organism(oid=0, x=50.0, y=50.0, energy=10.0, genome=Genome())
        b = Organism(oid=1, x=52.0, y=50.0, energy=10.0, genome=Genome())
        sim = controlled_sim([a, b], [patch])
        sim.tick()
        self.assertEqual((a.x, b.x), (51.0, 51.0))
        self.assertEqual(a.energy, b.energy)


class DetritusTests(unittest.TestCase):
    def test_age_death_leaves_decaying_detritus(self):
        cfg = SimulationConfig(detritus_fraction=0.5, detritus_decay=1.0)
        g = Genome(max_age=100.0, sensor_range=1.0)
        o = Organism(oid=0, x=5.0, y=5.0, energy=10.0, genome=g, age=99)
        sim = controlled_sim([o], [], cfg)
        sim.tick()
        self.assertEqual(sim.organisms, [])
        (patch,) = sim.world.resources
        self.assertAlmostEqual(patch.energy, 0.5 * (10.0 - basal_metabolism(g, cfg) - g.speed * g.wander_step
                                                    * cfg.movement_cost * g.speed))
        for _ in range(10):
            sim.tick()
        self.assertEqual(sim.world.resources, [])

    def test_no_detritus_by_default_or_from_starvation(self):
        o = Organism(oid=0, x=5.0, y=5.0, energy=10.0, genome=Genome(max_age=100.0), age=99)
        sim = controlled_sim([o], [])
        sim.tick()
        self.assertEqual(sim.world.resources, [])
        starving = Organism(oid=0, x=5.0, y=5.0, energy=0.01, genome=Genome())
        sim = controlled_sim([starving], [], SimulationConfig(detritus_fraction=1.0))
        sim.tick()
        self.assertEqual(sim.world.resources, [])


class LifecycleCharacterizationTests(unittest.TestCase):
    """Pin the documented tick semantics of contract 2 (see docs/specifications/ORGANISM_SPEC.md)."""

    def test_feeding_after_costs_can_rescue_an_organism(self):
        o = Organism(oid=0, x=5.0, y=5.0, energy=0.1, genome=Genome())
        sim = controlled_sim([o], [ResourcePatch(5.0, 5.0, 10.0, 10.0, 0.0)])
        sim.tick()
        self.assertEqual(sim.organisms, [o])
        self.assertAlmostEqual(o.energy, 0.1 - basal_metabolism(Genome(), SimulationConfig()) + 3.0)

    def test_organism_at_age_limit_eats_but_cannot_reproduce(self):
        g = Genome(max_age=100.0, reproduction_threshold=12.0)
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

    def test_fractional_lifespan_is_respected(self):
        o = Organism(oid=0, x=5.0, y=5.0, energy=50.0, genome=replace(Genome(), max_age=100.5), age=99)
        sim = controlled_sim([o], [ResourcePatch(5.0, 5.0, 10.0, 10.0, 0.0)])
        sim.tick()  # age 100 < 100.5: still alive
        self.assertEqual(len(sim.organisms) - sim.births_total, 1)
        sim.tick()  # age 101 >= 100.5
        self.assertNotIn(o, sim.organisms)


if __name__ == "__main__":
    unittest.main()
