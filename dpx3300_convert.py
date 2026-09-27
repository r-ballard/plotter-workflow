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
  project supplies ``vpype.toml`` with a DPX-3300 device profile supporting
  both centered paper placement and lower-left paper placement.
* The machine's native coordinate origin remains near the center of the bed.
  ``--paper-position lower-left`` does not redefine the machine origin; it
  maps the selected paper size into the lower-left portion of the DPX-3300
  maximum plotting area.
* Always make a small pen-up or sacrificial-paper test before plotting.
* The plotter and computer serial settings must match. The factory serial
  settings documented by Roland are 9600 baud, no parity, 8 data bits,
  and 1 stop bit.

Examples
--------
Convert every SVG in ./input to ./output:

    python3 dpx3300_convert.py \
        --input-dir ./input \
        --output-dir ./output

Convert one file for US Letter paper placed at the lower-left of the bed:

    python3 dpx3300_convert.py \
        --input-dir ./input \
        --output-dir ./output \
        --file drawing.svg \
        --page-size letter \
        --landscape \
        --paper-position lower-left \
        --margin 0.5in \
        --absolute

Use ``--paper-position center`` to retain the previously verified centered
paper placement.

Convert and immediately send each result with Chiplotle3:

    python3 dpx3300_convert.py \
        --input-dir ./input \
        --output-dir ./output \
        --send

Use --dry-run to print commands without executing them.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import logging
import math
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from pathlib import Path

from hpgl_placement import validate_hpgl_placement, write_placement_report
from logical_layer_contract import (
    NEUTRAL_CONTRACT,
    inspect_svg_contract,
    load_logical_layer_manifest,
)
from pen_plan import (
    PEN_POLICIES,
    LogicalPenPlanSpec,
    PenPlanError,
    ResolvedAssignment,
    ResolvedPenPlan,
    default_resolved_pen_plan_path,
    discover_pen_plan,
    format_pen_plan,
    load_pen_plan,
    plan_has_documented_tools,
    remap_hpgl_pen_selections,
    resolve_logical_pen_plan,
    resolve_pen_plan,
    write_resolved_pen_plan,
    write_resolved_plot_pass,
)
from svg_pen_contract import inspect_pen_layer_contract

LOG = logging.getLogger("dpx3300")
DEFAULT_VPYPE_CONFIG = Path(__file__).resolve().with_name("vpype.toml")

PAPER_POSITION_CENTER = "center"
PAPER_POSITION_LOWER_LEFT = "lower-left"

# Lower-left profiles are intentionally explicit. Their coordinate limits come
# from the DPX-3300 manual's maximum plotting-area table:
#   ANSI-D: X=-17750..16790, Y=-11180..11180
#   ISO-A1: X=-17300..16340, Y=-11880..11880
#
# The first release of lower-left placement supports the landscape paper sizes
# we have defined and reviewed in vpype.toml.
LOWER_LEFT_DEVICE_PAPERS = {
    "letter": "letter_lower_left",
    "tabloid": "tabloid_lower_left",
    "a4": "a4_lower_left",
    "a3": "a3_lower_left",
}


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


def preserved_physical_layout_metadata(path: Path) -> tuple[str, str] | None:
    """Return declared page size/orientation for a pre-imposed physical SVG."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None

    if root.get("data-plotter-workflow-layout") != "preserve":
        return None

    page_size = root.get("data-plotter-workflow-page-size")
    orientation = root.get("data-plotter-workflow-orientation")
    if not page_size or orientation not in {"landscape", "portrait"}:
        raise ConversionError(
            "Preserved-layout SVG is missing valid physical page size/orientation metadata."
        )
    return page_size, orientation


def svg_preserves_physical_layout(path: Path) -> bool:
    """Return True when *path* declares already-imposed physical coordinates."""
    return preserved_physical_layout_metadata(path) is not None


def resolve_device_page_size(
    page_size: str,
    paper_position: str,
    landscape: bool,
) -> str:
    """
    Resolve the vpype HP-GL paper profile for a physical bed position.

    ``layout`` still uses the ordinary page size (for example ``letter``), so
    artwork is fitted and centered *within the sheet*. The HP-GL writer then
    uses a DPX-3300-specific paper profile describing where that physical sheet
    sits on the plotter bed.

    Lower-left placement is currently limited to landscape profiles because
    those are the orientations whose hard-clip mapping has been explicitly
    reviewed against the DPX-3300 manual.
    """
    if paper_position == PAPER_POSITION_CENTER:
        return page_size

    if paper_position != PAPER_POSITION_LOWER_LEFT:
        raise ValueError(f"Unsupported paper position: {paper_position}")

    if not landscape:
        raise ValueError(
            "--paper-position lower-left currently requires --landscape. "
            "Use --paper-position center for portrait jobs."
        )

    try:
        return LOWER_LEFT_DEVICE_PAPERS[page_size.lower()]
    except KeyError as exc:
        supported = ", ".join(sorted(LOWER_LEFT_DEVICE_PAPERS))
        raise ValueError(
            "Lower-left paper placement is currently defined for: "
            f"{supported}. Received: {page_size!r}"
        ) from exc


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
    device_page_size: str | None = None,
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
        Fits and centers the drawing within the selected physical sheet.
    write
        Serializes the result as HP-GL using a DPX-3300 paper profile that
        determines where the physical sheet sits on the machine bed.
    """
    if device_page_size is None:
        device_page_size = page_size

    physical_layout = preserved_physical_layout_metadata(source)
    preserve_layout = physical_layout is not None
    if physical_layout is not None:
        expected_page_size, expected_orientation = physical_layout
        if expected_page_size.lower() != page_size.lower():
            raise ConversionError(
                "Preserved-layout SVG expects page size "
                f"{expected_page_size!r}, not {page_size!r}."
            )
        if (expected_orientation == "landscape") != landscape:
            raise ConversionError(
                f"Preserved-layout SVG expects {expected_orientation} orientation."
            )
        LOG.info(
            "Preserving physical SVG layout for %s (%s %s).",
            source.name,
            expected_page_size,
            expected_orientation,
        )

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
    ]

    if not preserve_layout:
        command.extend(["layout", "--fit-to-margins", margin])
        if landscape:
            command.append("--landscape")
        command.append(page_size)

    command.extend(
        [
            "write",
            "--device",
            device,
            "--page-size",
            device_page_size,
        ]
    )
    if not preserve_layout:
        command.append("--center")

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


def validate_hpgl(
    path: Path, expected_pens: tuple[int, ...] | None = None
) -> None:
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


    if expected_pens:
        missing = [pen for pen in expected_pens if f"SP{pen};" not in text]
        if missing:
            raise ConversionError(
                f"{path} is missing expected HP-GL pen selections: "
                + ", ".join(f"SP{pen}" for pen in missing)
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


def _neutral_context(source: Path):
    """Validate the imposition audit against the actual authoritative manifest."""
    audit_path = source.with_suffix(".imposition.json")
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConversionError(
            f"Missing or malformed neutral imposition audit: {audit_path}"
        ) from exc
    if (
        not isinstance(audit, dict)
        or type(audit.get("schema_version")) is not int
        or audit.get("schema_version") != 1
        or audit.get("source_mode") != "neutral"
        or audit.get("logical_layer_contract") != NEUTRAL_CONTRACT
    ):
        raise ConversionError("Invalid neutral imposition audit contract")
    raw_path = audit.get("source_manifest_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ConversionError("Imposition audit requires source_manifest_path")
    manifest_path = Path(raw_path)
    if not manifest_path.is_absolute():
        manifest_path = audit_path.parent / manifest_path
    try:
        manifest = load_logical_layer_manifest(manifest_path)
        manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    except (OSError, ValueError) as exc:
        raise ConversionError(
            f"Invalid source manifest in imposition audit: {exc}"
        ) from exc
    if audit.get("source_manifest_sha256") != manifest_hash:
        raise ConversionError("Imposition audit source manifest SHA-256 mismatch")
    if json.dumps(audit.get("logical_layers"), sort_keys=True) != json.dumps(
        manifest.raw["logical_layers"], sort_keys=True
    ):
        raise ConversionError("Imposition audit catalog differs from source manifest")
    contract = inspect_svg_contract(source, catalog=manifest.layers)
    if audit.get("logical_layer_ids") != [layer.id for layer in contract.layers]:
        raise ConversionError("SVG logical inventory differs from imposition audit")
    physical = preserved_physical_layout_metadata(source)
    if physical is not None:
        sheet = audit.get("sheet", {})
        if (
            not isinstance(sheet, dict)
            or (sheet.get("name"), sheet.get("orientation")) != physical
        ):
            raise ConversionError("SVG physical layout differs from imposition audit")
    return contract, manifest_hash


def _materialize_neutral_layers(source: Path) -> dict[str, ET.Element]:
    """Flatten shapes and intersect explicit local polygon clips in root coordinates.

    Curves use vpype's 0.1-pixel quantization. Clip boundaries must be exact
    simple polygons: rect, polygon, or a single closed M/L/H/V/Z path.
    Unsupported rendering/reference semantics fail before any output is run.
    """
    import vpype
    from shapely.geometry import LineString, Polygon

    from booklet_impose import _validate_neutral_renderables

    root = ET.parse(source).getroot()
    _validate_neutral_renderables(root, source)
    svg_ns = "{http://www.w3.org/2000/svg}"
    drawable = {"path", "line", "polyline", "polygon", "rect", "circle", "ellipse"}
    local = lambda node: node.tag.rsplit("}", 1)[-1]
    ids = {}
    for node in root.iter():
        if node.get("id"):
            if node.get("id") in ids:
                raise ConversionError("Duplicate SVG reference id")
            ids[node.get("id")] = node
        for key, value in node.attrib.items():
            if key.startswith("data-"):
                continue
            if key.rsplit("}", 1)[-1] == "href" or key in {"mask", "filter"}:
                raise ConversionError(f"Unsupported SVG reference attribute {key}")
            if key == "style":
                for declaration in value.split(";"):
                    if not declaration.strip():
                        continue
                    prop, sep, val = declaration.partition(":")
                    if (
                        not sep
                        or prop.strip()
                        not in {
                            "fill",
                            "stroke",
                            "stroke-width",
                            "stroke-linecap",
                            "stroke-linejoin",
                            "opacity",
                            "fill-opacity",
                            "stroke-opacity",
                        }
                        or "url(" in val.lower()
                    ):
                        raise ConversionError(
                            f"Unsupported SVG style/clip property: {prop}"
                        )
            elif "url(" in value.lower() and key != "clip-path":
                raise ConversionError(f"Unsupported SVG reference attribute {key}")
    # Normalize only the reader's outer viewport so its results stay in the
    # original root user units. Preserve the actual pass dimensions/viewBox.
    reader_root = ET.Element(root.tag, dict(root.attrib))
    offset_x = offset_y = 0.0
    if root.get("viewBox"):
        try:
            offset_x, offset_y, width, height = map(
                float, re.split(r"[\s,]+", root.get("viewBox").strip())
            )
        except ValueError as exc:
            raise ConversionError("Invalid SVG viewBox") from exc
        if (
            not all(math.isfinite(v) for v in (offset_x, offset_y, width, height))
            or width <= 0
            or height <= 0
        ):
            raise ConversionError("Invalid SVG viewBox")
        reader_root.set("width", str(width))
        reader_root.set("height", str(height))

    def flatten(chain, leaf):
        fragment = copy.deepcopy(reader_root)
        fragment.attrib.pop("clip-path", None)
        parent = fragment
        for ancestor in chain:
            wrapper = ET.SubElement(
                parent,
                ancestor.tag if local(ancestor) in {"g", "svg"} else svg_ns + "g",
                dict(ancestor.attrib),
            )
            wrapper.attrib.pop("clip-path", None)
            parent = wrapper
        element = copy.deepcopy(leaf)
        element.attrib.pop("clip-path", None)
        parent.append(element)
        lines, _, _ = vpype.read_svg(
            io.StringIO(ET.tostring(fragment, encoding="unicode")),
            quantization=0.1,
            crop=False,
        )
        return [
            [(float(p.real) + offset_x, float(p.imag) + offset_y) for p in line]
            for line in lines
        ]

    def clip_polygon(raw, chain):
        match = re.fullmatch(r"url\(\s*#([^\s)]+)\s*\)", raw)
        clip = ids.get(match.group(1)) if match else None
        if clip is None or local(clip) != "clipPath":
            raise ConversionError(f"Unsupported or dangling clip reference: {raw}")
        if (
            clip.get("clipPathUnits", "userSpaceOnUse") != "userSpaceOnUse"
            or len(clip) != 1
            or clip.get("clip-path")
        ):
            raise ConversionError(
                "Unsupported clip units, nesting, or multiple clip shapes"
            )
        shape = clip[0]
        if (
            local(shape) not in {"rect", "polygon", "path"}
            or shape.get("clip-path")
            or shape.get("rx")
            or shape.get("ry")
        ):
            raise ConversionError("Unsupported clip shape; use a simple polygon")
        if local(shape) == "path" and any(
            c not in "MmLlHhVvZzEe" for c in re.findall(r"[A-Za-z]", shape.get("d", ""))
        ):
            raise ConversionError("Unsupported curved clip path; use M/L/H/V/Z")
        wrapper = ET.Element(svg_ns + "g", {"transform": clip.get("transform", "")})
        lines = flatten(chain + [wrapper], shape)
        if len(lines) != 1 or len(lines[0]) < 4 or lines[0][0] != lines[0][-1]:
            raise ConversionError("Clip must be one closed polygon")
        polygon = Polygon(lines[0])
        if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
            raise ConversionError("Clip must be a valid simple polygon")
        return polygon

    layers = {}

    def visit(node, chain, clips, output):
        name = local(node)
        if name in {"defs", "metadata", "title", "desc", "clipPath"}:
            return
        ancestry = chain + [node]
        if name == "svg" and node.get("overflow", "hidden") != "visible":
            if (
                node.get("overflow", "hidden") != "hidden"
                or not node.get("width")
                or not node.get("height")
            ):
                raise ConversionError(
                    "Unsupported nested SVG viewport; specify width/height and hidden or visible overflow"
                )
            viewport = ET.Element(
                svg_ns + "rect",
                {
                    "x": node.get("x", "0"),
                    "y": node.get("y", "0"),
                    "width": node.get("width"),
                    "height": node.get("height"),
                    "transform": node.get("transform", ""),
                },
            )
            bounds = flatten(chain, viewport)
            if len(bounds) != 1:
                raise ConversionError("Invalid nested SVG viewport clip")
            clips = clips + [Polygon(bounds[0])]
        if node.get("clip-path"):
            clips = clips + [clip_polygon(node.get("clip-path"), ancestry)]
        if name in drawable:
            for points in flatten(chain, node):
                if len(points) < 2:
                    continue
                geometry = LineString(points)
                for boundary in clips:
                    geometry = geometry.intersection(boundary)
                parts = (
                    [geometry]
                    if geometry.geom_type == "LineString"
                    else list(getattr(geometry, "geoms", ()))
                )
                for part in parts:
                    if part.geom_type != "LineString" or part.is_empty:
                        continue
                    ET.SubElement(
                        output,
                        svg_ns + "polyline",
                        {
                            "points": " ".join(
                                f"{x:.12g},{y:.12g}" for x, y in part.coords
                            ),
                            "fill": "none",
                            "stroke": "black",
                        },
                    )
            return
        for child in node:
            visit(child, ancestry, clips, output)

    root_clips = (
        [clip_polygon(root.get("clip-path"), [])] if root.get("clip-path") else []
    )
    for group in root:
        layer_id = group.get("data-viz-layer-id")
        if layer_id is not None:
            output = ET.Element(svg_ns + "g", {"data-viz-layer-id": layer_id})
            visit(group, [], root_clips, output)
            layers[layer_id] = output
    return layers


def _validate_neutral_hpgl(path: Path, expected: tuple[int, ...]) -> None:
    validate_hpgl(path, expected_pens=expected)
    text = path.read_text(encoding="ascii")
    selections = []
    for match in re.finditer(r"SP([^;]*);", text, re.IGNORECASE):
        value = match.group(1)
        if not re.fullmatch(r"[0-8]", value):
            raise ConversionError(f"Unexpected HP-GL pen selection SP{value}")
        if value != "0" and int(value) not in selections:
            selections.append(int(value))
    if tuple(selections) != expected:
        raise ConversionError(
            f"HP-GL physical pen order {selections} differs from {expected}"
        )


def convert_neutral_svg(
    source: Path,
    spec: LogicalPenPlanSpec | None,
    output_dir: Path,
    *,
    config_path: Path = DEFAULT_VPYPE_CONFIG,
    device: str = "dpx3300",
    page_size: str = "a3",
    landscape: bool = False,
    margin: str = "10mm",
    velocity: float | None = None,
    absolute: bool = False,
    device_page_size: str | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Convert validated neutral input into ordered, transactionally staged passes.

    Dry runs return planned (not existing) paths and log deterministic commands.
    No temporary SVGs or output directories are created by dry runs.
    """
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    contract, manifest_hash = _neutral_context(source)
    passes = resolve_logical_pen_plan(
        contract, spec, source_manifest_hash=manifest_hash
    )
    names = set()
    outputs = []
    for plot_pass in passes:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", plot_pass.id):
            raise ConversionError(f"Unsafe pass filename id: {plot_pass.id!r}")
        name = f"{source.stem}.{plot_pass.id}.hpgl"
        if name.casefold() in names:
            raise ConversionError(f"Pass filename collision: {name}")
        names.add(name.casefold())
        outputs.append(output_dir / name)
    artifacts = [
        path
        for dest in outputs
        for path in (
            dest,
            default_resolved_pen_plan_path(dest),
            dest.with_suffix(".placement.json"),
        )
    ]
    for path in artifacts:
        if path.exists() and (not overwrite or not path.is_file()):
            raise FileExistsError(f"Output already exists: {path}; use --overwrite")
    layers = _materialize_neutral_layers(source)
    root = ET.parse(source).getroot()
    roots = []
    for plot_pass in passes:
        fragment = ET.Element(root.tag, dict(root.attrib))
        fragment.attrib.pop("data-viz-layer-contract", None)
        fragment.attrib.pop("clip-path", None)
        fragment.attrib.pop("transform", None)
        for number, assignment in enumerate(plot_pass.assignments, 1):
            group = ET.SubElement(
                fragment, "{http://www.w3.org/2000/svg}g", {"id": f"pen-{number}"}
            )
            for layer_id in assignment.layer_ids:
                group.append(copy.deepcopy(layers[layer_id]))
            if not any(len(child) for child in group):
                raise ConversionError(
                    f"Pass {plot_pass.id} slot {assignment.physical_slot} has no geometry after clipping"
                )
        roots.append(fragment)
    options = {
        "config_path": config_path,
        "device": device,
        "page_size": page_size,
        "device_page_size": device_page_size,
        "landscape": landscape,
        "margin": margin,
        "velocity": velocity,
        "absolute": absolute,
    }
    # Validate layout against the real source; dry-run pass paths do not exist.
    template = build_vpype_command(source, outputs[0], **options)
    if dry_run:
        for dest in outputs:
            command = list(template)
            command[command.index("read") + 1] = str(dest.with_suffix(".svg"))
            command[-1] = str(dest)
            run_command(command, dry_run=True)
            LOG.info(
                "Planned artifacts: %s, %s", dest, default_resolved_pen_plan_path(dest)
            )
        return outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".neutral-", dir=output_dir) as scratch:
        staging = Path(scratch)
        staged = []
        for index, (plot_pass, fragment, destination) in enumerate(
            zip(passes, roots, outputs), 1
        ):
            temp_svg = staging / destination.with_suffix(".svg").name
            temp_hpgl = staging / destination.name
            ET.ElementTree(fragment).write(
                temp_svg, encoding="utf-8", xml_declaration=True
            )
            run_command(build_vpype_command(temp_svg, temp_hpgl, **options))
            logical = tuple(range(1, len(plot_pass.assignments) + 1))
            physical = tuple(a.physical_slot for a in plot_pass.assignments)
            _validate_neutral_hpgl(temp_hpgl, logical)
            remap = ResolvedPenPlan(
                str(source),
                "explicit",
                (),
                tuple(
                    ResolvedAssignment(n, a.physical_slot, (), "")
                    for n, a in enumerate(plot_pass.assignments, 1)
                ),
            )
            remap_hpgl_pen_selections(temp_hpgl, remap)
            _validate_neutral_hpgl(temp_hpgl, physical)
            placement = temp_hpgl.with_suffix(".placement.json")
            report = validate_hpgl_placement(
                temp_hpgl,
                config_path=config_path,
                device=device,
                page_profile=device_page_size or page_size,
                margin=margin,
            )
            write_placement_report(report, placement)
            sidecar = default_resolved_pen_plan_path(temp_hpgl)
            payload = {
                "schema_version": 2,
                "kind": "resolved-dpx3300-logical-pass",
                "pass_id": plot_pass.id,
                "pass_number": index,
                "pass_count": len(passes),
                "source_svg": str(source.resolve()),
                "source_svg_sha256": source_hash,
                "source_manifest_hash": manifest_hash,
                "assignments": [
                    {"layer_ids": list(a.layer_ids), "physical_slot": a.physical_slot}
                    for a in plot_pass.assignments
                ],
                "omitted_layers": list(plot_pass.omitted_layers),
                "repeated_layers": list(spec.repeated_layers if spec else ()),
                "physical_slots": list(physical),
            }
            write_resolved_plot_pass(sidecar, payload)
            staged.extend((temp_hpgl, sidecar, placement))
        # Keep previous artifacts intact until every pass has succeeded. Restore
        # them too if publication itself fails partway through.
        if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
            raise ConversionError(
                "Source SVG changed during conversion; no passes published"
            )
        if _neutral_context(source)[1] != manifest_hash:
            raise ConversionError(
                "Source manifest changed during conversion; no passes published"
            )
        backups = {path: path.read_bytes() for path in artifacts if path.exists()}
        published = []
        try:
            for path in staged:
                target = output_dir / path.name
                if target.exists() and not overwrite:
                    raise FileExistsError(
                        f"Output appeared during conversion: {target}"
                    )
                path.replace(target)
                published.append(target)
        except BaseException:
            for path in published:
                if path in backups:
                    path.write_bytes(backups[path])
                else:
                    path.unlink()
            raise
    return outputs


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
    paper_position: str = PAPER_POSITION_CENTER,
    pen_plan_path: Path | None = None,
    pen_policy: str | None = None,
    pen_map: str | None = None,
    confirm_pen_plan: bool = False,
) -> list[Path]:
    """Convert all *sources* and optionally transmit each result."""
    sources = list(sources)
    if pen_plan_path is not None and len(sources) != 1:
        raise ValueError("--pen-plan may only be used when converting one SVG")
    outputs: list[Path] = []

    device_page_size = resolve_device_page_size(
        page_size=page_size,
        paper_position=paper_position,
        landscape=landscape,
    )
    LOG.info(
        "Paper placement: %s (layout=%s, device-profile=%s)",
        paper_position,
        page_size,
        device_page_size,
    )

    for source in sources:
        root = ET.parse(source).getroot()
        if root.get("data-viz-layer-contract") == NEUTRAL_CONTRACT:
            if send:
                raise ConversionError("Neutral jobs do not support automatic --send; plot each verified pass separately")
            if pen_policy is not None or pen_map is not None or confirm_pen_plan:
                raise PenPlanError("Neutral input requires a v2 plan; legacy pen flags are incompatible")
            selected = discover_pen_plan(source, pen_plan_path)
            spec = load_pen_plan(selected) if selected is not None else None
            if spec is not None and not isinstance(spec, LogicalPenPlanSpec):
                raise PenPlanError("Neutral input requires a schema_version=2 pen plan")
            outputs.extend(convert_neutral_svg(
                source, spec, output_dir, config_path=config_path, device=device,
                page_size=page_size, device_page_size=device_page_size,
                landscape=landscape, margin=margin, velocity=velocity,
                absolute=absolute, overwrite=overwrite, dry_run=dry_run,
            ))
            continue
        inspect_svg_contract(source)  # Reject unknown, partial, and mixed declarations.
        output_dir.mkdir(parents=True, exist_ok=True)
        pen_contract = inspect_pen_layer_contract(source)
        resolved_pen_plan = None
        expected_logical_pens = None
        if pen_contract is not None:
            resolved_pen_plan = resolve_pen_plan(
                source,
                plan_path=pen_plan_path,
                cli_policy=pen_policy,
                cli_pen_map=pen_map,
            )
            expected_logical_pens = resolved_pen_plan.logical_pens
            LOG.info(
                "Detected logical SVG pen layers: %s",
                ", ".join(
                    f"pen-{pen}" for pen in resolved_pen_plan.declared_logical_pens
                ),
            )
            for line in format_pen_plan(resolved_pen_plan).splitlines():
                LOG.info("%s", line)
        elif pen_plan_path is not None or pen_policy is not None or pen_map is not None:
            raise PenPlanError(
                "Pen assignment options require a contract SVG with top-level pen-N layers"
            )

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
            device_page_size=device_page_size,
            landscape=landscape,
            margin=margin,
            velocity=velocity,
            absolute=absolute,
        )
        LOG.info("Converting %s -> %s", source.name, destination.name)
        run_command(command, dry_run=dry_run)

        if not dry_run:
            validate_hpgl(destination, expected_pens=expected_logical_pens)
            placement_report = validate_hpgl_placement(
                destination,
                config_path=config_path,
                device=device,
                page_profile=device_page_size,
                margin=margin,
            )
            placement_path = destination.with_suffix(".placement.json")
            write_placement_report(placement_report, placement_path)
            LOG.info(
                "Placement validated: drawing X=%.0f..%.0f, Y=%.0f..%.0f; report=%s",
                placement_report.drawing_bounds.min_x,
                placement_report.drawing_bounds.max_x,
                placement_report.drawing_bounds.min_y,
                placement_report.drawing_bounds.max_y,
                placement_path,
            )
            if resolved_pen_plan is not None:
                remap_hpgl_pen_selections(destination, resolved_pen_plan)
                validate_hpgl(
                    destination, expected_pens=resolved_pen_plan.physical_pens
                )
                sidecar = default_resolved_pen_plan_path(destination)
                write_resolved_pen_plan(sidecar, resolved_pen_plan)
                LOG.info("Created resolved pen plan: %s", sidecar)
                if send and len(resolved_pen_plan.physical_pens) > 1:
                    if not plan_has_documented_tools(resolved_pen_plan):
                        raise ConversionError(
                            "Multi-pen --send requires a pen-plan JSON with a tool "
                            "or label for every used physical slot."
                        )
                    if not confirm_pen_plan:
                        raise ConversionError(
                            "Multi-pen --send requires --confirm-pen-plan after "
                            "verifying the printed carriage loading plan."
                        )
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
            "DPX-3300 profile with selectable paper placement."
        ),
    )
    parser.add_argument(
        "--page-size",
        default="a3",
        help="vpype page size, such as a4, a3, letter, or tabloid. Default: a3.",
    )
    parser.add_argument(
        "--paper-position",
        choices=(PAPER_POSITION_CENTER, PAPER_POSITION_LOWER_LEFT),
        default=PAPER_POSITION_CENTER,
        help=(
            "Physical location of the selected sheet on the DPX-3300 bed. "
            "Default: center. Use lower-left to place supported landscape "
            "paper sizes against the lower-left maximum plotting-area corner."
        ),
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
        "--pen-plan",
        type=existing_file,
        help=(
            "User-authored .penplan.json file. If omitted, an adjacent "
            "<svg-stem>.penplan.json is discovered automatically."
        ),
    )
    parser.add_argument(
        "--pen-policy",
        choices=PEN_POLICIES,
        help=(
            "Physical pen assignment policy for contract SVGs when no JSON "
            "pen plan is present: preserve, compact, or explicit."
        ),
    )
    parser.add_argument(
        "--pen-map",
        help=(
            "Explicit logical:physical mapping, for example 2:1,3:2,4:5. "
            "Requires --pen-policy explicit and cannot be combined with a JSON plan."
        ),
    )
    parser.add_argument(
        "--confirm-pen-plan",
        action="store_true",
        help=(
            "Confirm that the printed multi-pen carriage loading plan has been "
            "checked. Required for multi-pen --send."
        ),
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
            paper_position=args.paper_position,
            pen_plan_path=args.pen_plan,
            pen_policy=args.pen_policy,
            pen_map=args.pen_map,
            confirm_pen_plan=args.confirm_pen_plan,
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
