# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from dataclasses import dataclass, replace
import random

#: Clamp range applied after each mutation. Genes whose improvement carries no cost in
#: the current model (for example metabolism, max_age) drift toward these bounds over
#: long runs, so the bounds are part of the model and are recorded with every run.
GENE_BOUNDS: dict[str, tuple[float, float]] = {
    "speed": (0.15, 4.0),
    "sensor_range": (1.0, 30.0),
    "metabolism": (0.05, 2.5),
    "movement_cost": (0.005, 0.8),
    "reproduction_threshold": (12.0, 120.0),
    "offspring_fraction": (0.20, 0.70),
    "mutation_scale": (0.005, 0.25),
    "max_age": (80.0, 2000.0),
}


@dataclass(frozen=True, slots=True)
class Genome:
    speed: float = 1.0
    sensor_range: float = 8.0
    metabolism: float = 0.22
    movement_cost: float = 0.04
    reproduction_threshold: float = 28.0
    offspring_fraction: float = 0.42
    mutation_scale: float = 0.06
    max_age: int = 420

    def mutate(self, rng: random.Random) -> "Genome":
        s = self.mutation_scale

        def m(name: str, value: float) -> float:
            lo, hi = GENE_BOUNDS[name]
            return max(lo, min(hi, value * (1.0 + rng.gauss(0.0, s))))

        # Keyword order fixes the order of random draws; do not reorder.
        return replace(
            self,
            speed=m("speed", self.speed),
            sensor_range=m("sensor_range", self.sensor_range),
            metabolism=m("metabolism", self.metabolism),
            movement_cost=m("movement_cost", self.movement_cost),
            reproduction_threshold=m("reproduction_threshold", self.reproduction_threshold),
            offspring_fraction=m("offspring_fraction", self.offspring_fraction),
            mutation_scale=m("mutation_scale", self.mutation_scale),
            max_age=int(round(m("max_age", float(self.max_age)))),
        )
