from __future__ import annotations

from pathlib import Path

import pytest

import cootie_impose as cootie


def _write_svg(path: Path, *, canvas_attributes: str = "") -> Path:
    path.write_text(
        (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            f'{canvas_attributes} width="100" height="100" viewBox="0 0 100 100">'
            '<path d="M 5 95 L 50 5 L 95 95 Z"/>'
            "</svg>"
        ),
        encoding="utf-8",
    )
    return path


def test_cootie_source_resolution_accepts_intrinsic_canvas_metadata(
    tmp_path: Path,
) -> None:
    source = _write_svg(
        tmp_path / "triangle.svg",
        canvas_attributes=(
            'data-viz-canvas-version="1" '
            'data-viz-canvas-shape="triangle" '
            'data-viz-canvas-coordinate-system="svg-y-down" '
            'data-viz-canvas-up-anchor="vertex:1" '
            'data-viz-canvas-up-vector="0,-1" '
            'data-viz-canvas-polygon="5,95 50,5 95,95"'
        ),
    )

    assert cootie._resolve_source(tmp_path, source.name) == source.resolve()


def test_cootie_source_resolution_rejects_partial_intrinsic_canvas_metadata(
    tmp_path: Path,
) -> None:
    source = _write_svg(
        tmp_path / "partial.svg",
        canvas_attributes='data-viz-canvas-shape="triangle"',
    )

    with pytest.raises(cootie.ImpositionError, match="incomplete intrinsic canvas"):
        cootie._resolve_source(tmp_path, source.name)


def test_cootie_source_resolution_keeps_generic_svg_compatible(tmp_path: Path) -> None:
    source = _write_svg(tmp_path / "generic.svg")

    assert cootie._resolve_source(tmp_path, source.name) == source.resolve()
