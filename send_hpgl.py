#!/usr/bin/env python3
"""Transmit an HP-GL file to a Roland DPX-3300 over RS-232.

The serial configuration is intentionally explicit and matches the project
playbook: 9600 baud, 8 data bits, no parity, one stop bit, and XON/XOFF flow
control. The script sends the file in chunks and waits for the operating-system
serial buffer to drain before closing the port.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports

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
) -> None:
    """Send *path* to *port* using the agreed DPX-3300 serial settings."""
    data = path.read_bytes()
    validate_hpgl(data)

    LOG.info("Opening %s at 9600 8N1 with XON/XOFF", port)
    with serial.Serial(
        port=port,
        baudrate=9600,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=timeout,
        write_timeout=write_timeout,
        xonxoff=True,
        rtscts=False,
        dsrdtr=False,
    ) as connection:
        connection.reset_output_buffer()

        sent = 0
        for start in range(0, len(data), chunk_size):
            chunk = data[start : start + chunk_size]
            connection.write(chunk)
            sent += len(chunk)
            LOG.debug("Sent %d/%d bytes", sent, len(data))
            if inter_chunk_delay:
                time.sleep(inter_chunk_delay)

        connection.flush()

    LOG.info("Transmission complete: %d bytes from %s", len(data), path.name)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hpgl", nargs="?", type=hpgl_file, help="HP-GL file to send.")
    parser.add_argument("--port", help="Serial port, such as COM3 or /dev/cu.usbserial-...")
    parser.add_argument("--list-ports", action="store_true", help="List detected serial ports and exit.")
    parser.add_argument("--chunk-size", type=int, default=1024, help="Bytes per write call. Default: 1024.")
    parser.add_argument(
        "--inter-chunk-delay",
        type=float,
        default=0.0,
        help="Optional delay in seconds between chunks. Default: 0.",
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

    if args.list_ports:
        print_ports()
        return 0
    if not args.port or args.hpgl is None:
        LOG.error("Provide both --port and an HP-GL file, or use --list-ports.")
        return 2
    if args.chunk_size <= 0:
        LOG.error("--chunk-size must be greater than zero.")
        return 2
    if args.inter_chunk_delay < 0:
        LOG.error("--inter-chunk-delay cannot be negative.")
        return 2

    try:
        send_file(
            args.port,
            args.hpgl,
            chunk_size=args.chunk_size,
            inter_chunk_delay=args.inter_chunk_delay,
        )
    except (OSError, serial.SerialException, ValueError) as exc:
        LOG.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
