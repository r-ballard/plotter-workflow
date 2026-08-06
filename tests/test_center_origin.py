"""Regression tests for the DPX-3300 centered-origin conversion profile."""

from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

import dpx3300_convert as converter


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "vpype.toml"


class VpypeProfileTests(unittest.TestCase):
    """Check the project profile and generated vpype command."""

    def test_letter_profile_is_centered(self) -> None:
        config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        profile = config["device"]["dpx3300"]
        papers = {paper["name"]: paper for paper in profile["paper"]}
        letter = papers["letter"]

        self.assertEqual(profile["plotter_unit_length"], "0.025mm")
        self.assertEqual(profile["pen_count"], 8)
        self.assertEqual(letter["paper_size"], ["11in", "8.5in"])
        self.assertEqual(letter["origin_location"], ["5.5in", "4.25in"])
        self.assertEqual(letter["x_range"], [-5588, 5588])
        self.assertEqual(letter["y_range"], [-4318, 4318])

    def test_converter_loads_project_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "drawing.svg"
            destination = directory / "drawing.hpgl"
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")

            command = converter.build_vpype_command(
                source,
                destination,
                config_path=CONFIG_PATH,
                device="dpx3300",
                page_size="letter",
                landscape=True,
                margin="0.5in",
                velocity=None,
                absolute=True,
            )

        self.assertEqual(command[:2], ["vpype", "--config"])
        self.assertEqual(Path(command[2]), CONFIG_PATH)
        self.assertEqual(command[command.index("--device") + 1], "dpx3300")
        self.assertEqual(command[command.index("--page-size") + 1], "letter")
        self.assertIn("--landscape", command)
        self.assertIn("--absolute", command)


if __name__ == "__main__":
    unittest.main()
