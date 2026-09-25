# EYGGDRANEX v0.1.1-alpha — GENESIS Review Integration

This alpha integrates the ACCEPT-NOW findings from independent Astra and Opus audits while keeping **simulation contract 1** as the active model contract.

## Highlights

- explicit `SimulationConfig` and reproducible `ExperimentSpec`
- versioned run records with provenance
- observer-only timeseries and lineage recorder
- neutral-drift and fixed-genome controls
- full dynamic-state + RNG digest
- Linux/Windows platform-specific golden digests
- stronger invariant and lifecycle characterization tests
- input validation and package wheel smoke testing
- removal of the old one-shot v0.1.0 publishing workflow

## Compatibility note

The model scheduler and mutation operator are unchanged. Initial resource values above capacity are normalized during construction in v0.1.1-alpha; v0.1.0-alpha clipped the same excess at the first regeneration tick, so trajectories are preserved from the first simulation tick onward.

## Deferred to contract 2

Scheduler semantics, named RNG streams, float `max_age`, mutation-operator redesign, and cross-OS bit-identical trajectories remain explicit future decisions.
