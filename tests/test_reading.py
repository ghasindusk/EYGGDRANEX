# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Heritable reading table: how an organism turns eaten data into growth."""

import hashlib
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest

from eyggnx.config import SimulationConfig
from eyggnx.genome import GENES, Genome
from eyggnx.organism import Organism
from eyggnx.simulation import Simulation
from eyggnx.world import World

N = len(GENES)


def table(entries: dict[tuple[int, int], float]) -> tuple[float, ...]:
    return tuple(entries.get((i, j), 0.0) for i in range(N) for j in range(N))


def food_dir(directory: str) -> str:
    for i in range(20):
        text = "".join(hashlib.sha256(f"{i}-{k}".encode()).hexdigest() for k in range(100))
        Path(directory, f"food{i:02d}").write_bytes(text.encode())
    return directory


class ReadingTests(unittest.TestCase):
    def test_reading_routes_a_signal_to_another_gene(self):
        cfg = SimulationConfig(nutrient_mutation_strength=1.0, growth_gain=1.0)
        o = Organism(0, 0.0, 0.0, 100.0, Genome(), data_learning_rate=0.005,
                     reading=table({(0, 1): 1.0}))  # signal 1 grows gene 0 (speed)
        o.absorb_data(1.0, (0.0, 0.3) + (0.0,) * (N - 2), cfg)
        self.assertAlmostEqual(o.growth[0], 0.005)
        self.assertTrue(all(g == 0.0 for g in o.growth[1:]))

    def test_negative_weight_reverses_the_direction(self):
        cfg = SimulationConfig(nutrient_mutation_strength=1.0, growth_gain=1.0)
        o = Organism(0, 0.0, 0.0, 100.0, Genome(), data_learning_rate=0.005,
                     reading=table({(2, 0): -0.5}))
        o.absorb_data(1.0, (0.4,) + (0.0,) * (N - 1), cfg)
        self.assertAlmostEqual(o.growth[2], -0.005)

    def test_identity_reading_is_the_default(self):
        o = Organism(0, 0.0, 0.0, 100.0, Genome())
        self.assertIsNone(o.reading)
        sig = (0.2, -0.1) + (0.0,) * (N - 2)
        self.assertEqual(o.growth_direction(sig), (1.0, -0.5) + (0.0,) * (N - 2))

    def test_founders_draw_random_tables_and_children_inherit_with_variation(self):
        cfg = SimulationConfig(nutrient_mutation_strength=0.2, growth_reading_heritable=True)
        sim = Simulation(seed=2, population=10, config=cfg)
        tables = [o.reading for o in sim.organisms]
        self.assertTrue(all(t is not None and len(t) == N * N for t in tables))
        self.assertEqual(len(set(tables)), 10)
        self.assertTrue(all(-1.0 <= w <= 1.0 for t in tables for w in t))
        parent = sim.organisms[0]
        child = parent.reproduce(99, sim.world, random.Random(1), random.Random(2), sim.rngs["learning"])
        self.assertNotEqual(child.reading, parent.reading)
        self.assertTrue(all(-1.0 <= w <= 1.0 for w in child.reading))
        diffs = [abs(a - b) for a, b in zip(child.reading, parent.reading)]
        self.assertLess(max(diffs), 0.6)  # a small variation, not a new table

    def test_tables_are_only_written_at_birth(self):
        cfg = SimulationConfig(nutrient_mutation_strength=1.0, growth_reading_heritable=True)
        o = Organism(0, 0.0, 0.0, 100.0, Genome(), data_learning_rate=0.005,
                     reading=table({(0, 0): 1.0}))
        before = o.reading
        o.absorb_data(5.0, (0.3,) + (0.0,) * (N - 1), cfg)
        self.assertIs(o.reading, before)

    def test_fixed_genome_control_copies_the_table(self):
        cfg = SimulationConfig(nutrient_mutation_strength=1.0, mutate_offspring=False)
        parent = Organism(0, 0.0, 0.0, 100.0, Genome(), reading=table({(0, 0): 1.0}))
        world = World(100.0, 100.0, random.Random(1), patches=0, config=cfg)
        child = parent.reproduce(1, world, random.Random(2), random.Random(3), random.Random(4))
        self.assertIs(child.reading, parent.reading)

    def test_heritable_runs_are_reproducible_and_differ_from_identity(self):
        with TemporaryDirectory() as directory:
            base = SimulationConfig(nutrient_dir=food_dir(directory), nutrient_mutation_strength=0.2)
            heritable = SimulationConfig(nutrient_dir=directory, nutrient_mutation_strength=0.2,
                                         growth_reading_heritable=True)
            runs = []
            for cfg in (heritable, heritable, base):
                sim = Simulation(seed=3, population=30, config=cfg)
                sim.run(600)
                runs.append(sim.state_digest())
            self.assertEqual(runs[0], runs[1])
            self.assertNotEqual(runs[0], runs[2])

    def test_validation(self):
        with self.assertRaises(TypeError):
            SimulationConfig(growth_reading_heritable=1)
        for value in (-0.1, float("nan"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SimulationConfig(reading_mutation_scale=value)


if __name__ == "__main__":
    unittest.main()
