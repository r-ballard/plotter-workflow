from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import cootie_impose as cootie
from imposition.source import inspect_svg_source

GENERATOR = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "generate_cootie_orientation_fixture.py"
)
CHECKER = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "check_cootie_orientation_audit.py"
)


def _load(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_fixture_uses_intrinsic_orientation_for_every_slot(tmp_path: Path) -> None:
    generator = _load(GENERATOR, "generate_cootie_orientation_fixture")
    generator.generate_fixture(tmp_path)

    manifest = json.loads((tmp_path / "cootie.json").read_text(encoding="utf-8"))
    assert len(manifest["panels"]) == 20
    assert all("rotation_degrees" not in panel for panel in manifest["panels"])

    entries = cootie.load_manifest(
        tmp_path,
        tmp_path / "cootie.json",
        default_fit="contain",
        default_margin_mm=3.0,
    )
    assert [entry.slot for entry in entries] == list(cootie.EXPECTED_SLOTS)
    assert all(entry.orientation_policy == "intrinsic-up-vector" for entry in entries)
    assert all(entry.rotation_override_degrees is None for entry in entries)

    triangles = 0
    for entry in entries:
        canvas = inspect_svg_source(entry.source)
        assert canvas is not None
        assert canvas.up_vector == (0.0, -1.0)
        family = entry.slot.split("-", 1)[0]
        if family in {"selector", "reveal"}:
            triangles += 1
            assert canvas.shape == "triangle"
            assert canvas.up_anchor == "vertex:0"
        else:
            assert canvas.shape == "square"
            assert canvas.up_anchor == "edge:0"
        assert "<text" not in entry.source.read_text(encoding="utf-8")
    assert triangles == 16


def test_expected_orientation_matches_resolved_manifest(tmp_path: Path) -> None:
    generator = _load(GENERATOR, "generate_cootie_orientation_fixture_expected")
    generator.generate_fixture(tmp_path)
    expected = json.loads(
        (tmp_path / "expected_orientation.json").read_text(encoding="utf-8")
    )
    entries = cootie.load_manifest(
        tmp_path,
        tmp_path / "cootie.json",
        default_fit="contain",
        default_margin_mm=3.0,
    )
    by_slot = {entry.slot: entry for entry in entries}

    for item in expected["slots"]:
        entry = by_slot[item["slot"]]
        assert item["orientation_policy"] == entry.orientation_policy
        assert item["target_up_vector"] == list(entry.target_up_vector)
        assert item["resolved_rotation_degrees"] == entry.rotation_degrees


def test_audit_checker_accepts_generated_semantic_orientation(tmp_path: Path) -> None:
    generator = _load(GENERATOR, "generate_cootie_orientation_fixture_audit")
    checker = _load(CHECKER, "check_cootie_orientation_audit")
    generator.generate_fixture(tmp_path)
    entries = cootie.load_manifest(
        tmp_path,
        tmp_path / "cootie.json",
        default_fit="contain",
        default_margin_mm=3.0,
    )

    panels = []
    for entry in entries:
        canvas = entry.source_intrinsic_canvas
        assert canvas is not None
        panels.append(
            {
                "slot": entry.slot,
                "orientation_policy": entry.orientation_policy,
                "rotation_override_degrees": entry.rotation_override_degrees,
                "source_intrinsic_canvas": {
                    "shape": canvas.shape,
                    "up_vector": list(canvas.up_vector),
                },
                "target_up_vector": list(entry.target_up_vector),
            }
        )

    summary = checker.validate_audit_payload(
        {"layout": "cootie_catcher", "panels": panels}
    )
    assert summary == {"panels": 20, "triangular_panels": 16}


def test_audit_checker_rejects_legacy_fallback(tmp_path: Path) -> None:
    generator = _load(GENERATOR, "generate_cootie_orientation_fixture_bad")
    checker = _load(CHECKER, "check_cootie_orientation_audit_bad")
    generator.generate_fixture(tmp_path)
    entries = cootie.load_manifest(
        tmp_path,
        tmp_path / "cootie.json",
        default_fit="contain",
        default_margin_mm=3.0,
    )
    panels = []
    for entry in entries:
        canvas = entry.source_intrinsic_canvas
        assert canvas is not None
        panels.append(
            {
                "slot": entry.slot,
                "orientation_policy": entry.orientation_policy,
                "rotation_override_degrees": entry.rotation_override_degrees,
                "source_intrinsic_canvas": {
                    "shape": canvas.shape,
                    "up_vector": list(canvas.up_vector),
                },
                "target_up_vector": list(entry.target_up_vector),
            }
        )
    panels[0]["orientation_policy"] = "legacy-default"

    try:
        checker.validate_audit_payload({"layout": "cootie_catcher", "panels": panels})
    except checker.OrientationAuditError as exc:
        assert "intrinsic-up-vector" in str(exc)
    else:
        raise AssertionError("legacy fallback should make the diagnostic audit fail")

def test_generator_runs_via_documented_direct_script_command(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--output-dir",
            str(tmp_path),
            "--overwrite",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "cootie.json").is_file()
    assert "Generated cootie orientation fixture" in result.stdout


def test_checker_runs_via_documented_direct_script_command(tmp_path: Path) -> None:
    generator = _load(GENERATOR, "generate_cootie_orientation_fixture_direct_checker")
    generator.generate_fixture(tmp_path)
    entries = cootie.load_manifest(
        tmp_path,
        tmp_path / "cootie.json",
        default_fit="contain",
        default_margin_mm=3.0,
    )
    panels = []
    for entry in entries:
        canvas = entry.source_intrinsic_canvas
        assert canvas is not None
        panels.append(
            {
                "slot": entry.slot,
                "orientation_policy": entry.orientation_policy,
                "rotation_override_degrees": entry.rotation_override_degrees,
                "source_intrinsic_canvas": {
                    "shape": canvas.shape,
                    "up_vector": list(canvas.up_vector),
                },
                "target_up_vector": list(entry.target_up_vector),
            }
        )

    sidecar = tmp_path / "direct.imposition.json"
    sidecar.write_text(
        json.dumps({"layout": "cootie_catcher", "panels": panels}),
        encoding="utf-8",
    )
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(sidecar)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "PASS: semantic orientation is active for 20 panels (16 triangular)." in result.stdout

