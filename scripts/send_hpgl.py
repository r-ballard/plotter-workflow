#!/usr/bin/env python3
"""Transmit an HP-GL file to a Roland DPX-3300 over RS-232.

The serial configuration is intentionally explicit and matches the project
playbook: 9600 baud, 8 data bits, no parity, one stop bit, and XON/XOFF flow
control. The script sends the file in chunks and waits for the operating-system
serial buffer to drain before closing the port.
"""

# Direct-script sys.path bootstrap intentionally precedes project imports.
# ruff: noqa: E402
from __future__ import annotations

import argparse
import logging
import math
import sys
import threading
from pathlib import Path

import serial
from serial.tools import list_ports

REPO_ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, "") and str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pen_plan import (
    PenPlanError,
    ResolvedPlotPass,
    discover_resolved_pen_plan_path,
    format_resolved_plot_pass,
    physical_pens_in_hpgl,
    plan_has_documented_tools,
    validate_resolved_sidecar_for_hpgl,
)
from serial_session import (
    CancelKeys,
    Cancellation,
    TransmissionCancelled,
    discard_and_close,
    open_serial,
    recover_port,
)

from scripts.job_preflight import (
    JobPreflightError,
    format_job_preflight,
    run_job_preflight,
    write_preflight_report,
)

LOG = logging.getLogger("dpx3300.sender")


def hpgl_file(value: str) -> Path:
    """Validate and return an existing HP-GL file path."""
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"File does not exist: {path}")
    if path.stat().st_size == 0:
        raise argparse.ArgumentTypeError(f"File is empty: {path}")
    return path


def print_ports() -> None:
    """Print serial ports visible to pySerial."""
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports detected.")
        return
    for port in ports:
        print(f"{port.device}\t{port.description}\t{port.hwid}")


def validate_hpgl(data: bytes) -> None:
    """Perform a lightweight sanity check before transmitting data."""
    upper = data.upper()
    if not any(token in upper for token in (b"IN;", b"PU", b"PD", b"PA", b"PR")):
        raise ValueError("The file does not appear to contain ordinary HP-GL commands.")


def send_file(
    port: str,
    path: Path,
    *,
    chunk_size: int = 1024,
    inter_chunk_delay: float = 0.0,
    timeout: float = 2.0,
    write_timeout: float = 30.0,
    cancellation: Cancellation | None = None,
    interactive: bool = True,
) -> None:
    """Send *path* to *port* using the agreed DPX-3300 serial settings."""
    data = path.read_bytes()
    validate_hpgl(data)
    if (
        type(chunk_size) is not int
        or chunk_size <= 0
        or not math.isfinite(inter_chunk_delay)
        or inter_chunk_delay < 0
    ):
        raise ValueError("chunk size must be positive and delay finite and nonnegative")
    ctrl = cancellation if cancellation is not None else Cancellation()
    if ctrl.event.is_set():
        raise TransmissionCancelled(0, len(data))
    sent = 0
    done = threading.Event()
    failures = []
    connection = None
    worker = None

    def transmit():
        nonlocal sent
        try:
            for start in range(0, len(data), chunk_size):
                chunk = data[start : start + chunk_size]
                offset = 0
                while offset < len(chunk):
                    if ctrl.event.is_set():
                        return
                    written = connection.write(chunk[offset:])
                    if type(written) is int and 0 <= written <= len(chunk) - offset:
                        sent += written
                        offset += written
                    elif not ctrl.event.is_set():
                        raise serial.SerialException("Serial write returned an invalid byte count")
                    if ctrl.event.is_set():
                        return
                    if written == 0:
                        raise serial.SerialTimeoutException("Serial write made no progress")
                LOG.debug("Driver reported %d/%d bytes written", sent, len(data))
                if ctrl.event.wait(inter_chunk_delay):
                    return
            if not ctrl.event.is_set():
                connection.flush()
        except BaseException as error:
            failures.append(error)
        finally:
            done.set()

    with CancelKeys(interactive) as keys:
        LOG.info("Cancel transmission with Ctrl+C%s.", " or Q/Escape" if keys.enabled else "")
        LOG.info("Opening %s at 9600 8N1 with XON/XOFF", port)
        try:
            if keys.requested():
                ctrl.request()
            if ctrl.event.is_set():
                raise TransmissionCancelled(sent, len(data))
            connection = open_serial(port, timeout=timeout, write_timeout=write_timeout)
            connection.reset_output_buffer()
            if keys.requested():
                ctrl.request()
            if ctrl.event.is_set():
                raise TransmissionCancelled(sent, len(data))
            worker = threading.Thread(target=transmit, name="hpgl-transmit", daemon=True)
            worker.start()
            try:
                while not done.wait(0.02):
                    if keys.requested():
                        ctrl.request()
                    if ctrl.event.is_set():
                        break
            except KeyboardInterrupt:
                ctrl.request()
            if keys.requested():
                ctrl.request()
            if ctrl.event.is_set():
                raise TransmissionCancelled(sent, len(data))
            if failures:
                raise failures[0]
        except KeyboardInterrupt:
            ctrl.request()
            raise TransmissionCancelled(sent, len(data)) from None
        finally:
            if connection is not None:
                if ctrl.event.is_set() or failures:
                    discard_and_close(connection)
                else:
                    connection.close()
            if worker is not None:
                worker.join(0.5)
                if worker.is_alive():
                    LOG.warning(
                        "Serial worker did not finish; connection closed. Do not resume this job."
                    )
    # Cancellation is accepted through cleanup; completion is committed here.
    if ctrl.event.is_set():
        raise TransmissionCancelled(sent, len(data))
    LOG.info("Transmission complete: %d bytes from %s", len(data), path.name)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hpgl", nargs="?", type=hpgl_file, help="HP-GL file to send.")
    parser.add_argument("--port", help="Serial port, such as COM3 or /dev/cu.usbserial-...")
    parser.add_argument(
        "--recover-port",
        metavar="PORT",
        help="Rescan and test reopening the selected port, then close it; sends no HP-GL.",
    )
    parser.add_argument(
        "--list-ports", action="store_true", help="List detected serial ports and exit."
    )
    parser.add_argument(
        "--chunk-size", type=int, default=1024, help="Bytes per write call. Default: 1024."
    )
    parser.add_argument(
        "--inter-chunk-delay",
        type=float,
        default=0.0,
        help="Optional delay in seconds between chunks. Default: 0.",
    )
    parser.add_argument(
        "--pen-plan",
        type=Path,
        help=(
            "Resolved .resolved.penplan.json sidecar. By default the sender "
            "discovers <stem>.resolved.penplan.json beside the HP-GL file, "
            "with read-only fallback for legacy resolved <stem>.penplan.json."
        ),
    )
    parser.add_argument(
        "--confirm-pen-plan",
        action="store_true",
        help=(
            "Confirm carriage loading and force setup: software requires AUTO off; "
            "panel force requires AUTO on and listed panel settings applied."
        ),
    )
    parser.add_argument(
        "--allow-unplanned-multipen",
        action="store_true",
        help=(
            "Allow sending multi-pen HP-GL without a resolved sidecar. This bypasses "
            "the carriage-plan safety check and should be used only for legacy jobs."
        ),
    )
    parser.add_argument(
        "--placement-report",
        type=Path,
        help=(
            "Resolved .placement.json sidecar. By default the sender looks beside "
            "the HP-GL file for <stem>.placement.json."
        ),
    )
    parser.add_argument(
        "--vpype-config",
        type=Path,
        default=REPO_ROOT / "vpype.toml",
        help="vpype TOML configuration used to revalidate physical placement.",
    )
    parser.add_argument(
        "--allow-unvalidated-job",
        action="store_true",
        help=(
            "Skip the unified placement/sidecar preflight for a deliberately "
            "reviewed legacy job. Existing sender safety checks still apply."
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging.")
    return parser.parse_args()


def main() -> int:
    """Run the command-line sender."""
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    recovery_port = getattr(args, "recover_port", None)
    if recovery_port is not None:
        if args.hpgl is not None or args.port is not None or args.list_ports:
            LOG.error(
                "--recover-port cannot be combined with an HP-GL file, --port, or --list-ports."
            )
            return 2
        try:
            recover_port(recovery_port)
        except KeyboardInterrupt:
            LOG.warning("Port recovery cancelled; no job resumed.")
            return 130
        except (OSError, ValueError) as error:
            LOG.error("Port recovery failed: %s", error)
            return 1
        return 0
    if args.list_ports:
        print_ports()
        return 0
    if not args.port or args.hpgl is None:
        LOG.error("Provide both --port and an HP-GL file, or use --list-ports.")
        return 2
    if args.chunk_size <= 0:
        LOG.error("--chunk-size must be greater than zero.")
        return 2
    if not math.isfinite(args.inter_chunk_delay) or args.inter_chunk_delay < 0:
        LOG.error("--inter-chunk-delay must be finite and nonnegative.")
        return 2

    try:
        if not args.allow_unvalidated_job:
            report, preflight_plan = run_job_preflight(
                args.hpgl,
                config_path=args.vpype_config,
                pen_plan_path=args.pen_plan,
                placement_report_path=args.placement_report,
                require_operator_confirmation=True,
                operator_confirmed=args.confirm_pen_plan,
            )
            for line in format_job_preflight(report, preflight_plan).splitlines():
                LOG.info("%s", line)
            preflight_path = args.hpgl.with_suffix(".preflight.json")
            write_preflight_report(report, preflight_path)
            LOG.info("Created preflight audit: %s", preflight_path)

        physical_pens = physical_pens_in_hpgl(args.hpgl)
        sidecar = (
            args.pen_plan.expanduser().resolve()
            if args.pen_plan is not None
            else discover_resolved_pen_plan_path(args.hpgl)
        )
        resolved_plan = None
        if args.pen_plan is not None and not sidecar.is_file():
            raise PenPlanError(f"Explicit resolved pen plan does not exist: {sidecar}")
        if sidecar.is_file():
            resolved_plan = validate_resolved_sidecar_for_hpgl(args.hpgl, sidecar)
            carriage = format_resolved_plot_pass(resolved_plan)
            for line in carriage.splitlines():
                LOG.info("%s", line)
        elif len(physical_pens) > 1 and not args.allow_unplanned_multipen:
            raise PenPlanError(
                f"Multi-pen HP-GL uses {physical_pens} but no resolved pen-plan "
                f"sidecar exists at {sidecar}. Use --allow-unplanned-multipen only "
                "for a deliberately reviewed legacy job."
            )

        if (
            resolved_plan is not None
            and resolved_plan.pen_force is not None
            and not args.confirm_pen_plan
        ):
            raise PenPlanError(
                "--confirm-pen-plan required for force setup: software AUTO off, "
                "or panel AUTO on with settings applied"
            )
        if len(physical_pens) > 1 and resolved_plan is not None:
            if isinstance(resolved_plan, ResolvedPlotPass) and not plan_has_documented_tools(
                resolved_plan
            ):
                raise PenPlanError(
                    "Multi-pen send requires a tool or label for every used physical slot."
                )
            if not args.confirm_pen_plan:
                raise PenPlanError(
                    "Multi-pen send requires --confirm-pen-plan after verifying the "
                    "printed carriage loading plan."
                )

        send_file(
            args.port,
            args.hpgl,
            chunk_size=args.chunk_size,
            inter_chunk_delay=args.inter_chunk_delay,
        )
    except TransmissionCancelled as exc:
        LOG.warning("%s", exc)
        LOG.warning(
            "Host cancellation may leave HP-GL inside the plotter. "
            "Clear or power-cycle it after a hardware fault before restarting a job."
        )
        return 130
    except KeyboardInterrupt:
        LOG.warning("Cancelled before transmission started.")
        return 130
    except (OSError, serial.SerialException, ValueError, JobPreflightError) as exc:
        LOG.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
