from __future__ import annotations

import pytest

from imposition.geometry import rotate_vector_clockwise
from imposition.model import ObjectPlacement, SheetSpec
from imposition.objects.cootie_catcher import (
    COOTIE_CATCHER,
    EXPECTED_SLOTS,
    LEGACY_ROTATIONS,
    PANEL_POLYGONS,
    SELECTOR_REVEAL_PAIRS,
    SUPPORTED_SHEETS,
)


def test_cootie_object_has_twenty_stable_semantic_slots() -> None:
    assert COOTIE_CATCHER.object_id == "cootie_catcher"
    assert COOTIE_CATCHER.schema_version == 1
    assert [slot.slot_id for slot in COOTIE_CATCHER.slots] == list(EXPECTED_SLOTS)
    assert {slot.family for slot in COOTIE_CATCHER.slots} == {
        "outer",
        "selector",
        "reveal",
    }
    assert len(PANEL_POLYGONS) == 20
    assert len(SELECTOR_REVEAL_PAIRS) == 8


def test_target_vectors_encode_current_rotation_contract() -> None:
    canonical_up = (0.0, -1.0)
    for slot in COOTIE_CATCHER.slots:
        expected = rotate_vector_clockwise(canonical_up, LEGACY_ROTATIONS[slot.slot_id])
        assert slot.target_orientation.up_vector == pytest.approx(expected)
        assert slot.target_orientation.validation == "provisional"


def test_default_letter_placement_is_largest_left_aligned_square() -> None:
    placement = COOTIE_CATCHER.resolve_placement(SUPPORTED_SHEETS["letter"], {})
    assert placement.sheet == SUPPORTED_SHEETS["letter"]
    assert placement.x_mm == pytest.approx(0.0)
    assert placement.y_mm == pytest.approx(0.0)
    assert placement.width_mm == pytest.approx(215.9)
    assert placement.height_mm == pytest.approx(215.9)


def test_centered_custom_square_placement() -> None:
    placement = COOTIE_CATCHER.resolve_placement(
        SUPPORTED_SHEETS["letter"],
        {"position": "center", "square_size_mm": 180.0},
    )
    assert placement.x_mm == pytest.approx((279.4 - 180.0) / 2.0)
    assert placement.y_mm == pytest.approx((215.9 - 180.0) / 2.0)


def test_default_letter_guides_preserve_existing_semantics() -> None:
    placement = COOTIE_CATCHER.resolve_placement(SUPPORTED_SHEETS["letter"], {})
    guides = COOTIE_CATCHER.guides(placement)
    by_kind: dict[str, list] = {}
    for guide in guides:
        by_kind.setdefault(guide.kind, []).append(guide)

    assert len(by_kind["trim"]) == 1
    assert len(by_kind["first-blintz"]) == 1
    assert by_kind["first-blintz"][0].closed is True
    assert len(by_kind["second-blintz"]) == 1
    assert by_kind["second-blintz"][0].closed is True
    assert len(by_kind["center-prefold"]) == 4


def test_smaller_centered_square_has_four_trim_edges() -> None:
    placement = COOTIE_CATCHER.resolve_placement(
        SUPPORTED_SHEETS["letter"],
        {"position": "center", "square_size_mm": 180.0},
    )
    assert sum(guide.kind == "trim" for guide in COOTIE_CATCHER.guides(placement)) == 4


def test_guides_require_sheet_context_on_placement() -> None:
    sheet = SheetSpec("test", 200.0, 100.0, "landscape")
    placement = ObjectPlacement(
        sheet=sheet,
        x_mm=50.0,
        y_mm=0.0,
        width_mm=100.0,
        height_mm=100.0,
    )
    trim = [guide for guide in COOTIE_CATCHER.guides(placement) if guide.kind == "trim"]
    assert len(trim) == 2
