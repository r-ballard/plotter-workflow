# Impose and plot a polygon SVG bundle

This guide starts with the 20 placement-free surface SVGs produced by
`viz_virtualserver` and ends with a plotted one-sheet cootie catcher on a
Roland DPX-3300. It uses Windows, Git Bash, and `uv`.

Stop at every checkpoint. Commands through preflight are repeatable software
operations. Loading media, confirming pens, and transmitting HP-GL affect
physical hardware and require operator judgment.

## What each repository owns

`viz_virtualserver` creates artwork in each polygon's intrinsic design space.
Its bundle contains `design.json`, `design.svg`, and one SVG per semantic
surface. Those SVGs deliberately have no sheet placement.

`plotter-workflow` owns physical placement and output: it maps the 20 semantic
surface names onto a cootie-catcher sheet, assigns logical layers to physical
pen slots when needed, converts the imposed SVG to HP-GL, validates placement,
and sends the job.

The handoff is the surface bundle plus a separate `cootie.json` placement
manifest. Do not add sheet coordinates to the source domain job.

## Before you begin

You need:

- both repositories checked out locally;
- Git Bash;
- `uv` and Python 3.12;
- the completed 20-surface bundle from the polygon-artwork guide;
- a powered-off DPX-3300 while checking interface switches;
- sacrificial Letter paper and a tested pen for the first plot;
- the correct data cable, with the serial workflow using the plotter's
  `SERIAL IN` connector; and
- permission to use the plotter and its serial port.

Open Git Bash and set paths for your machine. Use forward slashes and quote the
variables every time:

```bash
export VIZ_REPO=/c/path/to/viz_virtualserver
export PLOTTER_REPO=/c/path/to/plotter-workflow
export BUNDLE_DIR="$VIZ_REPO/output/cootie-design-bundle"
```

For example, a Windows path such as
`C:\Users\you\Documents\codex-github\plotter-workflow` becomes
`/c/Users/you/Documents/codex-github/plotter-workflow` in Git Bash.

Confirm that all 20 source SVGs exist:

```bash
find "$BUNDLE_DIR/surfaces" -maxdepth 1 -type f -name '*.svg' | sort
find "$BUNDLE_DIR/surfaces" -maxdepth 1 -type f -name '*.svg' | wc -l
```

The count must be `20`, with `outer-1` through `outer-4`, `selector-1`
through `selector-8`, and `reveal-1` through `reveal-8`. Stop if it is not.

Set up the plotting project:

```bash
cd "$PLOTTER_REPO"
uv python install 3.12
uv sync
uv run python -m pytest -q
```

## 1. Add the placement manifest

Copy the checked-in manifest into the generated bundle:

```bash
cp examples/cootie-bundle/cootie.json "$BUNDLE_DIR/cootie.json"
```

The manifest maps each semantic slot to the identically named file under
`surfaces/`. It requires all 20 slots exactly once. The slot controls physical
placement; array position and filename sorting do not.

Inspect it before imposition:

```bash
sed -n '1,240p' "$BUNDLE_DIR/cootie.json"
```

To swap artwork between panels, change the relevant `source` values while
leaving each `slot` unchanged. Sources must be SVG files inside `BUNDLE_DIR`.

Checkpoint: confirm that every intended `outer-N`, `selector-N`, and
`reveal-N` is paired with the correct source. In particular,
`selector-N` and `reveal-N` are an interaction pair.

## 2. Impose the artwork

Create the physical Letter-landscape composition and a separate construction
guide:

```bash
mkdir -p output/cootie-production

uv run python cootie_impose.py "$BUNDLE_DIR" \
  --manifest cootie.json \
  --sheet-size letter \
  --square-position left \
  --panel-margin-mm 3 \
  --guides \
  --output output/cootie-production/cootie-artwork.imposed.svg
```

Expected files:

```text
output/cootie-production/cootie-artwork.imposed.svg
output/cootie-production/cootie-artwork.imposed.imposition.json
output/cootie-production/cootie-artwork.imposed.guides.svg
```

The artwork and construction guide are separate plot jobs. Do not merge fold
or trim guides into the production artwork.

The default Letter layout creates a 215.9 mm square aligned to the left edge,
leaving a 63.5 mm strip to trim. The imposed SVG records that its physical
layout must be preserved downstream. Its orientation table is still marked
`provisional`; software tests do not prove how every panel reads after folding.

Open the artwork SVG and the guide SVG in a viewer. Check all 20 panels,
clipping, orientation, margins, the square position, and the single trim line.
Also inspect the audit:

```bash
sed -n '1,260p' \
  output/cootie-production/cootie-artwork.imposed.imposition.json
```

Checkpoint: do not convert until the flat sheet is visually correct. For a new
orientation or asymmetric design, plan a sacrificial plot-and-fold test.

If you intentionally regenerate the outputs, add `--overwrite` to the
imposition command. Without it, existing generated files are protected.

## 3. Understand layers before assigning pens

Logical artwork layers belong to the SVG. Physical pens are DPX-3300 carriage
slots `SP1` through `SP8`. Imposition preserves strict top-level `pen-N`
contracts, but generic SVG sources are flattened to one logical output layer.

The current `viz_virtualserver` cootie-catcher example produces generic
per-surface SVGs. Its imposed artwork is therefore a single-pen job and does
not need a pen-plan JSON. The converter will use `SP1` and finish with `SP0`.

If a future bundle uses strict `pen-N` layers, create an adjacent input plan
named after the imposed SVG, for example:

```text
output/cootie-production/cootie-artwork.imposed.penplan.json
```

Use `policy: "preserve"` to keep logical layer 1 on physical slot 1, layer 2
on slot 2, and so forth. Use `compact` to pack only active layers into the
lowest slots, or `explicit` for a deliberate mapping. Document a `label` or
`tool` for every physical slot used by a multi-pen job. See `PEN_PLAN.md` and
`penplan.schema.json` for the complete schema.

An adjacent `.penplan.json` is automatically authoritative. Do not combine it
with `--pen-policy` or `--pen-map`; doing so produces:

```text
ERROR: Do not combine a .penplan.json file with --pen-policy or --pen-map
```

Generation numbers do not automatically equal physical pen numbers. They do
so only when the SVG's logical layers and the selected pen policy establish
that mapping. Always follow the converter's resolved carriage table.

## 4. Convert the imposed SVG to HP-GL

For Letter paper placed at the lower-left of the ANSI-D plotting area, set
SW-1 switch 7 ON while the plotter is powered off. The DPX-3300 reads switches
at power-up.

Convert the artwork:

```bash
uv run python dpx3300_convert.py \
  --input-dir output/cootie-production \
  --output-dir output/cootie-production \
  --file cootie-artwork.imposed.svg \
  --page-size letter \
  --landscape \
  --paper-position lower-left \
  --margin 3mm \
  --absolute \
  --overwrite \
  --verbose
```

Use `3mm` here because the imposed artwork was created with a 3 mm panel
margin and its physical layout is preserved. A larger converter margin can
correctly reject this drawing as outside the allowed bounds. The converter
does not refit an already imposed SVG.

Expected files for the current single-pen example:

```text
output/cootie-production/cootie-artwork.imposed.hpgl
output/cootie-production/cootie-artwork.imposed.placement.json
```

A strict layered job additionally creates:

```text
output/cootie-production/cootie-artwork.imposed.resolved.penplan.json
```

Inspect HP-GL as data; never execute it as a shell script:

```bash
head -c 1000 \
  output/cootie-production/cootie-artwork.imposed.hpgl
printf '\n'
```

You should see ordinary commands such as `IN;`, `SP1;`, `PU`, `PD`, and a
terminal `SP0;`. In lower-left Letter placement, coordinates normally lie in
the negative ANSI-D Letter window documented in `README.md`.

If Git Bash prints many messages such as `IN: command not found` or
`SP1: command not found`, the HP-GL filename was accidentally entered as a
command—usually because a malformed line continuation ended the Python
command. Use one backslash as the final character of each continued line. Do
not use PowerShell backticks in Git Bash.

## 5. Run software preflight

Run preflight without claiming that the carriage has been checked:

```bash
uv run python job_preflight.py \
  output/cootie-production/cootie-artwork.imposed.hpgl
```

For the current single-pen bundle, expect `SP1 -> SP0`, placement `PASS`, and
`READY TO SEND`. A multi-pen job initially reports
`VALIDATED - OPERATOR CONFIRMATION REQUIRED`.

Review the reported page profile, margin, coordinate mode, drawing bounds,
pen order, and carriage table. Confirm that they match the intended sheet and
tools.

After physically checking every used carriage slot, write the audit report.
For the single-pen example:

```bash
uv run python job_preflight.py \
  output/cootie-production/cootie-artwork.imposed.hpgl \
  --write-report
```

For a multi-pen job, add `--confirm-pen-plan` only after loading and checking
the printed carriage plan:

```bash
uv run python job_preflight.py \
  output/cootie-production/cootie-artwork.imposed.hpgl \
  --confirm-pen-plan \
  --write-report
```

The report is
`output/cootie-production/cootie-artwork.imposed.preflight.json` and includes
a SHA-256 digest of the exact HP-GL reviewed. Regenerating or editing the HP-GL
invalidates that review; run preflight again.

Checkpoint: proceed only when the exact job reports `READY TO SEND`, its
placement is `PASS`, its bounds are plausible, and every used physical pen is
loaded, seated, tested, and matches the displayed plan.

## 6. Prepare the DPX-3300 serial connection

The established serial configuration is 9600 baud, 8 data bits, no parity,
one stop bit, and XON/XOFF flow control. Before power-up, verify the complete
switch table in `playbook.md`. Key settings include:

- cable connected to `SERIAL IN`;
- SW-1 switch 5 ON for serial;
- SW-1 switch 6 OFF for direct connection;
- SW-2 switch 5 ON for XON/XOFF;
- baud dial at 14 for 9600 baud; and
- SW-1 switch 7 ON for ANSI-D Letter lower-left placement.

Power-cycle after changing switches. Confirm that the `SERIAL/PARALLEL`
indicator is green; red means the plotter is still configured for parallel
operation. Confirm that the PAPER HOLD indicator is off, load and align the
sacrificial Letter sheet at the lower-left ANSI-D position, press PAPER HOLD,
and confirm that its indicator is on and the sheet is held flat. Keep a hand
near PAUSE and be ready to power off if motion leaves the expected area.

List serial ports from Git Bash:

```bash
uv run python send_hpgl.py --list-ports
```

On Windows the result is typically `COM3` or another `COMN` name. Close any
other program holding that port.

## 7. Send the physical plot

Replace `COM3` with the detected port. For the current single-pen example:

```bash
uv run python send_hpgl.py \
  --port COM3 \
  output/cootie-production/cootie-artwork.imposed.hpgl
```

For a multi-pen job, the sender requires the same physical confirmation:

```bash
uv run python send_hpgl.py \
  --port COM3 \
  --confirm-pen-plan \
  output/cootie-production/cootie-artwork.imposed.hpgl
```

The sender reruns preflight before opening the serial port, writes a fresh
preflight audit, sends in chunks, honors XON/XOFF, and waits for the host serial
buffer to drain. “Transmission complete” means the bytes were sent; continue
watching until the plotter has physically stopped.

During the first run, verify the first pen selection, origin, scale, direction,
and sheet boundary before allowing the full plot to continue. Pause or power
off immediately if the motion is unsafe.

At normal completion, the final `SP0;` returns the tool to pen stock. The
carriage moving to the lower-left afterward is expected.

## 8. Repeat a completed job

There is not yet a dedicated “repeat completed job” command. A repeat is a new
send of the same preflighted HP-GL file.

1. Wait until all physical motion has stopped and the tool has been returned.
2. Press PAPER HOLD and confirm that its indicator is off before removing the
   first sheet. Load a new sheet in exactly the same position, press PAPER HOLD,
   and confirm that its indicator is on and the sheet is held flat.
3. Check that the required pen is fully seated in its stock position and that
   the carriage is not in an error state.
4. Rerun the same `send_hpgl.py` command. Do not execute the `.hpgl` file.
5. Watch the first pickup and initial motion before letting the repeat continue.

Previously observed behavior: after one successful job, using PAUSE and BUFFER
CLEAR before rerunning led to a flashing error and an unsuccessful `SP1`
pickup. `UR` is the upper-right position key, but in this context it is also
part of the buffer-clear chord; it is not a separate “ready” command.

Use this recovery sequence if a job must be aborted or a pen pickup fails:

1. Press PAUSE once and wait for motion to stop. Pressing PAUSE again by itself
   resumes buffered drawing, so do not do that when aborting.
2. To discard the queued plotter data, hold ENTER and press `UR`. This is the
   DPX-3300 BUFFER CLEAR operation and is destructive to the queued job.
3. Wait until the machine is stationary. Press PAPER HOLD and confirm its
   indicator is off before touching or removing the sheet.
4. Power the plotter off. Inspect and reseat the intended pen in its stock
   position; do not force or reposition the carriage by hand.
5. Power on. The carriage should initialize to the upper-right corner. Confirm
   that the ERROR indicator is off and the `SERIAL/PARALLEL` indicator is
   green. If either check fails, stop and consult the operation manual rather
   than resending.
6. Reload and align the sheet, enable PAPER HOLD, rerun preflight, and then
   resend once while watching the first pickup.

BUFFER CLEAR is only for abort/recovery, not a routine step between completed
jobs. Never resend while the previous job is still buffered or moving.
The sequence—press PAUSE, then hold ENTER while pressing `UR`—is documented in
section 5.1 of the
[DPX-3300 operation manual](https://lesporteslogiques.net/materiel/plotter_roland_DPX-3300/DPX-3300_operation_manual.pdf).

## 9. Recover from common failures

### `Do not combine a .penplan.json file...`

The converter found an adjacent user-authored plan while command-line
`--pen-policy` or `--pen-map` was also supplied. Choose one source of truth:
use the JSON plan and remove the CLI options, or deliberately rename/remove
the adjacent plan and use CLI assignment.

### Placement margin violation

For preserved-layout cootie artwork, make the conversion margin agree with the
nearest imposed geometry. The documented 3 mm imposition uses `--margin 3mm`.
Do not reduce a margin merely to silence an unexpected failure; inspect the
imposition audit and drawing bounds first.

### Preflight says a sidecar is missing or stale

Rerun `dpx3300_convert.py`, then preflight the newly generated HP-GL and its
adjacent sidecars. Do not copy an old sidecar onto a new file.

### No serial ports detected

Check power, USB adapter seating, Device Manager, the assigned COM number, and
whether another application has the port open. Reconnect the adapter and run
`--list-ports` again.

### Plot starts and stops

Confirm 9600 8N1 and XON/XOFF on both ends, especially SW-2 switch 5 ON. Check
that RTS/CTS and DSR/DTR are not enabled, reconnect the adapter, and try a
small known-good job before this full sheet.

### Flashing error or failed pen pickup

Do not repeatedly resend. Follow the six-step abort/recovery procedure in
“Repeat a completed job”: PAUSE, hold ENTER and press `UR` only when discarding
the queued job, release PAPER HOLD, power off for inspection, then power on and
require normal ERROR and interface indicators before one retry. If the error
persists, stop and consult the operation manual.

## 10. Finish and shut down safely

After the job completes:

1. wait for all motion to stop;
2. verify the final pen was returned and the carriage is clear;
3. press PAPER HOLD and confirm that its indicator is off, then remove the
   plotted sheet without moving the carriage by hand;
4. retain the HP-GL, placement, resolved pen-plan when present, preflight, and
   imposition audit files together as the job record; and
5. power off before changing any DIP switch, baud dial, cable configuration,
   pen adapter, or other hardware setting that requires access to moving parts.

Use `playbook.md` as the authoritative hardware reference whenever it is more
specific than this walkthrough.

## Docker boundary

On Windows, use Docker only for non-hardware processing and run serial sending
on the host. Docker Desktop does not expose Windows COM ports through the
ordinary Compose workflow.

The current container image is not a supported substitute for this guide. A
clean image build succeeds, but runtime validation currently fails because the
converter's local imported modules and `cootie_impose.py` are absent from the
image. This is tracked as HAR-9. Until that issue is fixed and its commands are
revalidated, use native `uv` for imposition, conversion, and preflight. See
`playbook.md` only for the separately documented native-Linux serial device
passthrough constraints.

## Supervised acceptance procedure

The software portion can be dry-run without a plotter:

1. generate the 20 source SVGs;
2. copy the canonical manifest;
3. impose and visually inspect artwork and guides;
4. convert with the 3 mm placement margin;
5. inspect the HP-GL as data; and
6. require a passing preflight report.

The remaining acceptance requires the operator and physical DPX-3300:

1. run the first plot on sacrificial paper;
2. verify all panel positions and pen behavior;
3. cut and fold the square;
4. record each panel's folded reading orientation and selector/reveal pairing;
5. repeat the completed job on a second sheet without routine BUFFER CLEAR;
6. if recovery is needed, verify and record the PAUSE then ENTER + `UR` BUFFER
   CLEAR, power-cycle, indicators, and pen-pickup sequence; and
7. update this guide and the orientation-validation record with every observed
   discrepancy before treating the workflow as independently operable.
