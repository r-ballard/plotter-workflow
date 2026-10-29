# J-card physical sample plots

All three SVGs are A3 landscape (420 x 297 mm). Trim is exactly 406.4 x 101.6 mm.

1. fit-proof/front/design.svg: guide-only cut/fold/registration proof. Plot on scrap, measure the 406.4 mm trim width and 101.6 mm height, cut, roll-fold extensions and check cassette case fit.
2. artwork/front/design.svg: continuous Truchet curves; title/spine intentionally blank.
3. artwork/back/design.svg: independent panel artwork with hatching.

The artwork pair uses LEFT-RIGHT flipping around the sheet's vertical axis. Complete the front job, idle the arm, flip/register the paper, and start the back as a separate job. Keep the sheet landscape. Registration is the asymmetric three-cross pattern.

Cut/fold/registration are separate logical channels. They are ink, not machine cutting instructions. For a one-pen proof map all wanted channels to one physical pen in your pen plan. The artwork back also contains the fill channel. Inspect each design.json catalog before conversion. Do not plot a diagnostic sheet-preview.svg.

Keep design.svg, design.json and design.imposition.json together in each face directory. Use the existing converter/preflight workflow with A3 landscape and preserved layout; do not fit to content or resize. Confirm A3 fits the configured plotter usable area. No HPGL was transmitted. These samples do not yet include dedicated vector panel-number/orientation glyphs like the cootie fixture.

Software converter dry run was checked for all three sheets. Hardware, registration and cassette-case fit remain physical acceptance tasks (HAR-88).

## Location and regeneration

The generated files are retained in the jcard-object worktree under output/jcard-physical-samples/. The output directory is ignored by Git; merging the PR does not install these generated files in another checkout.

To regenerate, follow docs/how-to/cassette-jcard.md with examples/jcard/both.json and set all three guides flags to true. Export, generate, prepare and impose the two artwork faces. For the guide-only proof, select front only, remove back_artwork, and put front-panel-1 through front-panel-8 in front_artwork.blank_panels. Reuse the complete prepared front bundle; all eight sources remain required. Keep the same A3 sheet and left-right flip convention.

Record measured trim size, fold positions, duplex offset, stock thickness and cassette-case fit in HAR-88. Physical plotting is deferred and does not block the software PR merge.

