# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Boundary checks for public experiment inputs.

Validation never draws random numbers or touches simulation state, so valid inputs
produce exactly the same trajectories as before these checks existed.
"""

from __future__ import annotations

import math


def non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")
    return value


def positive_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and > 0, got {value}")
    return float(value)


def finite_range(name: str, lo: object, hi: object, *, allow_negative: bool = False) -> None:
    for bound in (lo, hi):
        if isinstance(bound, bool) or not isinstance(bound, (int, float)) or not math.isfinite(bound):
            raise ValueError(f"{name} bounds must be finite numbers, got ({lo}, {hi})")
    if lo > hi:
        raise ValueError(f"{name} lower bound exceeds upper bound: ({lo}, {hi})")
    if not allow_negative and lo < 0:
        raise ValueError(f"{name} must not be negative: ({lo}, {hi})")
