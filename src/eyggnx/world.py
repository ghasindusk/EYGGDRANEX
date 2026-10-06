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
    """An ingestible substrate: anything at a position holding energy.

    Renewable patches have ``regen > 0``; detritus left by a dead organism is the same
    substrate with ``regen < 0`` (it decays), and external data nutrients have
    ``regen == 0`` (finite, stable). A substrate with a ``reservoir`` has a finite supply
    behind it: ``regen`` moves energy from the reservoir to the exposed ``energy`` (up to
    ``capacity``) until the reservoir is empty, so it releases a finite amount slowly.
    ``reservoir is None`` means no such limit. Non-renewable substrates and substrates
    with an exhausted reservoir are removed once empty. There is no kind label: what a
    substrate is follows from its properties.
    """

    x: float
    y: float
    energy: float
    capacity: float
    regen: float
    reservoir: float | None = None

    def tick(self) -> None:
        if self.reservoir is None:
            self.energy = max(0.0, min(self.capacity, self.energy + self.regen))
            return
        moved = max(0.0, min(self.regen, self.reservoir, self.capacity - self.energy))
        self.energy += moved
        self.reservoir -= moved

    @property
    def exhausted(self) -> bool:
        """Empty and nothing left to replenish it."""
        if self.energy > 0.0:
            return False
        return self.regen <= 0.0 or (self.reservoir is not None and self.reservoir <= 0.0)


class World:
    #: Target cell size of the spatial grid. The grid only speeds up queries; results are
    #: identical to a full scan.
    CELL_SIZE = 8.0

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
        self.cols = max(1, int(self.width // self.CELL_SIZE))
        self.rows = max(1, int(self.height // self.CELL_SIZE))
        self.cell_w = self.width / self.cols
        self.cell_h = self.height / self.rows
        self._resources: list[ResourcePatch] = []
        self._grid: dict[tuple[int, int], list[int]] = {}
        resources = []
        for _ in range(patches):
            x, y = rng.random() * width, rng.random() * height
            energy = rng.uniform(*config.patch_energy_range)
            capacity = rng.uniform(*config.patch_capacity_range)
            regen = rng.uniform(*config.patch_regen_range)
            resources.append(ResourcePatch(x, y, min(energy, capacity), capacity, regen))
        self.resources = resources

    @property
    def resources(self) -> list[ResourcePatch]:
        return self._resources

    @resources.setter
    def resources(self, value: list[ResourcePatch]) -> None:
        self._resources = value
        self._rebuild_grid()

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        return min(self.cols - 1, int(x / self.cell_w)), min(self.rows - 1, int(y / self.cell_h))

    def _rebuild_grid(self) -> None:
        grid: dict[tuple[int, int], list[int]] = {}
        for i, r in enumerate(self._resources):
            grid.setdefault(self._cell(r.x, r.y), []).append(i)
        self._grid = grid

    def add_resource(self, patch: ResourcePatch) -> None:
        self._resources.append(patch)
        self._grid.setdefault(self._cell(patch.x, patch.y), []).append(len(self._resources) - 1)

    def wrap(self, x: float, y: float) -> tuple[float, float]:
        return x % self.width, y % self.height

    def delta(self, ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
        dx = (bx - ax + self.width / 2.0) % self.width - self.width / 2.0
        dy = (by - ay + self.height / 2.0) % self.height - self.height / 2.0
        return dx, dy

    def distance(self, ax: float, ay: float, bx: float, by: float) -> float:
        dx, dy = self.delta(ax, ay, bx, by)
        return math.hypot(dx, dy)

    def _candidates(self, x: float, y: float, radius: float) -> list[int]:
        """Indices of patches in grid cells that can hold a point within ``radius``, ascending."""
        cx, cy = self._cell(x, y)
        reach_x = int(radius / self.cell_w) + 1
        reach_y = int(radius / self.cell_h) + 1
        if 2 * reach_x + 1 >= self.cols and 2 * reach_y + 1 >= self.rows:
            return list(range(len(self._resources)))
        cols = {(cx + i) % self.cols for i in range(-reach_x, reach_x + 1)}
        rows = {(cy + j) % self.rows for j in range(-reach_y, reach_y + 1)}
        out: list[int] = []
        grid = self._grid
        for c in cols:
            for r in rows:
                cell = grid.get((c, r))
                if cell:
                    out.extend(cell)
        out.sort()
        return out

    def perceive(self, x: float, y: float, radius: float) -> list[tuple[float, int, ResourcePatch]]:
        """Perceivable patches within ``radius`` as ``(distance, index, patch)``, by index."""
        threshold = self.config.perception_threshold
        resources = self._resources
        found = []
        for i in self._candidates(x, y, radius):
            r = resources[i]
            if r.energy > threshold:
                d = self.distance(x, y, r.x, r.y)
                if d <= radius:
                    found.append((d, i, r))
        return found

    def nearest_resource(self, x: float, y: float, radius: float) -> ResourcePatch | None:
        """Nearest perceivable patch within ``radius``; ties go to the earlier patch."""
        found = self.perceive(x, y, radius)
        return min(found, key=lambda t: (t[0], t[1]))[2] if found else None

    def tick(self) -> None:
        for resource in self._resources:
            resource.tick()
        if any(r.exhausted for r in self._resources):
            self.resources = [r for r in self._resources if not r.exhausted]
