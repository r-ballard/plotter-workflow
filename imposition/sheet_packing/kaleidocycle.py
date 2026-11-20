"""Kaleidocycle native artwork and full blank-tab footprint adapter."""

from ..kaleidocycle_native import prepare_native_kaleidocycle
from ..model import ObjectPlacement, SheetSpec
from ..objects.kaleidocycle import Kaleidocycle
from .jcard import PreparedPackingObject
from .model import ObjectFootprint, PolygonRegion, RectMM


def prepare_object(spec, native=None):
    native = (
        native
        if native is not None
        else prepare_native_kaleidocycle(spec.faces[0].request)
    )
    w, h = native.width_mm, native.height_mm
    obj = Kaleidocycle()
    placement = ObjectPlacement(SheetSpec("custom", w, h, "landscape"), 0, 0, w, h)
    polygons = [s.polygon for s in obj.slots] + list(obj.glue_polygons)
    regions = tuple(
        PolygonRegion(tuple((x * w, y * h) for x, y in p)) for p in polygons
    )
    b = spec.bleed_allowance_mm
    footprint = ObjectFootprint(
        spec.object_id, regions, RectMM(-b, -b, w + 2 * b, h + 2 * b), spec.rotations
    )
    guides = tuple(g for g in obj.guides(placement) if g.kind in spec.guides)
    return PreparedPackingObject(
        spec.object_id,
        "kaleidocycle",
        spec.quantity,
        footprint,
        (("front", native),),
        (1, 0, 0, 1, 0, 0),
        guides,
        spec.guides,
        (("front", spec.faces[0].layer_map),),
    )
