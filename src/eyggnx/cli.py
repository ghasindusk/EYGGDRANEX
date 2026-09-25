# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json

from .config import ExperimentSpec, load_experiment
from .run_record import build_run_record
from .simulation import Simulation


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the EYGGDRANEX (EYGGNX) GENESIS simulation.")
    p.add_argument("--config", metavar="PATH",
                   help="experiment JSON (e.g. configs/default_genesis.json); flags below override it")
    p.add_argument("--steps", type=_non_negative_int, default=None, help="ticks to run (default 200)")
    p.add_argument("--seed", type=int, default=None, help="random seed (default 42)")
    p.add_argument("--population", type=_non_negative_int, default=None, help="founders (default 60)")
    p.add_argument("--format", choices=("snapshot", "record"), default="snapshot",
                   help="'snapshot' prints the final Snapshot (legacy output); "
                        "'record' prints a versioned run record with seed, config and provenance")
    return p


def resolve_spec(args: argparse.Namespace) -> ExperimentSpec:
    spec = load_experiment(args.config) if args.config else ExperimentSpec()
    overrides = {k: getattr(args, k) for k in ("steps", "seed", "population") if getattr(args, k) is not None}
    return replace(spec, **overrides)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        spec = resolve_spec(args)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    sim = Simulation(seed=spec.seed, population=spec.population, config=spec.config)
    snap = sim.run(spec.steps)
    output = asdict(snap) if args.format == "snapshot" else build_run_record(spec, sim, snap)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
