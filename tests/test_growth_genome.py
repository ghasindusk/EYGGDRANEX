# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Base genome (fixed for life) and growth genome (grows with eaten data, bounded)."""

import math
import random
import unittest

from eyggnx.config import SimulationConfig
from eyggnx.genome import Genome
from eyggnx.organism import Organism
from eyggnx.simulation import Simulation
from eyggnx.world import World

SIGNATURE = (1.0,) + (0.0,) * 7


def grown_parent(cfg: SimulationConfig, rate: float = 0.005) -> Organism:
    parent = Organism(0, 0.0, 0.0, 100.0, Genome(), data_learning_rate=rate)
    parent.absorb_data(28.0, SIGNATURE, cfg)
    return parent


class GrowthGenomeTests(unittest.TestCase):
    def test_base_genome_is_fixed_and_growth_is_expressed(self):
        cfg = SimulationConfig(nutrient_mutation_strength=1.0)
        parent = grown_parent(cfg)
        self.assertEqual(parent.base, Genome())
        self.assertEqual(parent.growth[0], 0.005)
        self.assertEqual(parent.genome, Genome().shift(parent.growth))
        self.assertAlmostEqual(parent.genome.speed, math.exp(0.005))

    def test_growth_is_bounded_per_gene(self):
        cfg = SimulationConfig(nutrient_mutation_strength=1.0, growth_max_log=0.001)
        parent = grown_parent(cfg)
        self.assertEqual(parent.growth[0], 0.001)
        self.assertAlmostEqual(parent.genome.speed, math.exp(0.001))
        self.assertEqual(parent.base, Genome())

    def test_without_growth_the_organism_keeps_a_single_genome(self):
        parent = Organism(0, 0.0, 0.0, 100.0, Genome())
        self.assertIsNone(parent.base_genome)
        self.assertIsNone(parent.growth)
        self.assertIs(parent.base, parent.genome)

    def test_inheritance_probability_selects_the_source_genome(self):
        for p, expected_source in ((1.0, "expressed"), (0.0, "base")):
            with self.subTest(p=p):
                cfg = SimulationConfig(nutrient_mutation_strength=1.0, nutrient_offspring_guidance=False,
                                       growth_inheritance_probability=p)
                parent = grown_parent(cfg)
                world = World(100.0, 100.0, random.Random(1), patches=0, config=cfg)
                child = parent.reproduce(1, world, random.Random(2), random.Random(3))
                source = parent.genome if expected_source == "expressed" else parent.base
                self.assertEqual(child.genome, source.mutate(random.Random(3)))
                self.assertEqual(child.growth_inherited, p == 1.0)
                self.assertIsNone(child.growth)  # a child starts with no growth of its own
                self.assertEqual(parent.base, Genome())  # reproduction does not touch the parent

    def test_partial_probability_draws_from_the_learning_stream(self):
        cfg = SimulationConfig(nutrient_mutation_strength=1.0, growth_inheritance_probability=0.5)
        outcomes = set()
        for seed in range(20):
            parent = grown_parent(cfg)
            world = World(100.0, 100.0, random.Random(1), patches=0, config=cfg)
            child = parent.reproduce(1, world, random.Random(2), random.Random(3), random.Random(seed))
            outcomes.add(child.growth_inherited)
        self.assertEqual(outcomes, {True, False})

    def test_fixed_genome_control_never_grows_or_inherits_growth(self):
        cfg = SimulationConfig(nutrient_mutation_strength=1.0, mutate_offspring=False,
                               growth_inheritance_probability=1.0)
        parent = grown_parent(cfg)
        self.assertIsNone(parent.growth)
        world = World(100.0, 100.0, random.Random(1), patches=0, config=cfg)
        child = parent.reproduce(1, world, random.Random(2), random.Random(3))
        self.assertIs(child.genome, parent.genome)
        self.assertFalse(child.growth_inherited)

    def test_validation(self):
        for value in (-0.1, float("nan"), True):
            with self.subTest(growth_max_log=value), self.assertRaises(ValueError):
                SimulationConfig(growth_max_log=value)
        for value in (-0.1, 1.1, float("nan"), True):
            with self.subTest(growth_inheritance_probability=value), self.assertRaises(ValueError):
                SimulationConfig(growth_inheritance_probability=value)

    def test_simulation_counts_growth_inherited_births_reproducibly(self):
        import os
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            Path(directory, "food").write_bytes(os.urandom(4000).hex().encode())
            cfg = SimulationConfig(nutrient_dir=directory, nutrient_mutation_strength=0.5,
                                   nutrient_parent_learning_fraction=0.02)
            a = Simulation(seed=5, population=30, config=cfg)
            b = Simulation(seed=5, population=30, config=cfg)
            a.run(1500)
            b.run(1500)
            self.assertEqual(a.state_digest(), b.state_digest())
            self.assertGreater(a.growth_inherited_births, 0)
            self.assertLess(a.growth_inherited_births, a.births_total)
            for o in a.organisms:
                if o.growth is not None:
                    self.assertTrue(all(abs(g) <= cfg.growth_max_log for g in o.growth))
                    self.assertEqual(o.genome, o.base.shift(o.growth))


if __name__ == "__main__":
    unittest.main()
