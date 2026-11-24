import math

import pytest

from imposition.artwork_layout import affine, layout_dict, parse_layout
from imposition.kaleidocycle_artwork import resolve_kaleidocycle_state
from imposition.model import SheetSpec
from imposition.objects.kaleidocycle import Kaleidocycle


def test_net_has_32_stable_triangles_and_four_states_cover_every_panel():
    obj = Kaleidocycle(tetrahedron_count=8)
    assert len(obj.slots) == 32
    assert len({s.slot_id for s in obj.slots}) == 32
    assert all(len(s.polygon) == 3 for s in obj.slots)
    layouts = [
        resolve_kaleidocycle_state(state, width_mm=240, tetrahedron_count=8)
        for state in "ABCD"
    ]
    assert {p.panel_id for v in layouts for p in v.panels} == {
        s.slot_id for s in obj.slots
    }
    assert all(v.validation_status == "provisional" for v in layouts)
    for layout in layouts:
        assert layout_dict(parse_layout(layout_dict(layout))) == layout_dict(layout)
        panels = {p.panel_id: p for p in layout.panels}
        for seam in layout.settings["adjacency"]:
            endpoints = []
            for panel_id, edge in seam:
                p = panels[panel_id]
                endpoints.append(
                    [
                        affine(p.assembled_matrix, p.crop_polygon[i % 3])
                        for i in (edge, edge + 1)
                    ]
                )
            for a, b in zip(endpoints[0], reversed(endpoints[1])):
                assert a == pytest.approx(b, abs=1e-8)


def test_placement_guides_and_glue_tabs_fit_sheet():
    obj = Kaleidocycle(tetrahedron_count=8)
    sheet = SheetSpec("letter", 279.4, 215.9, "landscape")
    placement = obj.resolve_placement(sheet, {"width_mm": 240, "margin_mm": 5})
    assert placement.width_mm / placement.height_mm == pytest.approx(obj.aspect_ratio)
    assert placement.x_mm == pytest.approx((279.4 - 240) / 2)
    guides = obj.guides(placement)
    assert {g.kind for g in guides} == {"cut", "fold", "glue"}
    assert all(
        0 <= x <= sheet.width_mm and 0 <= y <= sheet.height_mm
        for g in guides
        for x, y in g.points
    )
    folds = [tuple(sorted(g.points)) for g in guides if g.kind == "fold"]
    assert len(set(folds)) == len(folds)


@pytest.mark.parametrize(
    "options",
    [{"width_mm": 500}, {"width_mm": math.nan}, {"margin_mm": -1}, {"oops": 1}],
)
def test_invalid_placement(options):
    with pytest.raises(ValueError):
        Kaleidocycle(tetrahedron_count=8).resolve_placement(
            SheetSpec("x", 200, 100, "landscape"), options
        )


def test_invalid_state():
    with pytest.raises(ValueError):
        resolve_kaleidocycle_state("AB", width_mm=240, tetrahedron_count=8)


def test_triangle_export_return_and_partial_bindings(tmp_path):
    import json

    from imposition.artwork_return import prepare_layout_assets
    from tests.test_artwork_layout_return import producer_fixture

    layout = resolve_kaleidocycle_state("A", width_mm=240, tetrahedron_count=8)
    _, export, producer = producer_fixture(tmp_path, layout=layout)
    output = prepare_layout_assets(
        producer_bundle=producer,
        handoff=export / "layout-handoff.json",
        output_dir=tmp_path / "restored",
    )
    bindings = json.loads((output / "bindings.json").read_text())
    assert bindings["kind"] == "kaleidocycle"
    assert bindings["complete"] is False
    assert len(bindings["remaining_assignments"]) == 24


@pytest.mark.parametrize(
    "crop",
    [
        ((0, 0), (2, 2), (0, 2), (2, 0)),
        ((0, 0), (1, 0), (2, 0)),
        ((0, 0), (2, 0), (1, 1), (2, 2), (0, 2)),
    ],
)
def test_invalid_convex_crop(crop):
    from imposition.artwork_layout import PanelLayout, rect

    with pytest.raises(ValueError):
        PanelLayout("bad", rect(0, 0, 2, 2), crop, (1, 0, 0, 1, 0, 0), {})


@pytest.mark.parametrize("blank", [False, True])
def test_four_state_assets_impose_once_preserving_layers_and_provenance(
    tmp_path, blank
):
    import json
    import xml.etree.ElementTree as ET

    from imposition.artwork_return import prepare_layout_assets
    from imposition.kaleidocycle_impose import write_kaleidocycle
    from tests.test_artwork_layout_return import producer_fixture

    states = {}
    for state in "ABCD":
        folder = tmp_path / state
        folder.mkdir()
        layout = resolve_kaleidocycle_state(state, width_mm=240, tetrahedron_count=8)
        _, export, producer = producer_fixture(
            folder, layout=layout, blank=blank, stroke="M 0 30 L 300 30"
        )
        assets = prepare_layout_assets(
            producer_bundle=producer,
            handoff=export / "layout-handoff.json",
            output_dir=folder / "assets",
        )
        states[state] = str(assets.relative_to(tmp_path))
    config = tmp_path / "kaleidocycle.json"
    payload = {
        "schema_version": 1,
        "tetrahedron_count": 8,
        "width_mm": 240,
        "sheet_size": "letter",
        "states": states,
    }
    config.write_text(json.dumps(payload))
    out = write_kaleidocycle(config, tmp_path / "sheet")
    root = ET.parse(out / "design.svg").getroot()
    ns = "{http://www.w3.org/2000/svg}"
    groups = [g for g in root if g.get("data-viz-layer-id")]
    assert [g.get("data-viz-layer-id") for g in groups] == ["curve", "fill"]
    assert len([g for g in root.iter() if g.get("data-imposed-slot")]) == (
        0 if blank else 32
    )
    assert len([p for p in root.iter(ns + "path") if p.get("data-viz-path-id")]) == (
        0 if blank else 32
    )
    assert not any(g.get("data-guide-kind") for g in root.iter())
    assert (out / "guides.svg").is_file()
    preview = ET.parse(out / "net-preview.svg").getroot()
    assert len([t for t in preview.iter() if t.get("data-slot-label")]) == 32
    from scripts.dpx3300_convert import _neutral_context

    contract, manifest_hash = _neutral_context(out / "design.svg")
    assert [layer.id for layer in contract.layers] == ["curve", "fill"]
    assert len(manifest_hash) == 64
    audit = json.loads((out / "design.imposition.json").read_text())
    assert len(audit["panels"]) == 32
    assert audit["validation_status"] == "provisional"
    for record in audit["panels"]:
        slot = next(
            s
            for s in Kaleidocycle(tetrahedron_count=8).slots
            if s.slot_id == record["slot"]
        )
        p = audit["placement_mm"]
        expected = [(p[0] + x * p[2], p[1] + y * p[3]) for x, y in slot.polygon]
        for actual, point in zip(record["polygon_mm"], expected):
            assert actual == pytest.approx(point)
    # Flatten the emitted SVG exactly as the converter does and inspect the
    # crossing stroke in column-1-A: local y=30 intersects x=0..60.
    import io

    import vpype

    from scripts.dpx3300_convert import _materialize_neutral_layers

    materialized = ET.Element(ns + "svg")
    materialized.append(_materialize_neutral_layers(out / "design.svg")["curve"])
    lines, _, _ = vpype.read_svg(
        io.StringIO(ET.tostring(materialized, encoding="unicode")), quantization=0.01
    )
    if blank:
        assert len(lines) == 0
    else:
        record = audit["panels"][0]
        tx = min(x for x, y in record["polygon_mm"]) * 96 / 25.4
        ty = min(y for x, y in record["polygon_mm"]) * 96 / 25.4
        scale = 240 / Kaleidocycle(8).net_width * 2 / 128 * 96 / 25.4
        candidate = [
            line
            for line in lines
            if all(abs(z.imag - (ty + 30 * scale)) < 1e-6 for z in line)
            and abs(min(z.real for z in line) - tx) < 1e-6
        ]
        assert candidate, (tx, ty, [list(line) for line in lines][:4])
        assert max(z.real for z in candidate[0]) == pytest.approx(
            tx + 60 * scale, abs=1e-6
        )
    # A different but internally valid handoff must not claim these assets.
    handoff_path = tmp_path / states["A"] / "layout-handoff.json"
    handoff = json.loads(handoff_path.read_text())
    original = handoff_path.read_bytes()
    handoff["layout"]["profile_id"] = "different-profile-A"
    handoff_path.write_text(json.dumps(handoff))
    with pytest.raises(ValueError, match="provenance"):
        write_kaleidocycle(config, tmp_path / "stale")
    handoff_path.write_bytes(original)
    payload["states"]["D"] = states["A"]
    config.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        write_kaleidocycle(config, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_declared_state_profile_checks_geometry_and_seams():
    from imposition.kaleidocycle_artwork import validate_kaleidocycle_layout

    layout = resolve_kaleidocycle_state("A", width_mm=240, tetrahedron_count=8)
    payload = layout_dict(layout)
    payload["profile_id"] = "paper-test-A"
    validate_kaleidocycle_layout(parse_layout(payload))
    payload["settings"] = {**payload["settings"], "adjacency": [("unknown", "bad")]}
    with pytest.raises(ValueError):
        validate_kaleidocycle_layout(parse_layout(payload))
