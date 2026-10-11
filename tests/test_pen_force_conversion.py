import hashlib
import json
from pathlib import Path

import pytest

from pen_plan_io import load_resolved_plot_pass
from scripts import dpx3300_convert as converter

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = dict(
    config_path=ROOT / "vpype.toml",
    device="dpx3300",
    page_size="a3",
    landscape=False,
    margin="10mm",
    velocity=None,
    absolute=True,
    send=False,
    dry_run=False,
)


def legacy_svg(tmp_path):
    source = tmp_path / "drawing.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<g id="pen-1" data-pen="1" data-generations="0" fill="none" stroke="black">'
        '<g data-generation="0"><path d="M10 10L20 20"/></g></g></svg>'
    )
    return source


def test_legacy_force_conversion_uses_schema3_final_hash_and_validated_fs(tmp_path, monkeypatch):
    source = legacy_svg(tmp_path)
    plan = source.with_suffix(".penplan.json")
    plan.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "policy": "compact",
                "slots": [{"slot": 1, "tool": "Micron"}],
                "pen_force": {"mode": "software", "default_gf": 65},
            }
        )
    )

    def vpype(command, **kwargs):
        Path(command[-1]).write_text("IN;SP1;PU0,0;PD10,10;PU;SP0;")

    monkeypatch.setattr(converter, "run_command", vpype)
    outputs = converter.convert_files([source], tmp_path / "output", overwrite=False, **OPTIONS)
    hpgl = outputs[0]
    assert "IN;FS7;" in hpgl.read_text()
    resolved = load_resolved_plot_pass(hpgl.with_suffix(".resolved.penplan.json"))
    assert resolved.hpgl_sha256 == hashlib.sha256(hpgl.read_bytes()).hexdigest()
    assert resolved.pen_force.effective_slot_forces == ((1, 65),)


def test_legacy_failure_does_not_replace_prior_artifacts(tmp_path, monkeypatch):
    source = legacy_svg(tmp_path)
    dest = tmp_path / "output"
    dest.mkdir()
    (dest / "drawing.hpgl").write_bytes(b"old plot")
    (dest / "drawing.resolved.penplan.json").write_bytes(b"old audit")

    def fail(command, **kwargs):
        Path(command[-1]).write_text("IN;SP1;PD999999,999999;")

    monkeypatch.setattr(converter, "run_command", fail)
    with pytest.raises(ValueError):
        converter.convert_files([source], dest, overwrite=True, **OPTIONS)
    assert (dest / "drawing.hpgl").read_bytes() == b"old plot"
    assert (dest / "drawing.resolved.penplan.json").read_bytes() == b"old audit"
