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
from .controller import Intent
from .genome import Genome
from .world import World


def basal_metabolism(genome: Genome, config: SimulationConfig) -> float:
    """Energy paid every tick to stay alive. Wider senses and longer life cost energy."""
    return (config.base_metabolism + config.sensor_cost * genome.sensor_range
            + config.longevity_cost * genome.max_age)


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

    def act(self, intent: Intent, world: World) -> None:
        """Age one tick, move by ``intent`` and pay basal metabolism plus movement cost."""
        cfg = world.config
        self.age += 1
        self.x, self.y = world.wrap(self.x + intent.dx, self.y + intent.dy)
        travelled = math.hypot(intent.dx, intent.dy)
        self.energy -= basal_metabolism(self.genome, cfg) + travelled * cfg.movement_cost * self.genome.speed

    def can_reproduce(self) -> bool:
        return self.energy >= self.genome.reproduction_threshold and self.alive

    def reproduce(self, child_id: int, world: World, placement: random.Random,
                  mutation: random.Random) -> "Organism":
        child_energy = self.energy * self.genome.offspring_fraction
        self.energy -= child_energy
        angle = placement.random() * math.tau
        offset = world.config.offspring_offset
        x, y = world.wrap(self.x + math.cos(angle) * offset, self.y + math.sin(angle) * offset)
        return Organism(
            oid=child_id,
            x=x,
            y=y,
            energy=child_energy,
            genome=self.genome.mutate(mutation) if world.config.mutate_offspring else self.genome,
            generation=self.generation + 1,
            parent_id=self.oid,
        )
