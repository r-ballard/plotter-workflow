"""Explicit neutral-layer merging without inferring physical pens."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ..artwork_layout import _freeze, _thaw

GUIDE_IDS = {
    "cut": "sheet-cut-guides",
    "fold": "sheet-fold-guides",
    "registration": "sheet-registration",
}


@dataclass(frozen=True)
class ResolvedCatalog:
    catalog: tuple
    maps: object
    guide_ids: tuple


def _catalog(value):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("output catalog must be nonempty")
    seen = set()
    ordinals = set()
    copied = []
    for v in value:
        if (
            not isinstance(v, Mapping)
            or not isinstance(v.get("id"), str)
            or not v["id"]
            or not isinstance(v.get("label"), str)
            or not v["label"].strip()
            or type(v.get("ordinal")) is not int
            or v["ordinal"] < 0
            or v["id"] in seen
            or v["ordinal"] in ordinals
        ):
            raise ValueError("invalid or conflicting catalog IDs/ordinals/metadata")
        seen.add(v["id"])
        ordinals.add(v["ordinal"])
        copied.append(_freeze(_thaw(v)))
    if tuple(v["ordinal"] for v in copied) != tuple(range(1, len(copied) + 1)):
        raise ValueError("catalog ordinals must be contiguous in catalog order, starting at 1")
    return tuple(copied)


def resolve_catalog(objects, requested_catalog):
    sources = [(o, face, native) for o in objects for face, native in o.faces]
    if not sources:
        raise ValueError("catalog resolution requires native faces")
    first = sources[0][2].catalog
    same = all(native.catalog == first for _, _, native in sources)
    if requested_catalog is None:
        if not same or any(m is not None for o in objects for _, m in o.layer_maps):
            raise ValueError("different catalogs or layer maps require an explicit output catalog")
        catalog = _catalog(first)
    else:
        catalog = _catalog(requested_catalog)
    targets = {v["id"] for v in catalog}
    maps = {}
    for obj, face, native in sources:
        source_ids = {v["id"] for v in native.catalog}
        supplied = dict(obj.layer_maps)[face]
        if requested_catalog is None:
            mapping = {key: key for key in source_ids}
        else:
            if supplied is None:
                raise ValueError("explicit catalog requires complete per-face layer maps")
            mapping = dict(supplied)
            if set(mapping) != source_ids or set(mapping.values()) - targets:
                raise ValueError("layer map requires every source layer and known targets")
        maps[(obj.object_id, face)] = MappingProxyType(mapping)
    enabled = tuple(k for k in GUIDE_IDS if any(k in o.guides for o in objects))
    if targets & {GUIDE_IDS[k] for k in enabled}:
        raise ValueError("enabled reserved guide IDs collide with artwork")
    next_ordinal = max(v["ordinal"] for v in catalog) + 1
    guides = tuple(
        _freeze(dict(id=GUIDE_IDS[k], label=GUIDE_IDS[k], ordinal=next_ordinal + i))
        for i, k in enumerate(enabled)
    )
    return ResolvedCatalog(
        catalog + guides, MappingProxyType(maps), tuple((k, GUIDE_IDS[k]) for k in enabled)
    )
