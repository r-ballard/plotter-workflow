from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import booklet_impose as booklet


class PocketmodLayoutTests(unittest.TestCase):
    def test_mapping_matches_golden_fixture(self) -> None:
        fixture_path = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "imposition"
            / "pocketmod8"
            / "expected.json"
        )
        expected = json.loads(fixture_path.read_text(encoding="utf-8"))
        actual = {
            str(page): {
                "row": row,
                "column": column,
                "rotation_degrees": rotation,
            }
            for page, (row, column, rotation) in booklet.POCKETMOD8_CELLS.items()
        }
        self.assertEqual(actual, expected["logical_to_physical"])
        self.assertEqual(
            {tuple(pair) for pair in expected["facing_spreads"]},
            booklet.ALLOWED_SPREADS,
        )

    def test_physical_validation_fixture_has_eight_vector_pages(self) -> None:
        fixture_dir = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "imposition"
            / "pocketmod8"
            / "validation_pages"
        )
        pages = sorted(fixture_dir.glob("*.svg"))
        self.assertEqual([page.name for page in pages], [f"{n:02d}.svg" for n in range(1, 9)])
        for page in pages:
            text = page.read_text(encoding="utf-8")
            self.assertIn("<path", text)
            self.assertNotIn("<text", text)
            self.assertNotIn("<image", text)

    def test_automatic_mode_uses_natural_filename_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for number in (8, 2, 1, 7, 3, 6, 4, 5):
                (root / f"page-{number}.svg").write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
                )
            entries = booklet.discover_automatic_pages(root, fit="contain", margin_mm=4.0)
            self.assertEqual(
                [entry.source.name for entry in entries],
                [f"page-{number}.svg" for number in range(1, 9)],
            )
            self.assertEqual([entry.pages for entry in entries], [(n,) for n in range(1, 9)])

    def test_manifest_spread_covers_pages_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("cover.svg", "spread.svg", "p4.svg", "p5.svg", "p6.svg", "p7.svg", "p8.svg"):
                (root / name).write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
                )
            manifest = root / "booklet.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "layout": "pocketmod8",
                        "pages": [
                            {"page": 1, "source": "cover.svg"},
                            {"spread": [2, 3], "source": "spread.svg"},
                            {"page": 4, "source": "p4.svg"},
                            {"page": 5, "source": "p5.svg"},
                            {"page": 6, "source": "p6.svg"},
                            {"page": 7, "source": "p7.svg"},
                            {"page": 8, "source": "p8.svg"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            entries = booklet.load_manifest(
                root,
                manifest,
                default_fit="contain",
                default_margin_mm=4.0,
                default_gutter_mm=0.0,
            )
            self.assertEqual(entries[1].pages, (2, 3))
            self.assertTrue(entries[1].is_spread)

    def test_manifest_rejects_nonfacing_spread(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.svg"
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
            manifest = root / "booklet.json"
            manifest.write_text(
                json.dumps(
                    {
                        "pages": [
                            {"spread": [1, 2], "source": "source.svg"},
                            {"page": 3, "source": "source.svg"},
                            {"page": 4, "source": "source.svg"},
                            {"page": 5, "source": "source.svg"},
                            {"page": 6, "source": "source.svg"},
                            {"page": 7, "source": "source.svg"},
                            {"page": 8, "source": "source.svg"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(booklet.ImpositionError, "not a facing"):
                booklet.load_manifest(
                    root,
                    manifest,
                    default_fit="contain",
                    default_margin_mm=4.0,
                    default_gutter_mm=0.0,
                )


    def test_cell_transform_rotates_top_row_geometry(self) -> None:
        class FakeLines:
            def __init__(self) -> None:
                self.points = [0 + 0j, 10 + 20j]

            def scale(self, sx: float, sy: float | None = None) -> None:
                sy = sx if sy is None else sy
                self.points = [complex(p.real * sx, p.imag * sy) for p in self.points]

            def translate(self, dx: float, dy: float) -> None:
                self.points = [complex(p.real + dx, p.imag + dy) for p in self.points]

        upright = FakeLines()
        booklet._place_in_cell(upright, 1, 100.0, 200.0)
        self.assertEqual(upright.points, [300 + 200j, 310 + 220j])

        upside_down = FakeLines()
        booklet._place_in_cell(upside_down, 5, 100.0, 200.0)
        self.assertEqual(upside_down.points, [100 + 200j, 90 + 180j])

    def test_pen_contract_rejects_stray_top_level_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "bad.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg">'
                '<g id="pen-1" data-pen="1" data-generations="0" fill="none" stroke="#000">'
                '<g data-generation="0"><path d="M0,0 L1,1"/></g></g>'
                '<path d="M2,2 L3,3"/></svg>',
                encoding="utf-8",
            )
            entry = booklet.PageEntry((1,), source, "contain", 4.0, 0.0)
            with self.assertRaisesRegex(booklet.ImpositionError, "top-level drawable"):
                booklet.determine_source_mode([entry])

    def test_guide_svg_uses_one_logical_pen_and_two_generation_kinds(self) -> None:
        # Replace contract inspection so this unit test does not require the
        # repository module to parse generated content twice.
        original = booklet.inspect_pen_layer_contract
        booklet.inspect_pen_layer_contract = lambda path: object()
        try:
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "guides.svg"
                booklet.write_guide_svg(path, sheet_name="letter")
                text = path.read_text(encoding="utf-8")
                self.assertIn('id="pen-1"', text)
                self.assertIn('data-generations="1,2"', text)
                self.assertIn('data-guide-kind="fold"', text)
                self.assertIn('data-guide-kind="cut"', text)
                self.assertIn('data-plotter-workflow-layout="preserve"', text)
                self.assertIn('data-plotter-workflow-page-size="letter"', text)
                self.assertIn('data-plotter-workflow-orientation="landscape"', text)
        finally:
            booklet.inspect_pen_layer_contract = original


if __name__ == "__main__":
    unittest.main()
