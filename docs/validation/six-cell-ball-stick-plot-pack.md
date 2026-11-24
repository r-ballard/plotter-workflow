# Six-cell diagnostic and ball-and-stick plot pack

Prepared from plotter base `19d3668` with the accompanying ball-and-stick export
adapter and helper. Producer: `a552442ac59c864c09f5dca3062fe96b280a982c`.
Output: `output/six-cell-plot-pack/`. Reproduction and pen-slot instructions are
in `docs/how-to/plot-six-cell-ball-stick-kaleidocycles.md` and the pack's README.

## Artifact checks

- Live producer ran for all four states of three distinct ball-and-stick
  recipes: crystal lattice, honeycomb nodes, organic network.
- Each output is a six-tetrahedron net with 24 faces. Nets measure
  161.291 × 65.30 mm; the three-up Letter landscape sheet has 5 mm margins/gutters.
- Panel orientation and state continuity diagnostics use the same net size.
- Artwork proof, artwork-only and diagnostic sheets were converted offline to
  DPX-3300 HP-GL, using Letter landscape lower-left, absolute coordinates and
  a 4 mm margin check. `vpype` initially was missing from PATH; adding the
  existing virtual environment's Scripts directory resolved setup.
- Pen-plan and placement preflight PASS for all three jobs. Operator pen
  confirmation remains required; force is unmanaged. No hardware was operated.
- Exact HP-GL pen-down strokes were rendered to PNG and visually inspected:
  three distinct artwork nets, legible diagnostic marks, blank tabs, no sheet
  clipping. SVG previews also retain pen-up travel for operator review.
- `verification.json` checks current HP-GL hashes against metrics/preflight,
  sheet counts, footprints and required files. The ZIP package includes source
  bundles, job configurations, observations, previews and all job sidecars.

## Software verification

- Adapter regressions: 2 expected failures before implementation.
- Focused artwork export checks: 24 passed in 0.14 seconds, including existing
  classic/triangular Truchet replay and the new ball-and-stick adapters.
- Final repository run: 868 passed, 5 failed in 26.28 seconds. All five failures
  were Windows `WinError 5` during existing atomic-directory rename operations.
  Those five exact nodes passed unchanged in fresh temp directories: 5 passed
  in 2.99 seconds. No product failure remains observed across the 873 tests.
  Logs: `artwork-final-tests.log` and `artwork-retry.log`.
- Ruff lint and formatting pass for the three changed/new Python files.

Failed nodes retried:

- `test_jcard_profile_workflow.py::test_profile_artwork_geometry_and_restore[independent-5]`
- `test_jcard_profile_workflow.py::test_foreign_manufacturer_same_geometry_rejected`
- `test_kaleidocycle.py::test_four_state_assets_impose_once_preserving_layers_and_provenance[False]`
- `test_kaleidocycle_orientation_fixture.py::test_diagnostic_nets_use_real_imposition_and_plotter_safe_labels`
- `test_sheet_packing_export.py::test_cli_and_input_overlap`

## Review and boundaries

Independent read-only review found no Critical/Important source defects. Its
minor observation about nominal height metadata is covered by the regression
asserting width/profile resolve to exactly 65.3 mm; retain this explicit selected
sheet height rather than add a separate configuration mechanism. Changing width
without updating the selected height fails that regression.

The review process could not read generated files under sandbox permissions;
the parent verified them with working permissions, including hashes, preflight
and visual rendering. Physical folding, assembled-view accuracy and actual
plotting remain owner acceptance. All views remain provisional.
