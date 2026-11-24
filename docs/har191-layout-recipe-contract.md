# HAR-191 — Layout, recipe and surface handoff contract

Status: proposed contract for review. Evidence revision: `79fa5ef` in
plotter-workflow. Producer reference: `a552442` in viz_virtualserver.

## How the coupling developed

1. Commit `23637b5` introduced `imposition/artwork_export.py` with the description
   “Algorithm-neutral resolved layout export with a small Truchet job adapter.”
   Its public `build_artwork_job` simultaneously accepted a layout, selected
   supported Truchet algorithms, validated fill and palette controls, enforced
   one pass, rejected dependencies, and injected composition settings. Generic
   geometry transport and a particular recipe adapter shared one entry point.
2. Commit `0ec2bfc` introduced J-card artwork handling around that standard job
   builder. `build_jcard_artwork_job` rewrites coordinate and composition modes
   before calling it. Object-specific code therefore learned generator controls.
3. Commit `559e3b2` reused this exporter for kaleidocycle layouts. Its design
   correctly selected the existing slots, layouts and neutral bundle contracts,
   but did not establish an algorithm-independent recipe boundary. Kaleidocycle
   geometry did not itself introduce the Truchet restriction.
4. Commit `49096f0` extended the supported algorithm list for triangular Truchet.
   Commit `0bfd521` repeated that pattern for ball-and-stick. Both changes made
   requested samples possible while retaining the algorithm-dependent boundary.
5. `imposition/artwork_return.py::_load_handoff` calls `build_artwork_job` to
   reconstruct the request before accepting a bundle. This makes the current
   recipe adapter part of historical asset loading and provenance verification.
   Removing a whitelist alone would leave request rewriting and replay coupled.

These observations come from the named commits and current function bodies.
They establish the implementation history. They do not establish an individual's
intent beyond the recorded code and design documents.

The process failure was treating a working example adapter as the common
contract. Tests reinforced that boundary by exercising the supported recipe
families. A portability check using an unrelated registered algorithm would
have exposed it. The v2 sample also exposed a separate modeling distinction:
one composition across all 24 flat-net facets differs from four compositions
across the six facets visible in each provisional folded view.

## Ownership

| Layer | Owns and validates |
| --- | --- |
| Imposition object | Semantic slot IDs, topology, construction geometry, object parameters, physical aspect ratio and object-specific constraints |
| Layout description | Intrinsic canvases, crops, coordinate units, composition frames and transforms, stable bindings |
| Producer | Recipe syntax, algorithm registry, parameters, pass dependencies, recipe channel routing, capabilities and compatibility with requested target geometry/mode |
| Surface preparation | Returned surface identities, hashes, dimensions, crop/rebase restoration, declared logical channels and provenance |
| Physical imposition | Complete assignments, one physical scale/placement transform, clipping, sheet bounds and consistent logical-layer catalog |
| Plotting | Physical pen assignment, conversion, placement checks, operator confirmation and transport |

Every boundary validates its own received envelope, sizes and references.
Producer-specific settings stay inside the producer-owned recipe. Object-specific
slot semantics stay with the object. Generic geometry validation may be repeated
where each consumer must protect its input assumptions.

## Request contract

Use the existing ArtworkLayout/PanelLayout representations where their semantics
fit. The following describes fields and responsibilities rather than fixing a
new wire schema before consumer analysis in HAR-192/HAR-193.

- A versioned request identifies a layout, an opaque recipe or content-addressed
  recipe reference, and the intended generation mode.
- Each canvas has a stable ID, intrinsic dimensions and explicit design units.
  Crops use that canvas's coordinates. Every transform states its source and
  destination frame. Physical millimetres are resolved through a declared scale.
- A composition frame identifies its target canvas IDs, window and transforms.
  It can represent a flat net, reading spread or a named folded-view profile.
  Frame identity and acceptance status travel with the request.
- Bindings map returned surface IDs to object slots separately from recipe pass
  targeting. A producer receives geometry and target identities without needing
  to interpret kaleidocycle column names or J-card panel semantics.
- Generation mode is either independent per canvas or shared across a declared
  composition. Aggregating existing surfaces is an asset-binding operation and
  requires no generation recipe.
- Preserve recipe values and pass structure through transport. The producer
  resolves layout target references and its own generator-specific controls.
  Multi-pass recipes and semantic groups/relations require explicit supported
  transport semantics. They must not be dropped or reduced to one pass.
- Contradictory recipe targeting and envelope targeting produce a clear error.
  Producers report unsupported geometry, transforms or modes before publication.
  Automatic changes of mode or geometry require an explicit requested policy.

## Adjacency and folded-view profiles

The cootie catcher's `folded-outer` profile is an existing folded-view example.
It declares the four outer canvases and their matrices into a shared 2D view.
`imposition/assembled_profiles.py::load_cootie_assembled_profile` checks canonical
canvas dimensions and slot identities. Its profile JSON contains no separate
adjacency list. Contact follows from the transformed canvas geometry. The
illustrative profile's validation status is provisional.

Kaleidocycle state profiles additionally store explicit edge pairs in
`ArtworkLayout.settings.adjacency`, for example
`[["column-1-a", 2], ["column-2-a", 0]]`. Edge indices address the ordered
`crop_polygon` vertices. `validate_kaleidocycle_layout` verifies that each pair's
transformed endpoints coincide in reverse order, rejects repeated references,
and checks coverage. This list describes seams of the selected state view.

The shared `ArtworkLayout` representation currently has no typed adjacency
field. The producer's `canvas/placed_targets.py::plan_placed_targets` derives
geometric seams from transformed domain boundaries and their union. The
kaleidocycle adjacency metadata is validated on the plotter side and is not
exported as an authoritative generic topology graph to the producer.

For the new contract, composition transforms remain sufficient to describe a
geometric arrangement. A layout can also declare intended edge correspondences
as versioned generic topology metadata. Geometry-derived contact and declared
topology have distinct meanings and are checked for agreement when a profile
requires coincident edges. Shared-edge correspondence belongs to the layout
contract, independent of the selected algorithm.

Each declared correspondence identifies the composition-frame ID and two
canvas/crop-edge references, endpoint orientation, and any required tolerance
in explicit units. Edge references are versioned with crop vertex order.
Partial-edge contacts require explicit endpoint intervals when supported.
Profiles may explicitly declare an empty topology set. An absent declaration
means unspecified topology. Retain existing full-edge behavior during migration.

Physical hinges and glued edges belong to object topology. Visible adjacency
belongs to a named composition/view profile. Sheet contact belongs to physical
placement. The request identifies which relationship is being supplied.
Visibility or occlusion rules, if required by a future profile, need an explicit
capability and contract extension. A 2D canvas arrangement alone cannot establish
physical folding behavior.

Acceptance covers the cootie profile with geometry-derived contact, the
kaleidocycle profile with declared paired edges, and the 24-facet flat-net
composition. A recipe change must preserve each selected layout's adjacency.
Tests check mismatched edge pairs, reversed crop order, point-only contact,
near-coincident edges, and partial contacts according to declared capabilities.

## Three paired request/return examples

### Shared composition split into facets

Request: object instance `net-1`, count six, one flat-net composition frame,
24 target canvases and crops, transforms into that frame, and an opaque recipe
identifying the desired producer algorithm and seed.

Return: 24 surface entries with the same target IDs, explicit local coordinate
and rebase data, logical channels, resolved-request digest, producer/version
identity, and file hashes. Preparation restores intrinsic canvases. Imposition
binds each surface to its declared slot and applies physical placement once.
The layout declaration determines composition scope, including blank facets.

### Independent per-canvas generation

Request: the same 24 target canvases with independent generation mode, plus an
opaque recipe and explicit seed/variation policy. No shared composition
transform is needed for generation. Physical slot bindings still identify where
each resulting image belongs.

Return: 24 independently generated surface entries with the same geometry and
provenance requirements. Independence is recorded explicitly. It cannot be
inferred merely from a collection of SVG files.

### Aggregate supplied surfaces

Request: an object layout and explicit bindings from existing validated surface
bundles to its slots. The inputs include their intrinsic geometry, logical
channels and provenance. Repeated use of an asset is explicit in the bindings.

Return: an imposed artwork bundle and placement audit referencing the supplied
assets and applied transforms. No producer run is required. Any deliberate
channel mapping is recorded before catalog validation. Missing assignments,
ambiguous catalogs and incompatible dimensions produce actionable errors.

## Return contract and integrity

Retain neutral logical layers and content hashes. Each returned entry declares
its surface and canvas IDs, intrinsic extent, crop, local origin/rebase offset,
units, channel identities and source file digest. Blank surfaces remain valid
dimensioned assets. Producer metadata records the original opaque request digest
and the resolved request digest, plus the producer version and any adaptation.

The consumer compares identities, geometry and hashes against the exported
layout and recorded request. It does not reconstruct the request with the current
algorithm adapter. Integrity checks prove correspondence and tamper detection.
Algorithm validity is established by the producer's successful validation/run.
Unsupported contract versions are rejected explicitly. Output publication uses
the existing atomic-directory behavior so a failed request preserves prior output.

## Migration

Historical v1 handoffs retain their original request bytes, hashes, units and
interpretation. The old replay behavior belongs in a clearly version-scoped
compatibility reader while v1 assets are supported. Existing eight-cell handoffs
without a count continue to mean eight. New six-cell requests remain explicit.

For the new contract, store and validate the exported request directly. A
producer-side compatibility adapter can translate old Truchet controls when
needed, recording the translation. Reprocessing historical artwork creates a new
bundle with new provenance. Preserve legacy fixtures to verify returned surface
geometry, slot assignments, physical scale and channels during migration.

## Portability checks and delivery ownership

HAR-192 implements producer validation/capability resolution. HAR-193 removes
algorithm-specific export and replay dependencies. HAR-194 provides consistent
surface binding for generated and supplied assets. HAR-195 verifies all three
paths end to end with Truchet, ball-and-stick and another registered algorithm.

Acceptance includes adding an algorithm without editing imposition and adding an
object through the existing object/layout interfaces without editing producer
algorithms. New capabilities may require an explicit shared-contract revision.
Exercise blank canvases, reordered surfaces, unknown IDs, changed recipes,
unsupported transforms, multi-pass requests, mixed catalogs and physical scale.

The proposed decisions for review are explicit generation mode, explicit
composition-frame identity, producer-owned recipe resolution, and version-scoped
legacy replay. Physical validation status stays attached to the selected layout.
