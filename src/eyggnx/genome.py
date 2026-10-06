# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from dataclasses import dataclass, fields, replace
import math
import random


@dataclass(frozen=True, slots=True)
class GeneSpec:
    """One row of the gene registry: name, default value and hard bounds (both > 0)."""

    name: str
    default: float
    lo: float
    hi: float
    doc: str


#: Gene registry. Order is the order of random draws during mutation; append new genes
#: at the end. Physiological constants (basal metabolism, movement cost) are not genes:
#: they are physics in ``SimulationConfig``, and every gene that improves survival pays
#: for itself through them (see ``docs/specifications/GENOME_SPEC.md``).
GENES: tuple[GeneSpec, ...] = (
    GeneSpec("speed", 1.0, 0.15, 4.0, "maximum distance moved per tick; movement cost scales with it"),
    GeneSpec("sensor_range", 8.0, 1.0, 30.0, "perception radius; adds sensor_cost per unit to basal metabolism"),
    GeneSpec("reproduction_threshold", 28.0, 12.0, 120.0, "energy at which the organism reproduces"),
    GeneSpec("offspring_fraction", 0.42, 0.20, 0.70, "fraction of parent energy given to the child"),
    GeneSpec("mutation_scale", 0.06, 0.005, 0.25, "log-space standard deviation of mutation"),
    GeneSpec("max_age", 420.0, 80.0, 2000.0, "lifespan in ticks; adds longevity_cost per tick to basal metabolism"),
    GeneSpec("distance_aversion", 1.0, 0.01, 100.0, "controller: patch score = energy / (1 + aversion * distance)"),
    GeneSpec("wander_step", 0.625, 0.05, 1.0, "controller: random-walk step as a fraction of speed"),
)

#: Clamp range of every gene, recorded with every run.
GENE_BOUNDS: dict[str, tuple[float, float]] = {g.name: (g.lo, g.hi) for g in GENES}


def at_bounds(name: str, value: float, tolerance: float = 0.01) -> tuple[bool, bool]:
    """Whether ``value`` lies within ``tolerance`` of the gene's log-range from each bound."""
    lo, hi = GENE_BOUNDS[name]
    width = (math.log(hi) - math.log(lo)) * tolerance
    u = math.log(value)
    return u <= math.log(lo) + width, u >= math.log(hi) - width


def reflect(value: float, lo: float, hi: float) -> float:
    """Fold ``value`` back into ``[lo, hi]`` by reflecting at the bounds."""
    if lo <= value <= hi:
        return value
    span = hi - lo
    t = (value - lo) % (2.0 * span)
    return lo + (t if t <= span else 2.0 * span - t)


@dataclass(frozen=True, slots=True)
class Genome:
    speed: float = 1.0
    sensor_range: float = 8.0
    reproduction_threshold: float = 28.0
    offspring_fraction: float = 0.42
    mutation_scale: float = 0.06
    max_age: float = 420.0
    distance_aversion: float = 1.0
    wander_step: float = 0.625

    def mutate(self, rng: random.Random) -> "Genome":
        """Log-normal mutation with reflecting bounds in log space.

        ``log v' = reflect(log v + N(0, s), log lo, log hi)``. The operator is unbiased in
        log space (no neutral drift away from the start value) and does not pile values up
        at the bounds.
        """
        s = self.mutation_scale
        values = {}
        for gene in GENES:
            u = math.log(getattr(self, gene.name)) + rng.gauss(0.0, s)
            v = math.exp(reflect(u, math.log(gene.lo), math.log(gene.hi)))
            values[gene.name] = min(gene.hi, max(gene.lo, v))  # guard exp/log round-off
        return replace(self, **values)


assert tuple(f.name for f in fields(Genome)) == tuple(g.name for g in GENES), "Genome fields must match GENES"
assert all(getattr(Genome(), g.name) == g.default for g in GENES), "Genome defaults must match GENES"
