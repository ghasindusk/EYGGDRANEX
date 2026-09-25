# Changelog

## [0.1.1-alpha] — 2026-09-25 — GENESIS review integration

Approved ACCEPT-NOW items from the independent Astra/Opus audits
(see the AI handoff pack's `03_AFTER_AUDIT/REVIEW_MATRIX.md`). **Simulation contract 1 remains the active contract.**
For valid default runs, trajectories are preserved from the first simulation tick onward. Initial resource values that
spawn above capacity are normalized at construction time in v0.1.1-alpha; v0.1.0-alpha performed the same clipping at
the first world-regeneration tick.

### Added
- `SimulationConfig` holding every former hard-coded constant (defaults unchanged), `ExperimentSpec`, `SIMULATION_CONTRACT = 1` and `GENE_BOUNDS`.
- CLI: `--config PATH` (loads `configs/default_genesis.json`), `--format record` (versioned run record with seed, config, gene bounds, provenance and dynamic-state digest), `--record-dir` / `--record-every`.
- `Simulation.state_digest()`: exact SHA-256 over dynamic organism/resource/counter state plus RNG state. Experiment configuration and simulation contract are stored separately in the run record.
- `eyggnx.recorder.Recorder`: observer-only JSONL time series (per-gene mean/sd/min/max, fraction at bounds) and lineage events with death causes.
- Controls: `python -m eyggnx.controls` (mutation-only neutral drift) and `SimulationConfig(mutate_offspring=False)` (fixed-genome control).
- Tests: invariants, torus geometry, energy ledger, lifecycle characterization (including list-order priority), per-platform golden digest, validation, config and recorder tests. CI builds and smoke-tests the wheel.

### Changed
- Invalid inputs (negative steps/population, non-finite or non-positive dimensions) are rejected up front; the CLI exits with code 2.
- Initial resource energy is clamped to patch capacity during construction; from the first world tick onward this matches the previous trajectory because v0.1.0-alpha clipped the same excess during regeneration.
- `nearest_resource` scans once (same result, ~8% faster).
- The reference-seed test no longer requires survival; extinction is a valid outcome.

### Removed
- `publish-genesis.yml` one-shot release workflow (its release exists; the workflow was not gated on tests or pinned to a commit). The `v0.1.0-alpha` tag and release remain untouched.

### Documentation
- Exact tick semantics, list-order priority, mutation math, known directional biases, adaptation-channel rules, controls and a revised genesis-001 protocol.
- Clarified the scope of `state_digest()` and the tick-0 resource-normalization nuance.

## [0.1.0-alpha] — 2026-09-25

### Added
- EYGGDRANEX project identity and GENESIS architecture
- Minimal digital organism model
- Mutable heritable genome
- Energy metabolism and resource-seeking behavior
- Reproduction, mutation, aging and death
- Toroidal 2D world with renewable resources
- Deterministic seeded experiments
- Baseline tests and GitHub contribution templates
- Research protocol for distinguishing emergence from scripted behavior

### Branding refinement — 2026-09-25

- Official Japanese reading changed to **エグドラネクス**.
- Official technical short form established as **EYGGNX**.
- Python distribution / package / primary CLI moved to `eyggnx`; `eyggdranex` remains a CLI alias.
- Trademark/naming clearance updated to account for existing `エグドラシル`, `ヌ・エグドラ`, and YGGDRASIL software/game usage.
- Added `BRAND_IDENTITY.md`.
