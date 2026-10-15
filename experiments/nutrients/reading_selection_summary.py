# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Summarise reading_selection.py runs with exact paired permutation tests.

Reads ``<data>_<condition>_<seed>.jsonl`` files from a directory. Every comparison is
paired by seed (the same seed gives the same founders and food in every condition) and
tested by enumerating all sign flips of the per-seed differences (two-sided, exact).

    python experiments/nutrients/reading_selection_summary.py RESULTS_DIR
"""

from __future__ import annotations

from itertools import product
import json
import math
from pathlib import Path
import sys
from statistics import fmean


def sign_flip_p(diffs: list[float]) -> float:
    """Exact two-sided p-value of the mean paired difference under sign flips."""
    observed = abs(fmean(diffs))
    count = total = 0
    for signs in product((1, -1), repeat=len(diffs)):
        total += 1
        if abs(fmean(s * d for s, d in zip(signs, diffs))) >= observed - 1e-12:
            count += 1
    return count / total


def cosine(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na > 0 and nb > 0 else 0.0


def load(directory: Path) -> dict:
    runs = {}
    for f in directory.glob("*.jsonl"):
        rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        if rows:
            data = f.stem.split("_")[0]
            runs[(data, rows[0]["condition"], rows[0]["seed"])] = rows
    return runs


def consensus_alignment(dirs: dict[int, list[float]]) -> dict[int, float]:
    """For each seed: cosine between its direction and the mean direction of the other seeds."""
    out = {}
    for s, d in dirs.items():
        others = [v for t, v in dirs.items() if t != s]
        if others:
            mean_other = [fmean(v[i] for v in others) for i in range(len(d))]
            out[s] = cosine(d, mean_other)
    return out


def main() -> None:
    runs = load(Path(sys.argv[1]))
    datasets = sorted({k[0] for k in runs})
    for data in datasets:
        print(f"\n===== {data}")
        final = {}
        for (d, cond, seed), rows in runs.items():
            if d == data:
                final[(cond, seed)] = rows[-1]
        conds = sorted({c for c, _ in final})
        seeds = sorted({s for _, s in final})
        print("condition        seeds  survived  population  births  max_generation")
        for c in conds:
            rs = [final[(c, s)] for s in seeds if (c, s) in final]
            print(f"{c:16s} {len(rs):5d} {sum(r['population'] > 0 for r in rs):9d} "
                  f"{fmean(r['population'] for r in rs):11.1f} {fmean(r['births_total'] for r in rs):7.0f} "
                  f"{fmean(r['max_generation_living'] for r in rs):15.1f}")

        def paired(a: str, b: str, key) -> None:
            common = [s for s in seeds if (a, s) in final and (b, s) in final]
            diffs = [key(final[(a, s)]) - key(final[(b, s)]) for s in common]
            if diffs:
                wins = sum(x > 0 for x in diffs)
                print(f"  {a} - {b}: mean {fmean(diffs):+.3f}  ({wins}/{len(diffs)} seeds higher)  "
                      f"p = {sign_flip_p(diffs):.4f}")

        print("population (final), paired by seed:")
        for a, b in (("read", "identity"), ("read", "off"), ("identity", "off"),
                     ("read_noguide", "off"), ("read_noguide", "identity")):
            paired(a, b, lambda r: r["population"])
        print("max generation (final), paired by seed:")
        for a, b in (("read", "off"), ("read", "identity"), ("read_noguide", "off")):
            paired(a, b, lambda r: r["max_generation_living"])

        for c in ("read", "read_noguide"):
            common = [s for s in seeds if (c, s) in final and final[(c, s)]["real"] and final[(c, s)]["shadow"]]
            if not common:
                continue
            print(f"selection on the table ({c}): real vs shadow agreement, paired by seed")
            real = [final[(c, s)]["real"]["agreement"] for s in common]
            shadow = [final[(c, s)]["shadow"]["agreement"] for s in common]
            diffs = [r - h for r, h in zip(real, shadow)]
            print(f"  real {fmean(real):.3f}  shadow {fmean(shadow):.3f}  diff {fmean(diffs):+.3f}  "
                  f"({sum(x > 0 for x in diffs)}/{len(diffs)} seeds)  p = {sign_flip_p(diffs):.4f}")
            rows = {s: runs[(data, c, s)] for s in common}
            ticks = sorted({r["tick"] for rs in rows.values() for r in rs})
            course = []
            for t in ticks:
                pts = [(r["real"]["agreement"], r["shadow"]["agreement"]) for rs in rows.values()
                       for r in rs if r["tick"] == t and r["real"] and r["shadow"]]
                if len(pts) == len(common):
                    course.append(f"{t // 1000}k:{fmean(a - b for a, b in pts):+.2f}")
            print("  real - shadow over time: " + " ".join(course))
            real_dirs = {s: final[(c, s)]["real"]["direction"] for s in common}
            shadow_dirs = {s: final[(c, s)]["shadow"]["direction"] for s in common}
            ra, sa = consensus_alignment(real_dirs), consensus_alignment(shadow_dirs)
            diffs = [ra[s] - sa[s] for s in common]
            print(f"  common reading across seeds (cosine to the other seeds' mean): real {fmean(ra.values()):+.3f}  "
                  f"shadow {fmean(sa.values()):+.3f}  p = {sign_flip_p(diffs):.4f}")
            mean_real = [fmean(v[i] for v in real_dirs.values()) for i in range(8)]
            print("  mean real direction: " + " ".join(f"{x:+.2f}" for x in mean_real))


if __name__ == "__main__":
    main()
