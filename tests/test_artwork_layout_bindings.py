import copy

import pytest

from imposition.artwork_layout import resolve_booklet_spread
from imposition.assembled_profiles import load_cootie_assembled_profile
from tests.test_assembled_profiles import profile


def test_binding_avoids_double_settings():
    from imposition.artwork_bindings import apply_layout_bindings, build_layout_bindings

    layout = resolve_booklet_spread(
        sheet_size="letter", pages=(8, 1), margin_mm=3.0, gutter_mm=2.0
    )
    patch = build_layout_bindings(
        layout, {p.panel_id: f"surfaces/{p.panel_id}.svg" for p in layout.panels}
    )
    assert [e["page"] for e in patch["entries"]] == [8, 1]
    assert all(
        e["margin_mm"] == 0 and e["fit"] == "contain" and "rotation_degrees" not in e
        for e in patch["entries"]
    )
    manifest = {
        "schema_version": 1,
        "pages": [{"page": i, "source": f"old{i}.svg"} for i in range(1, 9)],
    }
    original = copy.deepcopy(manifest)
    new = apply_layout_bindings(manifest, patch)
    assert manifest == original
    assert next(e for e in new["pages"] if e["page"] == 4) == manifest["pages"][3]
    assert (
        next(e for e in new["pages"] if e["page"] == 8)["source"]
        == "surfaces/page-8.svg"
    )


def test_partial_binding_is_not_complete_manifest():
    from imposition.artwork_bindings import apply_layout_bindings, build_layout_bindings

    layout = load_cootie_assembled_profile(profile(), square_size_mm=100.0)
    patch = build_layout_bindings(
        layout, {p.panel_id: f"surfaces/{p.panel_id}.svg" for p in layout.panels}
    )
    assert patch["complete"] is False and len(patch["remaining_assignments"]) == 16
    manifest = {
        "schema_version": 1,
        "panels": [
            {"slot": s, "source": s + ".svg", "rotation_degrees": 90}
            for s in ["outer-1", "outer-2", "outer-3", "outer-4", "selector-1"]
        ],
    }
    new = apply_layout_bindings(manifest, patch)
    assert new["panels"][-1] == manifest["panels"][-1]
    assert new["panels"][0]["rotation_degrees"] == 90
    with pytest.raises(ValueError):
        build_layout_bindings(layout, {"outer-1": "a.svg"})
    with pytest.raises(ValueError):
        build_layout_bindings(
            layout, {p.panel_id: "../outside.svg" for p in layout.panels}
        )
