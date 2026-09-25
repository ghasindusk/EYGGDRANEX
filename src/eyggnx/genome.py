# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from dataclasses import dataclass, replace
import random


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

        def m(value: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, value * (1.0 + rng.gauss(0.0, s))))

        return replace(
            self,
            speed=m(self.speed, 0.15, 4.0),
            sensor_range=m(self.sensor_range, 1.0, 30.0),
            metabolism=m(self.metabolism, 0.05, 2.5),
            movement_cost=m(self.movement_cost, 0.005, 0.8),
            reproduction_threshold=m(self.reproduction_threshold, 12.0, 120.0),
            offspring_fraction=m(self.offspring_fraction, 0.20, 0.70),
            mutation_scale=m(self.mutation_scale, 0.005, 0.25),
            max_age=int(round(m(float(self.max_age), 80.0, 2000.0))),
        )
