# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Explicit, recordable configuration for GENESIS experiments.

Every constant of the model lives here, so a run record fully describes the
experiment. Fields are grouped by what they are:

* baseline parameters: tuning values that set the scale of an experiment;
* physics: costs every organism pays; genes cannot change them, only how much of
  them an organism incurs (for example a wider sensor raises basal metabolism);
* model assumptions: values that encode a modelling decision (for example "intake is
  independent of body" or "perception is noise-free"). Varying them is a change of
  model, and results must be reported as such.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import json
import math
from pathlib import Path
from typing import Any

from .validation import finite_range, non_negative_int, positive_finite

#: Default properties of external data nutrients by content category (see eyggnx.nutrients).
#: ``energy`` multiplies the information-based energy; ``digestibility`` multiplies the
#: release rate. Hypotheses: already-compressed containers are rich but slow to digest.
NUTRIENT_ATTRIBUTES: dict[str, dict[str, float]] = {
    "text": {"energy": 1.0, "digestibility": 1.0},
    "archive": {"energy": 1.25, "digestibility": 0.5},
    "image": {"energy": 1.0, "digestibility": 0.5},
    "media": {"energy": 1.0, "digestibility": 0.5},
    "document": {"energy": 1.0, "digestibility": 0.75},
    "executable": {"energy": 1.0, "digestibility": 0.75},
    "binary": {"energy": 1.0, "digestibility": 0.75},
}

#: Version of the simulation semantics. Bump it whenever the same seed and
#: configuration would produce a different trajectory.
SIMULATION_CONTRACT = 2


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
    # Physics: basal metabolism per tick = base + sensor_cost * sensor_range + longevity_cost * max_age
    base_metabolism: float = 0.10
    sensor_cost: float = 0.006
    longevity_cost: float = 0.00017
    movement_cost: float = 0.04  # energy per unit distance at speed 1; scales linearly with speed (drag)
    # Model assumptions
    bite_size: float = 3.0  # max energy taken from a patch per tick, independent of body
    contact_radius: float = 1.1  # distance at which a patch can be eaten
    perception_threshold: float = 0.2  # patches at or below this energy are invisible
    offspring_offset: float = 1.0  # distance at which a child is placed from its parent
    # Detritus: an organism dying of age leaves this fraction of its energy as a decaying,
    # non-renewable patch (0 = off). Starved organisms have no energy left to leave.
    detritus_fraction: float = 0.0
    detritus_decay: float = 0.05  # energy lost per tick by a detritus patch
    # External data nutrients (see eyggnx.nutrients): files directly in this directory become
    # non-renewable food patches. None = off. Only the bytes are read; nothing is executed.
    nutrient_dir: str | None = None
    nutrient_energy_per_byte: float = 0.01  # energy per byte of zlib-compressed data
    # Cap per patch (a whole file, or one chunk). 1,000,000 bytes read give at most about
    # 12,500 (archive), so the cap binds only near the read limit and file size still counts.
    nutrient_max_energy: float = 10_000.0
    # 0 = one patch per file; otherwise each file is split into chunks of this many bytes,
    # each its own patch with its own energy and content-derived position.
    nutrient_chunk_bytes: int = 0
    # A file whose energy exceeds this is split into the fewest equal chunks that bring each
    # near or below it, so large files can be eaten at several places; smaller files stay
    # whole. 0 = off. Hypothesis: 2,000 balanced large and small files (experiments/nutrients).
    nutrient_split_energy: float = 2_000.0
    # A nutrient exposes at most nutrient_release_capacity and refills it by this much per
    # tick from its finite supply (slow release, the default). 0 = all energy exposed at once.
    # Hypothesis: chosen near the regen/capacity of ordinary patches (experiments/nutrients).
    nutrient_release_rate: float = 0.4
    nutrient_release_capacity: float = 30.0
    # 0 = off; otherwise every this many ticks all external data nutrients are restored to
    # their loaded energy (eaten-up ones reappear at the same place): food that comes back.
    nutrient_regrow_interval: int = 0
    # 0 = off; otherwise an eaten-up external data nutrient comes back this many ticks later:
    # half of its energy at the same place, half far away (about the opposite side of the
    # world, offset by a hash of the position). Each new patch does the same when eaten up.
    # A half below nutrient_respawn_min_energy is not split: everything returns in place.
    # Cannot be combined with nutrient_regrow_interval.
    nutrient_respawn_delay: int = 0
    nutrient_respawn_min_energy: float = 10.0
    # Overrides of NUTRIENT_ATTRIBUTES, e.g. {"archive": {"energy": 1.5}}. Empty = defaults.
    nutrient_attributes: dict[str, dict[str, float]] = field(default_factory=dict)
    nutrient_max_files: int = 1000
    nutrient_max_bytes: int = 1_000_000  # bytes read from each file
    # Experiment control: False = fixed-genome control, children copy the parent genome exactly
    # (founders still receive their one initial mutation). Changes the trajectory by design.
    mutate_offspring: bool = True
    # Experimental evolution reward (off by default). It breaks invariants #1 (no explicit
    # fitness) and #5 (no free lunch) on purpose; see docs/architecture/INVARIANTS.md.
    # An organism "evolved" when its lifetime intake per tick at reproduction exceeds its
    # parent's at the child's birth. Its children are strong (basal metabolism and birth
    # mutation width scaled by the *_strong_* factors) and it has evolution_bonus_offspring
    # extra children, each paid from its own energy. Children of an organism that did not
    # evolve are weak (*_weak_* factors), and each birth fails with evolution_drop_probability
    # (the energy given to the child is lost). Founders have no parent and reproduce normally.
    evolution_reward: bool = False
    # Hypothesis: strength chosen in experiments/nutrients (stronger than first tried, 0.9/1.2/1.1/0.8/0.25).
    evolution_strong_metabolism: float = 0.8
    evolution_weak_metabolism: float = 1.2
    evolution_strong_mutation: float = 1.4
    evolution_weak_mutation: float = 0.6
    evolution_bonus_offspring: int = 1
    evolution_drop_probability: float = 0.4

    def __post_init__(self) -> None:
        positive_finite("width", self.width)
        positive_finite("height", self.height)
        non_negative_int("resource_patches", self.resource_patches)
        for name in ("patch_energy_range", "patch_capacity_range", "patch_regen_range",
                     "founder_energy_range"):
            lo, hi = getattr(self, name)
            finite_range(name, lo, hi)
        positive_finite("bite_size", self.bite_size)
        positive_finite("contact_radius", self.contact_radius)
        if not math.isfinite(self.perception_threshold) or self.perception_threshold < 0:
            raise ValueError(f"perception_threshold must be finite and >= 0, got {self.perception_threshold}")
        positive_finite("offspring_offset", self.offspring_offset)
        for name in ("base_metabolism", "sensor_cost", "longevity_cost", "movement_cost", "detritus_decay"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0, got {value}")
        if self.nutrient_dir is not None and not isinstance(self.nutrient_dir, str):
            raise TypeError("nutrient_dir must be a path string or None")
        positive_finite("nutrient_energy_per_byte", self.nutrient_energy_per_byte)
        positive_finite("nutrient_max_energy", self.nutrient_max_energy)
        non_negative_int("nutrient_max_files", self.nutrient_max_files)
        non_negative_int("nutrient_max_bytes", self.nutrient_max_bytes)
        non_negative_int("nutrient_chunk_bytes", self.nutrient_chunk_bytes)
        non_negative_int("nutrient_regrow_interval", self.nutrient_regrow_interval)
        non_negative_int("nutrient_respawn_delay", self.nutrient_respawn_delay)
        if self.nutrient_regrow_interval > 0 and self.nutrient_respawn_delay > 0:
            raise ValueError("nutrient_regrow_interval and nutrient_respawn_delay cannot both be set")
        positive_finite("nutrient_respawn_min_energy", self.nutrient_respawn_min_energy)
        split = self.nutrient_split_energy
        if isinstance(split, bool) or not isinstance(split, (int, float)) or not math.isfinite(split) or split < 0:
            raise ValueError(f"nutrient_split_energy must be finite and >= 0, got {split}")
        rate = self.nutrient_release_rate
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate < 0:
            raise ValueError(f"nutrient_release_rate must be finite and >= 0, got {rate}")
        positive_finite("nutrient_release_capacity", self.nutrient_release_capacity)
        if not isinstance(self.nutrient_attributes, dict):
            raise TypeError("nutrient_attributes must be a mapping of category to attributes")
        for category, attrs in self.nutrient_attributes.items():
            if category not in NUTRIENT_ATTRIBUTES:
                raise ValueError(f"unknown nutrient category {category!r}; known: {sorted(NUTRIENT_ATTRIBUTES)}")
            if not isinstance(attrs, dict) or not set(attrs) <= {"energy", "digestibility"}:
                raise ValueError(f"nutrient_attributes[{category!r}] may set only 'energy' and 'digestibility'")
            for name, value in attrs.items():
                positive_finite(f"nutrient_attributes[{category!r}][{name!r}]", value)
        if not (isinstance(self.detritus_fraction, (int, float)) and 0.0 <= self.detritus_fraction <= 1.0):
            raise ValueError(f"detritus_fraction must be in [0, 1], got {self.detritus_fraction}")
        if not isinstance(self.mutate_offspring, bool):
            raise TypeError("mutate_offspring must be a bool")
        if not isinstance(self.evolution_reward, bool):
            raise TypeError("evolution_reward must be a bool")
        for name in ("evolution_strong_metabolism", "evolution_weak_metabolism",
                     "evolution_strong_mutation", "evolution_weak_mutation"):
            positive_finite(name, getattr(self, name))
        non_negative_int("evolution_bonus_offspring", self.evolution_bonus_offspring)
        p = self.evolution_drop_probability
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0.0 <= p <= 1.0:
            raise ValueError(f"evolution_drop_probability must be in [0, 1], got {p}")

    def to_dict(self) -> dict[str, Any]:
        return {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(self).items()}

    def nutrient_attributes_for(self, category: str) -> dict[str, float]:
        """Default attributes of ``category`` with this config's overrides applied."""
        return {**NUTRIENT_ATTRIBUTES[category], **self.nutrient_attributes.get(category, {})}

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
