#!/usr/bin/env python3
"""
dpx3300_convert.py

Convert one SVG file, or every SVG file in a directory, to HP-GL for a
Roland DPX-3300. The conversion and path optimization are performed by
vpype. Optionally, Chiplotle3 can send the resulting HP-GL file to a
connected plotter.

Why SVG?
--------
A pen plotter draws vector paths. vpype's ``read`` command is designed
primarily for SVG vector artwork; it does not trace arbitrary PNG/JPEG
pixels into lines. Convert or trace raster artwork to SVG first, for
example with Inkscape, Potrace, or another vectorization tool.

Important DPX-3300 assumptions
------------------------------
* The DPX-3300 uses Roland RD-GL II, which is closely related to HP-GL.
* The plotter coordinate resolution is 0.025 mm (40 plotter units/mm).
* vpype does not currently include a built-in DPX-3300 profile. This
  project supplies ``vpype.toml`` with a centered-origin ``dpx3300`` device
  profile. The profile maps the physical center of the selected page to
  plotter coordinate ``(0, 0)``, matching the behavior verified on the
  machine. Always make a small pen-up or sacrificial-paper test before plotting.
* The plotter and computer serial settings must match. The factory serial
  settings documented by Roland are 9600 baud, no parity, 8 data bits,
  and 1 stop bit.

Examples
--------
Convert every SVG in ./input to ./output:

    python3 dpx3300_convert.py \
        --input-dir ./input \
        --output-dir ./output

Convert one file for US Letter paper loaded landscape:

    python3 dpx3300_convert.py \
        --input-dir ./input \
        --output-dir ./output \
        --file drawing.svg \
        --page-size letter \
        --landscape \
        --margin 0.5in \
        --absolute

Convert and immediately send each result with Chiplotle3:

    python3 dpx3300_convert.py \
        --input-dir ./input \
        --output-dir ./output \
        --send

Use --dry-run to print commands without executing them.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

LOG = logging.getLogger("dpx3300")
DEFAULT_VPYPE_CONFIG = Path(__file__).resolve().with_name("vpype.toml")


class ConversionError(RuntimeError):
    """Raised when vpype cannot convert an SVG file to HP-GL."""


def existing_directory(value: str) -> Path:
    """Return *value* as a resolved directory path or raise argparse error."""
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"Directory does not exist: {path}")
    return path


def positive_float(value: str) -> float:
    """Parse a strictly positive floating-point command-line argument."""
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero.")
    return number


def existing_file(value: str) -> Path:
    """Return *value* as a resolved file path or raise an argparse error."""
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"File does not exist: {path}")
    return path


def discover_svg_files(input_dir: Path, filename: str | None) -> list[Path]:
    """
    Locate the SVG input files to process.

    When *filename* is supplied, exactly that file is selected. Otherwise,
    all ``.svg`` files directly inside *input_dir* are returned in sorted
    order. The directory is intentionally not searched recursively, which
    avoids unexpectedly plotting files from nested folders.
    """
    if filename:
        candidate = (input_dir / filename).resolve()

        # Prevent "../" in --file from escaping the configured input folder.
        try:
            candidate.relative_to(input_dir)
        except ValueError as exc:
            raise ValueError("--file must refer to a file inside --input-dir") from exc

        if not candidate.is_file():
            raise FileNotFoundError(f"Input file does not exist: {candidate}")
        if candidate.suffix.lower() != ".svg":
            raise ValueError(
                f"Unsupported input format {candidate.suffix!r}; use an SVG vector file."
            )
        return [candidate]

    files = sorted(
        path for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".svg"
    )
    if not files:
        raise FileNotFoundError(f"No SVG files found in {input_dir}")
    return files


def build_vpype_command(
    source: Path,
    destination: Path,
    *,
    config_path: Path,
    device: str,
    page_size: str,
    landscape: bool,
    margin: str,
    velocity: float | None,
    absolute: bool,
) -> list[str]:
    """
    Construct the vpype command used for conversion.

    Pipeline stages
    ---------------
    read
        Imports SVG paths.
    linemerge
        Joins path fragments whose endpoints coincide.
    linesimplify
        Removes redundant points while preserving path shape.
    reloop
        Chooses a favorable start point for closed paths.
    linesort
        Reorders paths to reduce pen-up travel.
    layout
        Fits and centers the drawing on the selected page.
    write
        Serializes the result as HP-GL using a plotter device profile.
    """
    command = [
        "vpype",
        "--config",
        str(config_path),
        "read",
        str(source),
        "linemerge",
        "linesimplify",
        "reloop",
        "linesort",
        "layout",
        "--fit-to-margins",
        margin,
    ]

    if landscape:
        command.append("--landscape")

    command.extend(
        [
            page_size,
            "write",
            "--device",
            device,
            "--page-size",
            page_size,
            "--center",
        ]
    )

    if landscape:
        command.append("--landscape")
    if velocity is not None:
        command.extend(["--velocity", str(velocity)])
    if absolute:
        command.append("--absolute")

    command.append(str(destination))
    return command


def run_command(command: Sequence[str], dry_run: bool = False) -> None:
    """Run a subprocess, logging the exact shell-equivalent command."""
    printable = subprocess.list2cmdline(list(command))
    LOG.info("Command: %s", printable)

    if dry_run:
        return

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise ConversionError(
            "The 'vpype' executable was not found. Install vpype in the "
            "active Python environment and confirm it is on PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise ConversionError(
            f"vpype exited with status {exc.returncode} while processing the file."
        ) from exc


def validate_hpgl(path: Path) -> None:
    """
    Perform lightweight safety checks on a generated HP-GL file.

    This is not a complete HP-GL parser. It catches empty output and verifies
    that the file contains common initialization/pen/motion instructions.
    """
    if not path.is_file() or path.stat().st_size == 0:
        raise ConversionError(f"vpype produced no usable output: {path}")

    text = path.read_text(encoding="ascii", errors="ignore").upper()
    expected_tokens = ("IN;", "PU", "PD", "PA", "PR")
    if not any(token in text for token in expected_tokens):
        raise ConversionError(
            f"{path} does not appear to contain ordinary HP-GL instructions."
        )


def send_with_chiplotle(hpgl_path: Path) -> None:
    """
    Send an HP-GL file through Chiplotle3 to the first detected plotter.

    Chiplotle3 is the Python-3 port. Some systems still expose the historical
    package name ``chiplotle``, so both imports are attempted. Device discovery
    may ask you to select a generic or similar Roland plotter profile the first
    time the DPX-3300 is connected.
    """
    try:
        from chiplotle3.tools.plottertools import instantiate_plotters
    except ImportError:
        try:
            from chiplotle.tools.plottertools import instantiate_plotters
        except ImportError as exc:
            raise RuntimeError(
                "Chiplotle3 is not installed. Install it before using --send."
            ) from exc

    plotters = instantiate_plotters()
    if not plotters:
        raise RuntimeError(
            "Chiplotle did not detect a plotter. Check power, cabling, serial "
            "permissions, and the DPX-3300 interface switch."
        )

    plotter = plotters[0]
    LOG.info("Sending %s to the first detected plotter.", hpgl_path.name)
    plotter.write_file(str(hpgl_path))


def convert_files(
    sources: Iterable[Path],
    output_dir: Path,
    *,
    config_path: Path,
    device: str,
    page_size: str,
    landscape: bool,
    margin: str,
    velocity: float | None,
    absolute: bool,
    overwrite: bool,
    send: bool,
    dry_run: bool,
) -> list[Path]:
    """Convert all *sources* and optionally transmit each result."""
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    for source in sources:
        destination = output_dir / f"{source.stem}.hpgl"

        if destination.exists() and not overwrite:
            raise FileExistsError(
                f"Output already exists: {destination}. Use --overwrite to replace it."
            )

        command = build_vpype_command(
            source,
            destination,
            config_path=config_path,
            device=device,
            page_size=page_size,
            landscape=landscape,
            margin=margin,
            velocity=velocity,
            absolute=absolute,
        )
        LOG.info("Converting %s -> %s", source.name, destination.name)
        run_command(command, dry_run=dry_run)

        if not dry_run:
            validate_hpgl(destination)
            LOG.info(
                "Created %s (%d bytes)", destination, destination.stat().st_size
            )
            if send:
                send_with_chiplotle(destination)

        outputs.append(destination)

    return outputs


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Define and parse command-line options."""
    parser = argparse.ArgumentParser(
        description="Convert SVG vector artwork to DPX-3300-compatible HP-GL."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=existing_directory,
        help="Directory containing source SVG files.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory in which .hpgl files will be written.",
    )
    parser.add_argument(
        "--file",
        help="Convert only this SVG filename inside --input-dir.",
    )
    parser.add_argument(
        "--vpype-config",
        type=existing_file,
        default=DEFAULT_VPYPE_CONFIG,
        help=(
            "vpype TOML configuration file. Default: the repository's "
            "vpype.toml next to this script."
        ),
    )
    parser.add_argument(
        "--device",
        default="dpx3300",
        help=(
            "vpype HP-GL device profile. Default: dpx3300, the project's "
            "center-origin profile for this machine."
        ),
    )
    parser.add_argument(
        "--page-size",
        default="a3",
        help="vpype page size, such as a4, a3, letter, or tabloid. Default: a3.",
    )
    parser.add_argument(
        "--landscape",
        action="store_true",
        help="Use landscape orientation.",
    )
    parser.add_argument(
        "--margin",
        default="10mm",
        help="Minimum layout margin understood by vpype. Default: 10mm.",
    )
    parser.add_argument(
        "--velocity",
        type=positive_float,
        help="Optional HP-GL VS pen-speed value. Begin conservatively.",
    )
    parser.add_argument(
        "--absolute",
        action="store_true",
        help="Generate absolute rather than compact relative HP-GL coordinates.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="After conversion, send each HP-GL file using Chiplotle3.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing .hpgl output files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the vpype commands without running them.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed logging.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Program entry point. Return a conventional process exit status."""
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if shutil.which("vpype") is None and not args.dry_run:
        LOG.error(
            "vpype is not available on PATH. Install it in the active environment."
        )
        return 2

    try:
        input_dir = args.input_dir
        output_dir = args.output_dir.expanduser().resolve()
        sources = discover_svg_files(input_dir, args.file)

        outputs = convert_files(
            sources,
            output_dir,
            config_path=args.vpype_config,
            device=args.device,
            page_size=args.page_size,
            landscape=args.landscape,
            margin=args.margin,
            velocity=args.velocity,
            absolute=args.absolute,
            overwrite=args.overwrite,
            send=args.send,
            dry_run=args.dry_run,
        )
    except (ConversionError, FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        LOG.error("%s", exc)
        return 1

    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
