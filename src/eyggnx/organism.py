# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .config import MAX_NUTRIENT_PARENT_LEARNING_RATE, SimulationConfig
from .controller import Intent
from .genome import Genome, reflect
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
    diet_signal: tuple[float, ...] | None = None
    diet_energy: float = 0.0
    learned_bias_applied: tuple[float, ...] | None = None
    data_learning_rate: float = 0.0
    #: Base genome, fixed for life. ``None`` until the organism first grows; until then
    #: ``genome`` is the base genome.
    base_genome: Genome | None = None
    #: Growth genome: per-gene log-space offsets, each within +/- growth_max_log.
    growth: tuple[float, ...] | None = None
    #: Whether this organism descended from its parent's expressed (base x growth) genome.
    growth_inherited: bool = False

    @property
    def base(self) -> Genome:
        """The base genome: fixed from birth to death."""
        return self.base_genome if self.base_genome is not None else self.genome

    def grow(self, delta: tuple[float, ...], cap: float) -> None:
        """Add ``delta`` to the growth genome (bounded per gene) and re-express the genome.

        Only the growth genome changes; the base genome stays as it was at birth.
        """
        base = self.base
        current = self.growth or (0.0,) * len(delta)
        growth = tuple(max(-cap, min(cap, g + d)) for g, d in zip(current, delta))
        if growth == current:
            return
        self.base_genome = base
        self.growth = growth
        self.genome = base.shift(growth)

    @staticmethod
    def vary_learning_rate(rate: float, scale: float, rng: random.Random) -> float:
        """Inherit a rate with independent log-space variation, bounded at 2%."""
        if rate <= 0.0:
            return 0.0
        low = 1e-6
        upper = MAX_NUTRIENT_PARENT_LEARNING_RATE
        value = math.exp(reflect(math.log(rate) + rng.gauss(0.0, scale),
                                 math.log(low), math.log(upper)))
        return min(upper, max(low, value))

    def learned_bias(self, config: SimulationConfig) -> tuple[float, ...] | None:
        if self.diet_energy <= 0.0 or self.diet_signal is None:
            return None
        exposure = min(1.0, self.diet_energy / self.genome.reproduction_threshold)
        return tuple(config.nutrient_mutation_strength * exposure * value / self.diet_energy
                     for value in self.diet_signal)

    def absorb_data(self, amount: float, signature: tuple[float, ...],
                    config: SimulationConfig | None = None) -> None:
        """Accumulate consumed data for life and apply only new learning to the parent."""
        if amount <= 0.0:
            return
        if self.diet_signal is None:
            self.diet_signal = (0.0,) * len(signature)
        self.diet_signal = tuple(a + amount * b for a, b in zip(self.diet_signal, signature))
        self.diet_energy += amount
        if (config is not None and config.mutate_offspring
                and config.nutrient_mutation_strength > 0):
            bias = self.learned_bias(config)
            assert bias is not None
            previous = self.learned_bias_applied or (0.0,) * len(bias)
            fraction = self.data_learning_rate
            delta = tuple(fraction * (new - old) for new, old in zip(bias, previous))
            if any(delta):
                self.grow(delta, config.growth_max_log)
            self.learned_bias_applied = bias

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
                  mutation: random.Random, learning: random.Random | None = None) -> "Organism":
        child_energy = self.energy * self.genome.offspring_fraction
        self.energy -= child_energy
        angle = placement.random() * math.tau
        offset = world.config.offspring_offset
        x, y = world.wrap(self.x + math.cos(angle) * offset, self.y + math.sin(angle) * offset)
        cfg = world.config
        bias = self.learned_bias(cfg) if cfg.nutrient_mutation_strength > 0 else None
        # The child descends from base x growth with probability growth_inheritance_probability,
        # otherwise from the base genome; drawn from the learning stream, only when there is growth.
        inherit_growth = False
        if self.growth is not None and any(self.growth) and cfg.mutate_offspring:
            p = cfg.growth_inheritance_probability
            if p >= 1.0:
                inherit_growth = True
            elif p > 0.0 and learning is not None:
                inherit_growth = learning.random() < p
        source = self.genome if inherit_growth else self.base
        child = Organism(
            oid=child_id,
            x=x,
            y=y,
            energy=child_energy,
            genome=(source.mutate(mutation, bias if cfg.nutrient_offspring_guidance else None)
                    if cfg.mutate_offspring else self.genome),
            generation=self.generation + 1,
            parent_id=self.oid,
            diet_signal=self.diet_signal if world.config.nutrient_mutation_strength > 0 else None,
            diet_energy=self.diet_energy if world.config.nutrient_mutation_strength > 0 else 0.0,
            learned_bias_applied=bias,
            data_learning_rate=(self.vary_learning_rate(self.data_learning_rate,
                                self.genome.mutation_scale, learning)
                                if learning is not None and world.config.mutate_offspring
                                else self.data_learning_rate),
            growth_inherited=inherit_growth,
        )
        return child
