# EYGGDRANEX Project Status

**Version:** v0.1.2-alpha — Simulation Contract 2 and External Data Nutrients
**Date:** 2026-10-07
**Author:** SHAR-K
**Repository:** https://github.com/ghasindusk/EYGGDRANEX
**Release:** https://github.com/ghasindusk/EYGGDRANEX/releases/tag/v0.1.2-alpha

## Completion

**Simulation contract 2 and external data nutrients: complete / published**

## Completed

- Simulation contract 2 is the active contract on `main` (PR #3): order-neutral tick, named RNG streams, trade-off costs, log-normal reflecting mutation, continuous `max_age`, heritable foraging controller, spatial grid, optional detritus
- External data nutrients (PRs #3–#6): read-only file food, content-derived attributes, slow release, splitting of large files, periodic regrowth, skipping of unreadable files
- Architecture invariants adopted as project policy (`docs/architecture/INVARIANTS.md`)
- Long-run stability runs (`python -m eyggnx.stability`)
- CI on Linux (3.11–3.13), Windows and macOS (3.12) with per-platform golden digests
- Package metadata bumped to 0.1.2a1; CHANGELOG and CITATION updated
- Manual release workflow (`.github/workflows/release.yml`) that tags only a `main` commit with a successful CI run
- `v0.1.0-alpha` and `v0.1.1-alpha` tags unchanged; contract 1 is reproducible from `v0.1.1-alpha`

## Release status

- [x] PR #3–#6 merged
- [x] Release-prep PR #7 merged
- [x] main CI green on the release commit
- [x] package metadata bumped to 0.1.2a1
- [x] CHANGELOG finalized
- [x] CITATION metadata updated
- [x] annotated tag `v0.1.2-alpha` created and verified (`3444cdb5bc4a9b71aca5ae3002af05319a5bdf57`)
- [x] GitHub prerelease published

## Remaining repository administration

- Apply approved bilingual repository Description
- Apply repository Topics
- Enable GitHub Private Vulnerability Reporting

## Approved Description

自己複製・変異・選択を通じて適応・進化するデジタル生命のためのオープンエンドA-Life生態系。An open-ended artificial digital life ecosystem — designing the conditions for life to emerge, adapt, and evolve.

## Approved Topics

`eyggnx`, `artificial-life`, `alife`, `digital-life`, `open-ended-evolution`, `evolution`, `evolutionary-computation`, `emergent-behavior`, `agent-based-modeling`, `ecosystem-simulation`, `complex-systems`, `artificial-intelligence`, `simulation`, `digital-ecosystem`, `procedural-generation`, `computational-biology`
