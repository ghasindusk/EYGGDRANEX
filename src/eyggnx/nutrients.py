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
* Category: read from the content's leading bytes (format signatures such as ``PK``
  for zip or ``%PDF-``), never from the file name or extension, so renaming a file
  changes nothing. Valid UTF-8 without NUL bytes is ``text``; anything unrecognised is
  ``binary``. Archives are not unpacked. The category selects two substrate properties
  (``SimulationConfig.nutrient_attributes_for``): an ``energy`` factor and a
  ``digestibility`` factor. Organisms never see the category, only the resulting patch.
* Energy: proportional to the information in the bytes, measured as the zlib
  compressed size, ``min(nutrient_max_energy, energy_factor * compressed_bytes *
  nutrient_energy_per_byte)`` per patch. Padding or repetition adds little energy.
* Release: by default (``nutrient_release_rate > 0``) the energy sits in a finite
  reservoir, at most ``nutrient_release_capacity`` is exposed, and the reservoir refills
  it at ``nutrient_release_rate * digestibility`` per tick, like a slowly decomposing
  substrate. With
  ``nutrient_release_rate = 0`` all of it is exposed at once. The total energy is the
  same either way.
* Position: derived from the SHA-256 of the bytes (of the chunk), so loading nutrients
  draws no random numbers and shifts no other mechanism.
* Reproducibility: the manifest (name, size, bytes read, SHA-256, category, factors,
  energy) and its digest are stored with the simulation and in the run record.
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


#: Leading-byte signatures ``(offset, bytes, category)``, checked in order.
SIGNATURES: tuple[tuple[int, bytes, str], ...] = (
    (0, b"PK\x03\x04", "archive"), (0, b"PK\x05\x06", "archive"), (0, b"PK\x07\x08", "archive"),
    (0, b"\x1f\x8b", "archive"), (0, b"7z\xbc\xaf\x27\x1c", "archive"), (0, b"Rar!\x1a\x07", "archive"),
    (0, b"BZh", "archive"), (0, b"\xfd7zXZ\x00", "archive"), (0, b"\x28\xb5\x2f\xfd", "archive"),
    (0, b"\x89PNG\r\n\x1a\n", "image"), (0, b"\xff\xd8\xff", "image"), (0, b"GIF87a", "image"),
    (0, b"GIF89a", "image"), (8, b"WEBP", "image"), (0, b"II*\x00", "image"), (0, b"MM\x00*", "image"),
    (8, b"WAVE", "media"), (8, b"AVI ", "media"), (0, b"ID3", "media"), (0, b"OggS", "media"),
    (0, b"fLaC", "media"), (4, b"ftyp", "media"), (0, b"\x1a\x45\xdf\xa3", "media"),
    (0, b"%PDF-", "document"),
    (0, b"\x7fELF", "executable"), (0, b"MZ", "executable"), (0, b"\x00asm", "executable"),
    (0, b"\xfe\xed\xfa\xce", "executable"), (0, b"\xfe\xed\xfa\xcf", "executable"),
    (0, b"\xce\xfa\xed\xfe", "executable"), (0, b"\xcf\xfa\xed\xfe", "executable"),
)


def nutrient_category(data: bytes) -> str:
    """Content category from the leading bytes; the file name plays no role."""
    for offset, magic, category in SIGNATURES:
        if data[offset:offset + len(magic)] == magic:
            return category
    if b"\x00" in data:
        return "binary"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        # A multi-byte character cut off by nutrient_max_bytes is still text.
        if not (exc.reason == "unexpected end of data" and exc.start >= len(data) - 3):
            return "binary"
    return "text"


def nutrient_energy(data: bytes, config: SimulationConfig, factor: float = 1.0) -> float:
    """Energy of a nutrient: its compressed size (information content) times ``factor``, capped."""
    if not data:
        return 0.0
    compressed = len(zlib.compress(data, 9))
    return min(config.nutrient_max_energy, factor * compressed * config.nutrient_energy_per_byte)


def nutrient_position(digest: bytes, width: float, height: float) -> tuple[float, float]:
    x = int.from_bytes(digest[0:8], "big") / 2.0**64 * width
    y = int.from_bytes(digest[8:16], "big") / 2.0**64 * height
    return x, y


def nutrient_patch(x: float, y: float, energy: float, config: SimulationConfig,
                   digestibility: float = 1.0) -> ResourcePatch:
    """A finite patch holding ``energy``, exposed at once or released slowly."""
    rate = config.nutrient_release_rate * digestibility
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
        category = nutrient_category(data)
        attrs = config.nutrient_attributes_for(category)
        energy = 0.0
        pieces = chunks(data, config.nutrient_chunk_bytes)
        for piece in pieces:
            piece_energy = nutrient_energy(piece, config, attrs["energy"])
            if piece_energy > 0.0:
                x, y = nutrient_position(hashlib.sha256(piece).digest(), config.width, config.height)
                patches.append(nutrient_patch(x, y, piece_energy, config, attrs["digestibility"]))
                energy += piece_energy
        record = {"name": entry.name, "size": entry.stat(follow_symlinks=False).st_size,
                  "bytes_read": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                  "category": category, "energy_factor": attrs["energy"],
                  "digestibility": attrs["digestibility"], "energy": energy}
        if config.nutrient_chunk_bytes > 0:
            record["chunks"] = len(pieces) if data else 0
        files.append(record)
    manifest_digest = hashlib.sha256(
        json.dumps([[f["name"], f["bytes_read"], f["sha256"]] for f in files]).encode()).hexdigest()
    return patches, {"directory": str(directory), "files": files, "skipped_over_limit":
                     max(0, len(entries) - config.nutrient_max_files), "digest": manifest_digest}
