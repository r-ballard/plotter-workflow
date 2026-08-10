from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import dpx3300_convert as converter


class PreservedPhysicalLayoutTests(unittest.TestCase):
    def _command(self, source: Path, destination: Path) -> list[str]:
        return converter.build_vpype_command(
            source,
            destination,
            config_path=Path("vpype.toml"),
            device="dpx3300",
            page_size="letter",
            device_page_size="letter_lower_left",
            landscape=True,
            margin="4mm",
            velocity=None,
            absolute=True,
        )

    def test_normal_svg_keeps_layout_and_centering(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "normal.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="11in" height="8.5in"/>',
                encoding="utf-8",
            )
            command = self._command(source, root / "normal.hpgl")
        self.assertIn("layout", command)
        self.assertIn("--fit-to-margins", command)
        self.assertIn("--center", command)

    def test_imposed_svg_skips_geometry_relayout_and_writer_centering(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "book.imposed.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="11in" height="8.5in" '
                'data-plotter-workflow-layout="preserve" data-plotter-workflow-page-size="letter" data-plotter-workflow-orientation="landscape"/>',
                encoding="utf-8",
            )
            command = self._command(source, root / "book.hpgl")
        self.assertNotIn("layout", command)
        self.assertNotIn("--fit-to-margins", command)
        self.assertNotIn("--center", command)
        self.assertIn("write", command)
        self.assertIn("letter_lower_left", command)
        self.assertIn("--landscape", command)
        self.assertIn("--absolute", command)

    def test_layout_marker_detection_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "drawing.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" data-plotter-workflow-layout="other"/>',
                encoding="utf-8",
            )
            self.assertFalse(converter.svg_preserves_physical_layout(source))
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" data-plotter-workflow-layout="preserve" data-plotter-workflow-page-size="letter" data-plotter-workflow-orientation="landscape"/>',
                encoding="utf-8",
            )
            self.assertTrue(converter.svg_preserves_physical_layout(source))

    def test_preserved_layout_rejects_page_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "book.imposed.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" data-plotter-workflow-layout="preserve" '
                'data-plotter-workflow-page-size="a4" data-plotter-workflow-orientation="landscape"/>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(converter.ConversionError, "page size"):
                self._command(source, root / "book.hpgl")


if __name__ == "__main__":
    unittest.main()
