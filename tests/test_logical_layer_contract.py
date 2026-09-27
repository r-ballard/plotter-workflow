import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from logical_layer_contract import (
    InputMode,
    LogicalLayerContractError,
    inspect_svg_contract,
    load_logical_layer_manifest,
    validate_surface_against_manifest,
)
from svg_pen_contract import PenLayerContractError

FIXTURE = Path(__file__).parent / "fixtures" / "logical_layers" / "two-surface-v1.svg"
MANIFEST_FIXTURE = FIXTURE.with_name("design.json")


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


def write_neutral_bundle(
    tmp_path: Path,
    *,
    catalog: list[dict[str, object]] | None = None,
    active: list[dict[str, object]] | None = None,
    inventory: list[str] | None = None,
    surface_path: str = "surfaces/drawing.svg",
) -> tuple[Path, Path, dict[str, object]]:
    catalog = deepcopy(
        catalog
        if catalog is not None
        else [
            {"id": "orbit", "ordinal": 1, "label": "Orbit"},
            {"id": "body", "ordinal": 2, "label": "Body"},
        ]
    )
    active = deepcopy(active if active is not None else catalog)
    svg_path = tmp_path / Path(surface_path)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    groups = "".join(
        neutral_group(str(entry["id"]), str(entry["ordinal"]), str(entry["label"]))
        for entry in active
    )
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'data-viz-layer-contract="viz-logical-layers/v1">'
        f"{groups}</svg>",
        encoding="utf-8",
    )
    payload: dict[str, object] = {
        "logical_layer_contract": "viz-logical-layers/v1",
        "logical_layers": catalog,
        "surfaces": [
            {
                "surface_id": "drawing",
                "path": surface_path,
                "sha256": hashlib.sha256(svg_path.read_bytes()).hexdigest(),
                "logical_layer_ids": (
                    inventory
                    if inventory is not None
                    else [str(entry["id"]) for entry in active]
                ),
            }
        ],
    }
    manifest_path = tmp_path / "design.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    return manifest_path, svg_path, payload


def write_manifest(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "design.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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


def test_loads_and_validates_merged_producer_shaped_fixture():
    manifest = load_logical_layer_manifest(MANIFEST_FIXTURE)

    contract = validate_surface_against_manifest(FIXTURE, manifest)

    assert contract.mode is InputMode.NEUTRAL
    assert [layer.id for layer in manifest.layers] == ["orbit", "body-s-planet-a"]
    assert manifest.raw["logical_layers"][0]["preview_style"] == {
        "stroke": "#112233"
    }


def test_manifest_hash_must_match_exact_surface_bytes(tmp_path: Path):
    manifest_path, svg_path, _ = write_neutral_bundle(tmp_path)
    manifest = load_logical_layer_manifest(manifest_path)
    svg_path.write_bytes(svg_path.read_bytes() + b"\n")

    with pytest.raises(
        LogicalLayerContractError,
        match=r"drawing\.svg.*SHA-256",
    ):
        validate_surface_against_manifest(svg_path, manifest)


def test_explicit_expected_hash_is_checked_in_addition_to_manifest_hash(
    tmp_path: Path,
):
    manifest_path, svg_path, _ = write_neutral_bundle(tmp_path)
    manifest = load_logical_layer_manifest(manifest_path)

    with pytest.raises(
        LogicalLayerContractError,
        match=r"drawing\.svg.*expected_hash",
    ):
        validate_surface_against_manifest(svg_path, manifest, expected_hash="0" * 64)


def test_rejects_unsupported_manifest_contract_version(tmp_path: Path):
    manifest_path, _, payload = write_neutral_bundle(tmp_path)
    payload["logical_layer_contract"] = "viz-logical-layers/v2"
    write_manifest(tmp_path, payload)

    with pytest.raises(
        LogicalLayerContractError,
        match=r"design\.json.*logical_layer_contract.*v2",
    ):
        load_logical_layer_manifest(manifest_path)


def test_rejects_svg_and_manifest_contract_disagreement(tmp_path: Path):
    _, svg_path, payload = write_neutral_bundle(tmp_path)
    text = svg_path.read_text(encoding="utf-8").replace(
        "viz-logical-layers/v1", "viz-logical-layers/v2"
    )
    svg_path.write_text(text, encoding="utf-8")
    payload["surfaces"][0]["sha256"] = hashlib.sha256(svg_path.read_bytes()).hexdigest()
    manifest = load_logical_layer_manifest(write_manifest(tmp_path, payload))

    with pytest.raises(
        LogicalLayerContractError,
        match=r"drawing\.svg.*data-viz-layer-contract.*v2",
    ):
        validate_surface_against_manifest(svg_path, manifest)


def test_surface_cannot_name_layer_absent_from_catalog(tmp_path: Path):
    active = [{"id": "unknown", "ordinal": 1, "label": "Unknown"}]
    manifest_path, svg_path, _ = write_neutral_bundle(tmp_path, active=active)
    manifest = load_logical_layer_manifest(manifest_path)

    with pytest.raises(
        LogicalLayerContractError,
        match=r"drawing\.svg.*data-viz-layer-id.*unknown",
    ):
        validate_surface_against_manifest(svg_path, manifest)


def test_manifest_validation_translates_malformed_legacy_contract_error(
    tmp_path: Path,
):
    _, svg_path, payload = write_neutral_bundle(tmp_path)
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g id="pen-1" data-pen="2" data-generations="0" '
        'fill="none" stroke="#000">'
        '<g data-generation="0"><path d="M 0 0 L 1 1" /></g>'
        "</g></svg>",
        encoding="utf-8",
    )
    payload["surfaces"][0]["sha256"] = hashlib.sha256(svg_path.read_bytes()).hexdigest()
    manifest = load_logical_layer_manifest(write_manifest(tmp_path, payload))

    with pytest.raises(
        LogicalLayerContractError,
        match=r"drawing\.svg.*data-viz-layer-contract.*legacy",
    ):
        validate_surface_against_manifest(svg_path, manifest)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("ordinal", 1, "data-viz-layer-ordinal"),
        ("label", "Wrong body", "data-viz-layer-label"),
    ],
)
def test_surface_layer_metadata_must_match_catalog(
    tmp_path: Path, field: str, value: object, message: str
):
    catalog = [
        {"id": "orbit", "ordinal": 1, "label": "Orbit"},
        {"id": "body", "ordinal": 2, "label": "Body"},
    ]
    active = [deepcopy(catalog[1])]
    active[0][field] = value
    manifest_path, svg_path, _ = write_neutral_bundle(
        tmp_path,
        catalog=catalog,
        active=active,
        inventory=["body"],
    )
    manifest = load_logical_layer_manifest(manifest_path)

    with pytest.raises(
        LogicalLayerContractError,
        match=rf"drawing\.svg.*{message}.*body",
    ):
        validate_surface_against_manifest(svg_path, manifest)


def test_surface_inventory_order_must_match_svg(tmp_path: Path):
    manifest_path, svg_path, _ = write_neutral_bundle(
        tmp_path,
        inventory=["body", "orbit"],
    )
    manifest = load_logical_layer_manifest(manifest_path)

    with pytest.raises(
        LogicalLayerContractError,
        match=r"drawing\.svg.*logical_layer_ids.*order",
    ):
        validate_surface_against_manifest(svg_path, manifest)


def test_empty_catalog_and_empty_surface_are_valid(tmp_path: Path):
    manifest_path, svg_path, _ = write_neutral_bundle(
        tmp_path,
        catalog=[],
        active=[],
    )
    manifest = load_logical_layer_manifest(manifest_path)

    contract = validate_surface_against_manifest(svg_path, manifest)

    assert manifest.layers == ()
    assert contract.layers == ()


def test_sparse_surface_subset_uses_catalog_ordinals(tmp_path: Path):
    catalog = [
        {"id": "orbit", "ordinal": 1, "label": "Orbit"},
        {"id": "body", "ordinal": 2, "label": "Body"},
    ]
    manifest_path, svg_path, _ = write_neutral_bundle(
        tmp_path,
        catalog=catalog,
        active=[catalog[1]],
    )
    manifest = load_logical_layer_manifest(manifest_path)

    contract = validate_surface_against_manifest(svg_path, manifest)

    assert [(layer.id, layer.ordinal) for layer in contract.layers] == [("body", 2)]


def test_missing_surface_record_names_manifest_relative_path(tmp_path: Path):
    _, svg_path, payload = write_neutral_bundle(tmp_path)
    payload["surfaces"] = []
    manifest = load_logical_layer_manifest(write_manifest(tmp_path, payload))

    with pytest.raises(
        LogicalLayerContractError,
        match=r"drawing\.svg.*surfaces.*missing",
    ):
        validate_surface_against_manifest(svg_path, manifest)


def test_ambiguous_surface_record_is_rejected(tmp_path: Path):
    _, svg_path, payload = write_neutral_bundle(tmp_path)
    payload["surfaces"].append(deepcopy(payload["surfaces"][0]))
    manifest = load_logical_layer_manifest(write_manifest(tmp_path, payload))

    with pytest.raises(
        LogicalLayerContractError,
        match=r"drawing\.svg.*surfaces.*ambiguous",
    ):
        validate_surface_against_manifest(svg_path, manifest)


def test_surface_selection_uses_manifest_relative_path_not_basename(tmp_path: Path):
    _, svg_path, payload = write_neutral_bundle(
        tmp_path, surface_path="first/drawing.svg"
    )
    other = tmp_path / "second" / "drawing.svg"
    other.parent.mkdir()
    other.write_text(svg_path.read_text(encoding="utf-8"), encoding="utf-8")
    other_record = deepcopy(payload["surfaces"][0])
    other_record["path"] = "second/drawing.svg"
    other_record["sha256"] = hashlib.sha256(other.read_bytes()).hexdigest()
    payload["surfaces"].append(other_record)
    manifest = load_logical_layer_manifest(write_manifest(tmp_path, payload))

    contract = validate_surface_against_manifest(other, manifest)

    assert [layer.id for layer in contract.layers] == ["orbit", "body"]


@pytest.mark.parametrize(
    "unsafe_path",
    ["../drawing.svg", "./drawing.svg", "/drawing.svg", "C:/drawing.svg", "a\\b.svg"],
)
def test_rejects_unsafe_manifest_surface_paths(
    tmp_path: Path, unsafe_path: str
):
    _, _, payload = write_neutral_bundle(tmp_path)
    payload["surfaces"][0]["path"] = unsafe_path

    with pytest.raises(
        LogicalLayerContractError,
        match=r"design\.json.*surfaces\[0\]\.path.*unsafe",
    ):
        load_logical_layer_manifest(write_manifest(tmp_path, payload))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("logical_layers", {}, "logical_layers"),
        ("logical_layers", ["orbit"], r"logical_layers\[0\]"),
        (
            "logical_layers",
            [{"id": 1, "ordinal": 1, "label": "Orbit"}],
            r"logical_layers\[0\]\.id",
        ),
        (
            "logical_layers",
            [{"id": "orbit", "ordinal": True, "label": "Orbit"}],
            r"logical_layers\[0\]\.ordinal",
        ),
        (
            "logical_layers",
            [{"id": "orbit", "ordinal": 1, "label": " "}],
            r"logical_layers\[0\]\.label",
        ),
        ("surfaces", {}, "surfaces"),
    ],
)
def test_rejects_malformed_manifest_catalog_and_top_level_sequences(
    tmp_path: Path, field: str, value: object, message: str
):
    _, _, payload = write_neutral_bundle(tmp_path)
    payload[field] = value

    with pytest.raises(LogicalLayerContractError, match=message):
        load_logical_layer_manifest(write_manifest(tmp_path, payload))


@pytest.mark.parametrize(
    ("logical_layers", "message"),
    [
        (
            [
                {"id": "orbit", "ordinal": 1, "label": "Orbit"},
                {"id": "orbit", "ordinal": 2, "label": "Other"},
            ],
            "duplicate.*id",
        ),
        (
            [
                {"id": "orbit", "ordinal": 1, "label": "Orbit"},
                {"id": "body", "ordinal": 1, "label": "Body"},
            ],
            "duplicate.*ordinal",
        ),
        (
            [
                {"id": "orbit", "ordinal": 2, "label": "Orbit"},
                {"id": "body", "ordinal": 1, "label": "Body"},
            ],
            "contiguous.*order",
        ),
    ],
)
def test_rejects_duplicate_or_out_of_order_catalog_entries(
    tmp_path: Path, logical_layers: list[dict[str, object]], message: str
):
    _, _, payload = write_neutral_bundle(tmp_path)
    payload["logical_layers"] = logical_layers

    with pytest.raises(LogicalLayerContractError, match=message):
        load_logical_layer_manifest(write_manifest(tmp_path, payload))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sha256", "not-a-hash"),
        ("sha256", 123),
        ("logical_layer_ids", "orbit"),
        ("logical_layer_ids", [1]),
    ],
)
def test_rejects_malformed_surface_hash_and_inventory_types(
    tmp_path: Path, field: str, value: object
):
    _, _, payload = write_neutral_bundle(tmp_path)
    payload["surfaces"][0][field] = value

    with pytest.raises(
        LogicalLayerContractError,
        match=rf"design\.json.*surfaces\[0\]\.{field}",
    ):
        load_logical_layer_manifest(write_manifest(tmp_path, payload))
