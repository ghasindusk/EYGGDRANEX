# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Is the heritable reading table under selection? One run, with checkpoints.

Runs one seed of one condition and prints a JSON line per checkpoint: population, births,
generations and, for the reading table and its shadow (inherited exactly like it but never
used, ``reading_shadow_control``), the population's agreement and the direction its mean
table reads the food in. Shadow and real tables share one genealogy, so drift affects both
equally; only the real table can be selected. Summarise with ``reading_selection_summary.py``.

    PYTHONPATH=src python experiments/nutrients/reading_selection.py --nutrient-dir DIR \
        --condition read --seed 1 --steps 100000 --every 10000 > run.jsonl
"""

from __future__ import annotations

import argparse
import json
from statistics import fmean

from eyggnx.config import SimulationConfig
from eyggnx.genome import GENES
from eyggnx.simulation import Simulation

BASE = {"nutrient_mutation_strength": 0.2, "growth_inheritance_probability": 0.5}
CONDITIONS = {
    "off": {"nutrient_mutation_strength": 0.0},
    "identity": dict(BASE),
    "read": dict(BASE, growth_reading_heritable=True, reading_shadow_control=True),
    "read_noguide": dict(BASE, growth_reading_heritable=True, reading_shadow_control=True,
                         nutrient_offspring_guidance=False),
}


def food_direction(sim) -> list[float]:
    """Energy-weighted mean signature of the data food, scaled to a largest component of 1."""
    total = [0.0] * len(GENES)
    for r in sim.world.resources:
        if r.information_signature is not None:
            w = r.energy + (r.reservoir or 0.0)
            total = [t + w * s for t, s in zip(total, r.information_signature)]
    peak = max((abs(t) for t in total), default=0.0)
    return [t / peak for t in total] if peak > 0 else total


def table_summary(tables, food) -> dict | None:
    """Agreement (0 = scattered, 1 = identical) and the mean table's reading of the food."""
    tables = [t for t in tables if t is not None]
    if not tables:
        return None
    n = len(GENES)
    mean_table = [fmean(t[k] for t in tables) for k in range(n * n)]
    agreement = fmean(abs(m) for m in mean_table) / max(1e-12, fmean(abs(w) for t in tables for w in t))
    direction = [sum(mean_table[i * n + j] * food[j] for j in range(n)) for i in range(n)]
    return {"agreement": agreement, "direction": direction}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nutrient-dir", required=True)
    p.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--steps", type=int, default=100000)
    p.add_argument("--every", type=int, default=10000)
    p.add_argument("--regrow", type=int, default=250)
    p.add_argument("--resource-patches", type=int, default=0)
    args = p.parse_args()
    cfg = SimulationConfig(nutrient_dir=args.nutrient_dir, resource_patches=args.resource_patches,
                           nutrient_regrow_interval=args.regrow, **CONDITIONS[args.condition])
    sim = Simulation(seed=args.seed, population=60, config=cfg)
    food = food_direction(sim)
    while True:
        living = sim.organisms
        print(json.dumps({
            "condition": args.condition, "seed": args.seed, "tick": sim.tick_index,
            "population": len(living), "births_total": sim.births_total,
            "max_generation_living": max((o.generation for o in living), default=0),
            "growth_inherited_births": sim.growth_inherited_births,
            "real": table_summary([o.reading for o in living], food),
            "shadow": table_summary([o.reading_shadow for o in living], food),
            "manifest_digest": sim.nutrient_manifest["digest"],
        }), flush=True)
        if sim.tick_index >= args.steps or not living:
            break
        sim.run(min(args.every, args.steps - sim.tick_index))


if __name__ == "__main__":
    main()
