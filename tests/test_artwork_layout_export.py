import copy, json
import pytest
from imposition.artwork_layout import resolve_booklet_spread


def template():
    return dict(
        schema_version=1,
        seed=31,
        domains=[],
        passes=[
            dict(
                id="tiles",
                algorithm="truchet",
                target_domain_ids=[],
                parameters=dict(
                    region_fills={
                        "painted": dict(
                            effect="parallel-hatch",
                            layer_id="fill",
                            parameters=dict(spacing=12.0),
                        )
                    },
                    curve_layer_ids=["curve"],
                    tile_size=80.0,
                ),
                logical_layers=[dict(id="curve"), dict(id="fill")],
            )
        ],
    )


def test_export_uses_existing_producer_schema():
    from imposition.artwork_export import build_artwork_job

    layout = resolve_booklet_spread(
        sheet_size="letter", pages=(8, 1), margin_mm=3.0, gutter_mm=2.0
    )
    original = template()
    job = build_artwork_job(layout, original)
    assert original == template() and job["seed"] == 31
    assert [d["id"] for d in job["domains"]] == ["page-8", "page-1"]
    assert job["domains"][0]["vertices"] == [
        list(p) for p in layout.panels[0].crop_polygon
    ]
    assert job["passes"][0]["parameters"]["composition_mode"] == "continuous"
    assert (
        job["passes"][0]["parameters"]["region_fills"]
        == original["passes"][0]["parameters"]["region_fills"]
    )


def test_deterministic_atomic_export(tmp_path, monkeypatch):
    from imposition.artwork_export import write_layout_export
    from imposition import artwork_export

    layout = resolve_booklet_spread(
        sheet_size="a4", pages=(2, 3), margin_mm=1.0, gutter_mm=0.0
    )
    a = tmp_path / "a"
    b = tmp_path / "b"
    write_layout_export(layout, template(), a)
    write_layout_export(layout, template(), b)

    def snap(d):
        return {p.name: p.read_bytes() for p in d.iterdir()}

    assert snap(a) == snap(b)
    before = snap(a)
    with pytest.raises(ValueError):
        write_layout_export(layout, template(), a)
    monkeypatch.setattr(
        artwork_export,
        "layout_preview",
        lambda *a: (_ for _ in ()).throw(ValueError("injected preview failure")),
    )
    with pytest.raises(ValueError):
        write_layout_export(layout, template(), a, overwrite=True)
    assert snap(a) == before
    report = json.loads((b / "layout-handoff.json").read_text())
    assert report["schema_version"] == 1 and report["layout"]["units"] == "svg-px"
    assert report["panels"][0]["rebase_offset"] == [1 * 96 / 25.4, 1 * 96 / 25.4]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(schema_version=True),
        lambda p: p["passes"].append(copy.deepcopy(p["passes"][0])),
        lambda p: p["passes"][0].update(algorithm="other"),
        lambda p: p.update(unknown=1),
        lambda p: p["passes"][0]["parameters"].update(coordinate_frame="domain"),
        lambda p: p.update(groups=[dict(id="old")]),
    ],
)
def test_export_rejects_ambiguous_template(mutate):
    from imposition.artwork_export import build_artwork_job

    p = template()
    mutate(p)
    with pytest.raises(ValueError):
        build_artwork_job(
            resolve_booklet_spread(
                sheet_size="letter", pages=(2, 3), margin_mm=0.0, gutter_mm=0.0
            ),
            p,
        )
