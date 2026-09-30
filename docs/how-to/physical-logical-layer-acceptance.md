# DPX-3300 hardware acceptance for neutral logical-layer passes

Use this checklist at the plotter workstation. It covers the remaining physical
validation for `feat/logical-layer-plotter`: a single-pen orientation control,
then two registered passes from the neutral orbital software fixture. The
[Linear acceptance ticket](https://linear.app/hardcase/issue/HAR-26/physically-validate-neutral-logical-layer-multipass-plotting)
tracks the result. The
existing [serial playbook](../../playbook.md), [job preflight guide](../../JOB_PREFLIGHT.md),
and [neutral workflow](neutral-logical-layer-plotting.md) remain the authority
for switch settings, preflight semantics, and normal jobs. The separate
twenty-surface cootie-catcher proof is tracked by Linear `HAR-14` and uses
[its own guide](impose-and-plot-polygon-bundle.md).

## Before powering on

- Use sacrificial Letter paper and pens whose marks are easy to distinguish.
  Keep a hand near pause and be ready to power off if motion is unsafe.
- Keep the computer awake through transmission and until all physical plotting
  has stopped, including both passes. Temporarily prevent system sleep and
  hibernation for the run; do not rely on a fixed timeout for longer jobs.
  Restore your normal power settings afterward. `Transmission complete` reports
  host-side sending, not completion of plotter movement.
  A 2026-09-30 run moved outside the sheet after computer sleep; the operator
  reported a good repeat after extending sleep to 25 minutes. Sleep is a
  suspected contributor, not a confirmed cause; see the
  [incident record](../HARDWARE_VALIDATION.md#2026-09-30-neutral-two-pass-acceptance-incident-unresolved).
  If sleep occurs or motion leaves the reviewed area, pause or power off as
  needed and inspect the media. Treat the job as interrupted; do not resume it
  or resend without fresh preflight on the exact HP-GL.
- Use the documented USB-to-RS-232 adapter and null-modem cable to `SERIAL IN`.
  Do not connect the parallel adapter for this procedure.
- With power **off**, set the full serial switch table in `playbook.md`:
  SW-1 switch 5 ON (serial), switch 6 OFF (direct), switch 7 ON (ANSI-D),
  SW-2 switch 5 ON (XON/XOFF), and baud dial 14 (9600). Keep the other switches
  at the table's settings. Power on and check for a **green** interface light.
- Set Letter landscape paper's lower-left corner at the ANSI-D lower-left
  plotting-area limit; engage PAPER HOLD. These generated jobs use
  `letter_lower_left`, absolute coordinates, and a 4 mm converter margin.
  Stop if the media, switch setting, or preflight profile differs.
- In Windows Git Bash, use the existing workspace checkout and pinned toolchain:

  ```bash
  export ROOT=/c/Users/hardcase/Documents/developer/codex-repos
  export PLOTTER_REPO="$ROOT/plotter-workflow"
  export VIZ_REPO="$ROOT/viz_virtualserver"
  export UV="$ROOT/.tools/uv.exe"
  cd "$PLOTTER_REPO"
  (
    cd "$ROOT/generative-viz-workspace" &&
    bash scripts/verify-environment.sh
  )
  "$UV" run --frozen python send_hpgl.py --list-ports
  export PORT=COM3 # replace with the detected port
  ```

  If the workspace path or COM port differs, change it before continuing.
  Run verification from the tooling directory as shown: when run from an
  application repository, the verifier can mistake its local `.venv` for the
  shared Python and report `viz virtual environment uses the shared Python`.
  The subshell keeps your working directory at `"$PLOTTER_REPO"` afterward.
  Continue only after verification reports `SUCCESS`.
  The verifier checks software only; it does not authorize a send.

## 1. Small serial-motion check

First prove serial transport and placement with the checked-in 10 mm square
at the center of a preserved Letter landscape page. The source is
`tests/fixtures/hardware_validation/serial-smoke.svg`; its preserve-layout
metadata prevents the converter from enlarging it to fill the sheet. The
prepared job is `output/hardware-acceptance/serial-smoke.hpgl`. If missing,
generate it without `--overwrite`:

```bash
mkdir -p output/hardware-acceptance
"$UV" run --frozen python dpx3300_convert.py \
  --input-dir tests/fixtures/hardware_validation \
  --output-dir output/hardware-acceptance \
  --file serial-smoke.svg --page-size letter --landscape \
  --paper-position lower-left --margin 4mm --absolute
```

```bash
export SMOKE=output/hardware-acceptance/serial-smoke.hpgl
"$UV" run --frozen python job_preflight.py "$SMOKE"
```

Expect `SP1 -> SP0`, `Placement: PASS`, `READY TO SEND`, and drawing bounds
400 plotter units wide and high (10 mm per side). **Stop if the drawing
fills most of the page**; that indicates a layout or file mismatch. Load one
tested pen in SP1, check the sheet position, then send the exact preflighted
job while watching first motion:

```bash
"$UV" run --frozen python send_hpgl.py --port "$PORT" "$SMOKE"
```

Confirm a small centered square and normal pen return. Stop here if the
transport, scale, or location is wrong. Use a fresh sheet for the next test.

## 2. Single-pen orientation control

The prepared control job is
`output/hardware-acceptance/pocketmod8_validation.imposed.hpgl` with an
adjacent `.placement.json` report. If it is missing, regenerate it from the
checked-in vector fixture:

```bash
mkdir -p output/hardware-acceptance
"$UV" run --frozen python booklet_impose.py \
  tests/fixtures/imposition/pocketmod8/validation_pages \
  --sheet-size letter --page-margin-mm 6 --guides \
  --output output/hardware-acceptance/pocketmod8_validation.imposed.svg
"$UV" run --frozen python dpx3300_convert.py \
  --input-dir output/hardware-acceptance \
  --output-dir output/hardware-acceptance \
  --file pocketmod8_validation.imposed.svg \
  --page-size letter --landscape --paper-position lower-left \
  --margin 4mm --absolute
```

Set the job and preflight its **current bytes** immediately before sending:

```bash
export CONTROL=output/hardware-acceptance/pocketmod8_validation.imposed.hpgl
"$UV" run --frozen python job_preflight.py "$CONTROL"
```

Expect `letter_lower_left`, `SP1 -> SP0`, `Placement: PASS`, and
`READY TO SEND`. Stop on any different result. Inspect the imposed SVG and
guides before drawing; the guides are a separate job and are **not** sent
here. Load a single tested pen in SP1, recheck the paper position, then send:

```bash
"$UV" run --frozen python send_hpgl.py --port "$PORT" "$CONTROL"
```

Observe the first movement and stop for unexpected travel. After motion has
stopped, inspect the sheet. The fixture has page numbers 1–8, a top arrow,
and a bottom `V` on each page. Cut and fold only after the plot finishes;
record page order, arrow direction, scale, clipping, and paper position. See
the [fixture instructions](../../tests/fixtures/imposition/pocketmod8/VALIDATION.md).
Do not proceed to multipass if this control fails.

## 3. Neutral two-pass registration proof

Use a **new** sacrificial sheet for the two-pass proof. The prepared software
fixture is under ignored `tmp/neutral-orbital-e2e/`; its `design.json` has
50 catalog IDs. The `body` pass maps `orbits` to SP1 and 36 body IDs to SP2.
The `accent` pass repeats `orbits` on SP1 and maps 13 accent IDs to SP3. The
plan declares `orbits` in `repeated_layers`. This is a test fixture, not a
finished artwork layout. If the directory is missing, use the regeneration
recipe below before touching the plotter.

The regeneration recipe sets `JOB_DIR` to a timestamped run's `jobs` directory.
Keep that value when returning here; the default below applies only when
`JOB_DIR` is unset or empty. In a new shell, select the intended existing run
explicitly with `export JOB_DIR="tmp/neutral-orbital-e2e-YYYYMMDD-HHMMSS/jobs"`,
replacing the timestamp with your actual run. Do not select a run solely
because it is the newest. These generated files are ignored by Git and may
not exist in another checkout.

```bash
export JOB_DIR="${JOB_DIR:-tmp/neutral-orbital-e2e/jobs}"
export BODY="$JOB_DIR/booklet.imposed.body.hpgl"
export ACCENT="$JOB_DIR/booklet.imposed.accent.hpgl"
printf 'Selected job directory: %s\n' "$JOB_DIR"
test -f "$JOB_DIR/booklet.imposed.imposition.json" &&
test -f "$JOB_DIR/booklet.imposed.penplan.json" &&
test -f "$BODY" &&
test -f "$ACCENT" &&
"$UV" run --frozen python job_preflight.py "$BODY" &&
"$UV" run --frozen python job_preflight.py "$ACCENT"
```

If no preflight output appears, a required file is missing. Check the selected
`JOB_DIR`; use the regeneration recipe if no complete fixture exists.

Both must show `Pen plan: PASS` and `Placement: PASS`. The body pass must
show `SP1 -> SP2 -> SP0`, the accent pass `SP1 -> SP3 -> SP0`; each must
show `VALIDATED - OPERATOR CONFIRMATION REQUIRED`. Inspect the imposed SVG,
imposition audit, plan, HP-GL data, paper profile, and drawing bounds. Stop
if a file is missing, stale, out of bounds, or different from the intended
mapping. Preflight cannot independently re-hash the source bundle from HP-GL,
so retain the bundle and audit with the run record.

Physically load and verify the actual tools in SP1, SP2, and SP3. Write down
their colors or labels. Keep the **same new sheet registered and PAPER HOLD
engaged** between passes. Only after the carriage and media checks, record
operator confirmation for the first job and send it:

```bash
"$UV" run --frozen python job_preflight.py "$BODY" \
  --confirm-pen-plan --write-report
# Continue only if the exact job now reports READY TO SEND.
"$UV" run --frozen python send_hpgl.py --port "$PORT" \
  --confirm-pen-plan "$BODY"
```

Wait for physical movement to stop. Do not release PAPER HOLD or move the
sheet. Recheck loaded SP1 and SP3, preflight the second job, then send it:

```bash
"$UV" run --frozen python job_preflight.py "$ACCENT" \
  --confirm-pen-plan --write-report
# Continue only if the exact job now reports READY TO SEND.
"$UV" run --frozen python send_hpgl.py --port "$PORT" \
  --confirm-pen-plan "$ACCENT"
```

Observe the expected pen changes and first motion on each pass. Once the
plotter stops, check orbit overprinting, registration between body and accent
marks, clipping, scale, page orientation, and fold-safe placement. Record any
misalignment or paper movement before changing software or repeating a job.
Stop immediately for unexpected motion, tool selection, or out-of-bounds
travel; do not send a modified HP-GL without fresh conversion and preflight.

## Regenerate the neutral fixture if needed

Run these commands in Git Bash from `"$PLOTTER_REPO"`. They create a new,
ignored run directory. If the prepared set exists, use it and rerun preflight
instead. Preserve earlier evidence; do not regenerate over it.

```bash
export RUN_DIR="tmp/neutral-orbital-e2e-$(date +%Y%m%d-%H%M%S)"
export BUNDLE_DIR="$RUN_DIR/bundle"
export JOB_DIR="$RUN_DIR/jobs"
mkdir -p "$RUN_DIR" "$JOB_DIR"
"$VIZ_REPO/.venv/Scripts/python.exe" \
  "$VIZ_REPO/scripts/generate_domain_bundle.py" \
  "$VIZ_REPO/examples/domain-jobs/orbital-per-body.json" \
  --output-dir "$BUNDLE_DIR"

"$PLOTTER_REPO/.venv/Scripts/python.exe" - <<'PY'
import json
import os
from pathlib import Path

bundle = Path(os.environ["BUNDLE_DIR"])
names = ("square", "triangle", "pentagon", "square",
         "triangle", "pentagon", "square", "triangle")
manifest = {"schema_version": 1, "layout": "pocketmod8",
            "pages": [{"page": n, "source": f"surfaces/{name}.svg"}
                      for n, name in enumerate(names, 1)]}
(bundle / "booklet.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

"$UV" run --frozen python booklet_impose.py "$BUNDLE_DIR" \
  --manifest booklet.json --sheet-size letter --guides \
  --output "$JOB_DIR/booklet.imposed.svg"

"$PLOTTER_REPO/.venv/Scripts/python.exe" - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["RUN_DIR"])
ids = [row["id"] for row in json.loads((root / "bundle/design.json").read_text())["logical_layers"]]
body = [item for item in ids if item.startswith("body-")]
accent = [item for item in ids if item.startswith("accent-")]
assert len(ids) == 50 and len(body) == 36 and len(accent) == 13
assert set(ids) == {"orbits", *body, *accent}
plan = {
    "schema_version": 2,
    "passes": [
        {"id": "body", "assignments": [
            {"layer_ids": ["orbits"], "physical_slot": 1},
            {"layer_ids": body, "physical_slot": 2}]},
        {"id": "accent", "assignments": [
            {"layer_ids": ["orbits"], "physical_slot": 1},
            {"layer_ids": accent, "physical_slot": 3}]}],
    "omitted_layers": [], "repeated_layers": ["orbits"]}
(root / "jobs/booklet.imposed.penplan.json").write_text(json.dumps(plan, indent=2) + "\n")
PY

"$UV" run --frozen python dpx3300_convert.py \
  --input-dir "$JOB_DIR" --output-dir "$JOB_DIR" \
  --file booklet.imposed.svg --page-size letter --landscape \
  --paper-position lower-left --margin 4mm --absolute --dry-run
"$UV" run --frozen python dpx3300_convert.py \
  --input-dir "$JOB_DIR" --output-dir "$JOB_DIR" \
  --file booklet.imposed.svg --page-size letter --landscape \
  --paper-position lower-left --margin 4mm --absolute
export BODY="$JOB_DIR/booklet.imposed.body.hpgl"
export ACCENT="$JOB_DIR/booklet.imposed.accent.hpgl"
```

Then return to section 3's file checks and unconfirmed preflight commands in
the same shell, preserving the timestamped `JOB_DIR` set by this recipe. Do
not reset it to `tmp/neutral-orbital-e2e/jobs` or use `--overwrite` on prior
acceptance evidence.

## Record and close the acceptance

Keep the exact bundle, manifest, plan, imposed SVG and audit, both HP-GL files,
resolved and placement sidecars, and both `.preflight.json` reports together.
Record the date, machine, COM port, paper, physical pens in SP1/SP2/SP3,
preflight SHA-256 values, photos/scans before and after folding, and any
pauses or resets. A report for each job is tied to its HP-GL SHA-256; repeat
preflight if any job or sidecar changes. Add the result to
[`docs/HARDWARE_VALIDATION.md`](../HARDWARE_VALIDATION.md) and the linked
Linear acceptance issue. Open a narrow defect for any failure, with the
specific job and observed step. Keep production plotting blocked until the
physical result is reviewed.

Also record the computer's sleep setting, any sleep/resume during the run,
whether `Transmission complete` appeared before or after that event, and
separate physical results for the body and accent passes. A successful repeat
of one pass does not establish two-pass registration acceptance.
