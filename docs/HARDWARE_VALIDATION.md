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
