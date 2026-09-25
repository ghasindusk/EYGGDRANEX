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

from .genome import Genome
from .organism import Organism
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


class Simulation:
    def __init__(self, seed: int = 42, population: int = 60, width: float = 100.0, height: float = 100.0):
        self.rng = random.Random(seed)
        self.world = World(width, height, self.rng)
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
                energy=self.rng.uniform(16.0, 26.0),
                genome=base.mutate(self.rng),
            )
            for i in range(population)
        ]

    def tick(self) -> Snapshot:
        self.tick_index += 1
        self.world.tick()

        births: list[Organism] = []
        for organism in list(self.organisms):
            if organism.alive:
                organism.step(self.world, self.rng)
                if organism.can_reproduce():
                    births.append(organism.reproduce(self.next_id, self.rng, self.world))
                    self.next_id += 1

        before = len(self.organisms)
        self.organisms = [o for o in self.organisms if o.alive]
        deaths = before - len(self.organisms)
        self.organisms.extend(births)
        self.births_total += len(births)
        self.deaths_total += deaths
        return self.snapshot()

    def run(self, steps: int) -> Snapshot:
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
