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

## Remaining work

- Finish and review the Git Bash neutral logical-layer operator guide. The
  local Qwen worker is drafting its preparation and dry-run section in an
  isolated worktree through the two-attempt watchdog. Add preflight and send
  instructions only after reviewing the complete guide against the CLI.
- Final environment validation from `generative-viz-workspace` is blocked by
  the absent sibling `viz_virtualserver` repository. Its read-only
  `scripts/verify-environment.sh` reports the missing path. The workspace
  instructions prohibit cloning unless an operator explicitly uses
  `--clone-missing`; no clone was attempted.
- No physical plotter or serial-port test has been performed on this branch.

## Audit limits

V2 preflight validates sidecar structure, HP-GL pen order, and current physical
placement. It cannot recompute the recorded source SVG or manifest hashes from
the HP-GL job alone; retain the source bundle and imposition audit with job
records. `JOB_PREFLIGHT.md` describes the operator confirmation boundary.
