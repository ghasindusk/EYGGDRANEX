# Changelog

## [Unreleased] — GENESIS review integration

Approved ACCEPT-NOW items from the independent Astra/Opus audits
(see the AI handoff pack's `03_AFTER_AUDIT/REVIEW_MATRIX.md`). **Simulation contract 1 is
unchanged**: every valid seed produces a bit-identical trajectory to v0.1.0-alpha.

### Added
- `SimulationConfig` holding every former hard-coded constant (defaults unchanged), `ExperimentSpec`, `SIMULATION_CONTRACT = 1` and `GENE_BOUNDS`.
- CLI: `--config PATH` (loads `configs/default_genesis.json`), `--format record` (versioned run record with seed, config, gene bounds, provenance and full-state digest), `--record-dir` / `--record-every`.
- `Simulation.state_digest()`: exact full-state SHA-256 including RNG state.
- `eyggnx.recorder.Recorder`: observer-only JSONL time series (per-gene mean/sd/min/max, fraction at bounds) and lineage events with death causes.
- Controls: `python -m eyggnx.controls` (mutation-only neutral drift) and `SimulationConfig(mutate_offspring=False)` (fixed-genome control).
- Tests: invariants, torus geometry, energy ledger, lifecycle characterization (including list-order priority), per-platform golden digest, validation, config and recorder tests. CI builds and smoke-tests the wheel.

### Changed
- Invalid inputs (negative steps/population, non-finite or non-positive dimensions) are rejected up front; the CLI exits with code 2.
- Initial resource energy is clamped to patch capacity (trajectories unchanged, because the first regen tick already clipped it).
- `nearest_resource` scans once (same result, ~8% faster).
- The reference-seed test no longer requires survival; extinction is a valid outcome.

### Removed
- `publish-genesis.yml` one-shot release workflow (its release exists; the workflow was not gated on tests or pinned to a commit). The `v0.1.0-alpha` tag and release are untouched.

### Documentation
- Exact tick semantics, list-order priority, mutation math, known directional biases, adaptation-channel rules, controls and a revised genesis-001 protocol. Narrowed "自己生成" in the repository description text.

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
