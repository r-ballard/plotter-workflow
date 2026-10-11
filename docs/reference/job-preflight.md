# DPX-3300 job preflight

The final pre-send check combines three independently useful artifacts:

```text
<stem>.hpgl
<stem>.resolved.penplan.json
<stem>.placement.json
```

`scripts/job_preflight.py` does not merely trust those sidecars. It re-reads the current HP-GL, checks its actual `SP1`–`SP8` order against the resolved pen plan, and re-runs placement validation using the device/profile/margin recorded in the placement report. Stored drawing/addressed bounds must still match the current HP-GL. It accepts only schema-3 resolved-dpx3300-plot-pass audits, verifies final HP-GL SHA-256 and configured force state, and checks source hashes when available. Reconvert old jobs.

This catches a common unsafe workflow: generating valid sidecars and then editing or replacing the HP-GL file afterward.

All input SVG contracts use one carriage/pass model. Applicable tool metadata and expected force appear beside the physical slot. Force is either unmanaged, software encoded (AUTO off), or operator-applied panel force (AUTO on). The confirmation flag acknowledges setup, not a sensor reading.

## Review a job

```bash
uv run python scripts/job_preflight.py output/plant_test_drawing.hpgl
```

For a multi-pen job this validates the job but deliberately reports:

```text
VALIDATED - OPERATOR CONFIRMATION REQUIRED
```

because software cannot sense what is physically loaded in the DPX-3300 carriage.

After physically checking the carriage against the printed plan, the same standalone command may record the confirmation state and write an audit report:

```bash
uv run python scripts/job_preflight.py \
  output/plant_test_drawing.hpgl \
  --confirm-pen-plan \
  --write-report
```

This creates:

```text
output/plant_test_drawing.preflight.json
```

The report includes a SHA-256 digest of the exact HP-GL bytes reviewed.

## Sender integration

`scripts/send_hpgl.py` automatically runs the same preflight immediately before serial transmission. Multi-pen transmission and every force-configured job, including one pen, require `--confirm-pen-plan`. No separate integration step is required in a normal checkout.

```bash
uv run python scripts/send_hpgl.py \
  output/plant_test_drawing.hpgl \
  --port COM3 \
  --confirm-pen-plan
```

By default the sender discovers adjacent resolved sidecars:

```text
output/plant_test_drawing.resolved.penplan.json
output/plant_test_drawing.placement.json
```

`--pen-plan`, `--placement-report`, and `--vpype-config` may override those paths.

`--allow-unvalidated-job` is an explicit legacy escape hatch. It skips the unified placement/sidecar preflight; the existing sender sanity checks and any existing pen-plan checks still apply. It should not be used for normal DPX-3300 jobs.

## Raw parallel transmission

Raw parallel paths such as `/dev/usb/lp0`, `lp -o raw`, or Windows `copy /b`
bypass `scripts/send_hpgl.py`. They therefore **must** be preceded by the standalone
preflight after the operator physically verifies the carriage:

```bash
uv run python scripts/job_preflight.py \
  output/drawing.hpgl \
  --confirm-pen-plan \
  --write-report
```

Confirm that the command reports `READY TO SEND` before transmitting those
exact HP-GL bytes through the raw parallel path. If the HP-GL is regenerated or
modified afterward, run preflight again.

## Golden hardware validation

The repository keeps semantic commissioning invariants under
`tests/fixtures/hardware_validation/`. The fixture records stable behavior such
as pen order and assignment policy rather than machine-specific absolute paths
or a permanent HP-GL SHA-256. See `docs/validation/hardware-validation.md`.

## What must agree

A validated multi-pen job requires:

- current HP-GL is non-empty and contains physical `SP1`–`SP8` selections;
- HP-GL physical pen order exactly matches the resolved pen plan;
- every slot is mapped through the shared schema-3 layer-ID assignments; carriage tools must be physically checked;
- configured effective force covers every used slot and matches HP-GL force state;
- placement sidecar has `status: pass` and names the same HP-GL file;
- current HP-GL still fits the sidecar's device/page/margin configuration;
- current drawing/addressed bounds match the stored placement bounds;
- multi-pen or force-aware send has explicit carriage/force confirmation.

The operator remains responsible for confirming actual paper placement, pen/tool loading, pen condition, and a conservative first hardware test.

Old schema-1/2 resolved files are rejected, and old generated .penplan.json files are not used as a fallback. See [migration and force setup](pen-plan.md). Force audits distinguish required setup from operator-confirmed AUTO-off or panel-settings/AUTO-on state. No physical force is measured by preflight.
