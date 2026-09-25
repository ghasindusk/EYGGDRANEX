# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Observer-only experiment recorder.

Writes two JSON Lines files into a directory:

* ``timeseries.jsonl``: population metrics every ``every`` ticks, including per-gene
  mean, sd, min, max and the fraction of the population sitting at a clamp bound;
* ``events.jsonl``: one ``birth`` event per organism (founders at tick 0, with no
  parent) and one ``death`` event per organism, with its cause. Together they
  reconstruct the full lineage, including organisms that have died.

The recorder only reads simulation state and never touches the simulation RNG, so a
run is bit-identical with or without it. Rows are streamed to disk, not kept in memory.
"""

from __future__ import annotations

from dataclasses import asdict, fields
import json
import math
from pathlib import Path
from statistics import fmean, pstdev
from typing import IO, Any

from .genome import GENE_BOUNDS, Genome
from .organism import Organism
from .simulation import Simulation

#: A gene counts as "at a bound" when within this fraction of its range from the bound.
BOUND_TOLERANCE = 0.01


def gene_metrics(organisms: list[Organism]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    if not organisms:
        return out
    n = len(organisms)
    for f in fields(Genome):
        values = [float(getattr(o.genome, f.name)) for o in organisms]
        lo, hi = GENE_BOUNDS[f.name]
        eps = (hi - lo) * BOUND_TOLERANCE
        out[f.name] = {
            "mean": fmean(values),
            "sd": pstdev(values),
            "min": min(values),
            "max": max(values),
            "frac_at_lower": sum(v <= lo + eps for v in values) / n,
            "frac_at_upper": sum(v >= hi - eps for v in values) / n,
        }
    return out


def population_metrics(sim: Simulation) -> dict[str, Any]:
    organisms = sim.organisms
    return {
        "tick": sim.tick_index,
        "population": len(organisms),
        "births_total": sim.births_total,
        "deaths_total": sim.deaths_total,
        "max_generation_living": max((o.generation for o in organisms), default=None),
        "mean_energy": fmean(o.energy for o in organisms) if organisms else None,
        "resource_energy_total": math.fsum(r.energy for r in sim.world.resources),
        "genes": gene_metrics(organisms),
    }


def _organism_record(o: Organism) -> dict[str, Any]:
    return {"oid": o.oid, "parent_id": o.parent_id, "generation": o.generation,
            "x": o.x, "y": o.y, "energy": o.energy, "genome": asdict(o.genome)}


class Recorder:
    """Attach with ``Recorder(sim, directory)``; call ``close()`` (or use ``with``) when done."""

    def __init__(self, sim: Simulation, directory: str | Path, every: int = 1):
        if isinstance(every, bool) or not isinstance(every, int) or every < 1:
            raise ValueError(f"every must be an int >= 1, got {every!r}")
        if sim.observer is not None:
            raise ValueError("simulation already has an observer")
        self.every = every
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._timeseries: IO[str] = open(self.directory / "timeseries.jsonl", "w", encoding="utf-8")
        self._events: IO[str] = open(self.directory / "events.jsonl", "w", encoding="utf-8")
        self._sim = sim
        for o in sim.organisms:
            self._write_event({"event": "birth", "tick": sim.tick_index, **_organism_record(o)})
        self._write(self._timeseries, population_metrics(sim))
        sim.observer = self

    def on_birth(self, tick: int, child: Organism, parent: Organism) -> None:
        self._write_event({"event": "birth", "tick": tick, **_organism_record(child)})

    def on_death(self, tick: int, organism: Organism, cause: str) -> None:
        self._write_event({"event": "death", "tick": tick, "oid": organism.oid, "cause": cause,
                           "age": organism.age, "energy": organism.energy})

    def on_tick(self, sim: Simulation) -> None:
        if sim.tick_index % self.every == 0 or not sim.organisms:
            self._write(self._timeseries, population_metrics(sim))

    def close(self) -> None:
        if self._sim.observer is self:
            self._sim.observer = None
        self._timeseries.close()
        self._events.close()

    def __enter__(self) -> "Recorder":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _write_event(self, row: dict[str, Any]) -> None:
        self._write(self._events, row)

    @staticmethod
    def _write(fh: IO[str], row: dict[str, Any]) -> None:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
