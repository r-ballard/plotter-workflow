import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from svg_pen_contract import inspect_pen_layer_contract

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "voronoi" / "generate.py"
SVG_NS = "{http://www.w3.org/2000/svg}"


def generate(output: Path, *options: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(output), *options],
        capture_output=True, text=True, check=False,
    )


def test_clipped_voronoi_cells_partition_the_parent_without_gaps():
    spec = importlib.util.spec_from_file_location("voronoi_example", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parent = [(10.0, 10.0), (190.0, 10.0), (190.0, 190.0), (10.0, 190.0)]
    sites = [(30.0, 30.0), (150.0, 40.0), (110.0, 150.0)]
    cells = module.partition(parent, sites)
    assert len(cells) == len(sites)
    assert abs(sum(module.area(cell) for cell in cells) - module.area(parent)) < 1e-6
    assert all(10 - 1e-9 <= x <= 190 + 1e-9 and 10 - 1e-9 <= y <= 190 + 1e-9
               for cell in cells for x, y in cell)


def test_seeded_voronoi_is_reproducible_and_plotter_compatible(tmp_path: Path):
    first, second, changed = (tmp_path / name for name in ("first", "second", "changed"))
    for path, seed in ((first, "17"), (second, "17"), (changed, "18")):
        result = generate(path, "--seed", seed, "--depth", "4", "--branch", "3")
        assert result.returncode == 0, result.stderr
    expected = {"voronoi.svg", "voronoi.penplan.json", "voronoi.json"}
    assert {path.name for path in first.iterdir()} == expected
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in expected)
    assert (first / "voronoi.svg").read_bytes() != (changed / "voronoi.svg").read_bytes()
    assert inspect_pen_layer_contract(first / "voronoi.svg").pens == (1,)
    root = ET.parse(first / "voronoi.svg").getroot()
    assert root.get("viewBox") == "0 0 200 200"
    manifest = json.loads((first / "voronoi.json").read_text())
    assert manifest["algorithm"] == "recursive-clipped-voronoi"
    assert manifest["cell_count"] == 81
    assert manifest["edge_count"] > 50
    assert manifest["area_error_mm2"] < 1e-5
    assert manifest["source_pen_down_mm"] <= manifest["max_path_mm"]
    assert len(root.findall(f".//{SVG_NS}path")) == manifest["edge_count"] + 1


def test_limits_reject_output_without_overwriting(tmp_path: Path):
    output = tmp_path / "job"
    rejected = generate(output, "--max-path-mm", "10")
    assert rejected.returncode != 0
    assert not output.exists()
    assert generate(output, "--depth", "3").returncode == 0
    before = (output / "voronoi.svg").read_bytes()
    assert generate(output, "--depth", "4").returncode != 0
    assert (output / "voronoi.svg").read_bytes() == before
