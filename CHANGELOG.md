# Changelog

## [Unreleased]

**Simulation contract 2.** Every seeded trajectory changes. Contract 1 remains reproducible from tag
`v0.1.1-alpha`. Golden digests were re-recorded for contract 2 on Linux (`linux-x86_64`), Windows (`win32-amd64`) and macOS (`darwin-arm64`); the three platforms differ from each other, and each is checked in CI.

### Changed (simulation contract 2)
- Order-neutral tick: every organism decides on the same world state (`Controller.decide` returns an `Intent`), all moves and costs are applied, then contested patches are shared equally. Permuting the organism list no longer changes the trajectory; list order gives no feeding priority.
- Named RNG streams (`world`, `founders`, `movement`, `placement`, `mutation`), each derived from `(seed, name)` with SHA-256. Changing one mechanism no longer shifts the random numbers of the others.
- Costs instead of costless genes: `metabolism` and `movement_cost` are no longer genes but physics in `SimulationConfig` (`base_metabolism`, `sensor_cost`, `longevity_cost`, `movement_cost`). Basal metabolism grows with `sensor_range` and `max_age`; movement cost scales with `speed`. Defaults keep the default genome's metabolism at about 0.22.
- Log-normal mutation with reflecting bounds in log space replaces `v × (1 + N(0, s))` with clamping: no downward neutral drift and no pile-up at the bounds.
- `max_age` is continuous instead of integer-rounded.
- Heritable foraging controller: new genes `distance_aversion` (patch score `energy / (1 + aversion × distance)`) and `wander_step` (random-walk step as a fraction of speed) replace the fixed nearest-patch rule and `wander_step_range`.
- `Snapshot.mean_metabolism` reports the mean basal metabolism computed from genes and physics.
- Gene bound occupancy (`frac_at_lower` / `frac_at_upper`) is measured within 1% of each gene's log-range.

### Added
- Gene registry `eyggnx.genome.GENES` (name, default, bounds, description); `Genome` fields are checked against it.
- `eyggnx.controller`: `Controller` protocol, `Intent`, `ForagingController`.
- Spatial grid in `World` for perception queries (identical results to a full scan, tested).
- External data nutrients (`eyggnx.nutrients`, `--nutrient-dir DIR`, `SimulationConfig.nutrient_dir`): regular files directly in a directory become non-renewable food patches. Bytes are only read (never executed); energy is the zlib-compressed size × `nutrient_energy_per_byte`, capped by `nutrient_max_energy`; the position comes from the content's SHA-256, so no random numbers are drawn. The manifest (name, size, bytes read, SHA-256, energy) and its digest are stored in the run record. Off by default; trajectories without it are unchanged.
- Nutrient chunking and slow release: `nutrient_chunk_bytes > 0` splits each file into chunks that become separate patches (energy, cap and position per chunk); `nutrient_release_rate > 0` keeps a nutrient's energy in a finite `ResourcePatch.reservoir` and exposes at most `nutrient_release_capacity`, refilled at that rate per tick. Both are off by default, and nutrient runs without them are bit-identical to before (the reservoir enters `state_digest()` only when set). Recorder timeseries gain `finite_substrate_energy`.
- `python -m eyggnx` runs the CLI.

- Nutrient attributes: each nutrient file is classified from its content's leading bytes (format signatures; never the file name or extension) as `text`, `archive`, `image`, `media`, `document`, `executable` or `binary`. The category sets an `energy` factor (energy = factor × compressed size × `nutrient_energy_per_byte`; archive 1.25) and a `digestibility` factor on the release rate (archive, image, media 0.5; document, executable, binary 0.75; text 1.0). Overridable per category via `nutrient_attributes`; recorded in the manifest. Archives are never unpacked. Invariant #2 is revised to allow a property table for substrates (organisms never branch on it). Nutrient runs with only text files are unchanged; runs with binary files change.

- Large nutrient files are split by default: a file whose energy exceeds `nutrient_split_energy` (2,000) is split into the fewest equal chunks of about that energy, each its own patch; smaller files stay whole. Set it to 0 to keep every file whole.

### Fixed
- Loading nutrients no longer fails when a file in the directory cannot be read (e.g. Google Drive `.gdoc` placeholders); such files are skipped and listed under `unreadable` in the manifest.

### Changed
- `nutrient_max_energy` default 200 → 10,000: the cap now binds only near the 1,000,000-byte read limit, so larger documents give more energy (at 200, every 28 KB–3 MB docx was capped at the same value).
- External data nutrients release their energy slowly by default (`nutrient_release_rate = 0.4`, `nutrient_release_capacity = 30`): exposing everything at once produced a boom and crash (`experiments/nutrients/README.md`). `nutrient_release_rate = 0` restores immediate release. Runs without `nutrient_dir` and their golden digests are unchanged.
- Detritus: with `detritus_fraction > 0`, an organism dying of age leaves part of its energy as a decaying, non-renewable patch (`configs/detritus_genesis.json`). Off by default.
- `python -m eyggnx.stability`: long-run, multi-seed stability runs with structural invariant checks (finite energy, positions, resource capacity, population accounting, unique ids) and per-seed summaries; `--config` selects a model. `tests/test_stability.py` runs 2 seeds × 3,000 ticks.
- CI runs the test suite on Windows and macOS (Python 3.12) as well as Linux (3.11–3.13); a missing golden digest is reported with its value in the skip message.

### Documentation
- TRADEMARKS: the detailed clearance review is kept private; the link to the unpublished file was replaced with a note.
- Adopted the 12 architecture invariants from the Opus GENESIS audit as project policy (`docs/architecture/INVARIANTS.md`), with current compliance under simulation contract 1. No code or trajectory change.
- ROADMAP: marked Linux / Windows golden digests as done.

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
