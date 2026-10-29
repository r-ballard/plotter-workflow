"""Strict multi-object job configuration, with paths relative to its file."""

from dataclasses import dataclass
from pathlib import Path

from ..artwork_layout import _freeze
from ..jcard_config import record
from ..jcard_native import NativeFaceRequest
from ..jcard_profiles import get_jcard_profile
from .geometry import effective_area
from .model import ObjectFootprint, RectMM, SheetArea, identifier, number


@dataclass(frozen=True)
class FaceSpec:
    face: str
    request: NativeFaceRequest
    layer_map: tuple | None


@dataclass(frozen=True)
class ObjectSpec:
    object_id: str
    profile: str
    quantity: int
    rotations: tuple
    bleed_allowance_mm: float
    guides: tuple
    faces: tuple


@dataclass(frozen=True)
class PackingConfig:
    sheet: SheetArea
    gutter_mm: float
    strategy: str
    objects: tuple
    logical_layers: tuple | None
    source_path: Path | None = None


def _path(value, base_dir):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("asset/template paths require nonempty strings")
    return (Path(base_dir) / value).resolve()


def _rectangle(value, name):
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise ValueError(f"{name} requires [x,y,width,height]")
    return RectMM(*value)


def load_packing_config(payload, *, base_dir):
    p = record(
        payload,
        (
            "schema_version",
            "sheet_mm",
            "usable_front_mm",
            "usable_back_mm",
            "margins_mm",
            "gutter_mm",
            "strategy",
            "faces",
            "flip",
            "objects",
            "logical_layers",
        ),
        "packing",
    )
    if type(p.get("schema_version")) is not int or p["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    dims = p.get("sheet_mm")
    if not isinstance(dims, list) or len(dims) != 2:
        raise ValueError("sheet_mm requires [width,height]")
    w, h = (number(v, "sheet dimension") for v in dims)
    faces = p.get("faces", "front")
    if faces not in ("front", "both") or (
        faces == "front" and {"flip", "usable_back_mm"} & p.keys()
    ):
        raise ValueError("invalid or inapplicable face/flip controls")
    front = (
        _rectangle(p["usable_front_mm"], "usable_front_mm")
        if "usable_front_mm" in p
        else RectMM(0, 0, w, h)
    )
    back = _rectangle(p["usable_back_mm"], "usable_back_mm") if "usable_back_mm" in p else None
    sheet = SheetArea(
        w,
        h,
        front,
        back,
        p.get("margins_mm", (0, 0, 0, 0)),
        faces,
        p.get("flip", "left-right") if faces == "both" else None,
    )
    effective_area(sheet)
    gutter = number(p.get("gutter_mm", 0), "gutter")
    strategy = p.get("strategy", "auto")
    if gutter < 0 or strategy not in ("auto", "grid", "maxrects"):
        raise ValueError("invalid strategy/gutter")
    raw = p.get("objects")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 128:
        raise ValueError("objects require 1..128 definitions")
    objects = []
    seen = set()
    count = 0
    for raw_object in raw:
        obj = record(
            raw_object,
            (
                "id",
                "type",
                "profile",
                "quantity",
                "rotations",
                "bleed_allowance_mm",
                "guides",
                "front",
                "back",
            ),
            "object",
        )
        key = identifier(obj.get("id"))
        if key in seen:
            raise ValueError("object IDs must be unique")
        seen.add(key)
        if obj.get("type") != "jcard":
            raise ValueError("initial packing adapter requires type=jcard")
        profile = get_jcard_profile(obj.get("profile"))
        quantity = obj.get("quantity", 1)
        if type(quantity) is not int or not 1 <= quantity <= 1000:
            raise ValueError("quantity requires integer 1..1000")
        count += quantity
        if count > 1000:
            raise ValueError("expanded objects exceed 1000 instances")
        rotations = ObjectFootprint(
            key, (), RectMM(0, 0, 1, 1), obj.get("rotations", [0])
        ).rotations
        bleed = number(obj.get("bleed_allowance_mm", 0), "bleed_allowance_mm")
        if bleed < 0:
            raise ValueError("bleed allowance must be nonnegative")
        guide_fields = record(obj.get("guides", {}), ("cut", "fold", "registration"), "guides")
        if any(type(v) is not bool for v in guide_fields.values()):
            raise ValueError("guide values require booleans")
        guides = tuple(k for k in ("cut", "fold", "registration") if guide_fields.get(k, False))
        selected = ("front", "back") if faces == "both" else ("front",)
        if "back" in obj and faces == "front":
            raise ValueError("back artwork requires paired faces")
        entries = []
        for face in selected:
            entry = record(
                obj.get(face), ("assets", "template", "mode", "blank_panels", "layer_map"), face
            )
            request = NativeFaceRequest(
                profile.profile_id,
                face,
                _path(entry.get("assets"), base_dir),
                _path(entry.get("template"), base_dir),
                entry.get("mode", "independent"),
                entry.get("blank_panels", ()),
            )
            mapping = None
            if "layer_map" in entry:
                value = entry["layer_map"]
                if not isinstance(value, dict) or any(
                    not isinstance(k, str) or not k or not isinstance(v, str) or not v
                    for k, v in value.items()
                ):
                    raise ValueError("layer_map requires nonempty string IDs")
                mapping = tuple(sorted(value.items()))
            entries.append(FaceSpec(face, request, mapping))
        objects.append(
            ObjectSpec(key, profile.profile_id, quantity, rotations, bleed, guides, tuple(entries))
        )
    catalog = p.get("logical_layers")
    if "logical_layers" in p and (not isinstance(catalog, list) or not catalog):
        raise ValueError("logical_layers requires a nonempty catalogue")
    return PackingConfig(
        sheet,
        gutter,
        strategy,
        tuple(sorted(objects, key=lambda o: o.object_id)),
        None if catalog is None else tuple(_freeze(v) for v in catalog),
    )
