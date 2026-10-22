# Assembled-layout export for coherent polygon artwork

Date: 2026-10-21
Status: Proposed written design for user review. Product implementation has not started.
Repository: plotter-workflow, isolated feat/assembled-layout-export worktree.
Producer baseline: viz_virtualserver PR45, shared composition and inverse-projected assets.

## Intent and responsibility boundary

Replace synthetic artwork layouts with dimensions and orientation mappings owned by
plotter-workflow. A booklet spread and the visible outer faces of a folded Cootie
Catcher should be authorable as coherent compositions while retaining separate
page/panel assets for physical imposition.

User-approved division:
- plotter-workflow owns object/page definitions, named assembled views, physical
  sheet placement, page order, fit/margins/gutters, and pen/machine execution.
- viz_virtualserver applies supplied composition transforms, determines geometric
  adjacency/overlaps/gaps, generates artwork, and partitions it into owned assets.
- Do not introduce a third project or duplicate adjacency detection here.

Keep intrinsic asset, assembled/reading, and physical sheet coordinates distinct.
The assembled view determines artwork continuity. The sheet layout determines
where those independently retained assets are printed/plotted. Neither frame can
be substituted for the other, even when some polygons happen to share coordinates.

## Existing implementation evidence

Current main has scripts/booklet_impose.py, docs/reference/booklet-imposition.md,
imposition/objects/cootie_catcher.py and scripts/cootie_impose.py. The original
working checkout inspected first is on an older feature branch with root-level
script/document paths; implementation must use current-main paths in this worktree.

Booklet pocketmod8 already supports facing pairs 2-3,4-5,6-7,8-1. A full spread is
fitted once to a double-width canvas, cropped into halves with outer margin and
half-gutter setbacks, then each half is placed in its print-sheet cell. Page8 is
the left half and page1 the right half of the wraparound spread. This existing
reading-order and crop behavior is authoritative.

Cootie Catcher slots define the flat-sheet polygons; outer1 through outer4 occupy
separate sheet corners. They do not describe the adjoining folded view. Current
semantic orientation targets are explicitly provisional. Do not relabel them as
physically validated or silently derive a folded view from flat adjacency.

## Selected approach and alternatives

Add a small layout-export capability in plotter-workflow, backed by existing page
and object definitions. It writes the producer's existing domains and affine
composition transforms as part of a runnable artwork job plus a handoff report.
No runtime import or checkout dependency on viz_virtualserver is required to export.
Cross-repository integration checks invoke its CLI only as an explicit validation.

Direct producer imports of physical-layout code would couple two repositories and
mix assembled and sheet coordinates. A new shared geometry package would introduce
packaging/version overhead before there is duplicated substantial implementation.
Both alternatives are deferred in favor of the existing JSON job contract.

## Export interface and artifacts

Proposed command: scripts/export_artwork_layout.py, with explicit layout/profile,
sheet sizing and margin/gutter settings and an artwork-job template JSON.

The first template adapter supports one truchet or truchet-multiscale continuous
composition pass. Preserve seed, algorithm, styling and declared logical layers;
replace source domains, composition transforms, target IDs and composition_window
with the exported layout. Set coordinate_frame=composition and composition_mode=
continuous explicitly. Reject unexpected template shape, multiple passes, or
ambiguous mappings; do not silently discard user configuration. Algorithm-neutral
layout construction stays separate from the Truchet template adapter.

Write atomically into a new output directory, requiring explicit overwrite:
- artwork-job.json: uses the existing viz_virtualserver version1 job schema.
- layout-handoff.json: versioned report of named profile, geometry units, page/slot
  IDs, resolved dimensions, transforms, crop settings, intended returned asset
  names, profile validation status, and physical-imposition settings to use later.
- layout-preview.svg: labeled assembled view with corners/up arrows and an optional
  sheet-position comparison. These are diagnostic guides, never artwork strokes.

Use SVG user units matching plotter-workflow's 96/25.4 pixels-per-mm convention.
Record that conversion explicitly. Recipe fill lengths and pen widths remain
producer design units; do not reinterpret existing numbers as millimeters. The
handoff guide must show how to convert physical pen widths when authoring a recipe.

Returned artwork keeps its intrinsic canvas dimensions even when paths are sparse
or blank. Fit must use canvas geometry, not the drawn paths' bounding box. Generated
assets are then assigned by stable page/slot ID, not arbitrary filename ordering.
Do not silently refit or rotate returned assets a second time.

## Booklet reading-spread profile

Resolve page dimensions from the selected landscape sheet and existing pocketmod8
cell layout. Validate the selected logical pair against existing supported pairs.
Place the two intrinsic page canvases left-to-right in reading order, independent
of their physical row/column rotations. Export either a selected spread or explicit
separate jobs for several spreads; never force all8 pages into one reading canvas.

Represent page canvases as their full cell rectangles. Represent the drawable crop
in the intrinsic domain geometry using the existing spread margin/gutter rules;
retain the full canvas bounds through the handoff so later imposition does not
shrink or recenter a cropped domain. If the existing producer surface rebasing
cannot preserve that canvas/crop distinction, add an explicit full-canvas export
adapter rather than masking a discrepancy with a compensating arbitrary transform.
The implementation plan must pin this through a canvas-boundary roundtrip test.

Zero gutter permits a continuous seam. Positive gutter deliberately removes a band
around the seam; outer margin applies at spread edges under current crop rules.
Do not apply margins/gutter again on returning the already cropped page assets.
The handoff records exact single-page placement settings or a manifest path that
preserves canvas alignment. Existing full-source spread imposition remains valid
and unchanged as an alternative workflow.

## Cootie Catcher assembled-view profiles

Keep flat-sheet imposition geometry separate from a named folded outer-panel view.
The export profile maps stable outer1..outer4 intrinsic canvases into a planar
assembled reference, including rotations/reflections and corner correspondence.
Use original object dimensions and semantic feature anchors wherever they apply.

A folded profile must include explicit transforms and validation status. Support
an explicit supplied profile when a verified built-in mapping is unavailable;
reject missing mappings rather than reuse the synthetic producer example or guess
from the flat corners. A built-in default may be selected only after a documented
fold/corner derivation and labeled orientation fixture support it. Software review
of labeled fixtures is available now; physical acceptance remains deferred and
must remain marked provisional until actually performed.

The first scope is outer panels only. The complete current cootie manifest still
requires selector and reveal assets. Export a clear merge recipe/report for those
other16 entries; do not call an outer-only fragment a complete runnable20-panel
manifest or overwrite unrelated artwork assignments.

## Validation, failure behavior, and audit

Validate finite positive dimensions, supported paper/spread/profile, unique IDs,
well-conditioned invertible affine transforms, recipe shape and complete requested
mappings. Validate schema/version tags strictly, including booleans masquerading
as dimensions. Bound target/coordinate counts and output sizes. No implicit gap
snapping, geometry repair, overlap ownership, or adjacency table is emitted.

Re-exporting identical inputs produces identical geometry and reports. Input paths
are never overwritten. Failed overwrite leaves existing artifacts intact. Handoff
reports retain settings sufficient to reproduce page/panel placement without
changing artwork fitting based on stroke extents.

Required software evidence:
- Each supported booklet pair has correct left/right order, canvas dimensions and
  corner mappings;8-1 is explicitly covered.
- Margin/gutter exported crops match the existing full-spread crop at both halves;
  geometry generated/cropped/re-imposed matches a direct full-spread reference.
- Sparse and blank returned assets preserve full-canvas placement; no double fit,
  duplicate margin/gutter, or extra orientation correction occurs.
- Cootie labeled corners/up arrows survive assembled-to-intrinsic-to-sheet mapping;
  unspecified folded transforms fail. Provisional status is preserved.
- Existing booklet/cootie imposition outputs remain unchanged for old inputs.
- Explicit cross-repository run: export job, generate with merged viz_virtualserver,
  validate neutral logical layers, impose the retained assets, and inspect assembled
  and sheet previews. No plotting hardware or machine transmission.

## Scope and next stage

No fold simulation,3D rendering, new producer adjacency code, hardware acceptance,
automatic book pagination beyond pocketmod8, or new shared package. A generalized
arbitrary-layout exporter can use the same profile boundary later; do not hard-code
four-panel adjacency inside the producer.

After review of this written design, write a task-by-task implementation plan,
including the full-canvas/crop adapter decision and explicit orientation fixtures.
Retain the user's native-execution preference and isolated worktree workflow.
