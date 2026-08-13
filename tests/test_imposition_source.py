from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from imposition.source import (
    ImpositionSourceError,
    inspect_svg_source,
    parse_intrinsic_canvas,
)


def _canvas_svg(**overrides: str) -> str:
    attributes = {
        "data-viz-canvas-version": "1",
        "data-viz-canvas-shape": "triangle",
        "data-viz-canvas-coordinate-system": "svg-y-down",
        "data-viz-canvas-up-anchor": "vertex:0",
        "data-viz-canvas-up-vector": "0,-1",
        "data-viz-canvas-polygon": "50,0 100,100 0,100",
        "data-viz-canvas-clip-id": "viz-canvas-clip",
    }
    attributes.update(overrides)
    rendered = " ".join(f'{key}="{value}"' for key, value in attributes.items())
    return f'<svg xmlns="http://www.w3.org/2000/svg" {rendered}><path d="M0 0"/></svg>'


def test_generic_svg_has_no_intrinsic_canvas(tmp_path: Path) -> None:
    source = tmp_path / "generic.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0 L1 1"/></svg>',
        encoding="utf-8",
    )

    assert inspect_svg_source(source) is None


def test_triangle_intrinsic_canvas_is_parsed(tmp_path: Path) -> None:
    source = tmp_path / "triangle.svg"
    source.write_text(_canvas_svg(), encoding="utf-8")

    canvas = inspect_svg_source(source)

    assert canvas is not None
    assert canvas.version == 1
    assert canvas.shape == "triangle"
    assert canvas.coordinate_system == "svg-y-down"
    assert canvas.polygon == ((50.0, 0.0), (100.0, 100.0), (0.0, 100.0))
    assert canvas.up_anchor == "vertex:0"
    assert canvas.up_vector == (0.0, -1.0)
    assert canvas.clip_id == "viz-canvas-clip"


def test_partial_intrinsic_canvas_contract_is_rejected() -> None:
    root = ET.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg" data-viz-canvas-shape="triangle"/>'
    )

    with pytest.raises(ImpositionSourceError, match="incomplete intrinsic canvas"):
        parse_intrinsic_canvas(root)


def test_non_normalized_up_vector_is_rejected() -> None:
    root = ET.fromstring(_canvas_svg(**{"data-viz-canvas-up-vector": "0,-2"}))

    with pytest.raises(ImpositionSourceError, match="must be normalized"):
        parse_intrinsic_canvas(root)


def test_anchor_must_reference_existing_polygon_vertex() -> None:
    root = ET.fromstring(_canvas_svg(**{"data-viz-canvas-up-anchor": "vertex:3"}))

    with pytest.raises(ImpositionSourceError, match="outside a 3-vertex polygon"):
        parse_intrinsic_canvas(root)


def test_unknown_coordinate_system_is_rejected() -> None:
    root = ET.fromstring(
        _canvas_svg(**{"data-viz-canvas-coordinate-system": "cartesian-y-up"})
    )

    with pytest.raises(ImpositionSourceError, match="coordinate system"):
        parse_intrinsic_canvas(root)


def test_unsupported_svg_elements_remain_rejected(tmp_path: Path) -> None:
    source = tmp_path / "raster.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="x.png"/></svg>',
        encoding="utf-8",
    )

    with pytest.raises(ImpositionSourceError, match="unsupported SVG elements"):
        inspect_svg_source(source)
