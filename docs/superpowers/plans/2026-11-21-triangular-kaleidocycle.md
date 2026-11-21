# Triangular kaleidocycle artwork plan

> Native execution of the user-approved three-up artwork set and required adapter support.

Goal: three distinct triangular Truchet nets on one Letter landscape sheet.
Owner: plotter-workflow for export/return/imposition; viz_virtualserver for artwork.
Approved design: curves, light hatch/dot fills and multiscale, each with four A-D
states. Width 213.531 mm per net, 65.30 mm height including blank tabs; margins
and gutters 5 mm. Existing provisional square-fan state profiles are retained.

Approaches: extend the existing validated export adapter (selected), rather than
write a competing imposition or bypass handoff hash/geometry/catalog checks.
No new motif engine, fold mapping, hardware operation or pen assignment is needed.

- [x] Add RED adapter tests for uniform/multiscale triangular recipes, singular
  declared curve_layer_id, replayable hashed handoffs and invalid controls.
- [x] Extend only the known-algorithm and curve-layer validation in
  imposition/artwork_export.py; preserve classic palette behavior and all hashes.
- [x] Add a reproducible scripts/generate_triangular_kaleidocycle_samples.py using
  the normal export → external viz CLI → prepare → exact-width pack pipeline.
  Public interface: generate_samples(output_dir, *, viz_repo, viz_python,
  overwrite=False). Build 12 state bundles, three complete nets and one sheet.
- [x] Keep three declared artwork layers identical across all states and variants;
  preserve glue tabs, source width, provenance, source protection and budgets.
- [x] Generate actual A-D previews, individual and packed nets; inspect at a
  physical .3 mm preview width, verify 32 panels per net and 96 per sheet,
  matching hashes/catalogs and collision-free 5 mm margins/gutters.
- [x] Run focused adapter/roundtrip/kaleidocycle/packing consumers plus Ruff.
  No full-suite baseline, physical transmission or automatic merge. Read-only
  final review, record actual evidence and open a draft PR after checks pass.

Outputs: local SVG artwork, cut/fold guide proofs, JSON recipes and handoffs,
assembled A-D reference views, combined review gallery/contact sheet. No geometry
from the viewing profiles is described as physically validated. Author choices:
seeds/styles and conservative fill clearance/scale; revise artwork if dense.


## Verification record

Generated all twelve producer/return bundles, three individual nets, and one
three-object Letter landscape sheet through the existing validated handoffs.
Packing reports one sheet, 213.531 × 65.30 mm occupied bounds per net, x=5 mm,
y=5, 75.3, and 145.6 mm; the three nets therefore meet all 5 mm margins/gutters.
The common catalog contains curve, vertex-fill, and interstitial-fill; proof
adds the owned cut/fold channels. Each net binds all 32 canonical panel IDs.
Inspected the actual flattened SVG proof raster and local gallery containing
the twelve provisional assembled SVG views. The gallery and generated outputs
are ignored artifacts, not committed artwork fixtures.

Final affected-scope check: 217 passed in 15.28 seconds, no reported warnings.
Scope: new triangular tests; artwork layout/export/return/integration/bindings;
J-card artwork; kaleidocycle geometry/orientation/packing; sheet packing config,
export, geometry, solvers, and J-card consumers. Ruff on all four changed Python
files and git diff --check passed. No full suite or hardware/physical fold test
was run. An initial shared-output scratch run had three Windows access-denied
atomic rename errors; both the affected-file rerun (36 passed) and final scoped
worktree-scratch run passed without code changes for those errors.

Independent read-only reviewer found no important defects in the adapter,
generator, tests, or documentation. The profiles retain provisional status.
