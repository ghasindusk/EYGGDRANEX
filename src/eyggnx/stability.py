# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Long-run stability runs: many seeds, many ticks, structural checks and summaries.

For every seed the run is checked for structural invariants (finite energies,
positions inside the world, resources within capacity, population accounting, unique
ids) and summarised: extinction tick, population statistics over the second half of
the run, generations reached and per-gene bound occupancy at the end. Extinction is a
result, not a failure; only invariant violations are failures.

Usage::

    python -m eyggnx.stability --seeds 0-19 --ticks 30000 --check-every 100
    python -m eyggnx.stability --seeds 0-19 --ticks 30000 --config configs/detritus_genesis.json
"""

from __future__ import annotations

import argparse
import json
import math
from statistics import fmean, median, pstdev
from typing import Any

from .config import SIMULATION_CONTRACT, SimulationConfig, load_experiment
from .recorder import gene_metrics
from .simulation import Simulation
from .validation import non_negative_int


def structural_violations(sim: Simulation, population: int) -> list[str]:
    """Return a description of every structural invariant the current state breaks."""
    problems: list[str] = []
    if len(sim.organisms) != population + sim.births_total - sim.deaths_total:
        problems.append("population accounting")
    ids = [o.oid for o in sim.organisms]
    if len(ids) != len(set(ids)):
        problems.append("duplicate organism ids")
    for o in sim.organisms:
        if not math.isfinite(o.energy):
            problems.append(f"organism {o.oid}: non-finite energy")
        if not (0.0 <= o.x < sim.world.width and 0.0 <= o.y < sim.world.height):
            problems.append(f"organism {o.oid}: position outside the world")
    for i, r in enumerate(sim.world.resources):
        if not (0.0 <= r.energy <= r.capacity) or not math.isfinite(r.energy):
            problems.append(f"resource {i}: energy outside [0, capacity]")
    return problems


def run_seed(seed: int, ticks: int, population: int = 60, config: SimulationConfig | None = None,
             check_every: int = 100) -> dict[str, Any]:
    non_negative_int("ticks", ticks)
    if check_every < 1:
        raise ValueError("check_every must be >= 1")
    sim = Simulation(seed=seed, population=population, config=config or SimulationConfig())
    half = ticks // 2
    late_population: list[int] = []
    violations: list[dict[str, Any]] = []
    for _ in range(ticks):
        sim.tick()
        if sim.tick_index > half:
            late_population.append(len(sim.organisms))
        if sim.tick_index % check_every == 0 or not sim.organisms:
            for problem in structural_violations(sim, population):
                violations.append({"tick": sim.tick_index, "problem": problem})
        if not sim.organisms:
            break
    extinct = not sim.organisms
    mean_pop = fmean(late_population) if late_population else 0.0
    return {
        "seed": seed,
        "ticks_completed": sim.tick_index,
        "extinct_at": sim.tick_index if extinct else None,
        "population_late": {
            "min": min(late_population, default=0),
            "max": max(late_population, default=0),
            "mean": mean_pop,
            "cv": pstdev(late_population) / mean_pop if mean_pop else None,
        },
        "max_generation": max((o.generation for o in sim.organisms), default=None),
        "births_total": sim.births_total,
        "deaths_total": sim.deaths_total,
        "genes_final": gene_metrics(sim.organisms),
        "violations": violations,
        "state_digest": sim.state_digest(),
    }


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    survivors = [r for r in runs if r["extinct_at"] is None]
    genes: dict[str, Any] = {}
    for run in survivors:
        for name, m in run["genes_final"].items():
            g = genes.setdefault(name, {"mean": [], "frac_at_lower": [], "frac_at_upper": []})
            for key in g:
                g[key].append(m[key])
    return {
        "seeds": len(runs),
        "extinct": len(runs) - len(survivors),
        "violations": sum(len(r["violations"]) for r in runs),
        "population_late_mean_median": median(r["population_late"]["mean"] for r in survivors) if survivors else None,
        "population_late_cv_median": median(r["population_late"]["cv"] for r in survivors) if survivors else None,
        "max_generation_median": median(r["max_generation"] for r in survivors) if survivors else None,
        "genes_final_median": {name: {k: median(v) for k, v in g.items()} for name, g in genes.items()},
    }


def parse_seeds(text: str) -> list[int]:
    seeds: list[int] = []
    for part in text.split(","):
        if "-" in part.strip()[1:]:
            lo, hi = part.rsplit("-", 1)
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return seeds


def main() -> None:
    p = argparse.ArgumentParser(description="Long-run stability runs over many seeds.")
    p.add_argument("--seeds", default="0-9", help="seed list, e.g. '0-19' or '1,5,9' (default 0-9)")
    p.add_argument("--ticks", type=int, default=10000)
    p.add_argument("--population", type=int, default=60)
    p.add_argument("--check-every", type=int, default=100)
    p.add_argument("--config", metavar="PATH", help="experiment JSON whose model/world config is used")
    p.add_argument("--per-seed", action="store_true", help="include every per-seed result")
    args = p.parse_args()
    try:
        config = load_experiment(args.config).config if args.config else SimulationConfig()
        runs = [run_seed(s, args.ticks, args.population, config=config, check_every=args.check_every)
                for s in parse_seeds(args.seeds)]
    except ValueError as exc:
        p.error(str(exc))
    out: dict[str, Any] = {"simulation_contract": SIMULATION_CONTRACT, "config": config.to_dict(), "ticks": args.ticks,
                           "population": args.population, "summary": summarize(runs)}
    if args.per_seed:
        out["runs"] = runs
    print(json.dumps(out, indent=2))
    if out["summary"]["violations"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
