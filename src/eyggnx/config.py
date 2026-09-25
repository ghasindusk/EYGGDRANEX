# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Explicit, recordable configuration for GENESIS experiments.

Every constant that used to be hard-coded lives here with its original default, so
the default configuration reproduces simulation contract 1 bit for bit. Fields are
grouped by what they are:

* baseline parameters: tuning values that set the scale of an experiment;
* model assumptions: values that encode a modelling decision (for example "intake is
  independent of body" or "perception is free and noise-free"). Varying them is a
  change of model, and results must be reported as such.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
import math
from pathlib import Path
from typing import Any

from .validation import finite_range, non_negative_int, positive_finite

#: Version of the simulation semantics. Bump it whenever the same seed and
#: configuration would produce a different trajectory.
SIMULATION_CONTRACT = 1


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    # Baseline parameters: world
    width: float = 100.0
    height: float = 100.0
    resource_patches: int = 55
    patch_energy_range: tuple[float, float] = (18.0, 34.0)
    patch_capacity_range: tuple[float, float] = (26.0, 46.0)
    patch_regen_range: tuple[float, float] = (0.18, 0.55)
    # Baseline parameters: founders
    founder_energy_range: tuple[float, float] = (16.0, 26.0)
    # Model assumptions
    bite_size: float = 3.0  # max energy taken from a patch per tick, independent of body
    contact_radius: float = 1.1  # distance at which a patch can be eaten
    perception_threshold: float = 0.2  # patches at or below this energy are invisible
    wander_step_range: tuple[float, float] = (0.25, 1.0)  # random-walk step as a fraction of speed
    offspring_offset: float = 1.0  # distance at which a child is placed from its parent

    def __post_init__(self) -> None:
        positive_finite("width", self.width)
        positive_finite("height", self.height)
        non_negative_int("resource_patches", self.resource_patches)
        for name in ("patch_energy_range", "patch_capacity_range", "patch_regen_range",
                     "founder_energy_range", "wander_step_range"):
            lo, hi = getattr(self, name)
            finite_range(name, lo, hi)
        positive_finite("bite_size", self.bite_size)
        positive_finite("contact_radius", self.contact_radius)
        if not math.isfinite(self.perception_threshold) or self.perception_threshold < 0:
            raise ValueError(f"perception_threshold must be finite and >= 0, got {self.perception_threshold}")
        positive_finite("offspring_offset", self.offspring_offset)

    def to_dict(self) -> dict[str, Any]:
        return {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulationConfig":
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        values = {k: tuple(v) if isinstance(v, list) else v for k, v in data.items()}
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    """Everything needed to rerun an experiment: seed, founders, duration and config."""

    seed: int = 42
    population: int = 60
    steps: int = 200
    config: SimulationConfig = SimulationConfig()

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an int")
        non_negative_int("population", self.population)
        non_negative_int("steps", self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {"seed": self.seed, "population": self.population, "steps": self.steps,
                "config": self.config.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentSpec":
        """Accept both the flat record layout and the ``configs/*.json`` layout.

        The ``configs`` layout keeps world settings under ``"world"`` and any other
        config fields under ``"model"``.
        """
        allowed = {"seed", "population", "steps", "config", "world", "model", "$comment"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"unknown experiment keys: {sorted(unknown)}")
        config_data: dict[str, Any] = dict(data.get("config", {}))
        config_data.update(data.get("world", {}))
        config_data.update(data.get("model", {}))
        defaults = cls()
        return cls(
            seed=data.get("seed", defaults.seed),
            population=data.get("population", defaults.population),
            steps=data.get("steps", defaults.steps),
            config=SimulationConfig.from_dict(config_data),
        )


def load_experiment(path: str | Path) -> ExperimentSpec:
    with open(path, encoding="utf-8") as fh:
        return ExperimentSpec.from_dict(json.load(fh))
