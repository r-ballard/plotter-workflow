import json
from pathlib import Path

import pytest

from job_preflight import JobPreflightError, format_job_preflight, run_job_preflight


def write_config(path: Path) -> Path:
    path.write_text(
        '''[device.dpx3300]\nplotter_unit_length = "0.025mm"\npen_count = 8\n\n[[device.dpx3300.paper]]\nname = "letter"\nx_range = [-5588, 5588]\ny_range = [-4318, 4318]\n''',
        encoding="utf-8",
    )
    return path


def write_hpgl(path: Path, pens=(8, 6), x0=-1000, y0=-1000, x1=1000, y1=1000) -> Path:
    chunks = ["IN", "PA"]
    for index, pen in enumerate(pens):
        chunks += [f"SP{pen}", f"PU{x0 + index * 10},{y0}", f"PD{x1},{y1}"]
    chunks += ["PU", "SP0"]
    path.write_text(";".join(chunks) + ";", encoding="ascii")
    return path


def write_penplan(path: Path, pens=(8, 6), documented=True) -> Path:
    assignments = []
    logical_layers = []
    for logical, pen in enumerate(pens, start=2):
        logical_layers.append({
            "logical_layer": logical,
            "active": True,
            "generations": [logical - 1],
            "preview_color": "#000000",
        })
        assignments.append({
            "logical_layer": logical,
            "physical_slot": pen,
            "generations": [logical - 1],
            "preview_color": "#000000",
            "tool": "technical pen" if documented else None,
            "color": "black",
            "label": f"tool {logical}" if documented else None,
            "notes": None,
        })
    raw = {
        "schema_version": 1,
        "kind": "resolved-dpx3300-pen-plan",
        "source_svg": "drawing.svg",
        "policy": "explicit",
        "logical_layers": logical_layers,
        "assignments": assignments,
        "slots": [],
        "unused_physical_slots": [],
        "notes": None,
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def write_placement(path: Path, hpgl_name="drawing.hpgl", drawing=None) -> Path:
    drawing = drawing or {"min_x": -1000, "min_y": -1000, "max_x": 1000, "max_y": 1000}
    raw = {
        "source_hpgl": hpgl_name,
        "device": "dpx3300",
        "page_profile": "letter",
        "margin": "0.5in",
        "plotter_unit_length_mm": 0.025,
        "margin_units": 508.0,
        "tolerance_units": 2.0,
        "paper_bounds": {"min_x": -5588, "min_y": -4318, "max_x": 5588, "max_y": 4318},
        "margin_bounds": {"min_x": -5080, "min_y": -3810, "max_x": 5080, "max_y": 3810},
        "addressed_bounds": drawing,
        "drawing_bounds": drawing,
        "coordinate_modes": ["absolute"],
        "addressed_point_count": 4,
        "drawing_segment_count": 2,
        "status": "pass",
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def setup_job(tmp_path: Path, pens=(8, 6), documented=True):
    config = write_config(tmp_path / "vpype.toml")
    hpgl = write_hpgl(tmp_path / "drawing.hpgl", pens=pens)
    penplan = write_penplan(tmp_path / "drawing.penplan.json", pens=pens, documented=documented)
    placement = write_placement(tmp_path / "drawing.placement.json")
    return config, hpgl, penplan, placement


def test_valid_multi_pen_review_requires_operator_confirmation_for_ready_state(tmp_path: Path):
    config, hpgl, _, _ = setup_job(tmp_path)
    report, plan = run_job_preflight(hpgl, config_path=config)
    assert report.physical_pen_order == (8, 6)
    assert report.placement_status == "pass"
    assert report.pen_plan_status == "pass"
    assert report.ready_to_send is False
    assert plan is not None
    assert "VALIDATED - OPERATOR CONFIRMATION REQUIRED" in format_job_preflight(report, plan)


def test_confirmed_multi_pen_job_is_ready(tmp_path: Path):
    config, hpgl, _, _ = setup_job(tmp_path)
    report, _ = run_job_preflight(
        hpgl,
        config_path=config,
        require_operator_confirmation=True,
        operator_confirmed=True,
    )
    assert report.ready_to_send is True
    assert report.operator_confirmation_status == "confirmed"


def test_sender_mode_rejects_unconfirmed_multi_pen_job(tmp_path: Path):
    config, hpgl, _, _ = setup_job(tmp_path)
    with pytest.raises(JobPreflightError, match="requires --confirm-pen-plan"):
        run_job_preflight(
            hpgl,
            config_path=config,
            require_operator_confirmation=True,
            operator_confirmed=False,
        )


def test_pen_order_mismatch_is_rejected(tmp_path: Path):
    config, hpgl, _, _ = setup_job(tmp_path, pens=(8, 6))
    write_penplan(tmp_path / "drawing.penplan.json", pens=(8, 4))
    with pytest.raises(JobPreflightError, match="does not match resolved pen plan"):
        run_job_preflight(hpgl, config_path=config)


def test_undocumented_multi_pen_slots_are_rejected(tmp_path: Path):
    config, hpgl, _, _ = setup_job(tmp_path, documented=False)
    with pytest.raises(JobPreflightError, match="tool or label"):
        run_job_preflight(hpgl, config_path=config)


def test_missing_placement_report_is_rejected(tmp_path: Path):
    config, hpgl, _, placement = setup_job(tmp_path)
    placement.unlink()
    with pytest.raises(JobPreflightError, match="Placement report does not exist"):
        run_job_preflight(hpgl, config_path=config)


def test_stale_placement_bounds_are_rejected(tmp_path: Path):
    config, hpgl, _, _ = setup_job(tmp_path)
    stale = {"min_x": -900, "min_y": -900, "max_x": 900, "max_y": 900}
    write_placement(tmp_path / "drawing.placement.json", drawing=stale)
    with pytest.raises(JobPreflightError, match="Placement report is stale"):
        run_job_preflight(hpgl, config_path=config)


def test_current_out_of_bounds_hpgl_is_rejected_even_with_pass_sidecar(tmp_path: Path):
    config, hpgl, _, _ = setup_job(tmp_path)
    hpgl.write_text("IN;PA;SP8;PU0,0;PD6000,0;SP6;PU0,0;PD100,100;SP0;", encoding="ascii")
    with pytest.raises(JobPreflightError, match="Current HP-GL fails placement validation"):
        run_job_preflight(hpgl, config_path=config)


def test_single_pen_job_does_not_require_pen_plan(tmp_path: Path):
    config = write_config(tmp_path / "vpype.toml")
    hpgl = write_hpgl(tmp_path / "drawing.hpgl", pens=(1,))
    write_placement(tmp_path / "drawing.placement.json")
    report, plan = run_job_preflight(hpgl, config_path=config)
    assert plan is None
    assert report.ready_to_send is True
    assert report.pen_plan_status == "not-required-single-pen"
