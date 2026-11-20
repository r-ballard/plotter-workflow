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
