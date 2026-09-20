from pathlib import Path

import pytest

from logical_layer_contract import (
    InputMode,
    LogicalLayerContractError,
    inspect_svg_contract,
)
from svg_pen_contract import PenLayerContractError

FIXTURE = Path(__file__).parent / "fixtures" / "logical_layers" / "two-surface-v1.svg"


def write_svg(tmp_path: Path, body: str, *, root_contract: str | None = None) -> Path:
    path = tmp_path / "drawing.svg"
    contract = (
        f' data-viz-layer-contract="{root_contract}"' if root_contract else ""
    )
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"{contract}>{body}</svg>',
        encoding="utf-8",
    )
    return path


def neutral_group(
    layer_id: str = "orbit",
    ordinal: str = "1",
    label: str = "Orbit",
    body: str = '<path d="M 0 0 L 1 1" />',
) -> str:
    return (
        f'<g id="local-{layer_id}" data-viz-layer-id="{layer_id}" '
        f'data-viz-layer-ordinal="{ordinal}" data-viz-layer-label="{label}">{body}</g>'
    )


def test_reads_neutral_layers_in_ordinal_order():
    contract = inspect_svg_contract(FIXTURE)

    assert contract.mode is InputMode.NEUTRAL
    assert [layer.id for layer in contract.layers] == [
        "orbit",
        "body-s-planet-a",
    ]
    assert [layer.ordinal for layer in contract.layers] == [1, 2]
    assert [layer.label for layer in contract.layers] == ["Orbit", "Body S Planet A"]


def test_accepts_neutral_surface_with_no_layers(tmp_path: Path):
    path = write_svg(tmp_path, "", root_contract="viz-logical-layers/v1")

    contract = inspect_svg_contract(path)

    assert contract.mode is InputMode.NEUTRAL
    assert contract.layers == ()


def test_rejects_mixed_neutral_and_pen_groups(tmp_path: Path):
    path = write_svg(
        tmp_path,
        neutral_group()
        + '<g id="pen-1" data-pen="1" data-generations="0" fill="none" stroke="#000">'
        '<g data-generation="0"><path d="M 0 0 L 1 1" /></g></g>',
        root_contract="viz-logical-layers/v1",
    )

    with pytest.raises(LogicalLayerContractError, match="mixed"):
        inspect_svg_contract(path)


def test_identifies_generic_svg_without_neutral_or_legacy_metadata(tmp_path: Path):
    path = write_svg(tmp_path, '<g id="orbit"><path d="M 0 0 L 1 1" /></g>')

    contract = inspect_svg_contract(path)

    assert contract.mode is InputMode.GENERIC
    assert contract.layers == ()


def test_preserves_old_unversioned_logical_role_as_generic_input():
    contract = inspect_svg_contract(Path(__file__).parent / "fixtures" / "viz_virtualserver_surface.svg")

    assert contract.mode is InputMode.GENERIC


def test_identifies_legacy_svg_and_delegates_validation(tmp_path: Path):
    path = write_svg(
        tmp_path,
        '<g id="pen-2" data-pen="2" data-generations="0" fill="none" stroke="#000">'
        '<g data-generation="0"><path d="M 0 0 L 1 1" /></g></g>',
    )

    contract = inspect_svg_contract(path)

    assert contract.mode is InputMode.LEGACY
    assert contract.legacy is not None
    assert contract.legacy.pens == (2,)


def test_legacy_errors_are_unchanged(tmp_path: Path):
    path = write_svg(
        tmp_path,
        '<g id="pen-2" data-pen="3" data-generations="0" fill="none" stroke="#000">'
        '<g data-generation="0"><path d="M 0 0 L 1 1" /></g></g>',
    )

    with pytest.raises(PenLayerContractError, match="data-pen"):
        inspect_svg_contract(path)


def test_rejects_unknown_neutral_contract_version(tmp_path: Path):
    path = write_svg(
        tmp_path,
        neutral_group(),
        root_contract="viz-logical-layers/v2",
    )

    with pytest.raises(LogicalLayerContractError, match="unsupported.*version"):
        inspect_svg_contract(path)


def test_rejects_partial_neutral_root_declaration(tmp_path: Path):
    path = write_svg(tmp_path, '<path d="M 0 0 L 1 1" />', root_contract="viz-logical-layers/v1")

    with pytest.raises(LogicalLayerContractError, match="partial"):
        inspect_svg_contract(path)


def test_rejects_partial_neutral_group_declaration(tmp_path: Path):
    path = write_svg(
        tmp_path,
        '<g data-viz-layer-id="orbit"><path d="M 0 0 L 1 1" /></g>',
    )

    with pytest.raises(LogicalLayerContractError, match="partial"):
        inspect_svg_contract(path)


def test_rejects_nested_neutral_group_without_root_contract(tmp_path: Path):
    path = write_svg(
        tmp_path,
        '<g id="wrapper"><g data-viz-layer-id="orbit"><path d="M 0 0 L 1 1" /></g></g>',
    )

    with pytest.raises(LogicalLayerContractError, match="partial"):
        inspect_svg_contract(path)


def test_rejects_nested_partial_declaration_with_valid_top_level_layer(
    tmp_path: Path,
):
    path = write_svg(
        tmp_path,
        neutral_group()
        + '<g id="metadata-wrapper"><g data-viz-layer-ordinal="2" /></g>',
        root_contract="viz-logical-layers/v1",
    )

    with pytest.raises(LogicalLayerContractError, match="partial"):
        inspect_svg_contract(path)


@pytest.mark.parametrize(
    ("first", "second", "message"),
    [
        ("1", "3", "contiguous"),
        ("1", "1", "duplicate ordinal"),
    ],
)
def test_requires_contiguous_unique_ordinals(
    tmp_path: Path, first: str, second: str, message: str
):
    path = write_svg(
        tmp_path,
        neutral_group("orbit", first)
        + neutral_group("body", second, "Body"),
        root_contract="viz-logical-layers/v1",
    )

    with pytest.raises(LogicalLayerContractError, match=message):
        inspect_svg_contract(path)


def test_rejects_duplicate_layer_ids(tmp_path: Path):
    path = write_svg(
        tmp_path,
        neutral_group("orbit", "1") + neutral_group("orbit", "2", "Orbit again"),
        root_contract="viz-logical-layers/v1",
    )

    with pytest.raises(LogicalLayerContractError, match="duplicate.*ID"):
        inspect_svg_contract(path)


def test_requires_nonempty_layer_labels(tmp_path: Path):
    path = write_svg(
        tmp_path,
        neutral_group("orbit", "1", ""),
        root_contract="viz-logical-layers/v1",
    )

    with pytest.raises(LogicalLayerContractError, match="label"):
        inspect_svg_contract(path)


def test_rejects_drawable_geometry_outside_layer_group(tmp_path: Path):
    path = write_svg(
        tmp_path,
        neutral_group() + '<path d="M 2 2 L 3 3" />',
        root_contract="viz-logical-layers/v1",
    )

    with pytest.raises(LogicalLayerContractError, match="drawable.*layer"):
        inspect_svg_contract(path)


@pytest.mark.parametrize(
    "unowned_geometry",
    [
        '<use href="#path-id" />',
        '<a href="https://example.test"><path d="M 2 2 L 3 3" /></a>',
        '<switch><path d="M 2 2 L 3 3" /></switch>',
    ],
)
def test_rejects_renderable_geometry_outside_layer_group(
    tmp_path: Path, unowned_geometry: str
):
    path = write_svg(
        tmp_path,
        neutral_group() + unowned_geometry,
        root_contract="viz-logical-layers/v1",
    )

    with pytest.raises(LogicalLayerContractError, match="drawable.*layer"):
        inspect_svg_contract(path)
