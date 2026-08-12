from __future__ import annotations

import json
import math
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import cootie_impose as cootie


FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "imposition"
    / "cootie_catcher"
)


def test_layout_matches_golden_fixture() -> None:
    expected = json.loads((FIXTURE_DIR / "expected.json").read_text(encoding="utf-8"))
    actual = {
        slot: {
            "kind": slot.rsplit("-", 1)[0],
            "index": int(slot.rsplit("-", 1)[1]),
            "rotation_degrees": cootie.COOTIE_PANEL_ROTATIONS[slot],
            "polygon_normalized": [list(point) for point in cootie.COOTIE_PANEL_POLYGONS[slot]],
        }
        for slot in cootie.EXPECTED_SLOTS
    }
    assert expected["layout"] == cootie.LAYOUT_NAME
    assert expected["orientation_validation"] == cootie.ORIENTATION_VALIDATION
    assert actual == expected["logical_to_physical"]
    assert expected["selector_reveal_pairs"] == cootie.SELECTOR_REVEAL_PAIRS


def test_semantic_regions_partition_entire_square() -> None:
    total = sum(cootie.polygon_area(polygon) for polygon in cootie.COOTIE_PANEL_POLYGONS.values())
    assert math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-12)

    outer = sum(
        cootie.polygon_area(cootie.COOTIE_PANEL_POLYGONS[f"outer-{index}"])
        for index in range(1, 5)
    )
    selectors = sum(
        cootie.polygon_area(cootie.COOTIE_PANEL_POLYGONS[f"selector-{index}"])
        for index in range(1, 9)
    )
    reveals = sum(
        cootie.polygon_area(cootie.COOTIE_PANEL_POLYGONS[f"reveal-{index}"])
        for index in range(1, 9)
    )
    assert math.isclose(outer, 0.25)
    assert math.isclose(selectors, 0.25)
    assert math.isclose(reveals, 0.5)


def test_each_selector_shares_its_diagonal_with_paired_reveal() -> None:
    for number in range(1, 9):
        selector = set(cootie.COOTIE_PANEL_POLYGONS[f"selector-{number}"])
        reveal = set(cootie.COOTIE_PANEL_POLYGONS[f"reveal-{number}"])
        assert len(selector & reveal) == 2


def test_manifest_requires_each_semantic_slot_once() -> None:
    entries = cootie.load_manifest(
        FIXTURE_DIR,
        FIXTURE_DIR / "cootie.json",
        default_fit="contain",
        default_margin_mm=3.0,
    )
    assert [entry.slot for entry in entries] == list(cootie.EXPECTED_SLOTS)

    with tempfile.TemporaryDirectory() as temp:
        temp_dir = Path(temp)
        payload = json.loads((FIXTURE_DIR / "cootie.json").read_text(encoding="utf-8"))
        payload["panels"] = payload["panels"][:-1]
        # Sources are resolved before completeness is checked, so copy every
        # still-referenced fixture under the same relative path.
        validation = temp_dir / "validation_panels"
        validation.mkdir()
        for raw in payload["panels"]:
            source = FIXTURE_DIR / raw["source"]
            (temp_dir / raw["source"]).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        manifest = temp_dir / "cootie.json"
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(cootie.ImpositionError, match="all 20 semantic slots exactly once"):
            cootie.load_manifest(temp_dir, manifest)


def test_default_letter_square_has_one_trim_edge() -> None:
    expected = json.loads((FIXTURE_DIR / "expected.json").read_text(encoding="utf-8"))[
        "default_letter_square"
    ]
    placement = cootie.square_placement("letter", position="left")
    assert math.isclose(placement.x_mm, expected["x_mm"])
    assert math.isclose(placement.y_mm, expected["y_mm"])
    assert math.isclose(placement.size_mm, expected["size_mm"])

    segments = cootie.guide_segments("letter", placement)
    assert len(segments["trim"]) == expected["trim_edge_count"] == 1
    assert len(segments["first-blintz"]) == 4
    assert len(segments["second-blintz"]) == 4
    assert len(segments["center-prefold"]) == 4


def test_centered_smaller_square_requires_four_trim_edges() -> None:
    placement = cootie.square_placement("letter", position="center", square_size_mm=180.0)
    assert len(cootie.guide_segments("letter", placement)["trim"]) == 4


def test_inset_triangle_stays_inside_original() -> None:
    triangle = ((0.0, 0.0), (100.0, 0.0), (0.0, 100.0))
    inset = cootie.inset_convex_polygon(triangle, 5.0)
    assert cootie.polygon_area(inset) < cootie.polygon_area(triangle)
    for point in inset:
        for normal, c in cootie._inward_halfplanes(triangle):
            assert cootie._dot(normal, point) >= c - 1e-7


def test_convex_segment_clipping() -> None:
    triangle = ((0.0, 0.0), (100.0, 0.0), (0.0, 100.0))
    clipped = cootie.clip_segment_to_convex_polygon((-20.0, 50.0), (80.0, 50.0), triangle)
    assert clipped is not None
    assert clipped[0] == pytest.approx((0.0, 50.0))
    assert clipped[1] == pytest.approx((50.0, 50.0))
    assert cootie.clip_segment_to_convex_polygon((80.0, 80.0), (90.0, 90.0), triangle) is None


def test_preserved_layout_and_guide_metadata() -> None:
    placement = cootie.square_placement("letter")
    root = cootie._new_physical_svg_root("letter", placement)
    assert root.get("data-plotter-workflow-layout") == "preserve"
    assert root.get("data-plotter-workflow-page-size") == "letter"
    assert root.get("data-plotter-workflow-orientation") == "landscape"
    assert root.get("data-imposition-layout") == "cootie_catcher"
    assert root.get("data-imposition-orientation-validation") == "provisional"

    guide = cootie.build_guide_svg("letter", placement)
    assert guide.get("data-imposition-guide") == "true"
    guide_kinds = {
        element.get("data-guide-kind")
        for element in guide.iter()
        if element.get("data-guide-kind")
    }
    assert guide_kinds == {"trim", "first-blintz", "second-blintz", "center-prefold"}


def test_validation_fixture_has_twenty_vector_only_panels() -> None:
    panels = sorted((FIXTURE_DIR / "validation_panels").glob("*.svg"))
    assert len(panels) == 20
    assert {path.stem for path in panels} == set(cootie.EXPECTED_SLOTS)
    for path in panels:
        text = path.read_text(encoding="utf-8")
        assert "<path" in text
        assert "<text" not in text
        assert "<image" not in text
        assert f'data-validation-slot="{path.stem}"' in text


def test_fixture_imposition_writes_polygon_clipped_preserved_svg(tmp_path: Path) -> None:
    pytest.importorskip("vpype")
    entries = cootie.load_manifest(FIXTURE_DIR, FIXTURE_DIR / "cootie.json")
    placement = cootie.square_placement("letter")
    root, rendered, mode = cootie.impose(
        entries,
        sheet_size="letter",
        placement=placement,
        quantization_mm=0.2,
    )
    assert mode == "generic"
    assert len(rendered) == 20
    assert root.get("data-plotter-workflow-layout") == "preserve"
    assert any(element.tag.endswith("path") for element in root.iter())

    output = tmp_path / "validation.imposed.svg"
    cootie._write_xml(root, output, overwrite=False)
    parsed = ET.parse(output).getroot()
    assert parsed.get("data-imposition-layout") == "cootie_catcher"
