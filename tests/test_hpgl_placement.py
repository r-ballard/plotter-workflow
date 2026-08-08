from pathlib import Path

import pytest

from hpgl_placement import (
    Bounds,
    PlacementValidationError,
    parse_hpgl_coordinates,
    parse_length_mm,
    validate_hpgl_placement,
    write_placement_report,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "vpype.toml"


def test_absolute_coordinate_parser_tracks_drawing_start():
    parsed = parse_hpgl_coordinates("IN;PA;PU-10,-20;PD10,20,30,40;PU;SP0;")
    assert parsed.addressed_bounds == Bounds(-10, -20, 30, 40)
    assert parsed.drawing_bounds == Bounds(-10, -20, 30, 40)
    assert parsed.drawing_segment_count == 2
    assert parsed.coordinate_modes == ("absolute",)


def test_relative_coordinate_parser_accumulates_position():
    parsed = parse_hpgl_coordinates("IN;PR;PU10,20;PD5,-5,5,5;PU;")
    assert parsed.addressed_bounds == Bounds(10, 15, 20, 20)
    assert parsed.drawing_bounds == Bounds(10, 15, 20, 20)
    assert parsed.drawing_segment_count == 2
    assert parsed.coordinate_modes == ("relative",)


def test_parser_supports_mixed_pa_pr_modes():
    parsed = parse_hpgl_coordinates("IN;PA;PU100,100;PD200,100;PR;PD10,20;PA;PD250,150;")
    assert parsed.drawing_bounds == Bounds(100, 100, 250, 150)
    assert parsed.coordinate_modes == ("absolute", "relative")


@pytest.mark.parametrize(("value", "expected"), [("10mm", 10.0), ("1cm", 10.0), ("0.5in", 12.7)])
def test_parse_length_mm(value: str, expected: float):
    assert parse_length_mm(value) == pytest.approx(expected)


def _write_config(path: Path) -> Path:
    path.write_text(
        '''[device.dpx3300]\nplotter_unit_length = "0.025mm"\npen_count = 8\n\n[[device.dpx3300.paper]]\nname = "letter"\nx_range = [-5588, 5588]\ny_range = [-4318, 4318]\n\n[[device.dpx3300.paper]]\nname = "letter_lower_left"\nx_range = [-17750, -6574]\ny_range = [-11180, -2544]\n''',
        encoding="utf-8",
    )
    return path


def _write_hpgl(path: Path, x0: int, y0: int, x1: int, y1: int) -> Path:
    path.write_text(f"IN;PA;PU{x0},{y0};PD{x1},{y1};PU;SP0;", encoding="ascii")
    return path


def test_centered_letter_profile_with_half_inch_margin_passes(tmp_path: Path):
    config = _write_config(tmp_path / "vpype.toml")
    hpgl = _write_hpgl(tmp_path / "center.hpgl", -5000, -3700, 5000, 3700)
    report = validate_hpgl_placement(hpgl, config_path=config, device="dpx3300", page_profile="letter", margin="0.5in")
    assert report.margin_units == pytest.approx(508.0)
    assert report.paper_bounds == Bounds(-5588, -4318, 5588, 4318)
    assert report.margin_bounds == Bounds(-5080, -3810, 5080, 3810)


def test_lower_left_letter_profile_with_half_inch_margin_passes(tmp_path: Path):
    config = _write_config(tmp_path / "vpype.toml")
    hpgl = _write_hpgl(tmp_path / "lower.hpgl", -17200, -10600, -7100, -3100)
    report = validate_hpgl_placement(hpgl, config_path=config, device="dpx3300", page_profile="letter_lower_left", margin="0.5in")
    assert report.paper_bounds == Bounds(-17750, -11180, -6574, -2544)
    assert report.margin_bounds == Bounds(-17242, -10672, -7082, -3052)


def test_addressed_coordinate_outside_paper_fails(tmp_path: Path):
    config = _write_config(tmp_path / "vpype.toml")
    hpgl = _write_hpgl(tmp_path / "outside.hpgl", -6000, 0, 0, 0)
    with pytest.raises(PlacementValidationError, match="exceed the configured paper profile"):
        validate_hpgl_placement(hpgl, config_path=config, device="dpx3300", page_profile="letter", margin="0.5in")


def test_drawing_inside_paper_but_inside_margin_zone_fails(tmp_path: Path):
    config = _write_config(tmp_path / "vpype.toml")
    hpgl = _write_hpgl(tmp_path / "margin.hpgl", -5400, 0, 0, 0)
    with pytest.raises(PlacementValidationError, match="violate the requested layout margin"):
        validate_hpgl_placement(hpgl, config_path=config, device="dpx3300", page_profile="letter", margin="0.5in")


def test_placement_report_is_written_as_json(tmp_path: Path):
    config = _write_config(tmp_path / "vpype.toml")
    hpgl = _write_hpgl(tmp_path / "center.hpgl", -5000, -3700, 5000, 3700)
    report = validate_hpgl_placement(hpgl, config_path=config, device="dpx3300", page_profile="letter", margin="0.5in")
    output = write_placement_report(report, tmp_path / "center.placement.json")
    text = output.read_text(encoding="utf-8")
    assert '"status": "pass"' in text
    assert '"page_profile": "letter"' in text
