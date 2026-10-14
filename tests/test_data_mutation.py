# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Lifetime data memory biases offspring and gently updates the parent."""

from dataclasses import replace
import math
import os
import random
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from eyggnx.config import ExperimentSpec, SimulationConfig
from eyggnx.controller import Intent
from eyggnx.genome import Genome
from eyggnx.nutrients import information_signature, load_nutrients
from eyggnx.recorder import population_metrics
from eyggnx.run_record import build_run_record
from eyggnx.simulation import Simulation


class StayController:
    def decide(self, organism, world, rng):
        return Intent(0.0, 0.0)


class DataMutationTests(unittest.TestCase):
    def test_byte_content_changes_the_mutation_bias(self):
        left = information_signature(b" " * 300)
        right = information_signature(b"0" * 300)
        self.assertNotEqual(left, right)
        self.assertEqual(len(left), 8)
        parent = Genome()
        a = parent.mutate(random.Random(12), tuple(v * 0.2 for v in left))
        b = parent.mutate(random.Random(12), tuple(v * 0.2 for v in right))
        self.assertNotEqual(a, b)
        self.assertEqual(parent, Genome())

    def test_only_eaten_data_affects_the_child(self):
        with TemporaryDirectory() as directory:
            Path(directory, "food").write_bytes(os.urandom(200).hex().encode())
            plain = Simulation(seed=8, population=1, config=SimulationConfig(
                nutrient_dir=directory, resource_patches=0, nutrient_release_rate=0.0))
            guided = Simulation(seed=8, population=1, config=SimulationConfig(
                nutrient_dir=directory, resource_patches=0, nutrient_release_rate=0.0,
                nutrient_mutation_strength=1.0))
            for sim in (plain, guided):
                sim.controller = StayController()
                organism = sim.organisms[0]
                organism.energy = 29.0
                organism.genome = Genome()
                patch = sim.world.resources[0]
                patch.x, patch.y = organism.x, organism.y
                sim.world.resources = sim.world.resources  # rebuild spatial index
            guided_parent_genome = guided.organisms[0].genome
            guided.tick()
            plain.tick()
            self.assertNotEqual(guided.organisms[0].genome, guided_parent_genome)
            self.assertEqual(guided.births_total, 1)
            self.assertEqual(guided.data_influenced_births, 1)
            self.assertGreater(guided.data_eaten_total, 0.0)
            self.assertNotEqual(guided.organisms[1].genome, plain.organisms[1].genome)
            self.assertGreater(guided.organisms[0].diet_energy, 0.0)
            self.assertEqual(guided.organisms[1].diet_signal, guided.organisms[0].diet_signal)
            self.assertEqual(guided.organisms[1].diet_energy, guided.organisms[0].diet_energy)
            record = build_run_record(ExperimentSpec(config=guided.config), guided, guided.snapshot())
            self.assertEqual(record["result"]["data_influenced_births"], 1)
            self.assertIn("data_eaten_total", population_metrics(guided))

    def test_diet_is_energy_weighted_and_inherited_after_reproduction(self):
        from eyggnx.organism import Organism
        from eyggnx.world import World
        parent = Organism(0, 5.0, 5.0, 60.0, Genome())
        parent.absorb_data(1.0, (1.0,) + (0.0,) * 7)
        parent.absorb_data(3.0, (-1.0,) + (0.0,) * 7)
        self.assertEqual(parent.diet_signal[0] / parent.diet_energy, -0.5)
        world = World(100.0, 100.0, random.Random(1), patches=0,
                      config=SimulationConfig(nutrient_mutation_strength=0.4))
        child = parent.reproduce(1, world, random.Random(2), random.Random(3))
        self.assertEqual((parent.diet_signal, parent.diet_energy),
                         (child.diet_signal, child.diet_energy))

    def test_parent_applies_only_incremental_half_percent_learning(self):
        from eyggnx.organism import Organism
        cfg = SimulationConfig(nutrient_mutation_strength=1.0)
        parent = Organism(0, 0.0, 0.0, 100.0, Genome())
        signature = (1.0,) + (0.0,) * 7
        parent.absorb_data(28.0, signature, cfg)
        self.assertAlmostEqual(parent.genome.speed, math.exp(0.005))
        first = parent.genome
        parent.absorb_data(28.0, signature, cfg)
        self.assertEqual(parent.genome, first)
        self.assertEqual(parent.diet_energy, 56.0)

    def test_guidance_toggle_keeps_parent_learning_and_inheritance(self):
        from eyggnx.organism import Organism
        from eyggnx.world import World
        signature = (1.0,) + (0.0,) * 7
        children = []
        for guidance in (False, True):
            cfg = SimulationConfig(nutrient_mutation_strength=1.0,
                                   nutrient_offspring_guidance=guidance)
            parent = Organism(0, 0.0, 0.0, 100.0, Genome())
            parent.absorb_data(28.0, signature, cfg)
            self.assertAlmostEqual(parent.genome.speed, math.exp(0.005))
            world = World(100.0, 100.0, random.Random(1), patches=0, config=cfg)
            child = parent.reproduce(1, world, random.Random(2), random.Random(3))
            self.assertEqual(child.diet_signal, parent.diet_signal)
            self.assertEqual(child.diet_energy, parent.diet_energy)
            children.append(child)
        self.assertNotEqual(children[0].genome, children[1].genome)

    def test_inherited_memory_is_not_reapplied_to_child(self):
        from eyggnx.organism import Organism
        from eyggnx.world import World
        cfg = SimulationConfig(nutrient_mutation_strength=1.0)
        parent = Organism(0, 0.0, 0.0, 100.0, Genome())
        signature = (1.0,) + (0.0,) * 7
        parent.absorb_data(28.0, signature, cfg)
        world = World(100.0, 100.0, random.Random(1), patches=0, config=cfg)
        child = parent.reproduce(1, world, random.Random(2), random.Random(3))
        child.genome = Genome()  # same threshold: isolate the newly consumed data
        before = child.genome
        child.absorb_data(1.0, signature, cfg)
        self.assertAlmostEqual(child.genome.speed, before.speed)
        self.assertEqual(child.diet_energy, 29.0)

    def test_disabled_feature_does_not_load_signatures_or_change_digests(self):
        with TemporaryDirectory() as directory:
            Path(directory, "food").write_bytes(b"data" * 100)
            cfg = SimulationConfig(nutrient_dir=directory)
            patches, _ = load_nutrients(cfg)
            self.assertTrue(all(p.information_signature is None for p in patches))
            a = Simulation(seed=21, population=10, config=cfg)
            b = Simulation(seed=21, population=10, config=replace(cfg, nutrient_mutation_strength=0.0))
            a.run(200)
            b.run(200)
            self.assertEqual(a.state_digest(), b.state_digest())

    def test_enabled_runs_are_reproducible(self):
        with TemporaryDirectory() as directory:
            Path(directory, "food").write_bytes(b"abCD09" * 300)
            cfg = SimulationConfig(nutrient_dir=directory,
                                   nutrient_mutation_strength=0.2)
            a = Simulation(seed=31, population=15, config=cfg)
            b = Simulation(seed=31, population=15, config=cfg)
            a.run(300)
            b.run(300)
            self.assertEqual(a.state_digest(), b.state_digest())

    def test_contested_food_gives_equal_data_signal(self):
        from eyggnx.organism import Organism
        from eyggnx.world import ResourcePatch
        sim = Simulation(seed=4, population=0, config=SimulationConfig(
            resource_patches=0, nutrient_mutation_strength=0.2))
        signature = (1.0,) + (0.0,) * 7
        patch = ResourcePatch(5.0, 5.0, 1.0, 1.0, 0.0,
                              information_signature=signature)
        sim.world.resources = [patch]
        a = Organism(0, 5.0, 5.0, 10.0, Genome())
        b = Organism(1, 5.0, 5.0, 10.0, Genome())
        sim._resolve_feeding([b, a])
        self.assertEqual((a.diet_energy, b.diet_energy), (0.5, 0.5))
        self.assertEqual(a.diet_signal, b.diet_signal)

    def test_strength_validation(self):
        for strength in (-0.1, 1.1, float("nan"), True):
            with self.subTest(strength=strength), self.assertRaises(ValueError):
                SimulationConfig(nutrient_mutation_strength=strength)
        for fraction in (-0.1, 1.1, float("nan"), True):
            with self.subTest(fraction=fraction), self.assertRaises(ValueError):
                SimulationConfig(nutrient_parent_learning_fraction=fraction)
        with self.assertRaises(TypeError):
            SimulationConfig(nutrient_offspring_guidance=1)

    def test_fixed_genome_control_stays_fixed_after_data_intake(self):
        with TemporaryDirectory() as directory:
            Path(directory, "food").write_bytes(os.urandom(200).hex().encode())
            cfg = SimulationConfig(nutrient_dir=directory, resource_patches=0,
                                   nutrient_release_rate=0.0,
                                   nutrient_mutation_strength=1.0,
                                   mutate_offspring=False)
            sim = Simulation(seed=8, population=1, config=cfg)
            sim.controller = StayController()
            parent = sim.organisms[0]
            parent.energy = 29.0
            patch = sim.world.resources[0]
            patch.x, patch.y = parent.x, parent.y
            sim.world.resources = sim.world.resources
            sim.tick()
            self.assertEqual(sim.births_total, 1)
            self.assertGreater(sim.data_eaten_total, 0.0)
            self.assertEqual(sim.data_influenced_births, 0)
            self.assertIs(sim.organisms[1].genome, parent.genome)


if __name__ == "__main__":
    unittest.main()
