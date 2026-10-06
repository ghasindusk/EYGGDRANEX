# EYGGDRANEX Roadmap

## Phase 0 — Foundation
- [x] Name and project identity
- [x] Repository structure
- [x] Licensing boundary
- [x] Experiment protocol

## Phase 1 — GENESIS (`v0.1.x-alpha`)
- [x] Genome
- [x] Metabolism
- [x] Resource perception
- [x] Movement
- [x] Reproduction
- [x] Mutation
- [x] Death
- [x] Deterministic seed
- [x] JSON experiment export (run record, JSONL time series)
- [x] lineage event export (births/deaths incl. dead organisms)
- [x] invariant tests and versioned full-state golden digest
- [x] neutral-drift and fixed-genome controls
- [x] long-run stability tests (`python -m eyggnx.stability`, `tests/test_stability.py`)
- [x] order-neutral updates: simultaneous decisions, equal sharing of contested patches (simulation contract 2)
- [x] named RNG streams (simulation contract 2)
- [x] trade-off costs instead of costless genes; log-normal reflecting mutation; continuous `max_age` (simulation contract 2)
- [x] heritable foraging controller parameters (simulation contract 2)
- [x] golden digests for Linux / Windows / macOS (`linux-x86_64`, `win32-amd64`, `darwin-arm64`), verified in CI

## Phase 2 — ECOLOGY (`v0.2.x-alpha`)
- [x] seams: intent/resolve pipeline, spatial grid, gene registry, substrates (detritus)
- [ ] energy vector (multiple chemistries as config)
- [ ] multiple resource chemistries
- [ ] predation/scavenging
- [ ] competition
- [ ] parasites/pathogens
- [ ] immunity
- [ ] symbiosis

## Phase 3 — COGNITION (`v0.3.x-alpha`)
- [ ] neural controller
- [ ] memory
- [ ] drives
- [ ] curiosity
- [ ] fear/attraction biases
- [ ] optional high-level LLM layer

## Phase 4 — CULTURE
- [ ] communication
- [ ] social learning
- [ ] persistent artifacts
- [ ] intergenerational knowledge

## Phase 5 — EMBODIMENT
- [ ] developmental morphology
- [ ] procedural bodies
- [ ] physics-aware movement
- [ ] 3D visualization

## Phase 6 — OPEN BIOSPHERE
- [ ] external data nutrients
- [ ] distributed simulation
- [ ] persistent worlds
- [ ] network organisms
