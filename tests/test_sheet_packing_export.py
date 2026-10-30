import json
import re
import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest
from imposition.sheet_packing.config import load_packing_config
from imposition.sheet_packing.export import pack_impositions
from tests.test_jcard_artwork import configuration
from tests.test_jcard_impose import assets


def job(tmp_path, paired=True, rotations=(0,), quantity=2):
    config = configuration(tmp_path, "both" if paired else "front")
    native = {face: assets(tmp_path, config, face) for face in config.selected_faces}
    obj = dict(
        id="album",
        type="jcard",
        profile=config.profile,
        quantity=quantity,
        rotations=list(rotations),
        guides=dict(cut=True, fold=True, registration=True),
    )
    for face, bundle in native.items():
        obj[face] = dict(
            assets=str(bundle), template=str(getattr(config, f"{face}_artwork").template)
        )
    payload = dict(
        schema_version=1,
        sheet_mm=[420, 297],
        faces="both" if paired else "front",
        margins_mm=[3] * 4,
        gutter_mm=4,
        objects=[obj],
    )
    return payload, load_packing_config(payload, base_dir=tmp_path)


@pytest.mark.parametrize("axis", ["left-right", "top-bottom"])
def test_multi_object_duplex_contract_and_local_references(tmp_path, axis):
    from scripts.dpx3300_convert import _neutral_context, build_vpype_command

    _, config = job(tmp_path)
    config = replace(config, sheet=replace(config.sheet, flip=axis))
    out = pack_impositions(config, output_dir=tmp_path / "packed")
    root = json.loads((out / "packing.json").read_text())
    assert root["sheet_count"] == 1 and len(root["placements"]) == 2 and len(root["jobs"]) == 2
    assert root["trim_area_mm2"] == pytest.approx(2 * 406.4 * 101.6)
    assert all(len(p["back_matrix_mm"]) == 6 for p in root["placements"])
    assert root["sources"][0]["native_back_to_front"] == [-1, 0, 0, 1, 406.4, 0]
    for face in ("front", "back"):
        file = out / f"sheet-001/{face}/design.svg"
        svg = ET.parse(file).getroot()
        ids = [e.get("id") for e in svg.iter() if e.get("id")]
        assert len(ids) == len(set(ids))
        for element in svg.iter():
            for value in element.attrib.values():
                for ref in re.findall(r"url\(#([^)]*)\)", value):
                    assert ref in ids
        wrappers = [e for e in svg.iter() if e.get("data-imposed-instance")]
        assert {e.get("data-imposed-instance") for e in wrappers} == {"album-0001", "album-0002"}
        contract, _ = _neutral_context(file)
        assert [layer.id for layer in contract.layers][-3:] == [
            "sheet-cut-guides",
            "sheet-fold-guides",
            "sheet-registration",
        ]
        command = build_vpype_command(
            file,
            tmp_path / "test.hpgl",
            config_path=tmp_path / "vpype.toml",
            device="dpx3300",
            page_size="a3",
            device_page_size="a3",
            landscape=True,
            margin="0mm",
            velocity=None,
            absolute=True,
        )
        assert "layout" not in command and "--center" not in command


def test_forced_rotation_and_overflow_have_rigid_matrices(tmp_path):
    _, config = job(tmp_path, rotations=(90,), quantity=3)
    s = config.sheet
    config = replace(
        config,
        sheet=replace(
            s,
            width_mm=297,
            height_mm=420,
            usable_front=type(s.usable_front)(0, 0, 297, 420),
            usable_back=type(s.usable_front)(0, 0, 297, 420),
        ),
    )
    out = pack_impositions(config, output_dir=tmp_path / "packed")
    audit = json.loads((out / "packing.json").read_text())
    assert audit["sheet_count"] == 2 and all(p["rotation"] == 90 for p in audit["placements"])
    for p in audit["placements"]:
        a, b, c, d, _, _ = p["front_matrix_mm"]
        assert a * d - b * c == 1


def test_overwrite_late_failure_preserves_all_previous_outputs(tmp_path, monkeypatch):
    from imposition.sheet_packing import export

    _, config = job(tmp_path, quantity=3)
    out = pack_impositions(config, output_dir=tmp_path / "packed")
    before = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    real = export.render_sheet_face

    def fail(config, objects, result, page, face, catalog, budget):
        if page == 1 and face == "back":
            raise ValueError("late face failure")
        return real(config, objects, result, page, face, catalog, budget)

    monkeypatch.setattr(export, "render_sheet_face", fail)
    with pytest.raises(ValueError, match="late face"):
        pack_impositions(config, output_dir=out, overwrite=True)
    assert before == {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    new = tmp_path / "new"
    with pytest.raises(ValueError):
        pack_impositions(config, output_dir=new)
    assert not new.exists()


@pytest.mark.parametrize("limit", ["vertices", "svg_bytes"])
def test_output_budgets_fail_without_publication(tmp_path, monkeypatch, limit):
    from imposition.sheet_packing import export
    from imposition.sheet_packing.budget import PackingBudget

    _, config = job(tmp_path, paired=False)
    monkeypatch.setattr(export, "PackingBudget", lambda: PackingBudget(limits={limit: 1}))
    out = tmp_path / "packed"
    with pytest.raises(ValueError, match=limit):
        pack_impositions(config, output_dir=out)
    assert not out.exists()


@pytest.mark.parametrize("location", ["artwork", "definition"])
def test_retained_off_canvas_path_vertices_are_charged_before_duplication(
    tmp_path, monkeypatch, location
):
    import hashlib

    from imposition.sheet_packing import export
    from imposition.sheet_packing.budget import PackingBudget

    _, config = job(tmp_path, paired=False)
    bundle = config.objects[0].faces[0].request.assets
    file = bundle / "surfaces/front-panel-1.svg"
    tree = ET.parse(file)
    layer = next(e for e in tree.getroot() if e.get("data-viz-layer-id") == "curve")
    path = next(e for e in layer.iter() if e.tag.endswith("}path"))
    if location == "definition":
        defs = ET.SubElement(layer, "{http://www.w3.org/2000/svg}defs")
        path = ET.SubElement(defs, "{http://www.w3.org/2000/svg}path", id="unused-retained-path")
    path.set("d", "M1,1 L2,2 M10000,10000 " + " ".join(f"L{10001 + i},10000" for i in range(1000)))
    tree.write(file, encoding="utf-8", xml_declaration=True)
    manifest_file = bundle / "design.json"
    manifest = json.loads(manifest_file.read_text())
    record = next(v for v in manifest["surfaces"] if v["domain_id"] == "front-panel-1")
    record["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
    manifest_file.write_text(json.dumps(manifest))
    monkeypatch.setattr(export, "PackingBudget", lambda: PackingBudget(limits={"vertices": 500}))
    out = tmp_path / "packed"
    with pytest.raises(ValueError, match="vertices"):
        pack_impositions(config, output_dir=out)
    assert not out.exists()


def test_cli_and_input_overlap(tmp_path):
    from scripts.pack_impositions import main

    payload, config = job(tmp_path, paired=False)
    path = tmp_path / "packing-config.json"
    path.write_text(json.dumps(payload))
    assert main(["--config", str(path), "--output-dir", str(tmp_path / "packed")]) == 0
    with pytest.raises(ValueError, match="overlap"):
        pack_impositions(
            config, output_dir=config.objects[0].faces[0].request.assets, overwrite=True
        )
    with pytest.raises(SystemExit):
        main(["--config", str(path), "--output-dir", str(tmp_path)])


def test_explicit_pen_plan_preserves_physical_slots(tmp_path, monkeypatch):
    from pen_plan_models import Assignment, PassSpec, PenPlanSpec
    from tests.test_hpgl_pen_mapping import mock_vpype

    from scripts.dpx3300_convert import convert_planned_svg

    _, config = job(tmp_path, paired=False)
    packed = pack_impositions(config, output_dir=tmp_path / "packed")
    file = packed / "sheet-001/front/design.svg"
    mock_vpype(monkeypatch)
    assigned = [
        ("curve", 7),
        ("sheet-cut-guides", 1),
        ("sheet-fold-guides", 2),
        ("sheet-registration", 3),
    ]
    plan = PenPlanSpec(
        "explicit",
        (PassSpec("plot", tuple(Assignment((layer,), slot) for layer, slot in assigned)),),
    )
    outputs = convert_planned_svg(
        file, plan, tmp_path / "hpgl", page_size="a3", landscape=True, margin="0mm", absolute=True
    )
    resolved = json.loads(outputs[0].with_suffix(".resolved.penplan.json").read_text())
    assert resolved["assignments"] == [
        dict(layer_ids=[layer], physical_slot=slot) for layer, slot in assigned
    ]


def test_different_profiles_and_explicit_artwork_layers(tmp_path):
    payload, config = job(tmp_path, paired=False, quantity=1)
    second_dir = tmp_path / "second"
    second_dir.mkdir()
    second = replace(configuration(second_dir), profile="standard-jcard-3-panel-v1")
    bundle = assets(second_dir, second, "front")
    payload["logical_layers"] = [dict(id="art", ordinal=1, label="Artwork")]
    payload["objects"][0]["front"]["layer_map"] = {"curve": "art", "fill": "art"}
    payload["objects"].append(
        dict(
            id="small",
            type="jcard",
            profile=second.profile,
            front=dict(
                assets=str(bundle),
                template=str(second.front_artwork.template),
                layer_map={"curve": "art", "fill": "art"},
            ),
        )
    )
    config = load_packing_config(payload, base_dir=tmp_path)
    out = pack_impositions(config, output_dir=tmp_path / "packed")
    audit = json.loads((out / "packing.json").read_text())
    assert audit["resolved_strategy"] == "maxrects"
    design = json.loads((out / "sheet-001/front/design.json").read_text())
    assert {v["profile"] for v in design["instances"]} == {
        config.objects[0].profile,
        second.profile,
    }
    assert design["logical_layers"][0]["id"] == "art"


@pytest.mark.parametrize("axis", ["left-right", "top-bottom"])
def test_real_rotated_fragment_coordinates_match_native_mm(tmp_path, axis):
    import io

    import vpype
    from imposition.artwork_layout import MM_TO_PX

    _, config = job(tmp_path, rotations=(90,), quantity=1)
    s = config.sheet
    config = replace(
        config,
        sheet=replace(
            s,
            width_mm=297,
            height_mm=420,
            flip=axis,
            usable_front=type(s.usable_front)(0, 0, 297, 420),
            usable_back=type(s.usable_front)(0, 0, 297, 420),
        ),
    )
    out = pack_impositions(config, output_dir=tmp_path / "packed")
    for face, panel in (("front", "front-panel-1"), ("back", "back-panel-8")):
        root = ET.parse(out / f"sheet-001/{face}/design.svg").getroot()
        selected = next(e for e in root.iter() if e.get("data-imposed-slot") == panel)
        isolated = ET.Element(root.tag, dict(root.attrib))
        isolated.append(selected)
        lines, w, h = vpype.read_svg(io.BytesIO(ET.tostring(isolated)), quantization=0.1)
        actual = [(z.real * 297 / w, z.imag * 420 / h) for line in lines for z in line]
        if face == "front":
            expected = (107.6 - 2 / MM_TO_PX, 6 + 1 / MM_TO_PX)
        elif axis == "left-right":
            expected = (189.4 + 2 / MM_TO_PX, 412.4 - 1 / MM_TO_PX)
        else:
            expected = (107.6 - 2 / MM_TO_PX, 7.6 + 1 / MM_TO_PX)
        assert any(abs(x - expected[0]) < 1e-7 and abs(y - expected[1]) < 1e-7 for x, y in actual)
