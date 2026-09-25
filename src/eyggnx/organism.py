# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .genome import Genome
from .world import World


@dataclass(slots=True)
class Organism:
    oid: int
    x: float
    y: float
    energy: float
    genome: Genome
    generation: int = 0
    parent_id: int | None = None
    age: int = 0

    @property
    def alive(self) -> bool:
        return self.energy > 0.0 and self.age < self.genome.max_age

    def step(self, world: World, rng: random.Random) -> float:
        self.age += 1
        target = world.nearest_resource(self.x, self.y, self.genome.sensor_range)

        if target is None:
            angle = rng.random() * math.tau
            distance = self.genome.speed * rng.uniform(0.25, 1.0)
            dx, dy = math.cos(angle) * distance, math.sin(angle) * distance
        else:
            dx, dy = world.delta(self.x, self.y, target.x, target.y)
            d = math.hypot(dx, dy)
            distance = min(self.genome.speed, d)
            if d > 1e-12:
                dx, dy = dx / d * distance, dy / d * distance
            else:
                dx = dy = 0.0

        self.x, self.y = world.wrap(self.x + dx, self.y + dy)
        travelled = math.hypot(dx, dy)
        self.energy -= self.genome.metabolism + travelled * self.genome.movement_cost

        eaten = 0.0
        target = world.nearest_resource(self.x, self.y, radius=1.1)
        if target is not None:
            eaten = min(target.energy, 3.0)
            target.energy -= eaten
            self.energy += eaten
        return eaten

    def can_reproduce(self) -> bool:
        return self.energy >= self.genome.reproduction_threshold and self.alive

    def reproduce(self, child_id: int, rng: random.Random, world: World) -> "Organism":
        child_energy = self.energy * self.genome.offspring_fraction
        self.energy -= child_energy
        angle = rng.random() * math.tau
        x, y = world.wrap(self.x + math.cos(angle), self.y + math.sin(angle))
        return Organism(
            oid=child_id,
            x=x,
            y=y,
            energy=child_energy,
            genome=self.genome.mutate(rng),
            generation=self.generation + 1,
            parent_id=self.oid,
        )
