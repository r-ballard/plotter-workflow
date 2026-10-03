# Logical-layer plotter handoff

Branch: `feat/logical-layer-plotter`

## Completed work

- Tasks 1–5: strict neutral SVG inspection; manifest, hash, catalog, and
  surface-inventory validation; lossless neutral imposition; pen-plan v2;
  logical catalog resolution into explicit physical passes.
- Task 6: deterministic per-pass SVG/HP-GL conversion, v2 resolved sidecars,
  supported clip materialization, dry-run planning, and failure cleanup. The
  nested viewport translation and preserve-layout registration review findings
  were fixed with RED/GREEN integration tests in `48cae13`, then independently
  re-reviewed. The full suite and Ruff passed.
- Task 7 code: v2 resolved logical-pass sidecars now pass preflight and the
  sender's final sidecar check. The carriage table names logical layers and
  physical slots; multi-pen sends still require operator confirmation. Legacy
  v1 resolved plans retain the tool-or-label requirement and filename fallback.
  Real neutral conversion output is preflighted in integration coverage.
  Commits: `27b1301`, `47b4c64`, `74bbdfb`. Full suite: 405 passed; Ruff and
  `git diff --check` passed.
- Task 7 operator guide: `docs/how-to/neutral-logical-layer-plotting.md`
  documents the Git Bash path from neutral bundle through registered passes.
  The third Qwen trial was stopped by its watchdog after two 30-minute
  attempts with no file edit; the guide was completed by the orchestrator.
  A later Qwen trial added a validated, software-only `booklet.json` example
  so the orbital-per-body bundle can follow the guide without inventing a
  manifest.

## Remaining work

- No physical plotter or serial-port test has been performed on this branch.
  Follow `docs/how-to/physical-logical-layer-acceptance.md` at the workstation;
  it covers a small serial check, pocketmod orientation, and registered neutral
  multipass proof. Linear `HAR-26` tracks that acceptance. The separate
  twenty-surface cootie-catcher proof is Linear `HAR-14`.

## Final software validation

After the operator cloned the sibling `viz_virtualserver` repository, the
`generative-viz-workspace` bootstrap installed pinned uv 0.6.14 and CPython
3.12.10 and created both repository environments. Its built-in verifier and
a separate run of `scripts/verify-environment.sh` passed. The viz repository
passed 483 tests and Ruff. The plotter repository passed 405 tests and Ruff;
its pytest run needed an approved shell because the managed sandbox denied
temporary fixture writes. Broad pytest collection also entered ignored `tmp`
directories. The project now sets pytest `testpaths = ["tests"]`, so bare
`pytest --collect-only -q` collects all 405 tests without entering `tmp`.
Bare `pytest -q` passes all 405 when temporary fixtures have filesystem
access; that sandbox write boundary remains separate from collection scope.

Qwen's 65,536-context documentation task corrected the exact per-pass
sidecar names in `docs/reference/pen-plan.md` and the operator guide. Its attempt reached
the 600-second deadline after editing; the watchdog returned `REVIEW`, and
the orchestrator checked and integrated the in-scope diff. The documentation
and benchmark are recorded in `docs/qwen-pilot-configuration-debrief.md`.

A software-only cross-repository check used `viz_virtualserver`'s
`examples/domain-jobs/orbital-per-body.json` to generate a neutral bundle with
50 catalog IDs (one `orbits`, 36 `body-*`, 13 `accent-*`). A disposable
eight-page manifest and two-pass v2 plan in ignored `tmp/neutral-orbital-e2e/`
covered every ID, repeating `orbits` as declared. Imposition, converter
`--dry-run`, and conversion produced `body` and `accent` HP-GL jobs with
resolved and placement sidecars. Read-only preflight reported `Pen plan: PASS`
and `Placement: PASS` for both, then `VALIDATED - OPERATOR CONFIRMATION REQUIRED`.
No pen confirmation, serial access, or physical plotting occurred.

## Audit limits

V2 preflight validates sidecar structure, HP-GL pen order, and current physical
placement. It cannot recompute the recorded source SVG or manifest hashes from
the HP-GL job alone; retain the source bundle and imposition audit with job
records. `docs/reference/job-preflight.md` describes the operator confirmation boundary.
