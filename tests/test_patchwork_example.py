import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from svg_pen_contract import inspect_pen_layer_contract

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "patchwork" / "generate.py"
SVG_NS = "{http://www.w3.org/2000/svg}"


def generate(output: Path, *options: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(output), *options],
        capture_output=True, text=True, check=False,
    )


def test_seeded_patchwork_is_reproducible_and_matches_pen_contract(tmp_path: Path):
    first, second, changed = (tmp_path / name for name in ("first", "second", "changed"))
    for path, seed in ((first, "17"), (second, "17"), (changed, "18")):
        result = generate(path, "--seed", seed, "--points", "120", "--clusters", "3", "--depth", "1")
        assert result.returncode == 0, result.stderr

    names = {"patchwork.svg", "patchwork.penplan.json", "patchwork.json"}
    assert {path.name for path in first.iterdir()} == names
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in names)
    assert (first / "patchwork.svg").read_bytes() != (changed / "patchwork.svg").read_bytes()
    assert inspect_pen_layer_contract(first / "patchwork.svg").pens == (1,)

    root = ET.parse(first / "patchwork.svg").getroot()
    paths = root.findall(f".//{SVG_NS}path")
    assert root.get("viewBox") == "0 0 200 200"
    assert len(paths) > 10
    assert all(path.get("d", "").startswith("M ") and path.get("d", "").endswith(" Z") for path in paths)
    plan = json.loads((first / "patchwork.penplan.json").read_text())
    assert plan["policy"] == "preserve"
    assert plan["slots"][0]["slot"] == 1
    manifest = json.loads((first / "patchwork.json").read_text())
    assert manifest["algorithm"] == "seeded-cluster-convex-hull"
    assert manifest["seed"] == 17
    assert manifest["depth"] == 1
    assert manifest["polygon_count"] == len(paths)
    assert 0 < manifest["pen_down_mm"] <= manifest["max_path_mm"]
    assert len(manifest["svg_sha256"]) == 64


def test_recursion_adds_local_polygons_and_path_limit_prevents_outputs(tmp_path: Path):
    shallow, deep, limited = (tmp_path / name for name in ("shallow", "deep", "limited"))
    options = ("--seed", "17", "--points", "120", "--clusters", "3")
    assert generate(shallow, *options, "--depth", "0").returncode == 0
    assert generate(deep, *options, "--depth", "1").returncode == 0
    shallow_data = json.loads((shallow / "patchwork.json").read_text())
    deep_data = json.loads((deep / "patchwork.json").read_text())
    assert deep_data["polygon_count"] > shallow_data["polygon_count"]
    assert deep_data["pen_down_mm"] > shallow_data["pen_down_mm"]

    rejected = generate(limited, *options, "--max-path-mm", "10")
    assert rejected.returncode != 0
    assert not limited.exists()
    before = (deep / "patchwork.svg").read_bytes()
    assert generate(deep, *options, "--depth", "1").returncode != 0
    assert (deep / "patchwork.svg").read_bytes() == before
