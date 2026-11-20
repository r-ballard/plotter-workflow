# Kaleidocycle Implementation Plan

> Implement inline with superpowers:executing-plans, using test-first checks.

**Goal:** Compose named kaleidocycle states and impose their panels onto a net.

**Architecture:** Extend convex crops in shared artwork layouts; add an object,
explicit state layouts, binding support, and neutral SVG imposition CLI.

**Tech Stack:** Python, existing SVG/neutral layer utilities, pytest, vpype.

**Spec:** ../specs/2026-11-20-kaleidocycle-design.md

## Constraints and review focus

Retain existing rectangular behavior and source provenance. Profiles are
provisional. Check triangle clipping, reflected transforms, seam endpoints,
placement bounds, duplicate/missing assignments, and source path containment.

## Tasks

- [x] Add tests for 32 slots, aspect-preserving placement, guides, A-D panel
  coverage and shared seam endpoints. Run red; implement object and profiles.
- [x] Add tests for convex triangle crops, export/parse and neutral return.
  Run red; extend shared layout/return and binding code without changing
  rectangular behavior. Add kaleidocycle export controls to the existing CLI.
- [x] Add end-to-end neutral imposition tests for clipping, physical placement,
  layer/provenance retention, and invalid manifests. Run red; implement the
  imposition CLI, separate guides, examples and instructions.
- [x] Run focused tests and regression suite, lint changed Python, review diff.

## Execution ledger

Initial baseline: 30 shared layout/profile tests pass. Git worktree creation
required sandbox escalation and succeeded. Work uses the J-card format branch
to retain the existing assembled-artwork abstractions.

Ruling: execute inline following the user's explicit request to proceed with
implementation; keep all work isolated from the older active checkout.

Ruling: canonical source triangles use exact integer 128-square coordinates
and integer square fan projections. The real producer rejected floating seam
gaps in the initial projection. Physical scaling now occurs in imposition;
`source_unit_mm` records the scale. Lowercase panel IDs match producer paths.

Verification: real producer generated all four states, the return adapter
prepared all 32 surfaces, and the imposer produced the net. Converter context
accepted the audit and materialized 177 curve paths and 969 hatch paths.
Crossing-stroke regression checks clipped endpoints in physical coordinates;
blank-state and swapped valid handoff tests pass. Full suite: 684 passed.

Independent read-only review found one important handoff provenance issue;
added a failing regression and fixed it. Follow-up review found no remaining
critical or important issues. Physical fold verification remains outstanding.
