from pathlib import Path

import pytest

from svg_pen_contract import PenLayerContractError, inspect_pen_layer_contract


def write_svg(tmp_path: Path, body: str, *, xmlns: bool = True) -> Path:
    path = tmp_path / "drawing.svg"
    namespace = ' xmlns="http://www.w3.org/2000/svg"' if xmlns else ""
    path.write_text(
        f"<svg{namespace} width=\"100\" height=\"100\">{body}</svg>",
        encoding="utf-8",
    )
    return path


def test_generic_svg_does_not_activate_contract(tmp_path: Path):
    path = write_svg(tmp_path, '<path d="M 0 0 L 10 10"/>')
    assert inspect_pen_layer_contract(path) is None


def test_generic_svg_without_namespace_remains_supported(tmp_path: Path):
    path = write_svg(tmp_path, '<path d="M 0 0 L 10 10"/>', xmlns=False)
    assert inspect_pen_layer_contract(path) is None


def test_valid_contract_preserves_explicit_pen_numbers(tmp_path: Path):
    path = write_svg(
        tmp_path,
        """
        <g id="pen-1" data-pen="1" data-generations="0,1" fill="none" stroke="#000000">
          <g data-generation="0"><path d="M 0 0 L 1 1"/></g>
          <g data-generation="1"><path d="M 1 1 L 2 2"/></g>
        </g>
        <g id="pen-3" data-pen="3" data-generations="2" fill="none" stroke="#ff0000">
          <g data-generation="2"><path d="M 2 2 L 3 3"/></g>
        </g>
        """,
    )
    contract = inspect_pen_layer_contract(path)
    assert contract is not None
    assert contract.pens == (1, 3)


def test_data_pen_must_match_group_id(tmp_path: Path):
    path = write_svg(
        tmp_path,
        '<g id="pen-2" data-pen="3" data-generations="0" fill="none" stroke="#000">'
        '<g data-generation="0"><path d="M 0 0 L 1 1"/></g></g>',
    )
    with pytest.raises(PenLayerContractError, match="data-pen"):
        inspect_pen_layer_contract(path)


def test_pen_must_be_within_dpx_range(tmp_path: Path):
    path = write_svg(
        tmp_path,
        '<g id="pen-9" data-pen="9" data-generations="0" fill="none" stroke="#000">'
        '<g data-generation="0"><path d="M 0 0 L 1 1"/></g></g>',
    )
    with pytest.raises(PenLayerContractError, match="range 1-8"):
        inspect_pen_layer_contract(path)


def test_generation_metadata_must_match(tmp_path: Path):
    path = write_svg(
        tmp_path,
        '<g id="pen-1" data-pen="1" data-generations="0,1" fill="none" stroke="#000">'
        '<g data-generation="0"><path d="M 0 0 L 1 1"/></g></g>',
    )
    with pytest.raises(PenLayerContractError, match="does not match"):
        inspect_pen_layer_contract(path)


def test_contract_rejects_unmapped_top_level_geometry(tmp_path: Path):
    path = write_svg(
        tmp_path,
        '<g id="pen-1" data-pen="1" data-generations="0" fill="none" stroke="#000">'
        '<g data-generation="0"><path d="M 0 0 L 1 1"/></g></g>'
        '<g id="other"><path d="M 2 2 L 3 3"/></g>',
    )
    with pytest.raises(PenLayerContractError, match="drawable top-level groups"):
        inspect_pen_layer_contract(path)
