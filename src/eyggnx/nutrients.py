# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""External data nutrients: files in a directory become food in the world.

Every regular file directly inside ``SimulationConfig.nutrient_dir`` becomes one
non-renewable substrate patch. The data is only read as bytes, never executed or
interpreted, and nothing is fetched from the network.

* Which files: regular files directly in the directory, by name. Subdirectories and
  symbolic links are ignored. At most ``nutrient_max_files`` files and the first
  ``nutrient_max_bytes`` bytes of each are read.
* Patches: one per file, or, with ``nutrient_chunk_bytes > 0``, one per chunk of that
  many bytes, so a large file is spread over the world instead of sitting in one spot.
* Energy: proportional to the information in the bytes, measured as the zlib
  compressed size, ``min(nutrient_max_energy, compressed_bytes * nutrient_energy_per_byte)``
  per patch. File names, extensions and types play no role (no kinds).
* Release: by default (``nutrient_release_rate > 0``) the energy sits in a finite
  reservoir, at most ``nutrient_release_capacity`` is exposed, and the reservoir refills
  it at that rate per tick, like a slowly decomposing substrate. With
  ``nutrient_release_rate = 0`` all of it is exposed at once. The total energy is the
  same either way.
* Position: derived from the SHA-256 of the bytes (of the chunk), so loading nutrients
  draws no random numbers and shifts no other mechanism.
* Reproducibility: the manifest (name, size, bytes read, SHA-256, energy) and its digest
  are stored with the simulation and in the run record.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
import zlib

from .config import SimulationConfig
from .world import ResourcePatch


def nutrient_energy(data: bytes, config: SimulationConfig) -> float:
    """Energy of a nutrient: its compressed size (information content), capped."""
    if not data:
        return 0.0
    compressed = len(zlib.compress(data, 9))
    return min(config.nutrient_max_energy, compressed * config.nutrient_energy_per_byte)


def nutrient_position(digest: bytes, width: float, height: float) -> tuple[float, float]:
    x = int.from_bytes(digest[0:8], "big") / 2.0**64 * width
    y = int.from_bytes(digest[8:16], "big") / 2.0**64 * height
    return x, y


def nutrient_patch(x: float, y: float, energy: float, config: SimulationConfig) -> ResourcePatch:
    """A finite patch holding ``energy``, exposed at once or released slowly."""
    rate = config.nutrient_release_rate
    if rate <= 0.0:
        return ResourcePatch(x, y, energy, energy, 0.0)
    exposed = min(energy, config.nutrient_release_capacity)
    return ResourcePatch(x, y, exposed, config.nutrient_release_capacity, rate, energy - exposed)


def chunks(data: bytes, size: int) -> list[bytes]:
    if size <= 0 or len(data) <= size:
        return [data]
    return [data[i:i + size] for i in range(0, len(data), size)]


def load_nutrients(config: SimulationConfig) -> tuple[list[ResourcePatch], dict[str, Any]]:
    """Read ``config.nutrient_dir`` and return its nutrient patches and manifest."""
    directory = Path(config.nutrient_dir) if config.nutrient_dir is not None else None
    if directory is None:
        return [], {"directory": None, "files": [], "digest": None}
    if not directory.is_dir():
        raise ValueError(f"nutrient_dir is not a directory: {directory}")
    with os.scandir(directory) as it:
        entries = sorted((e for e in it if e.is_file(follow_symlinks=False) and not e.is_symlink()),
                         key=lambda e: e.name)
    patches: list[ResourcePatch] = []
    files: list[dict[str, Any]] = []
    for entry in entries[: config.nutrient_max_files]:
        with open(entry.path, "rb") as fh:
            data = fh.read(config.nutrient_max_bytes)
        energy = 0.0
        pieces = chunks(data, config.nutrient_chunk_bytes)
        for piece in pieces:
            piece_energy = nutrient_energy(piece, config)
            if piece_energy > 0.0:
                x, y = nutrient_position(hashlib.sha256(piece).digest(), config.width, config.height)
                patches.append(nutrient_patch(x, y, piece_energy, config))
                energy += piece_energy
        record = {"name": entry.name, "size": entry.stat(follow_symlinks=False).st_size,
                  "bytes_read": len(data), "sha256": hashlib.sha256(data).hexdigest(), "energy": energy}
        if config.nutrient_chunk_bytes > 0:
            record["chunks"] = len(pieces) if data else 0
        files.append(record)
    manifest_digest = hashlib.sha256(
        json.dumps([[f["name"], f["bytes_read"], f["sha256"]] for f in files]).encode()).hexdigest()
    return patches, {"directory": str(directory), "files": files, "skipped_over_limit":
                     max(0, len(entries) - config.nutrient_max_files), "digest": manifest_digest}
