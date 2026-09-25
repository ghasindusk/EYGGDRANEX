# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .config import SimulationConfig
from .validation import non_negative_int, positive_finite


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
    def __init__(
        self,
        width: float,
        height: float,
        rng: random.Random,
        patches: int = 55,
        config: SimulationConfig | None = None,
    ):
        self.width = positive_finite("width", width)
        self.height = positive_finite("height", height)
        non_negative_int("patches", patches)
        if config is None:
            config = SimulationConfig(width=self.width, height=self.height, resource_patches=patches)
        self.config = config
        self.rng = rng
        self.resources = [
            ResourcePatch(
                x=rng.random() * width,
                y=rng.random() * height,
                energy=rng.uniform(*config.patch_energy_range),
                capacity=rng.uniform(*config.patch_capacity_range),
                regen=rng.uniform(*config.patch_regen_range),
            )
            for _ in range(patches)
        ]
        # Energy and capacity are drawn independently, so a patch can start above capacity.
        # Normalize after drawing: same random draws, and the first regen tick would clip
        # the excess anyway, so trajectories are unchanged.
        for resource in self.resources:
            resource.energy = min(resource.energy, resource.capacity)

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
        # Single pass, same result as filter-then-min: strict "<" keeps the first patch on ties.
        threshold = self.config.perception_threshold
        best: ResourcePatch | None = None
        best_d = math.inf
        for r in self.resources:
            if r.energy > threshold:
                d = self.distance(x, y, r.x, r.y)
                if d <= radius and d < best_d:
                    best, best_d = r, d
        return best

    def tick(self) -> None:
        for resource in self.resources:
            resource.tick()
