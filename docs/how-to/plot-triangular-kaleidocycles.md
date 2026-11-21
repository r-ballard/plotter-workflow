# Plot the three triangular Truchet kaleidocycles

Run these commands in **Git Bash** on the Windows plotting host, from the
`plotter-workflow` repository. This plots the three different sample nets on
one Letter landscape sheet, including cut/fold guide lines. It does not repeat
one design three times. Generation and conversion do not send to the plotter.

## Generate and assign pens

```bash
cd /c/Users/hardcase/Documents/developer/codex-repos/plotter-workflow
uv sync --locked
uv run --locked python scripts/generate_triangular_kaleidocycle_samples.py \
  --viz-repo ../viz_virtualserver --output-dir output/triangle-review

export SHEET=output/triangle-review/sheet-proof/sheet-001/front
cp examples/penplans/triangular-kaleidocycle.penplan.json "$SHEET/design.penplan.json"
```

If using the original PR26 worktree, `cd` to that worktree instead; its existing
`output/triangle-review` can be used directly, without regenerating. To regenerate
a recognized existing sample directory, add `--overwrite` deliberately. Preserve
the complete generated directory tree and its relative source references.

The supplied schema-3 plan has one pass, `sample`, with these example assignments:

| Slot | Logical layers | Suggested tool |
| --- | --- | --- |
| 1 | `curve` | 0.3 mm outline pen |
| 2 | `vertex-fill` | 0.3 mm hatch pen |
| 3 | `interstitial-fill` | 0.3 mm dot pen |
| 4 | `sheet-cut-guides`, `sheet-fold-guides` | Light construction-line pen |

Edit the copied plan to match the pens actually loaded. The slots are examples,
not a claim about the current carriage. The fill clearance was designed for a
nominal 0.3 mm pen; review larger pens before plotting. Slot 4 **draws** guides;
it is not a knife or scoring command. Cut and fold guides share a pen and do not
encode mountain/valley direction. Glue tabs contain no artwork.

Open `$SHEET/design.svg` and inspect all three nets. Keep its adjacent
`design.json` and `design.imposition.json` in place. The sheet is already imposed
at 279.4 × 215.9 mm; do not fit, rotate, crop, or resize it. Each net occupies
213.531 × 65.30 mm, with 5 mm margins/gutters. Do not plot `net-preview.svg`,
which includes diagnostic labels.

## Dry-run, convert, and inspect the exact HP-GL

```bash
uv run --locked python scripts/dpx3300_convert.py \
  --input-dir "$SHEET" --output-dir "$SHEET" --file design.svg \
  --page-size letter --landscape --paper-position lower-left \
  --margin 4mm --absolute --dry-run

uv run --locked python scripts/dpx3300_convert.py \
  --input-dir "$SHEET" --output-dir "$SHEET" --file design.svg \
  --page-size letter --landscape --paper-position lower-left \
  --margin 4mm --absolute

export JOB="$SHEET/design.sample.hpgl"
uv run --locked python scripts/preview_hpgl.py --hpgl "$JOB" \
  --preview "$SHEET/design.sample.preview.svg" \
  --metrics "$SHEET/design.sample.metrics.json"
uv run --locked python scripts/job_preflight.py "$JOB" --write-report
```

The 4 mm converter margin checks the already imposed placement; it does not
replace the 5 mm design margin. Expect `design.sample.hpgl`,
`design.sample.resolved.penplan.json`, and `design.sample.placement.json`.
Review the resolved slot mapping, Letter landscape lower-left placement,
pen-down preview, travel, and metrics. Require pen-plan and placement PASS.
Offline multipen preflight may report operator confirmation required; do not
claim confirmation until checking the physical carriage. If conversion outputs
already exist, use `--overwrite` only intentionally and repeat preview/preflight.

## At the DPX-3300

Follow the [serial playbook](plotter-playbook.md) for switch settings, cable and
origin setup. The established serial connection is 9600 baud, 8N1, XON/XOFF.
Load the planned pens and a sacrificial Letter landscape sheet in the lower-left
ANSI-D paper position, engage PAPER HOLD, and keep the host awake throughout
transmission and all motion. Confirm the actual port rather than assuming COM3.

The commands below are **operator actions that send to hardware**. Run only after
inspecting the loaded pens, sheet registration, preview and placement report:

```bash
uv run --locked python scripts/send_hpgl.py --list-ports
export PORT=COM3  # replace with the detected plotter port
uv run --locked python scripts/job_preflight.py "$JOB" \
  --confirm-pen-plan --write-report
uv run --locked python scripts/send_hpgl.py --port "$PORT" \
  --confirm-pen-plan "$JOB"
```

Require `READY TO SEND` and placement PASS for the exact current job. The sender
runs fresh preflight before opening the port. Watch initial motion, slot changes,
scale and sheet limits; stop the machine if motion is wrong. Transmission
completion does not prove motion has stopped. Wait before releasing PAPER HOLD.
Keep the HP-GL and all sidecars/reports together.

Cut and assemble a sacrificial net to inspect panel order, closure and seam
continuity. The A–D square-fan profiles remain provisional; this artwork set has
not been physically validated. This guide documents sending commands; preparing
the documentation does not execute them.

For artwork without construction lines, use `sheet-artwork/sheet-001/front`
instead and remove the two guide IDs from the copied plan. Its catalog has only
the three artwork layers; do not apply the five-layer proof plan unchanged.
