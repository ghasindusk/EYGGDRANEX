# v0.1.2-alpha — Simulation Contract 2 and External Data Nutrients Release Checklist

## Code
- [x] PR #3 (simulation contract 2) merged
- [x] PRs #4, #5, #6 (external data nutrients) merged
- [ ] Release-prep PR merged
- [ ] Main-branch CI passes on the release commit
- [ ] Python 3.11 / 3.12 / 3.13 tests pass (Linux), 3.12 on Windows and macOS
- [ ] Package wheel build/install smoke test passes
- [x] Linux, Windows and macOS golden digests recorded for contract 2
- [x] Simulation contract 2 is active

## Release metadata
- [x] Python package version set to 0.1.2a1
- [x] CHANGELOG finalized
- [x] CITATION.cff updated
- [x] README status updated
- [x] PROJECT_STATUS updated
- [ ] Annotated Git tag `v0.1.2-alpha` created by `.github/workflows/release.yml`
- [ ] Tag target verified as a `main` commit with a successful CI run
- [ ] Public GitHub prerelease published

## Baseline protection
- [x] `v0.1.0-alpha` and `v0.1.1-alpha` remain untouched
- [x] No force-push
- [x] Contract 1 remains reproducible from tag `v0.1.1-alpha`

## Remaining GitHub administration
- [ ] Repository Description updated
- [ ] Repository Topics applied
- [ ] Private Vulnerability Reporting enabled
