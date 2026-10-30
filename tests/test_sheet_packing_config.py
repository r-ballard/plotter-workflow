import copy
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest
from imposition.sheet_packing.config import load_packing_config
from imposition.sheet_packing.layers import resolve_catalog


def payload():
    return dict(
        schema_version=1,
        sheet_mm=[420, 297],
        faces="front",
        objects=[
            dict(
                id="album",
                type="jcard",
                profile="standard-jcard-8-panel-v1",
                quantity=2,
                front=dict(assets="prepared", template="recipe.json", mode="independent"),
            )
        ],
    )


def test_complete_config_is_immutable_and_paths_are_relative(tmp_path):
    raw = payload()
    c = load_packing_config(raw, base_dir=tmp_path)
    raw["objects"][0]["front"]["assets"] = "elsewhere"
    assert c.objects[0].faces[0].request.assets == tmp_path / "prepared"
    assert c.objects[0].rotations == (0,) and c.gutter_mm == 0
    assert c.sheet.width_mm == 420 and c.sheet.flip is None
    with pytest.raises(FrozenInstanceError):
        c.objects = ()


@pytest.mark.parametrize(
    "update",
    [
        dict(schema_version=True),
        dict(schema_version=2),
        dict(sheet_mm=[True, 297]),
        dict(sheet_mm=[0, 297]),
        dict(sheet_mm=[1e7, 297]),
        dict(gutter_mm="1"),
        dict(gutter_mm=-1),
        dict(gutter_mm=None),
        dict(strategy="nest"),
        dict(faces="back"),
        dict(flip="left-right"),
        dict(usable_back_mm=[0, 0, 420, 297]),
        dict(margins_mm=[200, 0, 200, 0]),
        dict(objects=[]),
        dict(extra=1),
    ],
)
def test_bad_top_level_values(tmp_path, update):
    with pytest.raises(ValueError):
        load_packing_config(payload() | update, base_dir=tmp_path)


@pytest.mark.parametrize(
    "update",
    [
        dict(id=""),
        dict(type="cootie"),
        dict(profile="unknown"),
        dict(quantity=True),
        dict(quantity=1.5),
        dict(quantity=1001),
        dict(quantity=0),
        dict(rotations=[]),
        dict(rotations=[0, 0]),
        dict(rotations=[False]),
        dict(rotations=[45]),
        dict(bleed_allowance_mm=-1),
        dict(guides=dict(cut=1)),
        dict(guides=dict(safe=True)),
        dict(front=None),
        dict(back=dict(assets="b", template="r")),
        dict(origin_mm=[0, 0]),
    ],
)
def test_bad_object_values(tmp_path, update):
    data = payload()
    data["objects"][0].update(update)
    with pytest.raises(ValueError):
        load_packing_config(data, base_dir=tmp_path)


def test_paired_selection_and_aggregate_limits(tmp_path):
    data = payload()
    data["faces"] = "both"
    with pytest.raises(ValueError):
        load_packing_config(data, base_dir=tmp_path)
    data["objects"][0]["back"] = dict(data["objects"][0]["front"])
    c = load_packing_config(data, base_dir=tmp_path)
    assert c.sheet.flip == "left-right" and len(c.objects[0].faces) == 2
    data["objects"] *= 2
    with pytest.raises(ValueError, match="unique"):
        load_packing_config(data, base_dir=tmp_path)
    data = payload()
    obj = data["objects"][0]
    data["objects"] = [dict(obj, id=f"x{i}", quantity=1) for i in range(129)]
    with pytest.raises(ValueError, match="128"):
        load_packing_config(data, base_dir=tmp_path)
    data["objects"] = [dict(obj, id=f"x{i}", quantity=600) for i in range(2)]
    with pytest.raises(ValueError, match="1000"):
        load_packing_config(data, base_dir=tmp_path)


def catalogs(second_label="Curve", mapping=None):
    a = dict(id="curve", ordinal=1, label="Curve")
    b = dict(id="curve", ordinal=1, label=second_label)

    def obj(name, catalog):
        return SimpleNamespace(
            object_id=name,
            faces=(("front", SimpleNamespace(catalog=(catalog,))),),
            layer_maps=(("front", mapping),),
            guides=(),
        )

    return (obj("a", a), obj("b", b))


def test_implicit_catalog_identity_requires_complete_metadata_match():
    resolved = resolve_catalog(catalogs(), None)
    assert resolved.catalog[0]["id"] == "curve"
    assert dict(resolved.maps[("a", "front")]) == {"curve": "curve"}
    with pytest.raises(ValueError, match="catalog"):
        resolve_catalog(catalogs("Different"), None)


def test_explicit_maps_and_reserved_ids():
    target = [dict(id="art", ordinal=1, label="Artwork")]
    resolved = resolve_catalog(catalogs("Other", (("curve", "art"),)), target)
    assert resolved.catalog[0]["id"] == "art"
    for mapping in ((), (("missing", "art"),), (("curve", "missing"),)):
        with pytest.raises(ValueError):
            resolve_catalog(catalogs(mapping=mapping), target)
    source = catalogs()
    source[0].guides = ("cut",)
    with pytest.raises(ValueError):
        resolve_catalog(source, [dict(id="sheet-cut-guides", ordinal=1, label="cut")])


def test_source_data_not_mutated_by_catalog_resolution():
    source = catalogs()
    before = copy.deepcopy(source[0].faces[0][1].catalog)
    result = resolve_catalog(source, None)
    assert source[0].faces[0][1].catalog == before
    with pytest.raises(TypeError):
        result.catalog[0]["label"] = "changed"


@pytest.mark.parametrize(
    "entry",
    [
        dict(assets=None),
        dict(template=False),
        dict(mode=None),
        dict(blank_panels=[{}]),
        dict(blank_panels=["front-panel-99"]),
        dict(layer_map=None),
    ],
)
def test_invalid_face_fields_are_actionable(tmp_path, entry):
    data = payload()
    data["objects"][0]["front"].update(entry)
    with pytest.raises(ValueError):
        load_packing_config(data, base_dir=tmp_path)


@pytest.mark.parametrize(
    "target",
    [
        [dict(id="art", ordinal=0, label="Art")],
        [dict(id="art", ordinal=2, label="Art")],
        [dict(id="art", ordinal=1, label=" ")],
    ],
)
def test_output_catalog_matches_existing_contiguous_contract(target):
    with pytest.raises(ValueError):
        resolve_catalog(catalogs(mapping=(("curve", "art"),)), target)
