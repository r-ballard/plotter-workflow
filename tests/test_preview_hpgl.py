import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "preview_hpgl.py"


def write_job(tmp_path: Path, hpgl_text: str):
    hpgl = tmp_path / "drawing.hpgl"
    hpgl.write_text(hpgl_text, encoding="ascii")
    placement = tmp_path / "drawing.placement.json"
    placement.write_text(json.dumps({
        "source_hpgl": hpgl.name,
        "plotter_unit_length_mm": 0.025,
        "paper_bounds": {"min_x": 0, "min_y": 0, "max_x": 400, "max_y": 400},
        "status": "pass",
    }), encoding="utf-8")
    return hpgl


def run_preview(hpgl: Path):
    return subprocess.run([
        sys.executable, str(SCRIPT), "--hpgl", str(hpgl),
        "--preview", str(hpgl.with_suffix(".preview.svg")),
        "--metrics", str(hpgl.with_suffix(".metrics.json")),
    ], capture_output=True, text=True, check=False)


def test_preview_reports_actual_pen_motion_and_is_deterministic(tmp_path: Path):
    hpgl = write_job(
        tmp_path,
        "IN;DF;SP1;PA;PU0,0;PD100,0,100,100;PU200,100;"
        "SP2;PR;PU0,100;PD-100,0;PU;SP0;IN;",
    )
    assert run_preview(hpgl).returncode == 0
    metrics_path = tmp_path / "drawing.metrics.json"
    preview_path = tmp_path / "drawing.preview.svg"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["pen_down_segments"] == 3
    assert metrics["pen_up_segments"] == 2
    assert metrics["pen_down_mm"] == 7.5
    assert metrics["pen_up_mm"] == 5.0
    assert metrics["per_pen"]["1"]["pen_down_segments"] == 2
    assert metrics["per_pen"]["2"]["pen_down_segments"] == 1
    assert len(metrics["hpgl_sha256"]) == 64
    svg_bytes = preview_path.read_bytes()
    root = ET.fromstring(svg_bytes)
    assert root.attrib["viewBox"] == "0 -400 400 400"
    assert b"stroke-dasharray" in svg_bytes
    assert b"Pen-up travel" in svg_bytes
    assert run_preview(hpgl).returncode != 0
    assert preview_path.read_bytes() == svg_bytes


def test_preview_rejects_unsupported_motion_without_outputs(tmp_path: Path):
    hpgl = write_job(tmp_path, "IN;SP1;PU0,0;CI100;PD100,0;SP0;")
    result = run_preview(hpgl)
    assert result.returncode != 0
    assert "unsupported" in result.stderr.lower()
    assert not (tmp_path / "drawing.preview.svg").exists()
    assert not (tmp_path / "drawing.metrics.json").exists()


def test_preview_rejects_mismatched_placement(tmp_path: Path):
    hpgl = write_job(tmp_path, "IN;SP1;PU0,0;PD100,0;PU;SP0;")
    sidecar = tmp_path / "drawing.placement.json"
    data = json.loads(sidecar.read_text())
    data["source_hpgl"] = "different.hpgl"
    sidecar.write_text(json.dumps(data))
    result = run_preview(hpgl)
    assert result.returncode != 0
    assert not (tmp_path / "drawing.preview.svg").exists()
