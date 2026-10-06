# Copyright (c) 2026 SHAR-K
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Experimental evolution reward (SimulationConfig.evolution_reward)."""

import unittest

from eyggnx.config import SimulationConfig
from eyggnx.genome import Genome
from eyggnx.organism import Organism
from eyggnx.simulation import Simulation


def ready_parent(oid=0, parent_rate=None, intake=100.0, age=10):
    """An organism able to reproduce, with intake per tick ``intake / age``."""
    return Organism(oid=oid, x=50.0, y=50.0, energy=100.0, genome=Genome(), age=age,
                    intake=intake, parent_intake_rate=parent_rate)


class EvolutionRewardTests(unittest.TestCase):
    def sim(self, organisms, **kw):
        cfg = SimulationConfig(resource_patches=0, evolution_reward=True, **kw)
        sim = Simulation(seed=3, population=0, config=cfg)
        sim.organisms = organisms
        sim.next_id = 100
        return sim

    def test_evolved_parent_has_an_extra_strong_child_paid_from_its_energy(self):
        parent = ready_parent(parent_rate=1.0)  # 10 per tick > 1
        sim = self.sim([parent])
        sim.tick()
        children = [o for o in sim.organisms if o.parent_id == 0]
        self.assertEqual(len(children), 2)
        self.assertEqual(sim.evolved_births, 1)
        for c in children:
            self.assertEqual(c.metabolism_factor, sim.config.evolution_strong_metabolism)
            self.assertAlmostEqual(c.parent_intake_rate, 100.0 / 11)
        f = Genome().offspring_fraction
        # Children get f*E and f*(1-f)*E; with the parent's (1-f)^2*E the total is E = first / f.
        self.assertAlmostEqual(sum(c.energy for c in children) + parent.energy,
                               children[0].energy / f, places=9)
        self.assertLess(children[1].energy, children[0].energy)  # paid in turn from what was left

    def test_parent_that_did_not_evolve_has_weak_children_or_none(self):
        parents = [ready_parent(oid=i, parent_rate=1e9) for i in range(40)]
        sim = self.sim(parents)
        sim.tick()
        children = [o for o in sim.organisms if o.parent_id is not None]
        self.assertEqual(sim.unevolved_births, 40)
        self.assertEqual(len(children) + sim.failed_births, 40)
        self.assertGreater(sim.failed_births, 0)
        self.assertGreater(len(children), 0)
        for c in children:
            self.assertEqual(c.metabolism_factor, sim.config.evolution_weak_metabolism)
        # A failed birth still costs the parent its offspring share.
        for p in parents:
            self.assertLess(p.energy, 100.0 * (1 - Genome().offspring_fraction) + 1e-9)

    def test_founders_reproduce_normally(self):
        sim = self.sim([ready_parent()])
        sim.tick()
        (child,) = [o for o in sim.organisms if o.parent_id == 0]
        self.assertEqual(child.metabolism_factor, 1.0)
        self.assertEqual((sim.evolved_births, sim.unevolved_births), (0, 0))

    def test_metabolism_factor_scales_basal_metabolism(self):
        cfg = SimulationConfig(resource_patches=0)
        a = Simulation(seed=1, population=0, config=cfg)
        b = Simulation(seed=1, population=0, config=cfg)
        a.organisms = [Organism(oid=0, x=1.0, y=1.0, energy=10.0, genome=Genome(speed=0.15, wander_step=0.05))]
        b.organisms = [Organism(oid=0, x=1.0, y=1.0, energy=10.0, genome=Genome(speed=0.15, wander_step=0.05),
                                metabolism_factor=0.5)]
        a.tick()
        b.tick()
        self.assertGreater(b.organisms[0].energy, a.organisms[0].energy)

    def test_mutation_scale_factor_widens_mutation(self):
        import random
        base = Genome()
        narrow = [base.mutate(random.Random(i), 0.5).speed for i in range(200)]
        wide = [base.mutate(random.Random(i), 2.0).speed for i in range(200)]
        spread = lambda vs: sum(abs(v - base.speed) for v in vs)
        self.assertGreater(spread(wide), spread(narrow))
        self.assertEqual(base.mutate(random.Random(1)), base.mutate(random.Random(1), 1.0))

    def test_off_by_default_and_deterministic(self):
        self.assertFalse(SimulationConfig().evolution_reward)
        off = Simulation(seed=7, population=40)
        self.assertIsNone(off._evolution_rng)
        cfg = SimulationConfig(evolution_reward=True)
        a, b = Simulation(seed=7, population=40, config=cfg), Simulation(seed=7, population=40, config=cfg)
        a.run(600)
        b.run(600)
        self.assertEqual(a.state_digest(), b.state_digest())
        self.assertGreater(a.evolved_births + a.unevolved_births, 0)

    def test_reward_does_not_shift_the_other_streams_before_it_acts(self):
        """Until the first organism with a parent reproduces, trajectories match the reward-off run."""
        on = Simulation(seed=7, population=40, config=SimulationConfig(evolution_reward=True))
        off = Simulation(seed=7, population=40)
        while on.evolved_births + on.unevolved_births == 0 and on.tick_index < 2000 and on.organisms:
            before = [(o.oid, o.x, o.y, o.energy) for o in off.organisms]
            self.assertEqual(before, [(o.oid, o.x, o.y, o.energy) for o in on.organisms])
            on.tick()
            off.tick()

    def test_invalid_settings_rejected(self):
        for kw in ({"evolution_reward": 1}, {"evolution_drop_probability": 1.5},
                   {"evolution_bonus_offspring": -1}, {"evolution_strong_metabolism": 0.0}):
            with self.assertRaises((TypeError, ValueError)):
                SimulationConfig(**kw)


if __name__ == "__main__":
    unittest.main()
