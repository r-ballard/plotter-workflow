# Kaleidocycle

Implement the agreed state-based composition model using existing slots,
orientation frames, artwork layouts, neutral logical layers, and export/return
contracts. The reference has eight alternating columns of four triangular
faces (32 artwork panels), grouped visually into four repeated segments.
Use normalized net geometry with its aspect ratio retained in millimetres.

Approaches: a separate triangle renderer would duplicate composition and
provenance handling; a continuous 3D simulator exceeds the agreed scope.
Extend the existing assembled-artwork pipeline with convex polygon crops
and explicit named viewing profiles instead, as agreed in conversation.

Provide A-D provisional, illustrative assembled profiles, with explicit panel
transforms and paired edges. Do not infer physical adjacency from flat net
contact or claim these profiles have been physically validated. Profiles must
check shared endpoints and unique panel identities. A later physical fold test
can correct or validate the declared profiles without changing panel IDs.

The object owns triangle slots, cut/fold guides, glue tabs, and placement.
Composition uses local triangle bounding boxes and explicit affine matrices;
imposition maps restored local canvases back to net coordinates exactly once.
Artwork and construction guides are separate artifacts. Preserve neutral layer
catalogs and SVG provenance. Reject unknown slots, duplicate assignments,
unsafe sources, invalid geometry, and incomplete 32-panel manifests.

Transitions are deferred. State IDs remain stable so future directed A-to-B
records can reference them. The eight-page object refactor remains backlog.
