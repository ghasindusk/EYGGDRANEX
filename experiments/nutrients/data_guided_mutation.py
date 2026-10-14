# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Compare ordinary and data-guided mutation on the same files and seeds.

Run after installing eyggnx, or set PYTHONPATH=src from the repository root:
python experiments/nutrients/data_guided_mutation.py --nutrient-dir src/eyggnx
"""

from __future__ import annotations

import argparse
from dataclasses import fields
import json
from statistics import fmean

from eyggnx.config import SimulationConfig
from eyggnx.genome import Genome
from eyggnx.simulation import Simulation


def run(directory: str, seeds: int, steps: int, strength: float, regrow: int,
        resource_patches: int) -> list[dict]:
    rows = []
    for seed in range(1, seeds + 1):
        for value in (0.0, strength):
            config = SimulationConfig(nutrient_dir=directory,
                                      nutrient_regrow_interval=regrow,
                                      nutrient_mutation_strength=value,
                                      resource_patches=resource_patches)
            sim = Simulation(seed=seed, config=config)
            sim.run(steps)
            rows.append({
                "seed": seed,
                "strength": value,
                "ticks": sim.tick_index,
                "population": len(sim.organisms),
                "births": sim.births_total,
                "max_generation_living": sim.snapshot().max_generation,
                "data_eaten": sim.data_eaten_total,
                "data_influenced_births": sim.data_influenced_births,
                "genes": {f.name: fmean(getattr(o.genome, f.name) for o in sim.organisms)
                          for f in fields(Genome)} if sim.organisms else {},
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nutrient-dir", required=True)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--strength", type=float, default=0.2)
    parser.add_argument("--regrow", type=int, default=250)
    parser.add_argument("--resource-patches", type=int, default=55)
    args = parser.parse_args()
    if args.seeds < 1 or args.steps < 1 or args.resource_patches < 0:
        parser.error("--seeds and --steps must be positive; --resource-patches must be non-negative")
    print(json.dumps(run(args.nutrient_dir, args.seeds, args.steps,
                         args.strength, args.regrow, args.resource_patches), indent=2))


if __name__ == "__main__":
    main()
