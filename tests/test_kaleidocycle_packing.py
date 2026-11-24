import json
import re
import xml.etree.ElementTree as ET

import pytest

from imposition.artwork_return import prepare_layout_assets
from imposition.kaleidocycle_artwork import resolve_kaleidocycle_state
from imposition.model import SheetSpec
from imposition.objects.kaleidocycle import Kaleidocycle
from imposition.sheet_packing.config import load_packing_config
from imposition.sheet_packing.export import pack_impositions
from scripts.dpx3300_convert import _materialize_neutral_layers, _neutral_context
from tests.test_artwork_layout_return import producer_fixture


def states(tmp_path, width, *, blank=False):
    result = {}
    for state in "ABCD":
        folder = tmp_path / state
        folder.mkdir()
        _, export, producer = producer_fixture(
            folder,
            layout=resolve_kaleidocycle_state(
                state, width_mm=width, tetrahedron_count=8
            ),
            blank=blank,
            stroke="M 0 30 L 300 30",
        )
        assets = prepare_layout_assets(
            producer_bundle=producer,
            handoff=export / "layout-handoff.json",
            output_dir=folder / "assets",
        )
        result[state] = str(assets.relative_to(tmp_path))
    return result


def payload(assets, width=269.4, quantity=2):
    return {
        "schema_version": 1,
        "sheet_mm": [279.4, 215.9],
        "margins_mm": [5] * 4,
        "gutter_mm": 5,
        "objects": [
            {
                "id": "ring",
                "type": "kaleidocycle",
                "tetrahedron_count": 8,
                "width_mm": width,
                "states": assets,
                "quantity": quantity,
                "rotations": [0],
                "guides": {"cut": True, "fold": True},
            }
        ],
    }


def test_corner_placement_keeps_center_default():
    obj = Kaleidocycle(tetrahedron_count=8)
    sheet = SheetSpec("letter", 279.4, 215.9, "landscape")
    p = obj.resolve_placement(sheet, {"width_mm": 240, "position": "top-left"})
    assert (p.x_mm, p.y_mm) == (5, 5)
    c = obj.resolve_placement(sheet, {"width_mm": 240})
    assert c.x_mm == pytest.approx(19.7)


@pytest.mark.parametrize("quantity,width", [(1, 269.4), (2, 269.4), (3, 213.531)])
def test_letter_packing_reuses_geometry_and_preserves_instances(
    tmp_path, quantity, width
):
    config = load_packing_config(
        payload(states(tmp_path, width), width, quantity), base_dir=tmp_path
    )
    out = pack_impositions(config, output_dir=tmp_path / "packed")
    report = json.loads((out / "packing.json").read_text())
    assert report["sheet_count"] == 1
    assert len(report["placements"]) == quantity
    for i, p in enumerate(report["placements"]):
        b = p["occupied_bounds_mm"]
        assert b["x"] == pytest.approx(5)
        assert b["y"] == pytest.approx(5 + i * (width / 3.27 + 5))
        assert b["width"] == pytest.approx(width)
    file = out / "sheet-001/front/design.svg"
    root = ET.parse(file).getroot()
    assert len([g for g in root.iter() if g.get("data-imposed-slot")]) == quantity * 32
    ids = [n.get("id") for n in root.iter() if n.get("id")]
    assert len(ids) == len(set(ids))
    path_ids = [
        n.get("data-viz-path-id") for n in root.iter() if n.get("data-viz-path-id")
    ]
    assert len(path_ids) == len(set(path_ids))
    for n in root.iter():
        for value in n.attrib.values():
            assert all(ref in ids for ref in re.findall(r"url\(#([^)]*)\)", value))
    contract, _ = _neutral_context(file)
    assert [l.id for l in contract.layers] == [
        "curve",
        "fill",
        "sheet-cut-guides",
        "sheet-fold-guides",
    ]
    assert len(_materialize_neutral_layers(file)["curve"]) >= quantity * 32


@pytest.mark.parametrize(
    "update",
    [
        {"width_mm": True},
        {"width_mm": 0},
        {"width_mm": "240"},
        {"states": {}},
        {"profile": "nac-jcard-8-panel-v1"},
        {"front": {}},
        {"guides": {"registration": True}},
    ],
)
def test_reject_invalid_kaleidocycle_controls(tmp_path, update):
    raw = payload({s: f"{s}/assets" for s in "ABCD"})
    raw["objects"][0].update(update)
    with pytest.raises((ValueError, TypeError)):
        load_packing_config(raw, base_dir=tmp_path)


def test_width_mismatch_rejected_without_output(tmp_path):
    config = load_packing_config(
        payload(states(tmp_path, 240), 269.4), base_dir=tmp_path
    )
    with pytest.raises(ValueError, match="width"):
        pack_impositions(config, output_dir=tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize("angle", [0, 90])
def test_clipped_stroke_reaches_physical_sheet_once(tmp_path, angle):
    import io

    import vpype

    width = 240
    raw = payload(states(tmp_path, width), width, 1)
    raw["objects"][0]["rotations"] = [angle]
    if angle:
        raw["sheet_mm"] = [215.9, 279.4]
    config = load_packing_config(raw, base_dir=tmp_path)
    out = pack_impositions(config, output_dir=tmp_path / "packed")
    group = _materialize_neutral_layers(out / "sheet-001/front/design.svg")["curve"]
    svg = ET.Element("{http://www.w3.org/2000/svg}svg")
    svg.append(group)
    lines, _, _ = vpype.read_svg(
        io.StringIO(ET.tostring(svg, encoding="unicode")), quantization=0.01
    )
    px = 96 / 25.4
    scale = width / 16.35 * 2 / 128 * px
    tx = 5 * px + 0.35 / 16.35 * width * px
    ty = 5 * px
    if angle == 0:
        candidates = [
            line
            for line in lines
            if all(abs(z.imag - (ty + 30 * scale)) < 1e-6 for z in line)
            and abs(min(z.real for z in line) - tx) < 1e-6
        ]
        assert candidates
        assert max(z.real for z in candidates[0]) == pytest.approx(
            tx + 60 * scale, abs=1e-6
        )
    else:
        x = (5 + width / 3.27) * px - 30 * scale
        y = (5 + 0.35 / 16.35 * width) * px
        candidates = [
            line
            for line in lines
            if all(abs(z.real - x) < 1e-6 for z in line)
            and abs(min(z.imag for z in line) - y) < 1e-6
        ]
        assert candidates
        assert max(z.imag for z in candidates[0]) == pytest.approx(
            y + 60 * scale, abs=1e-6
        )


def test_empty_viewport_corruption_is_rejected(tmp_path):
    import hashlib

    paths = states(tmp_path, 240, blank=True)
    bundle = tmp_path / paths["A"]
    source = bundle / "surfaces/column-1-a.svg"
    root = ET.parse(source).getroot()
    root.set("width", "1")
    root.set("height", "1")
    root.set("viewBox", "0 0 1 1")
    source.write_bytes(ET.tostring(root))
    manifest_path = bundle / "design.json"
    manifest = json.loads(manifest_path.read_text())
    for record in manifest["surfaces"]:
        if record["path"].endswith("column-1-a.svg"):
            record["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    config = load_packing_config(payload(paths, 240), base_dir=tmp_path)
    with pytest.raises(ValueError, match="viewport"):
        pack_impositions(config, output_dir=tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_blank_guideless_copies_reserve_tabs_and_spill_to_next_sheet(tmp_path):
    raw = payload(states(tmp_path, 269.4, blank=True), 269.4, 3)
    raw["objects"][0]["guides"] = {}
    out = pack_impositions(
        load_packing_config(raw, base_dir=tmp_path), output_dir=tmp_path / "packed"
    )
    report = json.loads((out / "packing.json").read_text())
    assert report["sheet_count"] == 2
    assert report["sources"][0]["native_occupied_bounds_mm"]["width"] == pytest.approx(
        269.4
    )
    assert len(report["jobs"]) == 2


def test_state_bundle_is_protected_from_output_overwrite(tmp_path):
    paths = states(tmp_path, 240)
    bundle = tmp_path / paths["A"]
    before = (bundle / "design.json").read_bytes()
    with pytest.raises(ValueError, match="overlap"):
        pack_impositions(
            load_packing_config(payload(paths, 240), base_dir=tmp_path),
            output_dir=bundle,
            overwrite=True,
        )
    assert (bundle / "design.json").read_bytes() == before


def test_duplex_kaleidocycle_is_rejected(tmp_path):
    raw = payload({s: f"{s}/assets" for s in "ABCD"})
    raw["faces"] = "both"
    with pytest.raises(ValueError, match="front-only"):
        load_packing_config(raw, base_dir=tmp_path)


def test_single_imposer_accepts_top_left_config(tmp_path):
    from imposition.kaleidocycle_impose import write_kaleidocycle

    config_path = tmp_path / "corner.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tetrahedron_count": 8,
                "width_mm": 240,
                "states": states(tmp_path, 240),
                "position": "top-left",
            }
        )
    )
    out = write_kaleidocycle(config_path, tmp_path / "single")
    audit = json.loads((out / "design.imposition.json").read_text())
    assert audit["placement_mm"][:2] == [5, 5]


def test_explicit_layer_map_and_reserved_guide_collision(tmp_path):
    raw = payload(states(tmp_path, 240), 240, 1)
    raw["logical_layers"] = [{"id": "ink", "label": "Ink", "ordinal": 1}]
    raw["objects"][0]["layer_map"] = {"curve": "ink", "fill": "ink"}
    out = pack_impositions(
        load_packing_config(raw, base_dir=tmp_path), output_dir=tmp_path / "mapped"
    )
    contract, _ = _neutral_context(out / "sheet-001/front/design.svg")
    assert [v.id for v in contract.layers] == [
        "ink",
        "sheet-cut-guides",
        "sheet-fold-guides",
    ]
    raw["logical_layers"][0]["id"] = "sheet-cut-guides"
    raw["objects"][0]["layer_map"] = {
        "curve": "sheet-cut-guides",
        "fill": "sheet-cut-guides",
    }
    with pytest.raises(ValueError, match="collide"):
        pack_impositions(
            load_packing_config(raw, base_dir=tmp_path), output_dir=tmp_path / "bad"
        )


def test_packed_kaleidocycle_charges_retained_work_budget(tmp_path, monkeypatch):
    from imposition.sheet_packing import export
    from imposition.sheet_packing.budget import PackingBudget

    raw = payload(states(tmp_path, 240), 240, 2)
    monkeypatch.setattr(export, "PackingBudget", lambda: PackingBudget({"vertices": 1}))
    with pytest.raises(ValueError, match="budget"):
        pack_impositions(
            load_packing_config(raw, base_dir=tmp_path), output_dir=tmp_path / "bad"
        )
    assert not (tmp_path / "bad").exists()


def test_committed_letter_examples_regenerate(tmp_path):
    from scripts.generate_kaleidocycle_packing_samples import generate_samples

    out = generate_samples(tmp_path / "samples")
    for n, width in ((1, 269.4), (2, 269.4), (3, 213.531)):
        config = json.loads((out / f"letter-{n}-up.json").read_text())
        assert config["objects"][0]["width_mm"] == width
        report = json.loads((out / f"letter-{n}-up/packing.json").read_text())
        assert report["sheet_count"] == 1
        assert len(report["placements"]) == n
        assert report["config_sha256"]
        assert (out / f"letter-{n}-up/sheet-001/front/design.penplan.json").is_file()
    with pytest.raises(ValueError, match="overwrite"):
        generate_samples(out)
