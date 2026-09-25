# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import random
from statistics import fmean
from typing import Protocol

from .config import SimulationConfig
from .genome import Genome
from .organism import Organism
from .validation import non_negative_int, positive_finite
from .world import World


@dataclass(frozen=True, slots=True)
class Snapshot:
    tick: int
    population: int
    births: int
    deaths: int
    max_generation: int
    mean_speed: float
    mean_sensor_range: float
    mean_metabolism: float


class SimulationObserver(Protocol):
    def on_birth(self, tick: int, child: Organism, parent: Organism) -> None: ...

    def on_death(self, tick: int, organism: Organism, cause: str) -> None: ...

    def on_tick(self, sim: "Simulation") -> None: ...


class Simulation:
    """GENESIS simulation, simulation contract 1.

    Pass either ``width``/``height`` or a full ``config``; with a config, leave
    ``width`` and ``height`` at their defaults.
    """

    def __init__(
        self,
        seed: int = 42,
        population: int = 60,
        width: float = 100.0,
        height: float = 100.0,
        *,
        config: SimulationConfig | None = None,
    ):
        non_negative_int("population", population)
        if config is None:
            config = SimulationConfig(width=positive_finite("width", width), height=positive_finite("height", height))
        elif (width, height) != (100.0, 100.0):
            raise ValueError("pass width/height through config, not as separate arguments")
        width, height = config.width, config.height
        self.seed = seed
        self.config = config
        self.rng = random.Random(seed)
        self.world = World(width, height, self.rng, config.resource_patches, config=config)
        self.tick_index = 0
        self.births_total = 0
        self.deaths_total = 0
        self.next_id = population
        base = Genome()
        self.organisms = [
            Organism(
                oid=i,
                x=self.rng.random() * width,
                y=self.rng.random() * height,
                energy=self.rng.uniform(*config.founder_energy_range),
                genome=base.mutate(self.rng),
            )
            for i in range(population)
        ]
        #: Optional observer (see ``eyggnx.recorder``). Observers must not mutate state or
        #: draw from ``self.rng``; the trajectory is identical with or without one.
        self.observer: SimulationObserver | None = None

    def tick(self) -> Snapshot:
        self.tick_index += 1
        self.world.tick()
        observer = self.observer

        births: list[Organism] = []
        for organism in list(self.organisms):
            if organism.alive:
                organism.step(self.world, self.rng)
                if organism.can_reproduce():
                    child = organism.reproduce(self.next_id, self.rng, self.world)
                    births.append(child)
                    self.next_id += 1
                    if observer is not None:
                        observer.on_birth(self.tick_index, child, organism)

        before = len(self.organisms)
        if observer is not None:
            for o in self.organisms:
                if not o.alive:
                    observer.on_death(self.tick_index, o, "starvation" if o.energy <= 0.0 else "age")
        self.organisms = [o for o in self.organisms if o.alive]
        deaths = before - len(self.organisms)
        self.organisms.extend(births)
        self.births_total += len(births)
        self.deaths_total += deaths
        if observer is not None:
            observer.on_tick(self)
        return self.snapshot()

    def run(self, steps: int) -> Snapshot:
        non_negative_int("steps", steps)
        snap = self.snapshot()
        for _ in range(steps):
            snap = self.tick()
            if not self.organisms:
                break
        return snap

    def state_digest(self) -> str:
        """SHA-256 over the complete simulation state, including the RNG state.

        Floats are encoded with ``float.hex`` so the digest is exact: equal digests mean
        bit-identical organisms, resources, counters and random stream.
        """
        parts: list[tuple] = []
        for o in self.organisms:
            genes = tuple(float(getattr(o.genome, f.name)).hex() for f in fields(o.genome))
            parts.append(("O", o.oid, o.parent_id, o.generation, o.age,
                          o.x.hex(), o.y.hex(), o.energy.hex(), genes))
        for r in self.world.resources:
            parts.append(("R", r.x.hex(), r.y.hex(), r.energy.hex(), r.capacity.hex(), r.regen.hex()))
        parts.append(("C", self.tick_index, self.births_total, self.deaths_total, self.next_id))
        parts.append(("RNG", repr(self.rng.getstate())))
        return hashlib.sha256(repr(parts).encode()).hexdigest()

    def snapshot(self) -> Snapshot:
        if not self.organisms:
            return Snapshot(self.tick_index, 0, self.births_total, self.deaths_total, 0, 0.0, 0.0, 0.0)
        return Snapshot(
            tick=self.tick_index,
            population=len(self.organisms),
            births=self.births_total,
            deaths=self.deaths_total,
            max_generation=max(o.generation for o in self.organisms),
            mean_speed=fmean(o.genome.speed for o in self.organisms),
            mean_sensor_range=fmean(o.genome.sensor_range for o in self.organisms),
            mean_metabolism=fmean(o.genome.metabolism for o in self.organisms),
        )
