# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Null and control conditions for telling selection apart from mutation bias.

* ``neutral_drift``: mutation-only lineages with no selection. The mutation operator
  ``v * (1 + N(0, s))`` followed by clamping is biased downward in log space, and
  ``mutation_scale`` mutates itself, so genes drift without any selection. Compare
  observed trait changes against this baseline before calling them adaptation.
* Fixed-genome control: run with ``SimulationConfig(mutate_offspring=False)``.

Usage::

    python -m eyggnx.controls --generations 300 --lineages 2000 --seed 7
"""

from __future__ import annotations

import argparse
from dataclasses import fields
import json
import random
from statistics import median
from typing import Any

from .genome import GENE_BOUNDS, Genome
from .validation import non_negative_int


def neutral_drift(generations: int, lineages: int, seed: int, start: Genome | None = None) -> dict[str, Any]:
    """Mutate ``lineages`` independent copies of ``start`` for ``generations`` steps."""
    non_negative_int("generations", generations)
    non_negative_int("lineages", lineages)
    start = start or Genome()
    rng = random.Random(seed)
    finals = []
    for _ in range(lineages):
        g = start
        for _ in range(generations):
            g = g.mutate(rng)
        finals.append(g)
    genes: dict[str, Any] = {}
    for f in fields(Genome):
        values = [float(getattr(g, f.name)) for g in finals]
        lo, hi = GENE_BOUNDS[f.name]
        eps = (hi - lo) * 0.01
        genes[f.name] = {
            "start": float(getattr(start, f.name)),
            "median": median(values) if values else None,
            "frac_at_lower": sum(v <= lo + eps for v in values) / len(values) if values else None,
            "frac_at_upper": sum(v >= hi - eps for v in values) / len(values) if values else None,
        }
    return {"control": "neutral_drift", "generations": generations, "lineages": lineages, "seed": seed,
            "genes": genes}


def main() -> None:
    p = argparse.ArgumentParser(description="Mutation-only neutral drift baseline (no selection).")
    p.add_argument("--generations", type=int, default=300)
    p.add_argument("--lineages", type=int, default=2000)
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()
    try:
        result = neutral_drift(args.generations, args.lineages, args.seed)
    except ValueError as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
