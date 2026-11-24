#!/usr/bin/env python3
"""Create vector-only identification and assembled-seam physical fold fixtures."""

import argparse
import copy
import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imposition.artwork_export import SVG_NS, write_layout_export
from imposition.artwork_io import atomic_directory, json_bytes, read_json
from imposition.artwork_layout import affine
from imposition.artwork_return import prepare_layout_assets
from imposition.kaleidocycle_artwork import resolve_kaleidocycle_state
from imposition.kaleidocycle_impose import write_kaleidocycle
from scripts.generate_cootie_orientation_fixture import _glyph_path

NS = "{" + SVG_NS + "}"


def _path(parent, commands, role):
    return ET.SubElement(
        parent,
        NS + "path",
        {"d": commands, "data-viz-feature-role": "diagnostic-" + role},
    )


def _label(parent, label, x, y, scale, role):
    commands = " ".join(
        _glyph_path(char, x + i * 12 * scale, y, scale) for i, char in enumerate(label)
    )
    return _path(parent, commands, role)


def _local_marks(panel, state, column):
    group = ET.Element(NS + "g")
    polygon = panel.crop_polygon
    cx = sum(x for x, y in polygon) / 3
    cy = sum(y for x, y in polygon) / 3
    inset = [(cx + (x - cx) * 0.88, cy + (y - cy) * 0.88) for x, y in polygon]
    _path(group, "M " + " L ".join(f"{x},{y}" for x, y in inset) + " Z", "inset-frame")
    # Upright arrow and R on the source-right side distinguish handedness.
    _path(group, f"M {cx},{cy - 4} L {cx},{cy - 27} m -5,7 l 5,-7 l 5,7", "up")
    _path(group, f"M {cx + 4},{cy - 4} h 17 m -6,-4 l 6,4 l -6,4", "right")
    _label(group, "R", cx + 15, cy + 2, 0.45, "right-label")
    _label(group, f"{column}{state}", cx - 10, cy + 10, 0.75, "panel-id")
    # Separate one/two/three edge ticks and vertex A/B/C labels.
    for i, (x, y) in enumerate(polygon):
        _label(
            group,
            "ABC"[i],
            cx + (x - cx) * 0.65 - 2,
            cy + (y - cy) * 0.65 - 3,
            0.38,
            f"vertex-{i}",
        )
        u, v = polygon[(i + 1) % 3]
        mx, my = (x + u) / 2, (y + v) / 2
        mx, my = cx + (mx - cx) * 0.84, cy + (my - cy) * 0.84
        for tick in range(i + 1):
            _path(group, f"M {mx - 3 + tick * 3},{my - 2} l 0,4", f"edge-{i}")
    return group


def _state_marks(layout):
    group = ET.Element(NS + "g")
    # Shared off-center lines and a large up/right frame cross multiple seams.
    _path(
        group,
        "M 60,176 H 452 M 60,336 H 452 M 176,60 V 452 M 336,60 V 452",
        "shared-lines",
    )
    _path(
        group,
        "M 256,310 V 90 M 236,120 L 256,90 L 276,120 "
        "M 256,256 H 430 M 408,242 L 430,256 L 408,270",
        "assembled-up-right",
    )
    _label(group, layout.settings["state"], 225, 360, 3, "state-id")
    _label(group, "R", 420, 278, 1.4, "assembled-right")
    for i, panel in enumerate(layout.panels, 1):
        points = [affine(panel.assembled_matrix, p) for p in panel.crop_polygon]
        x = sum(q[0] for q in points) / 3
        y = sum(q[1] for q in points) / 3
        _label(group, str(i), x - 6, y - 10, 1.2, "assembled-column")
    return group


def _inverse(matrix):
    a, b, c, d, e, f = matrix
    det = a * d - b * c
    return (
        d / det,
        -b / det,
        -c / det,
        a / det,
        (c * f - d * e) / det,
        (b * e - a * f) / det,
    )


def _source(panel, artwork, *, matrix=None):
    polygon = panel.crop_polygon
    root = ET.Element(
        NS + "svg",
        {
            "width": "128",
            "height": "128",
            "viewBox": "0 0 128 128",
            "data-viz-layer-contract": "viz-logical-layers/v1",
            "data-viz-canvas-version": "1",
            "data-viz-canvas-shape": "polygon",
            "data-viz-canvas-coordinate-system": "svg-y-down",
            "data-viz-canvas-up-anchor": "edge:0",
            "data-viz-canvas-up-vector": "0,-1",
            "data-viz-canvas-polygon": " ".join(f"{x},{y}" for x, y in polygon),
            "data-viz-canvas-clip-id": "triangle",
        },
    )
    clip = ET.SubElement(
        ET.SubElement(root, NS + "defs"),
        NS + "clipPath",
        {"id": "triangle", "clipPathUnits": "userSpaceOnUse"},
    )
    ET.SubElement(
        clip, NS + "polygon", {"points": " ".join(f"{x},{y}" for x, y in polygon)}
    )
    layer = ET.SubElement(
        root,
        NS + "g",
        {
            "id": "diagnostic",
            "data-viz-layer-id": "diagnostic",
            "data-viz-layer-ordinal": "1",
            "data-viz-layer-label": "Fold diagnostics",
            "fill": "none",
            "stroke": "black",
            "stroke-width": ".8",
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
            "clip-path": "url(#triangle)",
        },
    )
    content = copy.deepcopy(artwork)
    if matrix is not None:
        content.set("transform", "matrix(" + " ".join(str(v) for v in matrix) + ")")
    for i, path in enumerate(content.iter(NS + "path")):
        path.set("data-viz-path-id", f"{panel.panel_id}-diagnostic-{i}")
        path.set("data-viz-domain-id", panel.panel_id)
    layer.append(content)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _reference(layout, artwork):
    root = ET.Element(
        NS + "svg",
        {
            "width": "180mm",
            "height": "180mm",
            "viewBox": "-12 -12 536 536",
            "data-diagnostic-status": "provisional-declared-view",
        },
    )
    for panel in layout.panels:
        group = ET.SubElement(root, NS + "g", {"data-diagnostic-panel": panel.panel_id})
        points = [affine(panel.assembled_matrix, p) for p in panel.crop_polygon]
        ET.SubElement(
            group,
            NS + "polygon",
            {
                "points": " ".join(f"{x},{y}" for x, y in points),
                "fill": "none",
                "stroke": "#aaa",
                "stroke-width": ".6",
            },
        )
    wrapper = ET.SubElement(
        root, NS + "g", {"fill": "none", "stroke": "black", "stroke-width": "1.2"}
    )
    wrapper.append(copy.deepcopy(artwork))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def generate_fixture(output_dir, *, width_mm=240, tetrahedron_count=6, overwrite=False):
    layouts = [
        resolve_kaleidocycle_state(
            s, width_mm=width_mm, tetrahedron_count=tetrahedron_count
        )
        for s in "ABCD"
    ]
    # The shared exporter uses this recipe only as a validated transport envelope.
    # No Truchet algorithm runs: fixture provenance explicitly records hand-drawn diagnostics.
    template = {
        "schema_version": 1,
        "seed": 0,
        "domains": [],
        "passes": [
            {
                "id": "diagnostic",
                "algorithm": "truchet",
                "target_domain_ids": [],
                "parameters": {"curve_layer_ids": ["diagnostic"], "region_fills": {}},
                "logical_layers": [{"id": "diagnostic", "label": "Fold diagnostics"}],
            }
        ],
    }
    layers = [{"id": "diagnostic", "ordinal": 1, "label": "Fold diagnostics"}]

    def write(stage):
        for mode in ("panel-orientation", "state-continuity"):
            folder = stage / mode
            config = {
                "schema_version": 1,
                "width_mm": width_mm,
                "tetrahedron_count": tetrahedron_count,
                "sheet_size": "letter",
                "states": {},
            }
            for layout in layouts:
                state = layout.settings["state"]
                export = write_layout_export(
                    layout, template, folder / state / "export"
                )
                producer = folder / state / "fixture-source"
                (producer / "surfaces").mkdir(parents=True)
                whole = _state_marks(layout)
                inventory = []
                for column, panel in enumerate(layout.panels, 1):
                    artwork = (
                        _local_marks(panel, state, column)
                        if mode == "panel-orientation"
                        else whole
                    )
                    data = _source(
                        panel,
                        artwork,
                        matrix=None
                        if mode == "panel-orientation"
                        else _inverse(panel.assembled_matrix),
                    )
                    relative = f"surfaces/{panel.panel_id}.svg"
                    (producer / relative).write_bytes(data)
                    inventory.append(
                        {
                            "surface_id": panel.panel_id,
                            "domain_id": panel.panel_id,
                            "path": relative,
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "logical_layer_ids": ["diagnostic"],
                        }
                    )
                request = read_json(export / "artwork-job.json")
                (producer / "design.json").write_bytes(
                    json_bytes(
                        {
                            **request,
                            "fixture_generator": "kaleidocycle-orientation/v1",
                            "fixture_mode": mode,
                            "algorithm_executed": False,
                            "logical_layer_contract": "viz-logical-layers/v1",
                            "logical_layers": layers,
                            "surfaces": inventory,
                        }
                    )
                )
                prepare_layout_assets(
                    producer_bundle=producer,
                    handoff=export / "layout-handoff.json",
                    output_dir=folder / state / "assets",
                )
                config["states"][state] = f"{state}/assets"
                if mode == "state-continuity":
                    (folder / f"expected-{state}.svg").write_bytes(
                        _reference(layout, whole)
                    )
            config_path = folder / "kaleidocycle.json"
            config_path.write_bytes(json_bytes(config))
            write_kaleidocycle(config_path, folder / "sheet")
            construction = ET.parse(folder / "sheet/guides.svg").getroot()
            for group in list(construction):
                if group.get("data-guide-kind") not in ("cut", "fold"):
                    construction.remove(group)
            construction.set("data-imposition-artifact", "cut-fold-construction-proof")
            (folder / "sheet/construction.svg").write_bytes(
                ET.tostring(construction, encoding="utf-8", xml_declaration=True)
            )
            (folder / "sheet/construction.penplan.json").write_bytes(
                json_bytes(
                    {
                        "schema_version": 3,
                        "policy": "compact",
                        "slots": [
                            {
                                "slot": 1,
                                "tool": "Diagnostic marking pen",
                                "label": "Cut/fold reference ink",
                            }
                        ],
                        "notes": "Intended marking tool only; verify the pen loaded in slot 1. No cutting or scoring tool is commanded.",
                    }
                )
            )
            (folder / "sheet/design.penplan.json").write_bytes(
                json_bytes(
                    {
                        "schema_version": 3,
                        "policy": "explicit",
                        "passes": [
                            {
                                "id": "diagnostic",
                                "assignments": [
                                    {"layer_ids": ["diagnostic"], "physical_slot": 1}
                                ],
                            }
                        ],
                        "omitted_layers": [],
                        "repeated_layers": [],
                    }
                )
            )
        observations = {
            "schema_version": 1,
            "tetrahedron_count": tetrahedron_count,
            "validation_status": "not-tested",
            "note": "Record observations, not corrections inferred from the provisional profiles.",
            "panels": [
                {
                    "slot": p.panel_id,
                    "observed_state": None,
                    "observed_top_vertex_or_edge": None,
                    "observed_right_vertex_or_edge": None,
                    "neighbor_left": None,
                    "neighbor_right": None,
                    "notes": "",
                }
                for l in layouts
                for p in l.panels
            ],
        }
        (stage / "physical_validation.template.json").write_bytes(
            json_bytes(observations)
        )
        (stage / "validation.json").write_bytes(
            json_bytes(
                {
                    "schema_version": 1,
                    "fixture": "kaleidocycle-orientation/v1",
                    "width_mm": width_mm,
                    "tetrahedron_count": tetrahedron_count,
                    "status": "provisional",
                    "states": [
                        {
                            "state": l.settings["state"],
                            "profile_id": l.profile_id,
                            "adjacency": l.settings["adjacency"],
                        }
                        for l in layouts
                    ],
                }
            )
        )

    return atomic_directory(output_dir, write, overwrite=overwrite)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/hardware-acceptance/kaleidocycle"),
    )
    parser.add_argument("--width-mm", type=float, default=240)
    parser.add_argument("--tetrahedron-count", type=int, default=6)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = generate_fixture(
            args.output_dir,
            width_mm=args.width_mm,
            tetrahedron_count=args.tetrahedron_count,
            overwrite=args.overwrite,
        )
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
