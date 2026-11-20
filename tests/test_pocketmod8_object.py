import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from imposition.artwork_layout import resolve_booklet_spread
from imposition.geometry import rotate_vector_clockwise
from imposition.model import SheetSpec
from imposition.objects.pocketmod8 import POCKETMOD8, SUPPORTED_SHEETS, PocketMod8

EXPECTED = json.loads(
    (Path(__file__).parent / "fixtures/imposition/pocketmod8/expected.json").read_text()
)


def test_object_owns_eight_slots_and_existing_page_mapping():
    assert isinstance(POCKETMOD8, PocketMod8)
    assert POCKETMOD8.object_id == "pocketmod8"
    assert POCKETMOD8.schema_version == 1
    assert [s.slot_id for s in POCKETMOD8.slots] == [f"page-{i}" for i in range(1, 9)]
    for page, slot in enumerate(POCKETMOD8.slots, 1):
        expected = EXPECTED["logical_to_physical"][str(page)]
        row, column, rotation = POCKETMOD8.cell(page)
        assert (row, column, rotation) == (
            expected["row"],
            expected["column"],
            expected["rotation_degrees"],
        )
        assert slot.polygon == (
            (column / 4, row / 2),
            ((column + 1) / 4, row / 2),
            ((column + 1) / 4, (row + 1) / 2),
            (column / 4, (row + 1) / 2),
        )
        assert slot.target_orientation.up_vector == pytest.approx(
            rotate_vector_clockwise((0, -1), rotation)
        )
        assert slot.target_orientation.right_vector == pytest.approx(
            rotate_vector_clockwise((1, 0), rotation)
        )
    assert set(POCKETMOD8.facing_spreads) == {
        tuple(p) for p in EXPECTED["facing_spreads"]
    }


@pytest.mark.parametrize("name", ["letter", "a4", "a3", "tabloid"])
def test_full_sheet_placement_guides_and_reading_spreads(name):
    sheet = SUPPORTED_SHEETS[name]
    p = POCKETMOD8.resolve_placement(sheet, {})
    w, h = sheet.width_mm, sheet.height_mm
    assert (p.x_mm, p.y_mm, p.width_mm, p.height_mm) == (0, 0, w, h)
    assert POCKETMOD8.cell_size(p) == (w / 4, h / 2)
    guides = POCKETMOD8.guides(p)
    assert [g.kind for g in guides] == ["fold"] * 5 + ["cut"]
    assert [g.points for g in guides] == [
        ((w / 4, 0), (w / 4, h)),
        ((w / 2, 0), (w / 2, h)),
        ((3 * w / 4, 0), (3 * w / 4, h)),
        ((0, h / 2), (w / 4, h / 2)),
        ((3 * w / 4, h / 2), (w, h / 2)),
        ((w / 4, h / 2), (3 * w / 4, h / 2)),
    ]
    for pair in POCKETMOD8.facing_spreads:
        layout = resolve_booklet_spread(
            sheet_size=name, pages=pair, margin_mm=0, gutter_mm=0
        )
        assert [s.panel_id for s in layout.panels] == [f"page-{n}" for n in pair]
        assert layout.window[2:] == pytest.approx(
            (w / 2 * 96 / 25.4, h / 2 * 96 / 25.4)
        )


def test_cell_placement_keeps_legacy_asymmetric_coordinates():
    import vpype

    for page in range(1, 9):
        lines = vpype.LineCollection([[complex(3, 5), complex(11, 17)]])
        POCKETMOD8.place_in_cell(lines, page, 70, 100)
        row, col, rotation = POCKETMOD8.cell(page)
        expected = [
            complex(
                col * 70 + (70 - x if rotation else x),
                row * 100 + (100 - y if rotation else y),
            )
            for x, y in ((3, 5), (11, 17))
        ]
        assert list(next(iter(lines))) == pytest.approx(expected)


@pytest.mark.parametrize(
    "sheet,options",
    [
        (SheetSpec("bad", 100, 200, "portrait"), {}),
        (SheetSpec("bad", math.nan, 200, "landscape"), {}),
        (SheetSpec("bad", 200, 0, "landscape"), {}),
        (SUPPORTED_SHEETS["letter"], {"scale": 0.5}),
    ],
)
def test_invalid_object_placement(sheet, options):
    with pytest.raises(ValueError):
        POCKETMOD8.resolve_placement(sheet, options)


@pytest.mark.parametrize("page", [0, 9, True, "1"])
def test_invalid_page(page):
    with pytest.raises(ValueError):
        POCKETMOD8.cell(page)


def test_booklet_geometry_and_composition_do_not_depend_on_cli_imports():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from imposition.booklet_artwork import resolve_booklet_spread; "
                "resolve_booklet_spread(sheet_size='letter',pages=(8,1),margin_mm=0,gutter_mm=0); "
                "import sys; assert 'scripts.booklet_impose' not in sys.modules"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
