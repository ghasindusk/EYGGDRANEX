# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Versioned run record: the result of an experiment plus what is needed to rerun it."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import os
import platform
from typing import Any

from . import __version__
from .config import SIMULATION_CONTRACT, ExperimentSpec
from .genome import GENE_BOUNDS
from .simulation import Simulation, Snapshot

RECORD_FORMAT = "eyggnx.run-record"
RECORD_FORMAT_VERSION = 1


def run_metadata() -> dict[str, Any]:
    """Provenance that does not depend on the run. Reads no simulation state."""
    return {
        "package": "eyggnx",
        "package_version": __version__,
        "simulation_contract": SIMULATION_CONTRACT,
        # The commit is supplied by the runner (for example CI) instead of calling git.
        "commit": os.environ.get("EYGGNX_COMMIT"),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": f"{platform.system()}-{platform.machine()}",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def build_run_record(spec: ExperimentSpec, sim: Simulation, snap: Snapshot) -> dict[str, Any]:
    return {
        "format": RECORD_FORMAT,
        "format_version": RECORD_FORMAT_VERSION,
        "meta": run_metadata(),
        "experiment": spec.to_dict(),
        "gene_bounds": {k: list(v) for k, v in GENE_BOUNDS.items()},
        "result": {
            "requested_steps": spec.steps,
            "completed_ticks": sim.tick_index,
            "stop_reason": "extinct" if not sim.organisms else "completed",
            "snapshot": asdict(snap),
            "state_digest": sim.state_digest(),
        },
    }
