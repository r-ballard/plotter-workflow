# Logical-layer plotter handoff

Branch: `feat/logical-layer-plotter`

This branch is an in-progress checkpoint for the neutral logical-layer plotter workflow. Tasks 1 through 5 are independently reviewed and committed. Task 6 is implemented and test-covered, but it is intentionally committed as work in progress because independent review identified two unresolved conversion defects.

## Completed checkpoints

- `8af642c` — strict neutral SVG inspection
- `8287613` — manifest, hash, catalog, and surface-inventory validation
- `99fb33c` — lossless neutral imposition with authoritative manifest provenance
- `eb941c4` — pen-plan v2 parser, immutable model, schema, and example
- `46bb76a` — logical catalog resolution into explicit physical passes

## Task 6 work in progress

The uncommitted Task 6 implementation adds deterministic per-pass SVG/HP-GL conversion, resolved v2 sidecars, clip materialization for the supported subset, dry-run planning, and failure cleanup. Its tests were green before the review findings below, but review approval has not been granted.

### Unresolved review findings

1. Nested SVG viewport translation without a `viewBox` is incorrect. A nested `<svg x="20" y="10" width="40" height="40">` may have its viewport crop transformed while its geometry remains in the unshifted coordinate system. Add a failing integration test and make geometry and viewport use the same transform.
2. Neutral conversion currently accepts SVGs without `data-plotter-workflow-layout="preserve"`. Because vpype fits each selected pass independently, differing pass bounds can lose registration. Require and validate imposed preserve-layout metadata before neutral multi-pass conversion, or compute one source-wide transform and reuse it for every pass. The intended MVP path is to require the Task 3 imposed preserve-layout artifact.

Do not describe Task 6 as complete until both findings have strict RED/GREEN coverage, the focused and full suites pass, Ruff and `git diff --check` pass, and an independent re-review approves the result.

## Remaining planned work

- Finish and approve Task 6, then replace the WIP commit with a normal follow-up fix commit (history rewriting is not required).
- Task 7: resolved-sidecar preflight, compatibility regression coverage, and Git Bash operator documentation.
- Run final cross-repository integration validation from `generative-viz-workspace`.

No physical plotter or serial-port testing has been performed on this branch.
