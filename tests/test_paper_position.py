"""Regression tests for DPX-3300 paper placement profiles."""

from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

import dpx3300_convert as converter


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "vpype.toml"


class VpypePlacementTests(unittest.TestCase):
    """Check centered and lower-left device profiles and command generation."""

    @classmethod
    def setUpClass(cls) -> None:
        config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.profile = config["device"]["dpx3300"]
        cls.papers = {paper["name"]: paper for paper in cls.profile["paper"]}

    def test_centered_letter_profile(self) -> None:
        letter = self.papers["letter"]
        self.assertEqual(letter["paper_size"], ["11in", "8.5in"])
        self.assertEqual(letter["origin_location"], ["5.5in", "4.25in"])
        self.assertEqual(letter["x_range"], [-5588, 5588])
        self.assertEqual(letter["y_range"], [-4318, 4318])

    def test_lower_left_letter_matches_ansi_d_limits(self) -> None:
        letter = self.papers["letter_lower_left"]
        self.assertEqual(letter["paper_size"], ["11in", "8.5in"])
        self.assertEqual(letter["origin_location_reference"], "botleft")
        self.assertEqual(letter["origin_location"], ["443.75mm", "279.50mm"])
        self.assertEqual(letter["x_range"], [-17750, -6574])
        self.assertEqual(letter["y_range"], [-11180, -2544])

        # Letter landscape is 11in x 8.5in = 11176 x 8636 plotter units.
        self.assertEqual(letter["x_range"][1] - letter["x_range"][0], 11176)
        self.assertEqual(letter["y_range"][1] - letter["y_range"][0], 8636)

    def test_lower_left_profile_resolution(self) -> None:
        self.assertEqual(
            converter.resolve_device_page_size("letter", "lower-left", True),
            "letter_lower_left",
        )
        self.assertEqual(
            converter.resolve_device_page_size("letter", "center", True),
            "letter",
        )

    def test_lower_left_requires_landscape(self) -> None:
        with self.assertRaises(ValueError):
            converter.resolve_device_page_size("letter", "lower-left", False)

    def test_converter_uses_distinct_layout_and_device_page_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "drawing.svg"
            destination = directory / "drawing.hpgl"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"/>',
                encoding="utf-8",
            )

            command = converter.build_vpype_command(
                source,
                destination,
                config_path=CONFIG_PATH,
                device="dpx3300",
                page_size="letter",
                device_page_size="letter_lower_left",
                landscape=True,
                margin="0.5in",
                velocity=None,
                absolute=True,
            )

        # layout uses the standard vpype page name.
        layout_index = command.index("layout")
        write_index = command.index("write")
        self.assertIn("letter", command[layout_index:write_index])

        # HP-GL writer uses the physical-placement profile.
        page_size_index = command.index("--page-size", write_index)
        self.assertEqual(command[page_size_index + 1], "letter_lower_left")
        self.assertIn("--absolute", command)


if __name__ == "__main__":
    unittest.main()
