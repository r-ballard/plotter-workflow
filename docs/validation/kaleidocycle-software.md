# Kaleidocycle software validation, 2026-11-20

Implemented on `feat/kaleidocycle`, based on J-card format profiles (`07b8009`).

The real local `viz_virtualserver` producer generated each of the four state
exports from the existing Truchet recipe. All producer bundles passed the
shared return adapter. All 32 prepared surfaces passed imposition validation.
The final neutral artwork passed the converter's authoritative catalog/audit
check and polygon materialization: 177 curve and 969 hatch paths.

The full repository suite passes (684 tests). Focused coverage includes:

- Exact panel coverage across A-D, slot identity, aspect ratio and guide bounds.
- Explicit seam endpoint agreement and invalid convex crop rejection.
- Triangle export/return, partial binding inventory, empty state artwork.
- Physical coordinates and triangle clipping through the actual converter
  materializer; an asymmetric crossing stroke is scaled/translated once.
- Rejection of a different valid handoff attached to unchanged prepared assets.
- Existing booklet, cootie catcher, and J-card regression coverage.

The generated example is in `output/kaleidocycle-demo/` (ignored output): four
producer bundles, prepared assets, and `sheet/` with artwork, separate guides,
and a labeled diagnostic net. No plotter transmission was performed.

The A-D built-in projections are illustrative and provisional. Software
validation does not establish physical folded adjacency or reading orientation.
Use the labeled net to check assembly, closure, state order, and seam continuity;
correct the declared profiles before treating a composed image as physically
validated. Continuous transitions remain deferred.

## PR readiness and physical handoff

The feature branch was rebased onto current main (`d2a6d7c`, including sheet
packing). The combined full suite passed: **797 tests**, with changed-file Ruff
checks and diff whitespace checks passing. Independent review found no
remaining important issues.

Prepared physical-inspection output is retained separately in
`output/kaleidocycle-physical-inspection/`, with a local ZIP beside it. It includes
two diagnostic impositions, separate cut/fold construction proofs with blank
glue tabs, A-D reference views, observation template, pen plans, and four
converted HP-GL jobs. All four passed pen-plan and placement preflight. No
transmission occurred. Generated output stays ignored; the generator and
instructions are committed for reproducibility.

Physical inspection is a separate backlog item:
[HAR-179](https://linear.app/hardcase/issue/HAR-179/physically-inspect-kaleidocycle-diagnostic-plots).
Profiles remain provisional until that inspection establishes folded adjacency,
reading orientation, closure and seam continuity. It does not gate the software PR.
