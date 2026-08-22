from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from imposition.geometry import resolve_orientation_frame_degrees
from imposition.model import OrientationFrame
from imposition.source import parse_intrinsic_canvas


def _intrinsic_svg(
    *,
    shape: str,
    polygon: str,
    anchor: str,
    up_vector: str,
) -> ET.Element:
    return ET.fromstring(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'data-viz-canvas-version="1" '
        f'data-viz-canvas-shape="{shape}" '
        f'data-viz-canvas-coordinate-system="svg-y-down" '
        f'data-viz-canvas-up-anchor="{anchor}" '
        f'data-viz-canvas-up-vector="{up_vector}" '
        f'data-viz-canvas-polygon="{polygon}"/>'
    )


def test_corner_up_square_source_resolves_diagonal_frame() -> None:
    diagonal = 2**-0.5
    root = _intrinsic_svg(
        shape="square",
        polygon="0,0 100,0 100,100 0,100",
        anchor="vertex:0",
        up_vector=f"{-diagonal},{-diagonal}",
    )

    canvas = parse_intrinsic_canvas(root)

    assert canvas is not None
    assert canvas.orientation_frame.anchor == "vertex:0"
    assert resolve_orientation_frame_degrees(
        canvas.orientation_frame,
        OrientationFrame(up_vector=(0.0, -1.0)),
    ) == pytest.approx(45.0)


def test_triangle_edge_anchor_can_resolve_apex_right_layout() -> None:
    root = _intrinsic_svg(
        shape="triangle",
        polygon="50,0 100,100 0,100",
        anchor="edge:1",
        up_vector="1,0",
    )

    canvas = parse_intrinsic_canvas(root)

    assert canvas is not None
    assert canvas.orientation_frame.anchor == "edge:1"
    assert resolve_orientation_frame_degrees(
        canvas.orientation_frame,
        OrientationFrame(up_vector=(0.0, -1.0)),
    ) == pytest.approx(270.0)


def test_triangle_edge_anchor_can_resolve_apex_left_layout() -> None:
    root = _intrinsic_svg(
        shape="triangle",
        polygon="50,0 100,100 0,100",
        anchor="edge:1",
        up_vector="-1,0",
    )

    canvas = parse_intrinsic_canvas(root)

    assert canvas is not None
    assert resolve_orientation_frame_degrees(
        canvas.orientation_frame,
        OrientationFrame(up_vector=(0.0, -1.0)),
    ) == pytest.approx(90.0)


def test_arbitrary_non_cardinal_source_vector_is_preserved() -> None:
    root = _intrinsic_svg(
        shape="triangle",
        polygon="50,0 100,100 0,100",
        anchor="vertex:0",
        up_vector="0.6,-0.8",
    )

    canvas = parse_intrinsic_canvas(root)

    assert canvas is not None
    assert canvas.up_vector == (0.6, -0.8)
    assert canvas.orientation_frame.up_vector == (0.6, -0.8)
