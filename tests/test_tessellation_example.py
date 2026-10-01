import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from svg_pen_contract import inspect_pen_layer_contract

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "tessellation" / "generate.py"


def run_generator(output_dir: Path, seed: int = 17, depth: int = 3, *extra: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(output_dir),
         "--seed", str(seed), "--depth", str(depth), *extra],
        capture_output=True, text=True, check=False,
    )


def test_seeded_generator_is_reproducible_and_matches_pen_contract(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    third = tmp_path / "third"
    assert run_generator(first).returncode == 0
    assert run_generator(second).returncode == 0
    assert run_generator(third, seed=18).returncode == 0

    expected = {"tessellation.svg", "tessellation.penplan.json", "tessellation.json"}
    assert {p.name for p in first.iterdir()} == expected
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in expected)
    assert (first / "tessellation.svg").read_bytes() != (third / "tessellation.svg").read_bytes()

    svg = first / "tessellation.svg"
    assert inspect_pen_layer_contract(svg).pens == (1,)
    root = ET.parse(svg).getroot()
    assert root.get("viewBox") == "0 0 200 200"
    assert len(root.findall(".//{http://www.w3.org/2000/svg}path")) > 20
    plan = json.loads((first / "tessellation.penplan.json").read_text())
    assert plan["policy"] == "preserve"
    assert plan["slots"][0]["slot"] == 1
    manifest = json.loads((first / "tessellation.json").read_text())
    assert manifest["seed"] == 17
    assert manifest["depth"] == 3
    assert manifest["algorithm"] == "seeded-delaunay-triangulation"
    assert manifest["point_count"] == 200
    assert manifest["edge_count"] > 300
    assert "M 100.000 100.000" not in svg.read_text()
    assert len(manifest["svg_sha256"]) == 64


def test_generator_preserves_existing_files_without_overwrite(tmp_path: Path):
    assert run_generator(tmp_path).returncode == 0
    svg = tmp_path / "tessellation.svg"
    before = svg.read_bytes()
    result = run_generator(tmp_path, seed=22)
    assert result.returncode != 0
    assert svg.read_bytes() == before


def test_point_count_controls_density_without_a_fixed_center(tmp_path: Path):
    sparse = tmp_path / "sparse"
    dense = tmp_path / "dense"
    assert run_generator(sparse, 17, 3, "--points", "80").returncode != 0
    for output_dir, count in ((sparse, 80), (dense, 200)):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--output-dir", str(output_dir),
             "--seed", "17", "--points", str(count)],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
    sparse_manifest = json.loads((sparse / "tessellation.json").read_text())
    dense_manifest = json.loads((dense / "tessellation.json").read_text())
    assert sparse_manifest["point_count"] == 80
    assert dense_manifest["edge_count"] > sparse_manifest["edge_count"]
