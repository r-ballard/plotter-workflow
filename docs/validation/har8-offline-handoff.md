# HAR-8 offline handoff and physical session record

HAR-8 and HAR-10 remain In Progress until the supervised walkthrough passes.
Use the [complete operator guide](../how-to/impose-and-plot-polygon-bundle.md)
for hardware setup, transmission, repeat and recovery commands. This record
collects observations; it does not replace the guide or per-job preflight.

## Prepared local job

Retained in the main plotter-workflow checkout:
`output/hardware-acceptance/har8-polygon-guide/`.
Generated files are ignored by Git and are not installed by merging this PR.
No ZIP upload is required.

- `cootie-artwork.imposed.svg`: twenty-surface artwork on Letter landscape.
- `cootie-artwork.imposed.guides.svg`: separate construction reference, not merged into artwork.
- `cootie-artwork.imposed.imposition.json`: layout audit.
- `cootie-artwork.imposed.hpgl`: actual converted job.
- Adjacent placement, resolved pen-plan and preflight JSON: retain with HP-GL.
- `cootie-artwork.hpgl-preview.svg` and `cootie-artwork.metrics.json`: offline path inspection.
- `conversion.log` and `preflight.log`: software evidence.

Regenerate using steps 1-5 of the operator guide, substituting this output
folder for `output/cootie-production`. Generate the source bundle using the
linked polygon-artwork guide if it is absent; the retained source for this run
is the viz_virtualserver guide-validation worktree's
`output/cootie-design-bundle/`. Do not copy sidecars from an older conversion.

To regenerate the HP-GL preview from Git Bash at the repository root:

```bash
uv run --locked python scripts/preview_hpgl.py \
  --hpgl output/hardware-acceptance/har8-polygon-guide/cootie-artwork.imposed.hpgl \
  --preview output/hardware-acceptance/har8-polygon-guide/cootie-artwork.hpgl-preview.svg \
  --metrics output/hardware-acceptance/har8-polygon-guide/cootie-artwork.metrics.json \
  --overwrite
```

The preview is read-only with respect to the job; it does not transmit.

## Offline evidence, 2026-11-20

Runtime base: plotter-workflow `3ff38ea` (merged PR24). Reimposed the retained
20-surface bundle, converted and preflighted using current code. Letter
landscape, lower-left paper position, preserved scale, 3 mm margin, absolute
coordinates. Pen order SP1 then SP0; pen plan and placement PASS. Preview:
137 strokes, 2490 pen-down segments, 3525.524 mm pen-down travel.

HP-GL SHA-256:
`c85ac6330cb277d24ad9aacf8fb1bc073f492e2cde1e686e4f2e90b3294c5fae`.

This is the guide's unmanaged single-pen example. Preflight reports
`READY TO SEND`, while carriage documentation reports FAIL because the
physical tool is not documented. That software single-pen gate does not
establish that slot 1 is loaded or correct. Record and inspect the actual pen
before sending. Force remains unmanaged. No pen confirmation, serial
connection, physical plotting or folding was performed.

## Physical session record

Copy this section to a local observations file before filling it in. Record
results in HAR-8/HAR-10; retain photos and job files locally with links as needed.
An unchecked item is pending, not passed.

- Date/operator, plotter, COM port, stock, pen/adapter and physical slot:
- HP-GL path and current SHA-256; preflight report path:
- Host sleep prevention setting, checked for the full attended plot:
- [ ] Inspect artwork, construction reference and HP-GL preview.
- [ ] Verify current preflight, page placement and actual pen in slot 1.
- [ ] Follow guide setup; load sacrificial Letter paper in lower-left position.
- [ ] First plot: record pen pickup, initial motion, clipping and pen return.
- [ ] Measure scale: finished square should be 215.9 x 215.9 mm; record measurements.
- [ ] Trim the 63.5 mm strip, fold, and record orientation of all 20 surfaces.
- [ ] Check selector/reveal pairings and seams; record photos/discrepancies.
- [ ] Repeat on a second sheet after all motion stops, without routine BUFFER CLEAR.
- [ ] Record second pen pickup, placement consistency and normal completion.
- Recovery needed? Record cause, PAUSE, ENTER + UR buffer clear, power cycle,
  indicators and one retry outcome only if the guide's recovery procedure was used.
  Otherwise mark recovery unexercised; do not infer acceptance.
- [ ] Finish using guide shutdown steps and retain both sheets and job records.
- Documentation discrepancies and corresponding corrections:
- Unexercised checks and follow-up defects:

Close HAR-8/HAR-10 only after their required physical checks have evidence.
A successful run of this single-pen bundle does not establish HAR-14's
three-pen orbital-artwork acceptance.
