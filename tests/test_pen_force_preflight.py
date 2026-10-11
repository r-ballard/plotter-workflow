import hashlib
import json
from argparse import Namespace

import pytest

from hpgl_force import apply_force
from pen_force import parse_force
from scripts import send_hpgl
from scripts.job_preflight import (
    JobPreflightError,
    format_job_preflight,
    run_job_preflight,
)
from tests.test_job_preflight import setup_job


def force_job(tmp_path, mode="software"):
    config, hpgl, plan, placement = setup_job(tmp_path, pens=(8,))
    spec = parse_force({"mode": mode, "default_gf": 65})
    hpgl.write_text(apply_force(hpgl.read_text(), spec))
    raw = json.loads(plan.read_text())
    raw["hpgl_sha256"] = hashlib.sha256(hpgl.read_bytes()).hexdigest()
    raw["pen_force"] = {
        "spec": {"mode": mode, "default_gf": 65},
        "effective_slot_forces": [{"slot": 8, "force_gf": 65}],
    }
    plan.write_text(json.dumps(raw))
    return config, hpgl, plan, placement


@pytest.mark.parametrize(
    "mode,status",
    [
        ("software", "operator-confirmed-auto-off"),
        ("panel", "operator-confirmed-panel-settings-auto-on"),
    ],
)
def test_single_pen_force_requires_explicit_setup_acknowledgement(tmp_path, mode, status):
    config, hpgl, _, _ = force_job(tmp_path, mode)
    report, plan = run_job_preflight(hpgl, config_path=config)
    assert not report.ready_to_send
    assert report.force_confirmation_status == "required-before-send"
    assert "65 gf" in format_job_preflight(report, plan)
    with pytest.raises(JobPreflightError, match="confirm-pen-plan"):
        run_job_preflight(hpgl, config_path=config, require_operator_confirmation=True)
    report, _ = run_job_preflight(hpgl, config_path=config, operator_confirmed=True)
    assert report.ready_to_send and report.force_confirmation_status == status
    assert report.to_dict()["pen_force"]["effective_slot_forces"] == [{"slot": 8, "force_gf": 65}]


@pytest.mark.parametrize("mode", ["software", "panel"])
@pytest.mark.parametrize("bypass", [False, True])
def test_sender_does_not_open_port_without_force_confirmation(tmp_path, monkeypatch, mode, bypass):
    config, hpgl, plan, placement = force_job(tmp_path, mode)
    monkeypatch.setattr(
        send_hpgl,
        "parse_args",
        lambda: Namespace(
            hpgl=hpgl,
            port="COM_TEST",
            list_ports=False,
            chunk_size=1024,
            inter_chunk_delay=0,
            verbose=False,
            pen_plan=plan,
            placement_report=placement,
            vpype_config=config,
            allow_unvalidated_job=bypass,
            allow_unplanned_multipen=True,
            confirm_pen_plan=False,
        ),
    )
    monkeypatch.setattr(send_hpgl, "send_file", lambda *a, **kw: pytest.fail("port opened"))
    assert send_hpgl.main() == 1


def test_confirmed_force_job_can_reach_mock_sender(tmp_path, monkeypatch):
    config, hpgl, plan, placement = force_job(tmp_path)
    monkeypatch.setattr(
        send_hpgl,
        "parse_args",
        lambda: Namespace(
            hpgl=hpgl,
            port="COM_TEST",
            list_ports=False,
            chunk_size=1024,
            inter_chunk_delay=0,
            verbose=False,
            pen_plan=plan,
            placement_report=placement,
            vpype_config=config,
            allow_unvalidated_job=False,
            allow_unplanned_multipen=False,
            confirm_pen_plan=True,
        ),
    )
    sent = []
    monkeypatch.setattr(send_hpgl, "send_file", lambda *a, **kw: sent.append(a))
    assert send_hpgl.main() == 0 and len(sent) == 1


def test_updated_hash_cannot_hide_incorrect_software_force(tmp_path):
    config, hpgl, plan, _ = force_job(tmp_path)
    hpgl.write_text(hpgl.read_text().replace("FS7;", "FS5;"))
    raw = json.loads(plan.read_text())
    raw["hpgl_sha256"] = hashlib.sha256(hpgl.read_bytes()).hexdigest()
    plan.write_text(json.dumps(raw))
    with pytest.raises(JobPreflightError, match="incorrect force"):
        run_job_preflight(hpgl, config_path=config, operator_confirmed=True)


def test_stale_sidecar_is_not_ignored_even_with_bypass(tmp_path, monkeypatch):
    config, hpgl, plan, placement = force_job(tmp_path)
    plan.write_text('{"schema_version":1,"kind":"resolved-dpx3300-pen-plan"}')
    monkeypatch.setattr(
        send_hpgl,
        "parse_args",
        lambda: Namespace(
            hpgl=hpgl,
            port="COM_TEST",
            list_ports=False,
            chunk_size=1024,
            inter_chunk_delay=0,
            verbose=False,
            pen_plan=plan,
            placement_report=placement,
            vpype_config=config,
            allow_unvalidated_job=True,
            allow_unplanned_multipen=True,
            confirm_pen_plan=True,
        ),
    )
    monkeypatch.setattr(send_hpgl, "send_file", lambda *a, **kw: pytest.fail("port opened"))
    assert send_hpgl.main() == 1


@pytest.mark.parametrize("mode", ["software", "panel"])
def test_hidden_force_with_updated_hash_is_rejected(tmp_path, mode):
    config, hpgl, plan, _ = force_job(tmp_path, mode)
    hpgl.write_text(hpgl.read_text().replace("PU;", "PUFS15,8;PU;", 1))
    raw = json.loads(plan.read_text())
    raw["hpgl_sha256"] = hashlib.sha256(hpgl.read_bytes()).hexdigest()
    plan.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        run_job_preflight(hpgl, config_path=config, operator_confirmed=True)
