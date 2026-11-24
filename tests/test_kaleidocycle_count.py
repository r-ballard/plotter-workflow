import json

import pytest

from imposition.artwork_bindings import build_layout_bindings
from imposition.artwork_layout import layout_dict, parse_layout
from imposition.kaleidocycle_artwork import (
    resolve_kaleidocycle_state,
    validate_kaleidocycle_layout,
)
from imposition.model import SheetSpec
from imposition.objects.kaleidocycle import Kaleidocycle


def test_default_is_six():
    assert len(Kaleidocycle().slots) == 24
    layout = resolve_kaleidocycle_state("A", width_mm=240)
    assert len(layout.panels) == 6
    assert layout.settings["tetrahedron_count"] == 6


@pytest.mark.parametrize("count", [6, 8, 10, 12, 100, 1000])
def test_count_geometry_scale_seams_and_bindings(count):
    obj = Kaleidocycle(tetrahedron_count=count)
    assert len(obj.slots) == 4 * count
    assert len(obj.glue_polygons) == count // 2 + 2
    assert obj.net_width == 2 * count + 0.35
    placement = obj.resolve_placement(
        SheetSpec("letter", 279.4, 215.9, "landscape"), {"width_mm": 240}
    )
    assert placement.height_mm == pytest.approx(240 * 5 / obj.net_width)
    points = [p for s in obj.slots for p in s.polygon]
    points += [p for g in obj.glue_polygons for p in g]
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in points)
    assert {g.kind for g in obj.guides(placement)} == {"cut", "fold", "glue"}
    for state in "ABCD":
        layout = resolve_kaleidocycle_state(
            state, width_mm=240, tetrahedron_count=count
        )
        validate_kaleidocycle_layout(layout)
        assert len(layout.panels) == len(layout.settings["adjacency"]) == count
        assert layout.validation_status == "provisional"
        patch = build_layout_bindings(
            layout, {p.panel_id: f"surfaces/{p.panel_id}.svg" for p in layout.panels}
        )
        assert len(patch["remaining_assignments"]) == 3 * count


@pytest.mark.parametrize("count", [True, False, 0, 4, 7, -6, 6.0, "6", None])
def test_invalid_count(count):
    with pytest.raises(ValueError, match="tetrahedron_count"):
        Kaleidocycle(tetrahedron_count=count)


def test_legacy_eight_layout_and_mislabeled_layout():
    layout = layout_dict(
        resolve_kaleidocycle_state("A", width_mm=240, tetrahedron_count=8)
    )
    del layout["settings"]["tetrahedron_count"]
    validate_kaleidocycle_layout(parse_layout(layout))
    layout["settings"]["tetrahedron_count"] = 6
    with pytest.raises(ValueError):
        validate_kaleidocycle_layout(parse_layout(layout))


@pytest.mark.parametrize("count", [6, 8, 10])
def test_full_pipeline_and_packing(tmp_path, count):
    from imposition.artwork_return import prepare_layout_assets
    from imposition.kaleidocycle_impose import write_kaleidocycle
    from imposition.sheet_packing.config import load_packing_config
    from imposition.sheet_packing.export import pack_impositions
    from tests.test_artwork_layout_return import producer_fixture

    states = {}
    for state in "ABCD":
        folder = tmp_path / state
        folder.mkdir()
        layout = resolve_kaleidocycle_state(
            state, width_mm=180, tetrahedron_count=count
        )
        _, export, producer = producer_fixture(folder, layout=layout)
        prepare_layout_assets(
            producer_bundle=producer,
            handoff=export / "layout-handoff.json",
            output_dir=folder / "assets",
        )
        states[state] = f"{state}/assets"
    config = {"schema_version": 1, "width_mm": 180, "states": states}
    if count != 6:
        config["tetrahedron_count"] = count
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    out = write_kaleidocycle(path, tmp_path / "net")
    audit = json.loads((out / "design.imposition.json").read_text())
    assert audit["tetrahedron_count"] == count
    assert len(audit["panels"]) == 4 * count
    assert audit["placement_mm"][3] == pytest.approx(180 * 5 / (2 * count + 0.35))
    raw = {
        "schema_version": 1,
        "sheet_mm": [279.4, 215.9],
        "objects": [
            {
                "id": "ring",
                "type": "kaleidocycle",
                "width_mm": 180,
                "states": states,
                "tetrahedron_count": count,
                "guides": {"cut": True, "fold": True},
            }
        ],
    }
    packed = pack_impositions(
        load_packing_config(raw, base_dir=tmp_path), output_dir=tmp_path / "packed"
    )
    report = json.loads((packed / "packing.json").read_text())
    bounds = report["placements"][0]["occupied_bounds_mm"]
    assert bounds["width"] == pytest.approx(180)
    assert bounds["height"] == pytest.approx(180 * 5 / (2 * count + 0.35))
    config["tetrahedron_count"] = 8 if count != 8 else 6
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="count"):
        write_kaleidocycle(path, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_request_identity_and_packing_config(tmp_path):
    from imposition.kaleidocycle_native import KaleidocycleRequest
    from imposition.sheet_packing.config import load_packing_config

    paths = tuple((s, tmp_path / s) for s in "ABCD")
    six = KaleidocycleRequest(180, paths)
    eight = KaleidocycleRequest(180, paths, tetrahedron_count=8)
    assert six.tetrahedron_count == 6
    assert len({six, eight}) == 2
    raw = {
        "schema_version": 1,
        "sheet_mm": [279.4, 215.9],
        "objects": [
            {
                "id": "ring",
                "type": "kaleidocycle",
                "width_mm": 180,
                "states": {s: s for s in "ABCD"},
            }
        ],
    }
    config = load_packing_config(raw, base_dir=tmp_path)
    assert config.objects[0].faces[0].request.tetrahedron_count == 6
    raw["objects"][0]["tetrahedron_count"] = True
    with pytest.raises(ValueError, match="tetrahedron_count"):
        load_packing_config(raw, base_dir=tmp_path)


def test_cli_default_explicit_count_and_profile_mismatch(tmp_path):
    from scripts.export_artwork_layout import main
    from tests.test_artwork_layout_export import template

    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps(template()))
    common = [
        "--layout",
        "kaleidocycle-state",
        "--state",
        "A",
        "--width-mm",
        "180",
        "--job-template",
        str(recipe),
    ]
    assert main(common + ["--output-dir", str(tmp_path / "six")]) == 0
    six = json.loads((tmp_path / "six/layout-handoff.json").read_text())
    assert len(six["layout"]["panels"]) == 6
    assert (
        main(
            common
            + ["--tetrahedron-count", "8", "--output-dir", str(tmp_path / "eight")]
        )
        == 0
    )
    eight = json.loads((tmp_path / "eight/layout-handoff.json").read_text())
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps(eight["layout"]))
    with pytest.raises(SystemExit):
        main(
            common + ["--profile", str(profile), "--output-dir", str(tmp_path / "bad")]
        )
    assert not (tmp_path / "bad").exists()
    with pytest.raises(SystemExit):
        main(
            common + ["--tetrahedron-count", "7", "--output-dir", str(tmp_path / "odd")]
        )


def test_six_cell_diagnostic_remains_unvalidated(tmp_path):
    import xml.etree.ElementTree as ET

    from scripts.generate_kaleidocycle_orientation_fixture import generate_fixture

    out = generate_fixture(tmp_path / "diagnostic")
    preview = ET.parse(out / "panel-orientation/sheet/net-preview.svg").getroot()
    assert len([t for t in preview.iter() if t.get("data-slot-label")]) == 24
    report = json.loads((out / "physical_validation.template.json").read_text())
    assert report["tetrahedron_count"] == 6
    assert report["validation_status"] == "not-tested"
    assert all(p["observed_state"] is None for p in report["panels"])


def test_export_legacy_profile_records_explicit_count(tmp_path):
    from scripts.export_artwork_layout import main
    from tests.test_artwork_layout_export import template

    legacy = layout_dict(
        resolve_kaleidocycle_state("A", width_mm=180, tetrahedron_count=8)
    )
    del legacy["settings"]["tetrahedron_count"]
    profile = tmp_path / "legacy.json"
    profile.write_text(json.dumps(legacy))
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps(template()))
    main(
        [
            "--layout",
            "kaleidocycle-state",
            "--state",
            "A",
            "--width-mm",
            "180",
            "--tetrahedron-count",
            "8",
            "--profile",
            str(profile),
            "--job-template",
            str(recipe),
            "--output-dir",
            str(tmp_path / "export"),
        ]
    )
    report = json.loads((tmp_path / "export/layout-handoff.json").read_text())
    assert report["layout"]["settings"]["tetrahedron_count"] == 8
