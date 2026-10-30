"""J-card native-face adapter; the solvers never import this module."""

from dataclasses import dataclass

from ..jcard_native import prepare_native_face
from ..model import Guide
from ..objects.cassette_jcard import JCard
from .model import ObjectFootprint, PackingInstance, PolygonRegion, RectMM


@dataclass(frozen=True)
class PreparedPackingObject:
    object_id: str
    profile: str
    quantity: int
    footprint: ObjectFootprint
    faces: tuple
    native_back_to_front: tuple
    physical_guides: tuple
    guides: tuple
    layer_maps: tuple


def prepare_objects(config, budget):
    budget.reserve("specs", len(config.objects))
    result = []
    cache = {}
    for spec in config.objects:
        card = JCard(profile=spec.profile)
        w, h = card.trim_size_mm
        faces = []
        for f in spec.faces:
            if f.request not in cache:
                cache[f.request] = prepare_native_face(f.request)
            faces.append((f.face, cache[f.request]))
        guides = [g for g in card.native_guides() if g.kind in spec.guides]
        if "registration" in spec.guides:
            for x, y in ((-2, -2), (w + 2, -2), (-2, h + 2)):
                guides.extend(
                    (
                        Guide("registration", ((x - 1, y), (x + 1, y))),
                        Guide("registration", ((x, y - 1), (x, y + 1))),
                    )
                )
        b = spec.bleed_allowance_mm
        xs = [-b, w + b]
        ys = [-b, h + b]
        for g in guides:
            for x, y in g.points:
                xs.append(x)
                ys.append(y)
        occupied = RectMM(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        footprint = ObjectFootprint(
            spec.object_id,
            (PolygonRegion(((0, 0), (w, 0), (w, h), (0, h))),),
            occupied,
            spec.rotations,
        )
        result.append(
            PreparedPackingObject(
                spec.object_id,
                spec.profile,
                spec.quantity,
                footprint,
                tuple(faces),
                (-1, 0, 0, 1, w, 0),
                tuple(guides),
                spec.guides,
                tuple((f.face, f.layer_map) for f in spec.faces),
            )
        )
    return tuple(result)


def instances(objects):
    for obj in sorted(objects, key=lambda o: o.object_id):
        for number in range(1, obj.quantity + 1):
            yield PackingInstance(f"{obj.object_id}-{number:04}", obj.footprint)
