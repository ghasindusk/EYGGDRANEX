# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

from eyggnx import cli
from eyggnx.config import SIMULATION_CONTRACT, ExperimentSpec, SimulationConfig, load_experiment
from eyggnx.simulation import Simulation

REPO = Path(__file__).resolve().parents[1]


def run_cli(*argv):
    out = io.StringIO()
    with mock.patch.object(sys, "argv", ["eyggnx", *argv]), contextlib.redirect_stdout(out):
        cli.main()
    return json.loads(out.getvalue())


class ConfigTests(unittest.TestCase):
    def test_default_config_reproduces_contract_trajectory(self):
        a = Simulation(seed=8, population=40)
        b = Simulation(seed=8, population=40, config=SimulationConfig())
        a.run(300)
        b.run(300)
        self.assertEqual(a.state_digest(), b.state_digest())

    def test_round_trip_through_dict(self):
        cfg = SimulationConfig(width=60.0, resource_patches=20, bite_size=2.0)
        self.assertEqual(SimulationConfig.from_dict(json.loads(json.dumps(cfg.to_dict()))), cfg)

    def test_rejects_unknown_and_invalid_values(self):
        with self.assertRaises(ValueError):
            SimulationConfig.from_dict({"bite": 3.0})
        with self.assertRaises(ValueError):
            SimulationConfig(patch_energy_range=(34.0, 18.0))
        with self.assertRaises(ValueError):
            SimulationConfig(contact_radius=0.0)

    def test_width_and_config_are_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            Simulation(width=50.0, config=SimulationConfig())

    def test_non_default_world_is_applied(self):
        sim = Simulation(seed=1, population=5, config=SimulationConfig(width=30.0, height=20.0, resource_patches=7))
        self.assertEqual(len(sim.world.resources), 7)
        sim.run(50)
        for o in sim.organisms:
            self.assertTrue(0.0 <= o.x < 30.0 and 0.0 <= o.y < 20.0)

    def test_shipped_config_file_loads(self):
        spec = load_experiment(REPO / "configs" / "default_genesis.json")
        self.assertEqual((spec.seed, spec.population, spec.steps), (42, 60, 1000))
        self.assertEqual(spec.config, SimulationConfig())


class RunRecordTests(unittest.TestCase):
    def test_legacy_snapshot_output_is_unchanged(self):
        out = run_cli("--steps", "30", "--seed", "3")
        self.assertEqual(set(out), {"tick", "population", "births", "deaths", "max_generation",
                                    "mean_speed", "mean_sensor_range", "mean_metabolism"})

    def test_record_contains_provenance_and_reruns_exactly(self):
        record = run_cli("--steps", "40", "--seed", "5", "--population", "25", "--format", "record")
        self.assertEqual(record["format"], "eyggnx.run-record")
        self.assertEqual(record["meta"]["simulation_contract"], SIMULATION_CONTRACT)
        for key in ("package_version", "python", "platform", "commit"):
            self.assertIn(key, record["meta"])
        self.assertIn("max_age", record["gene_bounds"])
        spec = ExperimentSpec.from_dict(record["experiment"])
        sim = Simulation(seed=spec.seed, population=spec.population, config=spec.config)
        sim.run(spec.steps)
        self.assertEqual(sim.state_digest(), record["result"]["state_digest"])
        self.assertEqual(record["result"]["completed_ticks"], 40)
        self.assertEqual(record["result"]["stop_reason"], "completed")

    def test_flags_override_config_file(self):
        record = run_cli("--config", str(REPO / "configs" / "default_genesis.json"),
                         "--steps", "5", "--format", "record")
        self.assertEqual((record["experiment"]["steps"], record["experiment"]["seed"]), (5, 42))

    def test_extinction_is_reported_not_raised(self):
        record = run_cli("--population", "0", "--steps", "10", "--format", "record")
        self.assertEqual(record["result"]["stop_reason"], "extinct")


if __name__ == "__main__":
    unittest.main()
