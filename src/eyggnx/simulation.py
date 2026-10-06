# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from dataclasses import dataclass, fields, replace
import hashlib
import random
from statistics import fmean
from typing import Protocol

from .config import SimulationConfig
from .controller import DEFAULT_CONTROLLER, Controller
from .genome import Genome
from .nutrients import far_position, load_nutrients, respawned_patch
from .organism import Organism, basal_metabolism
from .validation import non_negative_int, positive_finite
from .world import ResourcePatch, World

#: Named random streams. Each mechanism draws only from its own stream, so adding or
#: changing one mechanism never shifts the random numbers another mechanism sees.
RNG_STREAMS = ("world", "founders", "movement", "placement", "mutation")


def derive_stream(seed: int, name: str) -> random.Random:
    """Independent, platform-stable random stream for ``(seed, name)``."""
    digest = hashlib.sha256(f"eyggnx:{seed}:{name}".encode()).digest()
    return random.Random(int.from_bytes(digest, "big"))


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
    """GENESIS simulation, simulation contract 2.

    Pass either ``width``/``height`` or a full ``config``; with a config, leave
    ``width`` and ``height`` at their defaults.

    A tick is order-neutral: every organism decides on the same world state, all moves
    and costs are applied, then contested patches are shared equally among the
    organisms eating from them. Organisms are kept in id order, and random draws are
    taken in id order from per-mechanism streams, so permuting ``organisms`` does not
    change the trajectory.
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
        self.rngs = {name: derive_stream(seed, name) for name in RNG_STREAMS}
        self.world = World(width, height, self.rngs["world"], config.resource_patches, config=config)
        nutrients, self.nutrient_manifest = load_nutrients(config)
        # Pristine copies for regrowth (nutrient_regrow_interval) and the live patches.
        self._nutrient_templates = [replace(p) for p in nutrients]
        self._nutrient_patches = nutrients
        for patch in nutrients:
            self.world.add_resource(patch)
        # Respawn (nutrient_respawn_delay): live nutrients with the total energy they started
        # with, and eaten-up ones waiting to come back as (due tick, patch, total energy).
        self._respawn_tracked: list[tuple[ResourcePatch, float]] = []
        self._respawn_pending: list[tuple[int, ResourcePatch, float]] = []
        if config.nutrient_respawn_delay > 0:
            self._respawn_tracked = [(p, p.energy + (p.reservoir or 0.0)) for p in nutrients]
        self.controller: Controller = DEFAULT_CONTROLLER
        self.tick_index = 0
        self.births_total = 0
        self.deaths_total = 0
        self.next_id = population
        #: Energy ingested during the last tick (observability only, not part of the state).
        self.eaten_last_tick = 0.0
        base = Genome()
        founders = self.rngs["founders"]
        self.organisms = []
        for i in range(population):
            x, y = founders.random() * width, founders.random() * height
            energy = founders.uniform(*config.founder_energy_range)
            self.organisms.append(Organism(oid=i, x=x, y=y, energy=energy, genome=base.mutate(founders)))
        #: Optional observer (see ``eyggnx.recorder``). Observers must not mutate state or
        #: draw from the simulation's random streams; the trajectory is identical with or without one.
        self.observer: SimulationObserver | None = None

    def tick(self) -> Snapshot:
        self.tick_index += 1
        world = self.world
        world.tick()
        interval = self.config.nutrient_regrow_interval
        if interval > 0 and self.tick_index % interval == 0:
            self._regrow_nutrients()
        if self.config.nutrient_respawn_delay > 0:
            self._respawn_nutrients()
        observer = self.observer
        self.organisms.sort(key=lambda o: o.oid)
        organisms = self.organisms

        # Decide on one shared world state, then act.
        movement = self.rngs["movement"]
        intents = [self.controller.decide(o, world, movement) for o in organisms]
        for organism, intent in zip(organisms, intents):
            organism.act(intent, world)
        self.eaten_last_tick = self._resolve_feeding(organisms)

        births: list[Organism] = []
        placement, mutation = self.rngs["placement"], self.rngs["mutation"]
        for organism in organisms:
            if organism.can_reproduce():
                child = organism.reproduce(self.next_id, world, placement, mutation)
                births.append(child)
                self.next_id += 1
                if observer is not None:
                    observer.on_birth(self.tick_index, child, organism)

        survivors: list[Organism] = []
        deaths = 0
        cfg = self.config
        for o in organisms:
            if o.alive:
                survivors.append(o)
                continue
            deaths += 1
            if observer is not None:
                observer.on_death(self.tick_index, o, "starvation" if o.energy <= 0.0 else "age")
            left = o.energy * cfg.detritus_fraction
            if left > 0.0:
                world.add_resource(ResourcePatch(o.x, o.y, left, left, -cfg.detritus_decay))
        self.organisms = survivors + births
        self.births_total += len(births)
        self.deaths_total += deaths
        if observer is not None:
            observer.on_tick(self)
        return self.snapshot()

    def _regrow_nutrients(self) -> None:
        """Restore every external data nutrient to its loaded state (a supply event).

        Patches still in the world are refilled in place; eaten-up ones that were removed
        are placed again at their original position, appended in manifest order.
        """
        present = {id(r) for r in self.world.resources}
        for i, template in enumerate(self._nutrient_templates):
            patch = self._nutrient_patches[i]
            patch.energy, patch.capacity = template.energy, template.capacity
            patch.regen, patch.reservoir = template.regen, template.reservoir
            if id(patch) not in present:
                self.world.add_resource(patch)

    def _respawn_nutrients(self) -> None:
        """Bring eaten-up nutrients back after ``nutrient_respawn_delay`` ticks (a supply event).

        A nutrient removed from the world since the last tick was eaten up. Half of the
        energy it started with is scheduled at the same place and half far away; a half
        below ``nutrient_respawn_min_energy`` is not split. Scheduled patches whose time
        has come are added in the order they were scheduled. No random numbers are drawn.
        """
        cfg, world = self.config, self.world
        present = {id(r) for r in world.resources}
        due = self.tick_index + cfg.nutrient_respawn_delay
        kept: list[tuple[ResourcePatch, float]] = []
        for patch, total in self._respawn_tracked:
            if id(patch) in present:
                kept.append((patch, total))
                continue
            half = total / 2.0
            if half < cfg.nutrient_respawn_min_energy:
                self._respawn_pending.append((due, respawned_patch(patch, patch.x, patch.y, total), total))
                continue
            fx, fy = far_position(patch.x, patch.y, total, world.width, world.height)
            self._respawn_pending.append((due, respawned_patch(patch, patch.x, patch.y, half), half))
            self._respawn_pending.append((due, respawned_patch(patch, fx, fy, half), half))
        waiting: list[tuple[int, ResourcePatch, float]] = []
        for entry in self._respawn_pending:
            if entry[0] <= self.tick_index:
                world.add_resource(entry[1])
                kept.append((entry[1], entry[2]))
            else:
                waiting.append(entry)
        self._respawn_tracked, self._respawn_pending = kept, waiting

    def _resolve_feeding(self, organisms: list[Organism]) -> float:
        """Each organism eats from its nearest patch in contact range; contested patches
        are shared equally, so no organism has priority. Returns the energy eaten."""
        world = self.world
        radius, bite = self.config.contact_radius, self.config.bite_size
        claims: dict[int, list[Organism]] = {}
        for o in organisms:
            found = world.perceive(o.x, o.y, radius)
            if found:
                _, index, _ = min(found, key=lambda t: (t[0], t[1]))
                claims.setdefault(index, []).append(o)
        eaten_total = 0.0
        for index in sorted(claims):
            patch, eaters = world.resources[index], claims[index]
            demand = bite * len(eaters)
            if patch.energy >= demand:
                share = bite
                patch.energy -= demand
                eaten_total += demand
            else:
                share = patch.energy / len(eaters)
                eaten_total += patch.energy
                patch.energy = 0.0
            for o in eaters:
                o.energy += share
        return eaten_total

    def run(self, steps: int) -> Snapshot:
        non_negative_int("steps", steps)
        snap = self.snapshot()
        for _ in range(steps):
            snap = self.tick()
            if not self.organisms:
                break
        return snap

    def state_digest(self) -> str:
        """SHA-256 over dynamic simulation state plus the RNG state.

        Floats are encoded with ``float.hex``. Equal digests mean bit-identical
        organisms, resources, counters and random stream for a given experiment
        configuration and simulation contract. Configuration/contract metadata are
        stored separately in the run record.
        """
        parts: list[tuple] = []
        for o in self.organisms:
            genes = tuple(float(getattr(o.genome, f.name)).hex() for f in fields(o.genome))
            parts.append(("O", o.oid, o.parent_id, o.generation, o.age,
                          o.x.hex(), o.y.hex(), o.energy.hex(), genes))
        for r in self.world.resources:
            part = ("R", r.x.hex(), r.y.hex(), r.energy.hex(), r.capacity.hex(), r.regen.hex())
            # Appended only when set, so digests of runs without reservoirs are unchanged.
            parts.append(part if r.reservoir is None else part + (r.reservoir.hex(),))
        if self.config.nutrient_respawn_delay > 0:
            # Only with respawn on, so digests of other runs are unchanged.
            parts.append(("RS", tuple(total.hex() for _, total in self._respawn_tracked), tuple(
                (due, p.x.hex(), p.y.hex(), p.energy.hex(), p.capacity.hex(), p.regen.hex(),
                 None if p.reservoir is None else p.reservoir.hex(), total.hex())
                for due, p, total in self._respawn_pending)))
        parts.append(("C", self.tick_index, self.births_total, self.deaths_total, self.next_id))
        for name in RNG_STREAMS:
            parts.append(("RNG", name, repr(self.rngs[name].getstate())))
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
            mean_metabolism=fmean(basal_metabolism(o.genome, self.config) for o in self.organisms),
        )
