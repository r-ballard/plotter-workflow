from pathlib import Path

import pytest

from dpx3300_convert import ConversionError, validate_hpgl


def test_validate_hpgl_accepts_expected_pen_selections(tmp_path: Path):
    path = tmp_path / "drawing.hpgl"
    path.write_text(
        "IN;DF;SP1;PU0,0;PD10,10;PU;SP3;PU20,20;PD30,30;PU;SP0;IN;",
        encoding="ascii",
    )
    validate_hpgl(path, expected_pens=(1, 3))


def test_validate_hpgl_rejects_missing_expected_pen(tmp_path: Path):
    path = tmp_path / "drawing.hpgl"
    path.write_text(
        "IN;DF;SP1;PU0,0;PD10,10;PU;SP0;IN;",
        encoding="ascii",
    )
    with pytest.raises(ConversionError, match="SP3"):
        validate_hpgl(path, expected_pens=(1, 3))
