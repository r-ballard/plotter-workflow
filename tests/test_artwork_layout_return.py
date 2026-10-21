import hashlib, json, xml.etree.ElementTree as E
import pytest
from imposition.artwork_layout import resolve_booklet_spread, bounds
from imposition.artwork_export import write_layout_export, SVG_NS
from imposition.artwork_io import json_bytes
from tests.test_artwork_layout_export import template
from logical_layer_contract import (
    load_logical_layer_manifest,
    validate_surface_against_manifest,
)
from imposition.source import inspect_svg_source


def producer_fixture(tmp_path, blank=False, layout=None):
    layout = layout or resolve_booklet_spread(
        sheet_size="letter", pages=(8, 1), margin_mm=3.0, gutter_mm=2.0
    )
    export = tmp_path / "export"
    write_layout_export(layout, template(), export)
    request = json.loads((export / "artwork-job.json").read_text())
    bundle = tmp_path / "producer"
    (bundle / "surfaces").mkdir(parents=True)
    records = []
    for panel in layout.panels:
        x0, y0, x1, y1 = bounds(panel.crop_polygon)
        w = x1 - x0
        h = y1 - y0
        root = E.Element(
            f"{{{SVG_NS}}}svg",
            {
                "viewBox": f"0 0 {w} {h}",
                "width": str(w),
                "height": str(h),
                "data-viz-layer-contract": "viz-logical-layers/v1",
                "data-viz-canvas-version": "1",
                "data-viz-canvas-shape": "polygon",
                "data-viz-canvas-coordinate-system": "svg-y-down",
                "data-viz-canvas-up-anchor": "edge:0",
                "data-viz-canvas-up-vector": "0,-1",
                "data-viz-canvas-polygon": f"0,0 {w},0 {w},{h} 0,{h}",
                "data-viz-canvas-clip-id": "crop",
            },
        )
        clip = E.SubElement(
            E.SubElement(root, f"{{{SVG_NS}}}defs"),
            f"{{{SVG_NS}}}clipPath",
            {"id": "crop"},
        )
        E.SubElement(
            clip, f"{{{SVG_NS}}}rect", dict(x="0", y="0", width=str(w), height=str(h))
        )
        if not blank:
            g = E.SubElement(
                root,
                f"{{{SVG_NS}}}g",
                {
                    "id": "layer",
                    "data-viz-layer-id": "curve",
                    "data-viz-layer-ordinal": "1",
                    "data-viz-layer-label": "curve",
                    "clip-path": "url(#crop)",
                    "fill": "none",
                    "stroke": "black",
                },
            )
            E.SubElement(
                g,
                f"{{{SVG_NS}}}path",
                {
                    "d": "M 1 2 L 3 4",
                    "data-viz-path-id": panel.panel_id + ":stroke",
                    "data-viz-domain-id": panel.panel_id,
                    "data-viz-feature-role": "truchet-curve",
                },
            )
        path = bundle / "surfaces" / (panel.panel_id + ".svg")
        path.write_bytes(E.tostring(root))
        records.append(
            dict(
                surface_id=panel.panel_id,
                domain_id=panel.panel_id,
                path="surfaces/" + path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                logical_layer_ids=[] if blank else ["curve"],
            )
        )
    audit = {
        **request,
        "logical_layer_contract": "viz-logical-layers/v1",
        "logical_layers": [
            dict(id="curve", ordinal=1, label="curve"),
            dict(id="fill", ordinal=2, label="fill"),
        ],
        "surfaces": records,
    }
    (bundle / "design.json").write_bytes(json_bytes(audit))
    return layout, export, bundle


@pytest.mark.parametrize("blank", [False, True])
def test_restore_rebased_crops_without_refit(tmp_path, blank):
    from imposition.artwork_return import prepare_layout_assets

    layout, export, bundle = producer_fixture(tmp_path, blank)
    before = {
        p.relative_to(bundle): p.read_bytes() for p in bundle.rglob("*") if p.is_file()
    }
    out = tmp_path / "returned"
    prepare_layout_assets(
        producer_bundle=bundle, handoff=export / "layout-handoff.json", output_dir=out
    )
    manifest = load_logical_layer_manifest(out / "design.json")
    for panel in layout.panels:
        path = out / "surfaces" / (panel.panel_id + ".svg")
        validate_surface_against_manifest(path, manifest)
        assert inspect_svg_source(path).polygon == panel.canvas_polygon
        root = E.parse(path).getroot()
        W = panel.canvas_polygon[2][0]
        H = panel.canvas_polygon[2][1]
        assert tuple(map(float, root.get("viewBox").split())) == pytest.approx(
            (0, 0, W, H)
        )
        if not blank:
            group = root.find(f"{{{SVG_NS}}}g")
            translation = group.find(f"{{{SVG_NS}}}g")
            x, y = bounds(panel.crop_polygon)[:2]
            assert tuple(
                map(float, translation.get("transform")[10:-1].split(","))
            ) == pytest.approx((x, y))
            assert translation.find(f"{{{SVG_NS}}}g").get("clip-path") == "url(#crop)"
            assert (
                next(root.iter(f"{{{SVG_NS}}}path")).get("data-viz-path-id")
                == panel.panel_id + ":stroke"
            )
    assert before == {
        p.relative_to(bundle): p.read_bytes() for p in bundle.rglob("*") if p.is_file()
    }
    assert (out / "producer-design.json").read_bytes() == (
        bundle / "design.json"
    ).read_bytes()


def test_derivative_hashes_and_failure_are_honest(tmp_path):
    from imposition.artwork_return import prepare_layout_assets

    _, export, bundle = producer_fixture(tmp_path)
    out = tmp_path / "returned"
    prepare_layout_assets(
        producer_bundle=bundle, handoff=export / "layout-handoff.json", output_dir=out
    )
    before = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    surface = bundle / "surfaces/page-8.svg"
    surface.write_bytes(surface.read_bytes() + b" ")
    with pytest.raises(ValueError):
        prepare_layout_assets(
            producer_bundle=bundle,
            handoff=export / "layout-handoff.json",
            output_dir=out,
            overwrite=True,
        )
    assert before == {
        p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }
    with pytest.raises(ValueError):
        prepare_layout_assets(
            producer_bundle=bundle,
            handoff=export / "layout-handoff.json",
            output_dir=bundle,
            overwrite=True,
        )


def test_nonzero_canvas_origin_and_reflected_profile(tmp_path):
    from imposition.artwork_layout import ArtworkLayout, PanelLayout, rect
    from imposition.artwork_return import prepare_layout_assets

    panel = PanelLayout(
        "page-8",
        rect(-10.0, -20.0, 200.0, 300.0),
        rect(-5.0, -15.0, 190.0, 290.0),
        (-1.0, 0.0, 0.0, 1.0, 200.0, 20.0),
        dict(kind="booklet-page", page=8),
    )
    layout = ArtworkLayout(
        "offset-test",
        "svg-px",
        (0.0, 0.0, 210.0, 320.0),
        (panel,),
        "provisional",
        dict(layout="booklet-spread"),
    )
    _, export, bundle = producer_fixture(tmp_path, layout=layout)
    out = tmp_path / "returned"
    prepare_layout_assets(
        producer_bundle=bundle, handoff=export / "layout-handoff.json", output_dir=out
    )
    assert (
        inspect_svg_source(out / "surfaces/page-8.svg").polygon == panel.canvas_polygon
    )


@pytest.mark.parametrize(
    "tamper", ["offset", "request", "foreign-domain", "missing-surface"]
)
def test_return_rejects_mismatched_provenance(tmp_path, tamper):
    from imposition.artwork_return import prepare_layout_assets

    _, export, bundle = producer_fixture(tmp_path)
    handoff = export / "layout-handoff.json"
    if tamper in ("offset", "request"):
        v = json.loads(handoff.read_text())
        if tamper == "offset":
            v["panels"][0]["rebase_offset"][0] += 1
        else:
            v["producer_request"]["seed"] += 1
        handoff.write_bytes(json_bytes(v))
    elif tamper == "missing-surface":
        (bundle / "surfaces/page-8.svg").unlink()
    else:
        v = json.loads((bundle / "design.json").read_text())
        v["surfaces"][0]["domain_id"] = "foreign"
        (bundle / "design.json").write_bytes(json_bytes(v))
    with pytest.raises((ValueError, OSError)):
        prepare_layout_assets(
            producer_bundle=bundle, handoff=handoff, output_dir=tmp_path / "out"
        )
