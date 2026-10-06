# EYGGDRANEX v0.1.2-alpha — Simulation Contract 2 and External Data Nutrients

This alpha makes **simulation contract 2** the active model contract. Every seeded trajectory differs from v0.1.1-alpha; contract 1 remains reproducible from tag `v0.1.1-alpha`.

## Simulation contract 2

- order-neutral tick: all organisms decide on one shared world state; contested patches are shared equally
- named, isolated RNG streams per mechanism (`world`, `founders`, `movement`, `placement`, `mutation`)
- trade-off costs instead of costless genes: basal metabolism grows with `sensor_range` and `max_age`, movement cost with `speed`
- log-normal mutation with reflecting bounds; continuous `max_age`
- heritable foraging controller (`distance_aversion`, `wander_step`) and a spatial grid for perception
- optional detritus

## External data nutrients

- `--nutrient-dir DIR`: regular files in a directory become finite food. Bytes are only read, never executed or interpreted.
- energy from information content (zlib-compressed size); content-derived categories (format signatures, never the file name) set energy and digestibility factors
- slow release by default, automatic splitting of large files, optional chunking
- optional periodic regrowth (`nutrient_regrow_interval`)
- unreadable files (e.g. cloud placeholders) are skipped and listed in the manifest

## Reproducibility and quality

- the 12 architecture invariants are adopted as project policy (`docs/architecture/INVARIANTS.md`)
- long-run multi-seed stability runs (`python -m eyggnx.stability`)
- CI on Linux (Python 3.11–3.13), Windows and macOS (3.12), with per-platform golden digests for contract 2
- `python -m eyggnx` runs the CLI
- manual release workflow that tags only a commit on `main` with a successful CI run

## Experiments

`experiments/nutrients/README.md` records the nutrient experiments. Highlight: with 466 Wikipedia articles as the only food and regrowth every 50–250 ticks, all 10 seeds survive 30,000 ticks, and the reproduction strategy evolves with the regrowth period (reproduction_threshold ×0.61 at 50 ticks to ×2.68 at 250), against a fixed-genome control.

## Compatibility note

Golden digests are recorded per platform; bit-identical trajectories across operating systems are not claimed. The coefficients of costs, nutrient energy and attributes are hypotheses.
