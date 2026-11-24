# Parameterized kaleidocycle count

Approved direction: default to six tetrahedra; accept even integer counts of at
least six. Keep the existing imposition abstractions uniform. Physical validation
is being conducted by the owner; no folded-view acceptance is implied.

## Approaches

Use one count parameter throughout the existing object, artwork handoff, native
preparation, and packing pipeline. The owner selected total-net `width_mm` sizing
over a cell-size control. Separate six-cell generators would duplicate the
pipeline and are unnecessary.

## Contract

- `tetrahedron_count` defaults to 6 for new object/config/CLI requests. Reject
  booleans, non-integers, odd counts, and counts below six.
- Object-owned normalized geometry supplies four triangular slots per cell,
  construction tabs, guides, and the count-dependent aspect ratio.
- Preserve current triangle proportions. In existing construction units the net
  width is `2 * tetrahedron_count + 0.35`, and height is 5. Total `width_mm`
  includes tabs; derive height and scale uniformly. Preserve standalone sheet
  fitting and exact-scale packing behavior.
- Count belongs to the object/request and travels in layout settings and audit
  metadata. Reject artwork/config count mismatches before writing output.
- Existing eight-cell examples, fixtures, and regeneration scripts explicitly
  request eight. Legacy handoffs with no count identify the historical eight-cell
  layout; newly generated handoffs always record their count. Do not silently
  reinterpret legacy assets as six-cell assets.
- Retain the existing eight-cell illustrative projection exactly. Other counts
  require deterministic illustrative arrangements with shared seam endpoints,
  using the current affine-panel contract. All remain provisional. No kinematic
  solution or physical validation claim is in scope.
- No cell-size control, triangle-shape control, new shared imposition protocol,
  producer schema redesign, or hardware operation is required.

## Acceptance

Cover default six, explicit eight, and larger even counts; invalid inputs;
unchanged eight-cell geometry; scale/aspect-ratio preservation; closed cut/fold
geometry; artwork seam validation and return assignments; mismatched counts;
standalone and packed outputs. Provide a labeled six-cell diagnostic net using
the existing preview mechanism. Run affected consumers and the repository suite.
