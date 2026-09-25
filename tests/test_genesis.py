# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import random
import unittest

from eyggnx.genome import Genome
from eyggnx.simulation import Simulation


class GenesisTests(unittest.TestCase):
    def test_mutation_respects_bounds(self):
        rng = random.Random(1)
        g = Genome(mutation_scale=0.25)
        for _ in range(1000):
            g = g.mutate(rng)
            self.assertGreaterEqual(g.speed, 0.15)
            self.assertLessEqual(g.speed, 4.0)
            self.assertGreaterEqual(g.sensor_range, 1.0)
            self.assertLessEqual(g.sensor_range, 30.0)
            self.assertGreaterEqual(g.max_age, 80)
            self.assertLessEqual(g.max_age, 2000)

    def test_same_seed_is_reproducible(self):
        a = Simulation(seed=123, population=30).run(80)
        b = Simulation(seed=123, population=30).run(80)
        self.assertEqual(a, b)

    def test_reference_seed_reaches_multiple_generations(self):
        snap = Simulation(seed=42, population=40).run(600)
        self.assertGreater(snap.population, 0)
        self.assertGreaterEqual(snap.max_generation, 2)

    def test_simulation_advances(self):
        sim = Simulation(seed=9, population=20)
        snap = sim.run(10)
        self.assertEqual(snap.tick, 10)
        self.assertGreaterEqual(snap.population, 0)


if __name__ == "__main__":
    unittest.main()
