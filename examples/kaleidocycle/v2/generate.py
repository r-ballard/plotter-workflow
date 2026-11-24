import copy
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from imposition.artwork_layout import MM_TO_PX
from imposition.objects.kaleidocycle import Kaleidocycle
from scripts import booklet_impose as booklet

ROOT = Path("output/six-cell-plot-pack-v2-2d").resolve()
ROOT.mkdir(exist_ok=True)
VIZ = Path("../../../viz_virtualserver").resolve()
PYTHON = VIZ / ".venv/Scripts/python.exe"
NS = "{http://www.w3.org/2000/svg}"
obj = Kaleidocycle(6)
w, h = 161.291, 65.3
styles = ["triangular-vortex", "flowing-honeycomb", "irregular-connections"]
catalog = [
    {"id": "sticks", "ordinal": 1, "label": "Bonds"},
    {"id": "balls", "ordinal": 2, "label": "Nodes"},
]
base = Path("output/six-cell-plot-pack")
sheetdir = ROOT / "sheet-proof/sheet-001/front"
sheetdir.mkdir(parents=True, exist_ok=True)
oldroot = ET.parse(base / "sheet-proof/sheet-001/front/design.svg").getroot()
root = ET.Element(oldroot.tag, oldroot.attrib)
groups = {}
for layer in catalog:
    groups[layer["id"]] = ET.SubElement(
        root,
        NS + "g",
        {
            "data-viz-layer-id": layer["id"],
            "data-viz-layer-ordinal": str(layer["ordinal"]),
            "data-viz-layer-label": layer["label"],
        },
    )
records = []
for index, style in enumerate(styles):
    folder = ROOT / style
    folder.mkdir(exist_ok=True)
    polygons = {s.slot_id: [(x * w, y * h) for x, y in s.polygon] for s in obj.slots}
    params = {
        "rows": 7,
        "columns": 17,
        "lattice": "triangular",
        "ball_radius_ratio": 0.23,
        "ball_size_mode": "seeded",
        "ball_radius_min_ratio": 0.09,
        "curve_tolerance": 0.05,
        "coordinate_frame": "composition",
    }
    if index == 0:
        params.update(
            deformation={
                "type": "flow",
                "distance": 1.0,
                "step_size": 0.05,
                "field": {"type": "vortex", "center_x": 0.4, "center_y": 0.55},
            },
            jitter=0.12,
        )
    elif index == 1:
        params.pop("rows")
        params.pop("columns")
        params.update(
            lattice="honeycomb",
            honeycomb_rows=4,
            honeycomb_columns=10,
            deformation={
                "type": "flow",
                "distance": 0.8,
                "step_size": 0.05,
                "field": {"type": "vortex", "center_x": 0.65, "center_y": 0.4},
            },
            jitter=0.12,
        )
    else:
        params.update(
            jitter=0.45,
            attraction=0.4,
            connection_probability=0.55,
            connection_span=3.0,
            max_extra_degree=3,
            exclude_crossing_connections=True,
        )
    job = {
        "schema_version": 1,
        "seed": [137, 593, 1031][index],
        "domains": [
            {"id": key, "vertices": points} for key, points in polygons.items()
        ],
        "composition_transforms": [
            {"domain_id": key, "matrix": [1, 0, 0, 1, 0, 0]} for key in polygons
        ],
        "passes": [
            {
                "id": "network",
                "algorithm": "ball-stick",
                "target_domain_ids": list(polygons),
                "parameters": params,
                "logical_layers": [
                    {"id": "sticks", "label": "Bonds"},
                    {"id": "balls", "label": "Nodes"},
                ],
            }
        ],
    }
    request = folder / "artwork-job.json"
    request.write_text(json.dumps(job, indent=2))
    subprocess.run(
        [
            str(PYTHON),
            "-B",
            "-m",
            "viz_virtualserver.cli.domain_bundle",
            str(request),
            "--output-dir",
            str(folder / "producer"),
        ],
        cwd=VIZ,
        check=True,
    )
    # A single producer composition targets all 24 triangles in one invocation.
    entries = []
    for key in polygons:
        entries.append(
            type("Entry", (), {"source": folder / "producer/surfaces" / f"{key}.svg"})()
        )
    mode, manifest = booklet._inspect_sources(entries)
    assert mode == "neutral" and len(manifest.surfaces) == 24
    for key, entry in zip(polygons, entries):
        points = polygons[key]
        x0 = min(p[0] for p in points)
        y0 = min(p[1] for p in points)
        for layer_id, geometry, width, height in booklet._neutral_fragments(
            entry.source, len(records) + 1, 0.05
        ):
            geometry.scale(MM_TO_PX)
            geometry.translate(
                (5 + x0) * MM_TO_PX, (5 + index * (h + 5) + y0) * MM_TO_PX
            )
            wrapper = ET.SubElement(
                groups[layer_id],
                NS + "g",
                {"data-imposed-slot": key, "data-sample": style},
            )
            wrapper.append(geometry.svg)
        records.append(
            {
                "sample": style,
                "slot": key,
                "polygon_mm": [(5 + x, 5 + index * (h + 5) + y) for x, y in points],
                "source_sha256": hashlib.sha256(entry.source.read_bytes()).hexdigest(),
            }
        )
for g in oldroot:
    if g.get("data-viz-layer-id") in ("sheet-cut-guides", "sheet-fold-guides"):
        root.append(copy.deepcopy(g))
ET.ElementTree(root).write(
    sheetdir / "design.svg", encoding="utf-8", xml_declaration=True
)
manifest = json.loads((base / "sheet-proof/sheet-001/front/design.json").read_text())
digest = hashlib.sha256((sheetdir / "design.svg").read_bytes()).hexdigest()
manifest["design_sha256"] = digest
manifest["surfaces"][0]["sha256"] = digest
manifest.pop("instances", None)
manifest["provenance"] = {
    "generation": "one shared master per net, partitioned into 24 intrinsic surfaces",
    "samples": styles,
}
(sheetdir / "design.json").write_text(json.dumps(manifest, indent=2))
audit = json.loads(
    (base / "sheet-proof/sheet-001/front/design.imposition.json").read_text()
)
audit.pop("instances", None)
audit["panels"] = records
audit["generation"] = "single-master-per-net/v2"
audit["source_manifest_sha256"] = hashlib.sha256(
    (sheetdir / "design.json").read_bytes()
).hexdigest()
(sheetdir / "design.imposition.json").write_text(json.dumps(audit, indent=2))
shutil.copyfile(
    base / "sheet-proof/sheet-001/front/design.penplan.json",
    sheetdir / "design.penplan.json",
)
shutil.copytree(base / "diagnostics", ROOT / "diagnostics")
shutil.copytree(base / "diagnostic-sheet", ROOT / "diagnostic-sheet")
(ROOT / "samples.json").write_text(
    json.dumps(
        {
            "version": 2,
            "styles": styles,
            "master_count": 3,
            "facets_per_master": 24,
            "tetrahedron_count": 6,
            "net_mm": [w, h],
            "diagnostics": "copied unchanged from v1",
            "composition": "one image across the flat net per object",
        },
        indent=2,
    )
)
print(ROOT)
