# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from dataclasses import dataclass
import math
import random


@dataclass(slots=True)
class ResourcePatch:
    x: float
    y: float
    energy: float
    capacity: float
    regen: float

    def tick(self) -> None:
        self.energy = min(self.capacity, self.energy + self.regen)


class World:
    def __init__(self, width: float, height: float, rng: random.Random, patches: int = 55):
        self.width = width
        self.height = height
        self.rng = rng
        self.resources = [
            ResourcePatch(
                x=rng.random() * width,
                y=rng.random() * height,
                energy=rng.uniform(18.0, 34.0),
                capacity=rng.uniform(26.0, 46.0),
                regen=rng.uniform(0.18, 0.55),
            )
            for _ in range(patches)
        ]

    def wrap(self, x: float, y: float) -> tuple[float, float]:
        return x % self.width, y % self.height

    def delta(self, ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
        dx = (bx - ax + self.width / 2.0) % self.width - self.width / 2.0
        dy = (by - ay + self.height / 2.0) % self.height - self.height / 2.0
        return dx, dy

    def distance(self, ax: float, ay: float, bx: float, by: float) -> float:
        dx, dy = self.delta(ax, ay, bx, by)
        return math.hypot(dx, dy)

    def nearest_resource(self, x: float, y: float, radius: float) -> ResourcePatch | None:
        candidates = [r for r in self.resources if r.energy > 0.2 and self.distance(x, y, r.x, r.y) <= radius]
        return min(candidates, key=lambda r: self.distance(x, y, r.x, r.y), default=None)

    def tick(self) -> None:
        for resource in self.resources:
            resource.tick()
