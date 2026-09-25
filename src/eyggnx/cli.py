# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from .simulation import Simulation


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the EYGGDRANEX (EYGGNX) GENESIS simulation.")
    p.add_argument("--steps", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--population", type=int, default=60)
    return p


def main() -> None:
    args = build_parser().parse_args()
    sim = Simulation(seed=args.seed, population=args.population)
    snap = sim.run(args.steps)
    print(json.dumps(asdict(snap), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
