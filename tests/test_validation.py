# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import contextlib
import io
import math
import random
import unittest

from eyggnx.cli import build_parser
from eyggnx.simulation import Simulation
from eyggnx.world import World


class SimulationInputValidationTests(unittest.TestCase):
    def test_rejects_invalid_dimensions(self):
        for bad in (0, -1.0, math.nan, math.inf):
            with self.subTest(width=bad), self.assertRaises(ValueError):
                Simulation(width=bad)
            with self.subTest(height=bad), self.assertRaises(ValueError):
                Simulation(height=bad)

    def test_rejects_invalid_population(self):
        with self.assertRaises(ValueError):
            Simulation(population=-3)
        for bad in (2.5, True, "10"):
            with self.subTest(population=bad), self.assertRaises(TypeError):
                Simulation(population=bad)

    def test_rejects_invalid_steps_without_touching_state(self):
        sim = Simulation(seed=4, population=10)
        before = sim.state_digest()
        with self.assertRaises(ValueError):
            sim.run(-5)
        with self.assertRaises(TypeError):
            sim.run(1.5)
        self.assertEqual(sim.state_digest(), before)

    def test_zero_population_and_zero_steps_are_valid_controls(self):
        snap = Simulation(seed=1, population=0).run(0)
        self.assertEqual((snap.tick, snap.population), (0, 0))

    def test_world_rejects_negative_patch_count(self):
        with self.assertRaises(ValueError):
            World(10.0, 10.0, random.Random(0), patches=-1)


class CliValidationTests(unittest.TestCase):
    def test_negative_counts_are_rejected_with_exit_code_2(self):
        for argv in (["--steps", "-5"], ["--population", "-3"], ["--steps", "x"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    build_parser().parse_args(argv)
                self.assertEqual(ctx.exception.code, 2)

    def test_zero_is_accepted(self):
        args = build_parser().parse_args(["--steps", "0", "--population", "0"])
        self.assertEqual((args.steps, args.population), (0, 0))


if __name__ == "__main__":
    unittest.main()
