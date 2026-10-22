import xml.etree.ElementTree as E

import pytest

from imposition.artwork_layout import bounds
from scripts import booklet_impose as booklet
from scripts import cootie_impose as cootie
from tests.test_artwork_layout_return import producer_fixture


def test_generated_crop_roundtrip_matches_resolved_spread(tmp_path, monkeypatch):
    import vpype

    from imposition.artwork_return import prepare_layout_assets

    layout, export, producer = producer_fixture(tmp_path)
    out = tmp_path / "assets"
    prepare_layout_assets(
        producer_bundle=producer, handoff=export / "layout-handoff.json", output_dir=out
    )
    W = layout.panels[0].canvas_polygon[2][0]
    H = layout.panels[0].canvas_polygon[2][1]
    M = 3 * booklet.MM_TO_PX
    G = 2 * booklet.MM_TO_PX
    for i, p in enumerate(layout.panels):
        fragment = next(iter(booklet._neutral_fragments(
                out / "surfaces" / (p.panel_id + ".svg"), i + 1, 0.01
            )))
        _, geometry, w, h = fragment
        actual = booklet._render_single(
            geometry,
            w,
            h,
            page=p.binding["page"],
            cell_width=W,
            cell_height=H,
            margin=0,
            fit="contain",
        ).lines
        x, y = bounds(p.crop_polygon)[:2]
        reference = vpype.LineCollection(
            [[complex(i * W + x + 1, y + 2), complex(i * W + x + 3, y + 4)]]
        )
        with monkeypatch.context() as ctx:
            ctx.setattr(booklet, "_fit_collection", lambda *a, **k: None)
            expected = booklet._render_spread_half(
                reference,
                2 * W,
                H,
                page=p.binding["page"],
                half="left" if i == 0 else "right",
                cell_width=W,
                cell_height=H,
                margin=M,
                gutter=G,
                fit="contain",
            )
        assert len(actual) == len(expected) == 1
        for a, b in zip(next(iter(actual)), next(iter(expected))):
            assert abs(a - b) < 1e-8


def test_cootie_neutral_imposition_preserves_catalog_and_provenance(tmp_path):
    from imposition.artwork_return import prepare_layout_assets
    from logical_layer_contract import InputMode, inspect_svg_contract

    _layout, export, producer = producer_fixture(tmp_path)
    out = tmp_path / "assets"
    prepare_layout_assets(
        producer_bundle=producer, handoff=export / "layout-handoff.json", output_dir=out
    )
    entries = [
        cootie.PanelEntry("outer-1", out / "surfaces/page-8.svg", "contain", 0.0, 0)
    ]
    placement = cootie.square_placement(
        "letter", position="center", square_size_mm=100.0
    )
    root, records, mode = cootie.impose(
        entries, sheet_size="letter", placement=placement
    )
    assert mode == "neutral" and len(records) == 1
    path = tmp_path / "sheet.svg"
    E.ElementTree(root).write(path)
    contract = inspect_svg_contract(path)
    assert contract.mode is InputMode.NEUTRAL
    assert [v.id for v in contract.layers] == ["curve", "fill"]
    assert any(
        p.get("data-viz-path-id") == "page-8:stroke"
        for p in root.iter("{http://www.w3.org/2000/svg}path")
    )


def test_folded_profile_roundtrip_corner_labels():
    import vpype

    from imposition.artwork_layout import affine
    from imposition.assembled_profiles import load_cootie_assembled_profile
    from tests.test_assembled_profiles import profile

    p = profile()
    s = p["window"][2] / 2
    p["panels"][1]["matrix"] = [-1, 0, 0, 1, 2 * s, 0]
    layout = load_cootie_assembled_profile(p, square_size_mm=100.0)
    placement = cootie.square_placement(
        "letter", position="center", square_size_mm=100.0
    )
    for panel in layout.panels:
        a, b, c, d, e, f = panel.assembled_matrix
        det = a * d - b * c
        from imposition.objects.cootie_catcher import LEGACY_ROTATIONS

        angle = LEGACY_ROTATIONS[panel.panel_id]
        target = cootie.panel_polygon_px(panel.panel_id, placement)
        for i, q in enumerate(panel.canvas_polygon):
            x, y = affine(panel.assembled_matrix, q)
            restored = (
                (d * (x - e) - c * (y - f)) / det,
                (-b * (x - e) + a * (y - f)) / det,
            )
            assert restored == pytest.approx(q)
            # Corner tick vectors are labels; no live text enters plotter input.
            center = (s / 2, s / 2)
            tick = (q[0] + (center[0] - q[0]) * 0.05, q[1] + (center[1] - q[1]) * 0.05)
            lines = vpype.LineCollection([[complex(*restored), complex(*tick)]])
            actual = cootie.render_lines_to_panel(
                lines, s, s, polygon=target, rotation_degrees=angle, fit="contain"
            )
            expected = target[(i + angle // 90) % 4]
            assert abs(next(iter(actual))[0] - complex(*expected)) < 1e-7
    assert layout.validation_status == "provisional"


def test_validation_rejects_missing_producer_before_publication(tmp_path):
    from scripts.validate_assembled_artwork import run_validation

    with pytest.raises(ValueError):
        run_validation(
            viz_repo=tmp_path / "missing",
            viz_python=tmp_path / "python",
            output_dir=tmp_path / "out",
        )
    assert not (tmp_path / "out").exists()
