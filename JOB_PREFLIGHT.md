# DPX-3300 job preflight

The final pre-send check combines three independently useful artifacts:

```text
<stem>.hpgl
<stem>.penplan.json
<stem>.placement.json
```

`job_preflight.py` does not merely trust those sidecars. It re-reads the current HP-GL, checks its actual `SP1`–`SP8` order against the resolved pen plan, and re-runs placement validation using the device/profile/margin recorded in the placement report. Stored drawing/addressed bounds must still match the current HP-GL.

This catches a common unsafe workflow: generating valid sidecars and then editing or replacing the HP-GL file afterward.

## Review a job

```bash
uv run python job_preflight.py output/plant_test_drawing.hpgl
```

For a multi-pen job this validates the job but deliberately reports:

```text
VALIDATED - OPERATOR CONFIRMATION REQUIRED
```

because software cannot sense what is physically loaded in the DPX-3300 carriage.

After physically checking the carriage against the printed plan, the same standalone command may record the confirmation state and write an audit report:

```bash
uv run python job_preflight.py \
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

After running `scripts/integrate_job_preflight.py`, `send_hpgl.py` automatically runs the same preflight immediately before serial transmission. Multi-pen transmission requires `--confirm-pen-plan`.

```bash
uv run python send_hpgl.py \
  output/plant_test_drawing.hpgl \
  --port COM3 \
  --confirm-pen-plan
```

By default the sender discovers adjacent resolved sidecars:

```text
output/plant_test_drawing.penplan.json
output/plant_test_drawing.placement.json
```

`--pen-plan`, `--placement-report`, and `--vpype-config` may override those paths.

`--allow-unvalidated-job` is an explicit legacy escape hatch. It skips the unified placement/sidecar preflight; the existing sender sanity checks and any existing pen-plan checks still apply. It should not be used for normal DPX-3300 jobs.

## What must agree

A validated multi-pen job requires:

- current HP-GL is non-empty and contains physical `SP1`–`SP8` selections;
- HP-GL physical pen order exactly matches the resolved pen plan;
- every used physical slot has a `tool` or `label` documented;
- placement sidecar has `status: pass` and names the same HP-GL file;
- current HP-GL still fits the sidecar's device/page/margin configuration;
- current drawing/addressed bounds match the stored placement bounds;
- multi-pen send has explicit operator confirmation.

The operator remains responsible for confirming actual paper placement, pen/tool loading, pen condition, and a conservative first hardware test.
