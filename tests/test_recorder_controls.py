# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import json
from pathlib import Path
import tempfile
import unittest

from eyggnx.config import SimulationConfig
from eyggnx.controls import neutral_drift
from eyggnx.genome import Genome
from eyggnx.organism import Organism
from eyggnx.recorder import Recorder, gene_metrics
from eyggnx.simulation import Simulation


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


class RecorderTests(unittest.TestCase):
    def test_recording_does_not_change_the_trajectory(self):
        plain = Simulation(seed=21, population=50)
        plain.run(300)
        with tempfile.TemporaryDirectory() as d:
            recorded = Simulation(seed=21, population=50)
            with Recorder(recorded, d, every=7):
                recorded.run(300)
        self.assertEqual(plain.state_digest(), recorded.state_digest())

    def test_events_reconstruct_lineage_and_counts(self):
        with tempfile.TemporaryDirectory() as d:
            sim = Simulation(seed=3, population=30)
            with Recorder(sim, d, every=10):
                sim.run(400)
            events = read_jsonl(Path(d) / "events.jsonl")
            series = read_jsonl(Path(d) / "timeseries.jsonl")
        births = [e for e in events if e["event"] == "birth"]
        deaths = [e for e in events if e["event"] == "death"]
        self.assertEqual(len(births), 30 + sim.births_total)
        self.assertEqual(len(deaths), sim.deaths_total)
        self.assertTrue({e["cause"] for e in deaths} <= {"starvation", "age"})
        known = set()
        for b in births:  # every parent is born before its children
            if b["parent_id"] is None:
                self.assertEqual(b["tick"], 0)
            else:
                self.assertIn(b["parent_id"], known)
            known.add(b["oid"])
        living = {o.oid for o in sim.organisms}
        self.assertEqual(known - {e["oid"] for e in deaths}, living)
        self.assertEqual([row["tick"] for row in series], list(range(0, 401, 10)))
        self.assertEqual(series[-1]["population"], len(sim.organisms))

    def test_gene_metrics_flag_bound_occupancy(self):
        organisms = [Organism(oid=i, x=0.0, y=0.0, energy=1.0, genome=Genome(distance_aversion=a))
                     for i, a in enumerate((0.01, 0.0105, 1.0, 100.0))]
        aversion = gene_metrics(organisms)["distance_aversion"]
        # Tolerance is 1% of the log-range, so 1.0 is far from both bounds of [0.01, 100].
        self.assertEqual((aversion["frac_at_lower"], aversion["frac_at_upper"]), (0.5, 0.25))


class ControlTests(unittest.TestCase):
    def test_fixed_genome_control_copies_parent_genomes(self):
        sim = Simulation(seed=2, population=30, config=SimulationConfig(mutate_offspring=False))
        founders = {o.genome for o in sim.organisms}
        sim.run(400)
        self.assertGreater(sim.births_total, 0)
        self.assertTrue({o.genome for o in sim.organisms} <= founders)

    def test_neutral_drift_has_no_directional_bias(self):
        # Contract 2's log-normal operator: no downward drift and no pile-up at the bounds.
        result = neutral_drift(generations=50, lineages=300, seed=7)
        for name in ("speed", "sensor_range", "max_age"):
            gene = result["genes"][name]
            self.assertLess(abs(gene["median"] / gene["start"] - 1.0), 0.1, name)
            self.assertLess(gene["frac_at_lower"] + gene["frac_at_upper"], 0.05, name)

    def test_neutral_drift_is_deterministic(self):
        self.assertEqual(neutral_drift(50, 20, seed=1), neutral_drift(50, 20, seed=1))


if __name__ == "__main__":
    unittest.main()
