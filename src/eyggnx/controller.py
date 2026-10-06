# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Behaviour controllers: perception in, movement intent out.

A controller only reads the world and the organism and returns an ``Intent``; it never
changes state. ``Simulation`` applies all intents and resolves contests afterwards, so
no organism acts on a world another organism has already changed in the same tick.
The default controller's parameters are genes, so foraging behaviour is heritable.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .organism import Organism
    from .world import World


@dataclass(frozen=True, slots=True)
class Intent:
    dx: float
    dy: float


class Controller(Protocol):
    def decide(self, organism: "Organism", world: "World", rng: random.Random) -> Intent: ...


class ForagingController:
    """Heritable foraging policy.

    Among perceivable patches, approach the one maximising
    ``energy / (1 + distance_aversion * distance)`` (high aversion approaches the nearest
    patch, low aversion travels to the richest). Ties go to the nearer, then the earlier
    patch. With nothing in view, take a random step of ``wander_step * speed``.
    """

    def decide(self, organism: "Organism", world: "World", rng: random.Random) -> Intent:
        g = organism.genome
        best = None
        best_key = None
        for d, i, patch in world.perceive(organism.x, organism.y, g.sensor_range):
            key = (-patch.energy / (1.0 + g.distance_aversion * d), d, i)
            if best_key is None or key < best_key:
                best, best_key = (d, patch), key
        if best is None:
            angle = rng.random() * math.tau
            step = g.speed * g.wander_step
            return Intent(math.cos(angle) * step, math.sin(angle) * step)
        d, patch = best
        if d <= 1e-12:
            return Intent(0.0, 0.0)
        dx, dy = world.delta(organism.x, organism.y, patch.x, patch.y)
        step = min(g.speed, d)
        return Intent(dx / d * step, dy / d * step)


DEFAULT_CONTROLLER = ForagingController()
