#!/usr/bin/env python3
"""Route the legacy cootie-catcher CLI through the declarative imposition object.

This migration is intentionally anchor-based so it can be applied to the active
refactor branch after nearby formatting or line-number changes. It is idempotent,
refuses to write when required anchors cannot be found, and compiles the modified
module before replacing it.
"""

from __future__ import annotations

import re
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "cootie_impose.py"


def replace_function(
    text: str,
    *,
    function_name: str,
    next_function_name: str,
    replacement: str,
    marker: str,
) -> str:
    """Replace one top-level function body using stable function-name anchors."""
    if marker in text:
        return text

    pattern = re.compile(
        rf"^def {re.escape(function_name)}\(.*?(?=^def {re.escape(next_function_name)}\()",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        raise SystemExit(
            f"Cannot integrate {function_name}: expected function boundary was not found."
        )
    return text[: match.start()] + replacement.rstrip() + "\n\n\n" + text[match.end() :]


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    object_import = (
        "from imposition.model import ObjectPlacement, SheetSpec\n"
        "from imposition.objects.cootie_catcher import COOTIE_CATCHER, CootieCatcherError\n"
    )
    if object_import not in text:
        anchor = "from imposition.source import ImpositionSourceError, inspect_svg_source\n"
        if anchor not in text:
            raise SystemExit(
                "Cannot integrate imposition-object imports: source-inspection import "
                "anchor was not found. Apply the prior imposition source slice first."
            )
        text = text.replace(anchor, object_import + anchor, 1)

    text = replace_function(
        text,
        function_name="square_placement",
        next_function_name="panel_polygon_normalized",
        marker="COOTIE_CATCHER.resolve_placement(",
        replacement='''def square_placement(
    sheet_size: str,
    *,
    position: str = "left",
    square_size_mm: float | None = None,
) -> SquarePlacement:
    """Return the square's placement within a supported landscape sheet."""
    if sheet_size not in SHEET_SIZES_MM:
        raise ImpositionError(f"Unsupported sheet size {sheet_size!r}.")

    sheet_width, sheet_height = SHEET_SIZES_MM[sheet_size]
    sheet = SheetSpec(
        name=sheet_size,
        width_mm=sheet_width,
        height_mm=sheet_height,
        orientation="landscape",
    )
    try:
        resolved = COOTIE_CATCHER.resolve_placement(
            sheet,
            {"position": position, "square_size_mm": square_size_mm},
        )
    except CootieCatcherError as exc:
        raise ImpositionError(str(exc)) from exc

    return SquarePlacement(
        x_mm=resolved.x_mm,
        y_mm=resolved.y_mm,
        size_mm=resolved.width_mm,
        position=position,
    )''',
    )

    text = replace_function(
        text,
        function_name="panel_polygon_normalized",
        next_function_name="panel_polygon_px",
        marker="COOTIE_CATCHER.slot(slot).polygon",
        replacement='''def panel_polygon_normalized(slot: str) -> Polygon:
    try:
        return COOTIE_CATCHER.slot(slot).polygon
    except CootieCatcherError as exc:
        raise ImpositionError(str(exc)) from exc''',
    )

    text = replace_function(
        text,
        function_name="guide_segments",
        next_function_name="build_guide_svg",
        marker="guides = COOTIE_CATCHER.guides(object_placement)",
        replacement='''def guide_segments(
    sheet_size: str, placement: SquarePlacement
) -> dict[str, list[tuple[Point, Point]]]:
    """Return object-owned trim and crease segments in physical SVG pixels."""
    if sheet_size not in SHEET_SIZES_MM:
        raise ImpositionError(f"Unsupported sheet size {sheet_size!r}.")

    sheet_width_mm, sheet_height_mm = SHEET_SIZES_MM[sheet_size]
    object_placement = ObjectPlacement(
        sheet=SheetSpec(
            name=sheet_size,
            width_mm=sheet_width_mm,
            height_mm=sheet_height_mm,
            orientation="landscape",
        ),
        x_mm=placement.x_mm,
        y_mm=placement.y_mm,
        width_mm=placement.size_mm,
        height_mm=placement.size_mm,
    )
    try:
        guides = COOTIE_CATCHER.guides(object_placement)
    except CootieCatcherError as exc:
        raise ImpositionError(str(exc)) from exc

    segments: dict[str, list[tuple[Point, Point]]] = {
        "trim": [],
        "first-blintz": [],
        "second-blintz": [],
        "center-prefold": [],
    }
    for guide in guides:
        points = guide.points
        point_pairs = pairwise((*points, points[0])) if guide.closed else pairwise(points)
        for start, end in point_pairs:
            segments[guide.kind].append(
                (
                    (_mm_to_px(start[0]), _mm_to_px(start[1])),
                    (_mm_to_px(end[0]), _mm_to_px(end[1])),
                )
            )
    return segments''',
    )

    compile(text, str(TARGET), "exec")
    TARGET.write_text(text, encoding="utf-8")
    print(f"Integrated declarative cootie-catcher object into {TARGET.name}.")


if __name__ == "__main__":
    main()
