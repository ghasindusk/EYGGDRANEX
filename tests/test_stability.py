# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Long-run stability: structural invariants must hold over thousands of ticks.

Survival is never required; an extinct run is a valid result.
"""

import unittest

from eyggnx.simulation import Simulation
from eyggnx.stability import parse_seeds, run_seed, structural_violations, summarize


class LongRunStabilityTests(unittest.TestCase):
    def test_long_runs_keep_structural_invariants(self):
        runs = [run_seed(seed, ticks=3000, check_every=50) for seed in (0, 1)]
        for run in runs:
            self.assertEqual(run["violations"], [], f"seed {run['seed']}")
            self.assertTrue(run["ticks_completed"] == 3000 or run["extinct_at"] is not None)
        summary = summarize(runs)
        self.assertEqual(summary["violations"], 0)
        self.assertEqual(summary["seeds"], 2)

    def test_long_run_is_deterministic(self):
        self.assertEqual(run_seed(4, ticks=500)["state_digest"], run_seed(4, ticks=500)["state_digest"])

    def test_violations_are_detected(self):
        sim = Simulation(seed=0, population=5)
        sim.organisms[0].energy = float("nan")
        sim.organisms[1].x = -1.0
        problems = structural_violations(sim, population=5)
        self.assertEqual(len(problems), 2)

    def test_parse_seeds(self):
        self.assertEqual(parse_seeds("0-3,7"), [0, 1, 2, 3, 7])
        self.assertEqual(parse_seeds("-2-0"), [-2, -1, 0])


if __name__ == "__main__":
    unittest.main()
