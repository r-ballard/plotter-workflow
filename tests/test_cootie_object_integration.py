from __future__ import annotations

import pytest

import scripts.cootie_impose as cootie
from imposition.objects.cootie_catcher import (
    COOTIE_CATCHER,
    EXPECTED_SLOTS,
    LEGACY_ROTATIONS,
    PANEL_POLYGONS,
    SUPPORTED_SHEETS,
)


def test_legacy_cootie_constants_match_declarative_object() -> None:
    assert tuple(cootie.EXPECTED_SLOTS) == EXPECTED_SLOTS
    assert cootie.COOTIE_PANEL_ROTATIONS == LEGACY_ROTATIONS
    for slot_id in EXPECTED_SLOTS:
        assert cootie.COOTIE_PANEL_POLYGONS[slot_id] == PANEL_POLYGONS[slot_id]
        assert cootie.panel_polygon_normalized(slot_id) == PANEL_POLYGONS[slot_id]


def test_legacy_square_placement_wrapper_matches_object() -> None:
    legacy = cootie.square_placement(
        "letter",
        position="center",
        square_size_mm=180.0,
    )
    resolved = COOTIE_CATCHER.resolve_placement(
        SUPPORTED_SHEETS["letter"],
        {"position": "center", "square_size_mm": 180.0},
    )
    assert legacy.x_mm == pytest.approx(resolved.x_mm)
    assert legacy.y_mm == pytest.approx(resolved.y_mm)
    assert legacy.size_mm == pytest.approx(resolved.width_mm)
    assert resolved.width_mm == pytest.approx(resolved.height_mm)


def test_legacy_guide_wrapper_keeps_existing_segment_counts() -> None:
    placement = cootie.square_placement("letter")
    segments = cootie.guide_segments("letter", placement)
    assert len(segments["trim"]) == 1
    assert len(segments["first-blintz"]) == 4
    assert len(segments["second-blintz"]) == 4
    assert len(segments["center-prefold"]) == 4
