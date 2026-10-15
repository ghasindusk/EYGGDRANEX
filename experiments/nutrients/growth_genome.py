# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Compare growth-genome inheritance and data reading on the same data and seeds.

Conditions: ``off`` (data learning disabled); data learning with
``growth_inheritance_probability`` 0, 0.5 and 1 (identity reading); ``read_p05``
(heritable reading table); and ``*_noguide`` variants without the data bias on
offspring mutation. For every organism that dies the largest per-gene growth and the
data it ate during its own life are recorded. With reading tables, the population's
agreement and the direction its mean table reads the food in are reported.

    PYTHONPATH=src python experiments/nutrients/growth_genome.py --nutrient-dir DIR \
        --seeds 5 --steps 20000 --condition p05 > out.json
"""

from __future__ import annotations

import argparse
from dataclasses import fields
import json
from statistics import fmean, median

from eyggnx.config import SimulationConfig
from eyggnx.genome import GENES, Genome
from eyggnx.simulation import Simulation

CONDITIONS = {
    "off": {"nutrient_mutation_strength": 0.0},
    "p0": {"nutrient_mutation_strength": 0.2, "growth_inheritance_probability": 0.0},
    "p05": {"nutrient_mutation_strength": 0.2, "growth_inheritance_probability": 0.5},
    "p1": {"nutrient_mutation_strength": 0.2, "growth_inheritance_probability": 1.0},
    "p05_noguide": {"nutrient_mutation_strength": 0.2, "growth_inheritance_probability": 0.5,
                    "nutrient_offspring_guidance": False},
    "read_p05": {"nutrient_mutation_strength": 0.2, "growth_inheritance_probability": 0.5,
                 "growth_reading_heritable": True},
    "read_p05_noguide": {"nutrient_mutation_strength": 0.2, "growth_inheritance_probability": 0.5,
                         "growth_reading_heritable": True, "nutrient_offspring_guidance": False},
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


def reading_summary(organisms, food) -> dict:
    tables = [o.reading for o in organisms if o.reading is not None]
    if not tables:
        return {}
    n = len(GENES)
    mean_table = [fmean(t[k] for t in tables) for k in range(n * n)]
    agreement = fmean(abs(m) for m in mean_table) / max(1e-12, fmean(abs(w) for t in tables for w in t))
    v = [sum(mean_table[i * n + j] * food[j] for j in range(n)) for i in range(n)]
    peak = max((abs(x) for x in v), default=0.0)
    return {"agreement": agreement,
            "food_growth_direction": {GENES[i].name: (v[i] / peak if peak > 0 else 0.0) for i in range(n)}}


class DeathLog:
    """Observer: reads organisms only (invariant #8)."""

    def __init__(self) -> None:
        self.inherited_diet: dict[int, float] = {}
        self.deaths: list[tuple[float, float]] = []

    def on_birth(self, tick, child, parent) -> None:
        self.inherited_diet[child.oid] = child.diet_energy

    def on_death(self, tick, organism, cause) -> None:
        growth = max((abs(g) for g in (organism.growth or ())), default=0.0)
        own_data = organism.diet_energy - self.inherited_diet.pop(organism.oid, 0.0)
        self.deaths.append((growth, own_data))

    def on_tick(self, sim) -> None:
        pass


def gene_means(genomes: list[Genome]) -> dict[str, float]:
    return {f.name: fmean(getattr(g, f.name) for g in genomes) for f in fields(Genome)} if genomes else {}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nutrient-dir", required=True)
    p.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--steps", type=int, default=20000)
    p.add_argument("--regrow", type=int, default=250)
    p.add_argument("--resource-patches", type=int, default=0)
    args = p.parse_args()
    cfg = SimulationConfig(nutrient_dir=args.nutrient_dir, resource_patches=args.resource_patches,
                           nutrient_regrow_interval=args.regrow, **CONDITIONS[args.condition])
    rows = []
    for seed in range(1, args.seeds + 1):
        sim = Simulation(seed=seed, population=60, config=cfg)
        food = food_direction(sim)
        start_reading = reading_summary(sim.organisms, food)
        log = DeathLog()
        sim.observer = log
        sim.run(args.steps)
        cap = cfg.growth_max_log
        living = sim.organisms
        rows.append({
            "seed": seed,
            "tick": sim.tick_index,
            "population": len(living),
            "births_total": sim.births_total,
            "max_generation_living": max((o.generation for o in living), default=0),
            "growth_inherited_births": sim.growth_inherited_births,
            "deaths": len(log.deaths),
            "median_growth_at_death": median(g for g, _ in log.deaths) if log.deaths else None,
            "frac_dead_reached_cap": (sum(g >= cap - 1e-12 for g, _ in log.deaths) / len(log.deaths)
                                      if log.deaths else None),
            "median_own_data_eaten": median(d for _, d in log.deaths) if log.deaths else None,
            "expressed_gene_means": gene_means([o.genome for o in living]),
            "base_gene_means": gene_means([o.base for o in living]),
            "reading_start": start_reading,
            "reading_end": reading_summary(living, food),
        })
    print(json.dumps({"condition": args.condition, "config": {k: v for k, v in CONDITIONS[args.condition].items()},
                      "growth_max_log": cfg.growth_max_log, "growth_gain": cfg.growth_gain,
                      "steps": args.steps, "regrow": args.regrow, "resource_patches": args.resource_patches,
                      "manifest_digest": sim.nutrient_manifest["digest"], "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
