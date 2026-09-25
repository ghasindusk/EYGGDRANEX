# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Record the golden full-state digests for the current platform.

Only add a digest for a platform that is not yet recorded. Overwriting an existing
digest means the simulation contract changed; do that deliberately and document it.

    python tests/record_golden.py            # print digests for this platform
    python tests/record_golden.py --write    # add missing digests for this platform
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys

from eyggnx.simulation import Simulation

GOLDEN = Path(__file__).with_name("golden_digests.json")


def platform_key() -> str:
    return f"{sys.platform}-{platform.machine().lower()}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="add missing digests for this platform")
    args = parser.parse_args()

    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    key = platform_key()
    for name, case in data["cases"].items():
        sim = Simulation(seed=case["seed"], population=case["population"])
        sim.run(case["ticks"])
        digest = sim.state_digest()
        known = case["digests"].get(key)
        status = "new" if known is None else ("match" if known == digest else "MISMATCH")
        print(f"{name} [{key}] {digest} ({status})")
        if args.write and known is None:
            case["digests"][key] = digest
    if args.write:
        GOLDEN.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
