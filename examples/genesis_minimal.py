# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from eyggnx.simulation import Simulation

sim = Simulation(seed=42, population=60)
for _ in range(500):
    snap = sim.tick()
    if snap.tick % 50 == 0:
        print(snap)
    if snap.population == 0:
        break
