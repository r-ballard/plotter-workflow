import copy
import json

import pytest

from imposition.artwork_layout import resolve_booklet_spread


def template():
    return {
        "schema_version": 1,
        "seed": 31,
        "domains": [],
        "passes": [
            {
                "id": "tiles",
                "algorithm": "truchet",
                "target_domain_ids": [],
                "parameters": {
                    "region_fills": {
                        "painted": {
                            "effect": "parallel-hatch",
                            "layer_id": "fill",
                            "parameters": {"spacing": 12.0},
                        }
                    },
                    "curve_layer_ids": ["curve"],
                    "tile_size": 80.0,
                },
                "logical_layers": [{"id": "curve"}, {"id": "fill"}],
            }
        ],
    }


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
    from imposition import artwork_export
    from imposition.artwork_export import write_layout_export

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
        lambda p: p.update(groups=[{"id": "old"}]),
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


def test_failed_commit_preserves_original_if_rollback_also_fails(tmp_path, monkeypatch):
    from imposition import artwork_io
    from imposition.artwork_export import write_layout_export

    layout = resolve_booklet_spread(
        sheet_size="letter", pages=(2, 3), margin_mm=0.0, gutter_mm=0.0
    )
    dest = tmp_path / "existing"
    write_layout_export(layout, template(), dest)
    before = (dest / "artwork-job.json").read_bytes()
    original = artwork_io.os.replace
    calls = []

    def fail_commit_and_restore(a, b):
        calls.append((a, b))
        if len(calls) > 1:
            raise OSError("injected persistent rename failure")
        return original(a, b)

    monkeypatch.setattr(artwork_io.os, "replace", fail_commit_and_restore)
    with pytest.raises(OSError):
        write_layout_export(layout, template(), dest, overwrite=True)
    backups = list(tmp_path.glob(".artwork-backup-*"))
    assert (
        len(backups) == 1 and (backups[0] / "artwork-job.json").read_bytes() == before
    )


@pytest.mark.parametrize(
    "palette", ["curve", ["not-declared"], ["curve", "curve"], [3]]
)
def test_export_rejects_invalid_curve_palette(palette):
    from imposition.artwork_export import build_artwork_job

    recipe = template()
    recipe["passes"][0]["parameters"]["curve_layer_ids"] = palette
    layout = resolve_booklet_spread(
        sheet_size="letter", pages=(8, 1), margin_mm=0, gutter_mm=0
    )
    with pytest.raises(ValueError, match="curve_layer_ids"):
        build_artwork_job(layout, recipe)


def test_validation_output_can_be_atomically_replaced(tmp_path):
    from imposition.artwork_io import atomic_directory

    destination = tmp_path / "validation"
    destination.mkdir()
    (destination / "validation.json").write_text("{}")
    atomic_directory(
        destination,
        lambda stage: (stage / "validation.json").write_text('{"fresh": true}'),
        overwrite=True,
    )
    assert json.loads((destination / "validation.json").read_text()) == {"fresh": True}
