# Plot a neutral logical-layer booklet

This Git Bash procedure takes a neutral `viz-logical-layers/v1` bundle through
imposition, a v2 pen plan, conversion, preflight, and DPX-3300 sending. The
logical layer IDs come from the bundle's `design.json`; physical `SP1`–`SP8`
slots are assigned by this repository. Keep the bundle, imposition audit,
pen plan, resolved pass sidecars, and preflight reports with the finished job.

Commands through preflight are software operations. Loading pens and sending
HP-GL require an operator at the plotter. Use a sacrificial sheet for the first
registered multipass plot.

## 1. Check the bundle and impose it

Set paths in Git Bash, using forward slashes:

```bash
export PLOTTER_REPO=/c/path/to/plotter-workflow
export BUNDLE_DIR=/c/path/to/neutral-booklet-bundle
cd "$PLOTTER_REPO"
uv sync
test -f "$BUNDLE_DIR/design.json"
```

A neutral bundle generated in `viz_virtualserver` with
`scripts/generate_domain_bundle.py` from
`examples/domain-jobs/orbital-per-body.json` does not include `booklet.json`.
If it is missing, save this software-only eight-page manifest example as
`$BUNDLE_DIR/booklet.json` before continuing. The example is a software
fixture, not a finished physical booklet design; inspect and adjust each page
for any real artwork.

```json
{
  "schema_version": 1,
  "layout": "pocketmod8",
  "pages": [
    { "page": 1, "source": "surfaces/square.svg" },
    { "page": 2, "source": "surfaces/triangle.svg" },
    { "page": 3, "source": "surfaces/pentagon.svg" },
    { "page": 4, "source": "surfaces/square.svg" },
    { "page": 5, "source": "surfaces/triangle.svg" },
    { "page": 6, "source": "surfaces/pentagon.svg" },
    { "page": 7, "source": "surfaces/square.svg" },
    { "page": 8, "source": "surfaces/triangle.svg" }
  ]
}
```

```bash
test -f "$BUNDLE_DIR/booklet.json"
```

Read `design.json` for its ordered `logical_layers` IDs and the source surface
inventory. Read `booklet.json` for the intended page sources and fit. Verify
every referenced SVG exists inside the bundle. The manifest, SVG hashes, and
layer catalog are validated again during imposition; stop on any mismatch.

```bash
mkdir -p output/neutral-booklet
uv run python scripts/booklet_impose.py "$BUNDLE_DIR" \
  --manifest booklet.json \
  --sheet-size letter \
  --guides \
  --output output/neutral-booklet/booklet.imposed.svg
```

The result is `booklet.imposed.svg` with an adjacent
`booklet.imposed.imposition.json` audit and separate guides SVG. Open both
SVGs to inspect page order, orientation, clipping, and margins. Keep guides
out of the artwork job. Use `--overwrite` only when deliberately regenerating
the imposed output; recheck the audit and plan afterward.

## 2. Assign logical layers to physical passes

Copy the sample v2 plan, then edit **every** layer ID and slot assignment to
match the actual `design.json` catalog and loaded pens:

```bash
cp examples/penplans/logical-multipass.penplan.json \
  output/neutral-booklet/booklet.imposed.penplan.json
```

The sample's `orbit`, `accent`, and `body-*` names are placeholders. Its
`passes` array controls output and send order. Each assignment names one or
more logical IDs and a physical slot from 1 through 8. Declare intentionally
omitted layers in `omitted_layers`, and IDs deliberately used in multiple
passes in `repeated_layers`. Do not silently leave layers out. The adjacent
plan is discovered automatically; an explicit `--pen-plan PATH` is also
supported. See `penplan.schema.json` for the contract.

Write down the intended ink or tool in each slot and the pass order before
conversion. The v2 resolved sidecar records layer and slot assignments; it
cannot sense the pen installed in the carriage.

## 3. Preview, then convert

For Letter landscape paper at the lower-left ANSI-D position, preview the
commands and planned artifacts first:

```bash
uv run python scripts/dpx3300_convert.py \
  --input-dir output/neutral-booklet \
  --output-dir output/neutral-booklet \
  --file booklet.imposed.svg \
  --page-size letter --landscape --paper-position lower-left \
  --margin 4mm --absolute --dry-run
```

The dry run checks the input and prints planned pass paths without creating
HP-GL. Use a margin compatible with the imposition; an already imposed SVG
is not refitted by the converter. Review pass order, layer membership, page
profile, and intended physical slots. Stop if any differs from the plan.

Run the same command without `--dry-run` to create the jobs:

```bash
uv run python scripts/dpx3300_convert.py \
  --input-dir output/neutral-booklet \
  --output-dir output/neutral-booklet \
  --file booklet.imposed.svg \
  --page-size letter --landscape --paper-position lower-left \
  --margin 4mm --absolute
```

For each pass ID, the converter writes `<svg-stem>.<pass-id>.hpgl` with
`<svg-stem>.<pass-id>.resolved.penplan.json` and
`<svg-stem>.<pass-id>.placement.json` beside it; the pass ID appears in all
three names. For pass ID `warm` on `booklet.imposed.svg`, expect
`booklet.imposed.warm.hpgl`, `booklet.imposed.warm.resolved.penplan.json`,
and `booklet.imposed.warm.placement.json`. Inspect the generated
filenames and resolved carriage table. Do not execute an `.hpgl` file as a
shell command. The converter does not send neutral jobs directly; send each
validated pass in plan order with `scripts/send_hpgl.py`.

## 4. Preflight each pass

Set `PASS_ID` to the first ID in the plan; repeat this section for each pass:

```bash
export PASS_ID=warm
export JOB="output/neutral-booklet/booklet.imposed.${PASS_ID}.hpgl"
uv run python scripts/job_preflight.py "$JOB"
```

Read the reported logical layers, physical carriage slots, actual HP-GL pen
order, sheet profile, drawing bounds, and placement result. Preflight checks
the current HP-GL against the resolved sidecar and placement report. It
cannot recheck original bundle hashes from HP-GL alone. A pass using more
than one physical pen requires operator confirmation. After checking the
loaded slots against the displayed mapping, record the review:

```bash
uv run python scripts/job_preflight.py "$JOB" --confirm-pen-plan --write-report
```

For a single-pen pass, `--confirm-pen-plan` may be omitted. Proceed only when
the exact job reports `READY TO SEND` and placement `PASS`. If HP-GL or any
sidecar is regenerated, run preflight again. See `JOB_PREFLIGHT.md` for the
report and confirmation rules.

## 5. Send registered passes

Follow `playbook.md` to configure the DPX-3300 serial interface and paper
position before power-up. The established serial settings are 9600 baud,
8 data bits, no parity, one stop bit, and XON/XOFF. Load and test the pens
listed by the resolved carriage plan. Load a sacrificial Letter sheet at the
lower-left ANSI-D position and engage PAPER HOLD. Check the detected port:

```bash
uv run python scripts/send_hpgl.py --list-ports
```

Replace `COM3` and `PASS_ID` with the actual port and the first pass ID:

```bash
export PASS_ID=warm
export JOB="output/neutral-booklet/booklet.imposed.${PASS_ID}.hpgl"
uv run python scripts/send_hpgl.py --port COM3 --confirm-pen-plan "$JOB"
```

The sender runs a fresh preflight before opening the port. It requires
`--confirm-pen-plan` for a multi-pen pass. Watch first motion, pen selection,
scale, and sheet boundaries; pause or power off if motion is unsafe. Wait for
physical motion to stop, then send the next pass with its own `PASS_ID` and
preflight. Keep the **same sheet registered in place** between passes; do not
release PAPER HOLD or move the media. A completed serial transmission does
not prove that the plotter has stopped drawing.

The logical-layer multipass workflow has software integration coverage, but
has not been validated on a physical plotter. Verify registration and folding
on sacrificial media before production use.
