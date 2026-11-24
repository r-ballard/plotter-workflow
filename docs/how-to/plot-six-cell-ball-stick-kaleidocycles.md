# Plot six-cell diagnostics and ball-and-stick samples

The prepared pack contains three different six-tetrahedron nets on one Letter
landscape sheet: crystal lattice, honeycomb nodes, and organic network, from top
to bottom. Each net is 161.291 × 65.30 mm. Margins and vertical gutters are 5 mm.
The diagnostic sheet contains two nets at the same scale: panel orientation on
top, assembled-state continuity below. Views remain provisional.

## Files and pens

From this feature worktree, the prepared pack is `output/six-cell-plot-pack/`.
Keep the complete pack together, including JSON sidecars and source bundles.

| Job | Directory below pack | Slots |
| --- | --- | --- |
| Three artwork nets with construction lines | `sheet-proof/sheet-001/front` | 1 bonds, 2 node outlines, 3 cut/fold guides |
| Two diagnostic nets with construction lines | `diagnostic-sheet/sheet-001/front` | 1 diagnostic marks, 3 cut/fold guides |
| Three artwork nets without construction lines | `sheet-artwork/sheet-001/front` | 1 bonds, 2 node outlines |

Each directory contains `design.svg`, `design.sample.hpgl`, the resolved pen
plan, placement report, preflight report, metrics, and exact HP-GL SVG preview.
`plot-preview.png` is a visual review aid, with travel omitted. The source
`design.svg` and HP-GL preserve physical scale; do not fit them to the sheet.
Individual net previews and blank observation templates are under `diagnostics/`.

Use nominal 0.3 mm pens for artwork; a light pen can draw construction lines.
These are proposed slot assignments, not a record of the loaded carriage.
SP3 draws cut/fold guides; it does not cut or score. Guides do not distinguish
mountain and valley folds. Offline checks report pen-plan PASS and placement
PASS; operator pen confirmation is still required before sending. Force remains
unmanaged by these jobs.

## At the plotting host

Commands below use Git Bash, from the feature worktree. Set `PACK` to the actual
prepared directory if using a different checkout. Choose either the proof or
diagnostic job; run each on its own sacrificial Letter landscape sheet.

```bash
export PACK=output/six-cell-plot-pack
export JOB="$PACK/diagnostic-sheet/sheet-001/front/design.sample.hpgl"
# Artwork proof instead:
# export JOB="$PACK/sheet-proof/sheet-001/front/design.sample.hpgl"

uv run --locked python scripts/job_preflight.py "$JOB" --write-report
```

Inspect the matching `design.sample.preview.svg` and loaded pens. Follow the
[plotter playbook](plotter-playbook.md) for registration, PAPER HOLD, serial
setup, and keeping the host awake. The conversion uses Letter landscape,
`letter_lower_left`, absolute coordinates and a 4 mm margin check. Paper is
registered at the DPX-3300 ANSI-D lower-left plotting-area limit.

After the physical setup and carriage check, the operator can send:

```bash
uv run --locked python scripts/send_hpgl.py --list-ports
export PORT=COM3  # replace with the actual detected port
uv run --locked python scripts/job_preflight.py "$JOB" --confirm-pen-plan --write-report
uv run --locked python scripts/send_hpgl.py --port "$PORT" --confirm-pen-plan "$JOB"
```

Require fresh placement PASS and `READY TO SEND` for the exact selected job.
Preparing this pack did not send either command or operate the hardware.

## Regenerate

Use a new destination to preserve earlier artifacts:

```bash
uv run --locked python scripts/generate_ball_stick_kaleidocycle_samples.py \
  --viz-repo ../../../viz_virtualserver --output-dir output/six-cell-plot-pack-new
```

That relative producer path assumes `.worktrees/kaleidocycle-count`. From the
main repository use `--viz-repo ../viz_virtualserver`. `--viz-python` can select
the producer interpreter explicitly. Generation creates neutral SVG jobs and
schema-3 pen plans; conversion is a separate offline step:

```bash
export SHEET=output/six-cell-plot-pack-new/sheet-proof/sheet-001/front
uv run --locked python scripts/dpx3300_convert.py \
  --input-dir "$SHEET" --output-dir "$SHEET" --file design.svg \
  --page-size letter --landscape --paper-position lower-left --margin 4mm --absolute
uv run --locked python scripts/preview_hpgl.py --hpgl "$SHEET/design.sample.hpgl" \
  --preview "$SHEET/design.sample.preview.svg" --metrics "$SHEET/design.sample.metrics.json"
uv run --locked python scripts/job_preflight.py "$SHEET/design.sample.hpgl" --write-report
```

Repeat with `diagnostic-sheet` or `sheet-artwork` when needed. Reconfirm pens
after any plan change and reconvert if the source, pen plan or placement changes.
