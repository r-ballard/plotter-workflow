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

## Remaining work

- No physical plotter or serial-port test has been performed on this branch.

## Final software validation

After the operator cloned the sibling `viz_virtualserver` repository, the
`generative-viz-workspace` bootstrap installed pinned uv 0.6.14 and CPython
3.12.10 and created both repository environments. Its built-in verifier and
a separate run of `scripts/verify-environment.sh` passed. The viz repository
passed 483 tests and Ruff. The plotter repository passed 405 tests and Ruff;
its pytest run needed an approved shell because the managed sandbox denied
temporary fixture writes. A broad `pytest -q` also tried to collect an
inaccessible ignored `tmp/pytest-of-hardcase` directory, so the final suite
was run explicitly as `pytest tests -q`.

Qwen's 65,536-context documentation task corrected the exact per-pass
sidecar names in `PEN_PLAN.md` and the operator guide. Its attempt reached
the 600-second deadline after editing; the watchdog returned `REVIEW`, and
the orchestrator checked and integrated the in-scope diff. The documentation
and benchmark are recorded in `docs/qwen-pilot-configuration-debrief.md`.

## Audit limits

V2 preflight validates sidecar structure, HP-GL pen order, and current physical
placement. It cannot recompute the recorded source SVG or manifest hashes from
the HP-GL job alone; retain the source bundle and imposition audit with job
records. `JOB_PREFLIGHT.md` describes the operator confirmation boundary.
