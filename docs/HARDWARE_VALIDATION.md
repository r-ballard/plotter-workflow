# DPX-3300 hardware validation

This document records commissioning evidence for the `plotter-workflow` path
from SVG through physical Roland DPX-3300 output. It is not a substitute for
per-job preflight.

## Verified commissioning result

On 2026-08-08, a three-pen Hilbert sample completed successfully on the Roland
DPX-3300 over the project's USB-to-RS-232 serial path. The run verified the
behavior that matters at the hardware boundary:

- HP-GL was accepted over 9600 baud, 8 data bits, no parity, one stop bit, with
  XON/XOFF flow control.
- Three physical pen selections were executed successfully.
- Pen changes occurred in the expected order.
- The generated placement was physically usable on the loaded sheet.
- The unified preflight completed before transmission.
- The job completed without a transport or plotter failure.

This establishes a known-good commissioning case for the software/hardware
chain. It does **not** make later generated HP-GL safe by inheritance. Every
job must still pass current pen-plan and placement validation.

## 2026-09-30 neutral two-pass acceptance incident (unresolved)

The operator reported that after switching to Pen 2 and drawing approximately
3-4 planetoids, the plotter moved beyond the drawing sheet while raising and
lowering the pen. The operator paused the plotter. The reported send command
was:

```bash
"$UV" run --frozen python send_hpgl.py --port "$PORT" \
  --confirm-pen-plan "$BODY"
```

Full two-pass physical acceptance remains **unconfirmed**. Do not resume the
original paused job. Preserve the sheet,
terminal output, job files, and sidecars rather than regenerating over them.

The operator supplied the sender's final output:

```text
INFO: Opening COM4 at 9600 8N1 with XON/XOFF
INFO: Transmission complete: 64495 bytes from booklet.imposed.body.hpgl
```

The sender reported completion without an error. Its completion message follows
host serial writes and `flush()`; it is not an acknowledgement of correct
receipt or completed physical plotting. The reported filename and byte count
match the inspected fixture below, but the output does not identify its full
path or hash.

The operator subsequently reported that the computer went to sleep shortly
before SP2 plotting began and that a repeat test was underway. Whether sleep
preceded or followed the sender's `Transmission complete` message is unknown.
Sleep/resume interference with serial transport is an investigation hypothesis,
not an established cause or evidence of a scaling change.

The operator then reported a repeat that completed without sleep after
extending the sleep timeout to 25 minutes, and described the result as looking
good. This supports keeping the computer awake throughout physical plotting;
it does not establish sleep as the root cause. Whether this result includes
both the body and accent passes and their registration remains unconfirmed.
The acceptance guide now requires keeping the computer awake until motion has
stopped, rather than relying on the sender's completion message or a fixed
25-minute timeout.

Offline inspection of the most recently selected local fixture,
`tmp/neutral-orbital-e2e-20260930-134828/jobs/booklet.imposed.body.hpgl`, found:

- 64,495 bytes; SHA-256
  `976efb18763aaf22d5540b706834cb57212cd6ad349f509e08505ebd080f508b`,
  matching its saved confirmed preflight report.
- Pen order `SP1 -> SP2 -> SP0`; `SP2` starts at byte offset 41,127 (zero-based).
- All 4,991 explicit coordinate pairs within X=-17323..-6838 and
  Y=-10175..-3549, inside the report's Letter margin bounds.
- Only `IN`, `DF`, `SP`, `PU`, and `PD` commands; initialization at the start
  and a final `IN` after `SP0`, with no mid-job scaling or relative-mode command.

These checks describe the file on disk, not the bytes received or the motion
executed by the plotter. The exact expanded `$BODY` path used for the failed
send and current adapter/cable identity still need operator confirmation. The
operator answered yes to the combined follow-up about successful square and
orientation controls and SW-2 switch 5 being ON at power-up; that response is
recorded as confirmation of both. Transport, command interpretation, and
hardware causes remain unconfirmed despite the reported good repeat with
sleep delayed.

## Golden fixture policy

`tests/fixtures/hardware_validation/hilbert/` contains semantic invariants for
the commissioning case. The fixture intentionally does not pin:

- an absolute local filesystem path;
- a COM-port name;
- a permanent generated HP-GL SHA-256;
- byte-for-byte vpype output.

Those values can change without changing the intended plot. Regression checks
should instead preserve stable behavior: assignment policy, active physical
pen order, terminal `SP0`, and the requirement that each used slot be
operator-documentable.

The checked-in pen plan is a reusable commissioning plan, not a claim about
pen color. Labels document the required physical slots while allowing the
operator to choose the actual pens for a test run.

## Re-running the commissioning test

1. Generate or copy the three-layer Hilbert SVG into `input/`.
2. Copy the golden pen plan next to the SVG and rename it to the SVG stem:

   ```bash
   cp tests/fixtures/hardware_validation/hilbert/golden.penplan.json \
      input/hilbert_sample_drawing.penplan.json
   ```

3. Convert using the intended paper profile and an appropriately conservative
   margin.
4. Run `job_preflight.py` without confirmation and review the printed mapping.
5. Physically load and verify the three required carriage slots.
6. Run `job_preflight.py --confirm-pen-plan --write-report`.
7. Send the exact reviewed HP-GL. For serial, use `send_hpgl.py` with
   `--confirm-pen-plan`; for raw parallel transport, do not modify the HP-GL
   after standalone preflight.
8. Record any material hardware or configuration change here rather than
   silently replacing the original commissioning result.

See `JOB_PREFLIGHT.md` for validation semantics and `playbook.md` for physical
interface and switch configuration.
