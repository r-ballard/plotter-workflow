"""Strict declared folded views; never infer them from flat-sheet adjacency."""

from .artwork_layout import ArtworkLayout, PanelLayout, MM_TO_PX, finite, rect
from .objects.cootie_catcher import CootieCatcher


def load_cootie_assembled_profile(payload, *, square_size_mm):
    keys = {
        "schema_version",
        "profile_id",
        "object_id",
        "view",
        "validation_status",
        "units",
        "window",
        "panels",
    }
    if not isinstance(payload, dict) or set(payload) != keys:
        raise ValueError("invalid folded profile fields")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("unsupported folded profile version")
    if payload["object_id"] != "cootie_catcher" or payload["view"] != "folded-outer":
        raise ValueError("unsupported folded profile object/view")
    size = finite(square_size_mm, "square_size_mm")
    if not 0 < size <= 1e6:
        raise ValueError("square size exceeds supported range")
    rows = payload["panels"]
    expected = {f"outer-{i}" for i in range(1, 5)}
    if (
        not isinstance(rows, list)
        or len(rows) != 4
        or any(
            not isinstance(p, dict) or set(p) != {"slot_id", "canvas_polygon", "matrix"}
            for p in rows
        )
    ):
        raise ValueError("profile requires explicit four outer panels")
    if {p["slot_id"] for p in rows} != expected:
        raise ValueError("profile requires unique outer1..4 slots")
    slots = {s.slot_id: s for s in CootieCatcher().slots}
    panels = []
    for row in sorted(rows, key=lambda r: r["slot_id"]):
        slot = slots[row["slot_id"]]
        width = (
            (max(x for x, y in slot.polygon) - min(x for x, y in slot.polygon))
            * size
            * MM_TO_PX
        )
        height = (
            (max(y for x, y in slot.polygon) - min(y for x, y in slot.polygon))
            * size
            * MM_TO_PX
        )
        full = rect(0.0, 0.0, width, height)
        supplied = row["canvas_polygon"]
        if (
            not isinstance(supplied, (tuple, list))
            or len(supplied) != 4
            or any(not isinstance(p, (tuple, list)) or len(p) != 2 for p in supplied)
        ):
            raise ValueError("profile requires canonical intrinsic canvas")
        values = tuple(tuple(finite(c, "profile canvas") for c in p) for p in supplied)
        if any(
            abs(a - b) > 1e-9 * max(1.0, abs(b))
            for p, q in zip(values, full)
            for a, b in zip(p, q)
        ):
            raise ValueError(
                "profile intrinsic canvas conflicts with canonical object size"
            )
        orientation = slot.target_orientation
        binding = dict(
            kind="cootie-slot",
            slot=slot.slot_id,
            up_vector=orientation.up_vector,
            right_vector=orientation.right_vector,
            top_feature_anchor=orientation.top_feature_anchor,
            right_feature_anchor=orientation.right_feature_anchor,
            orientation_validation=orientation.validation,
        )
        panels.append(PanelLayout(slot.slot_id, full, full, row["matrix"], binding))
    return ArtworkLayout(
        payload["profile_id"],
        payload["units"],
        payload["window"],
        tuple(panels),
        payload["validation_status"],
        dict(
            layout="cootie-folded-outer",
            square_size_mm=size,
            mm_to_px=MM_TO_PX,
            validation_basis="declared-profile-status; physical acceptance not performed by export",
        ),
    )
