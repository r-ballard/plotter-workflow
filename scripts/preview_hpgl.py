"""Render a read-only DPX-3300 HP-GL preview and measured path summary."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")
PEN_COLORS = ("#1d3557", "#b21e35", "#18714a", "#713d9a", "#a05214", "#007f91", "#765b15", "#4f4f4f")


def pairs(arguments: str) -> list[tuple[float, float]]:
    if not arguments.strip():
        return []
    parts = [part.strip() for part in arguments.split(",")]
    if len(parts) % 2 or any(not NUMBER.fullmatch(part) for part in parts):
        raise ValueError(f"invalid HP-GL coordinate list: {arguments!r}")
    return [(float(parts[i]), float(parts[i + 1])) for i in range(0, len(parts), 2)]


def trace(text: str):
    current = (0.0, 0.0)
    absolute = True
    pen_down = False
    slot = 0
    segments = []
    stroke_start = True
    stroke_count = 0
    selections = []
    for raw in text.replace("\r", "\n").split(";"):
        command = raw.strip()
        if not command:
            continue
        if len(command) < 2:
            raise ValueError(f"unsupported HP-GL command: {command!r}")
        opcode, arguments = command[:2].upper(), command[2:].strip()
        if opcode in ("IN", "DF"):
            if arguments:
                raise ValueError(f"unsupported HP-GL command: {command!r}")
            if opcode == "IN":
                current, absolute, pen_down, slot = (0.0, 0.0), True, False, 0
            continue
        if opcode == "SP":
            if pen_down or not arguments.isdigit() or not 0 <= int(arguments) <= 8:
                raise ValueError(f"invalid pen selection: {command!r}")
            slot = int(arguments)
            if slot:
                selections.append(slot)
            stroke_start = True
            continue
        if opcode not in ("PA", "PR", "PU", "PD"):
            raise ValueError(f"unsupported HP-GL command: {opcode}")
        if opcode == "PA":
            absolute = True
        elif opcode == "PR":
            absolute = False
        elif opcode == "PU":
            pen_down = False
            stroke_start = True
        else:
            if slot == 0:
                raise ValueError("pen-down motion has no selected physical pen")
            if not pen_down:
                stroke_start = True
            pen_down = True
        for x, y in pairs(arguments):
            end = (x, y) if absolute else (current[0] + x, current[1] + y)
            if not all(math.isfinite(value) for value in end):
                raise ValueError("non-finite HP-GL coordinate")
            if end != current:
                segments.append((current, end, pen_down, slot))
                if pen_down and stroke_start:
                    stroke_count += 1
                    stroke_start = False
            current = end
    if not any(segment[2] for segment in segments):
        raise ValueError("HP-GL contains no pen-down segments")
    return segments, selections, stroke_count


def placement_data(path: Path, hpgl: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("source_hpgl") != hpgl.name or data.get("status") != "pass":
        raise ValueError("placement sidecar does not describe a passing report for this HP-GL filename")
    unit = float(data["plotter_unit_length_mm"])
    bounds = data["paper_bounds"]
    xmin, ymin, xmax, ymax = (float(bounds[key]) for key in ("min_x", "min_y", "max_x", "max_y"))
    if not all(math.isfinite(value) for value in (unit, xmin, ymin, xmax, ymax)) or unit <= 0 or xmin >= xmax or ymin >= ymax:
        raise ValueError("invalid physical unit or paper bounds in placement sidecar")
    return unit, (xmin, ymin, xmax, ymax)


def output(segments, selections, stroke_count, unit, bounds, hpgl_bytes):
    per_pen = {}
    down_length = up_length = 0.0
    down_count = up_count = 0
    drawing = []
    travel = []
    for start, end, down, slot in segments:
        distance = math.dist(start, end) * unit
        x1, y1 = start[0], -start[1]
        x2, y2 = end[0], -end[1]
        if down:
            down_count += 1
            down_length += distance
            entry = per_pen.setdefault(str(slot), {"pen_down_segments": 0, "pen_down_mm": 0.0})
            entry["pen_down_segments"] += 1
            entry["pen_down_mm"] += distance
            color = PEN_COLORS[slot - 1]
            drawing.append(f'<path d="M {x1:g} {y1:g} L {x2:g} {y2:g}" stroke="{color}"/>')
        else:
            up_count += 1
            up_length += distance
            travel.append(f'<path d="M {x1:g} {y1:g} L {x2:g} {y2:g}"/>')
    for entry in per_pen.values():
        entry["pen_down_mm"] = round(entry["pen_down_mm"], 3)
    xmin, ymin, xmax, ymax = bounds
    width, height = xmax - xmin, ymax - ymin
    svg = "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width * unit:g}mm" height="{height * unit:g}mm" viewBox="{xmin:g} {-ymax:g} {width:g} {height:g}">',
        "<title>Offline HP-GL preview; colors identify physical slots, not actual ink</title>",
        f'<rect x="{xmin:g}" y="{-ymax:g}" width="{width:g}" height="{height:g}" fill="white" stroke="#888" stroke-width="3"/>',
        '<g fill="none" stroke="#a0a0a0" stroke-width="2" stroke-dasharray="12 8"><title>Pen-up travel</title>',
        *travel,
        "</g>",
        '<g fill="none" stroke-width="4"><title>Pen-down drawing</title>',
        *drawing,
        "</g>",
        "</svg>",
        "",
    ])
    metrics = {
        "schema_version": 1,
        "preview_only": True,
        "hpgl_sha256": hashlib.sha256(hpgl_bytes).hexdigest(),
        "plotter_unit_length_mm": unit,
        "pen_selections": selections,
        "stroke_count": stroke_count,
        "pen_down_segments": down_count,
        "pen_up_segments": up_count,
        "pen_down_mm": round(down_length, 3),
        "pen_up_mm": round(up_length, 3),
        "per_pen": per_pen,
    }
    return svg, metrics


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hpgl", required=True, type=Path)
    parser.add_argument("--placement", type=Path, help="defaults to adjacent .placement.json")
    parser.add_argument("--preview", required=True, type=Path)
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    placement = args.placement or args.hpgl.with_suffix(".placement.json")
    sources = {args.hpgl.resolve(), placement.resolve()}
    targets = (args.preview, args.metrics)
    if args.preview.resolve() == args.metrics.resolve() or any(path.resolve() in sources for path in targets):
        parser.error("preview and metrics must be distinct from each other and from source files")
    if not args.overwrite and any(path.exists() for path in targets):
        parser.error("output exists; use --overwrite intentionally")
    try:
        hpgl_bytes = args.hpgl.read_bytes()
        segments, selections, stroke_count = trace(hpgl_bytes.decode("ascii"))
        unit, bounds = placement_data(placement, args.hpgl)
        svg, metrics = output(segments, selections, stroke_count, unit, bounds, hpgl_bytes)
        for path in targets:
            path.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if args.overwrite else "x"
        with args.preview.open(mode, encoding="utf-8", newline="\n") as stream:
            stream.write(svg)
        with args.metrics.open(mode, encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(metrics, indent=2) + "\n")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"preview error: {exc}", file=sys.stderr)
        return 1
    print(f"Preview saved to {args.preview}; metrics saved to {args.metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
