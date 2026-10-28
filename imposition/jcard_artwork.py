"""Native face layouts and scoped Truchet recipes; no sheet transforms."""

import copy
import hashlib

from .artwork_export import _build_standard_artwork_job, write_layout_export
from .artwork_io import atomic_directory, json_bytes, read_json
from .artwork_layout import MM_TO_PX, ArtworkLayout, PanelLayout, layout_dict, rect
from .jcard_placement import resolve_jcard_placement
from .objects.cassette_jcard import PROFILE, JCard


def resolve_jcard_layout(config, face):
    if face not in config.selected_faces:
        raise ValueError("Face is not selected")
    card = JCard(face, config.profile)
    panels = []
    # Use exact integer SVG widths (sixteenths of an inch are six pixels).
    x = 0
    for slot in card.slots:
        number = int(slot.slot_id.rsplit("-", 1)[1])
        width = (17, 8, 41, 40, 39, 38, 37, 36)[number - 1] * 6
        full = rect(0, 0, width, 384)
        panels.append(
            PanelLayout(
                slot.slot_id,
                full,
                full,
                (1, 0, 0, 1, x, 0),
                {
                    "kind": "jcard-slot",
                    "profile": PROFILE,
                    "face": face,
                    "physical_panel_id": f"panel-{number}",
                    "slot": slot.slot_id,
                },
            )
        )
        x += width
    return ArtworkLayout(
        f"{PROFILE}-{face}",
        "svg-px",
        (0, 0, 1536, 384),
        tuple(panels),
        "provisional",
        {
            "layout": "cassette-jcard",
            "profile": PROFILE,
            "face": face,
            "mode": getattr(config, f"{face}_artwork").mode,
            "mm_to_px": MM_TO_PX,
        },
    )


def validate_jcard_layout(layout):
    from types import SimpleNamespace

    settings = layout.settings
    face, mode = settings.get("face"), settings.get("mode")
    if (
        face not in ("front", "back")
        or mode not in ("independent", "continuous")
        or settings.get("profile") != PROFILE
    ):
        raise ValueError("Invalid J-card layout identity")
    config = SimpleNamespace(
        selected_faces=(face,), profile=PROFILE, **{f"{face}_artwork": SimpleNamespace(mode=mode)}
    )
    expected = resolve_jcard_layout(config, face)
    if json_bytes(layout_dict(expected)) != json_bytes(layout_dict(layout)):
        raise ValueError("J-card layout differs from canonical native geometry")


def build_jcard_artwork_job(layout, template, *, mode):
    validate_jcard_layout(layout)
    if mode != layout.settings["mode"]:
        raise ValueError("Artwork mode differs from layout")
    adapted = copy.deepcopy(template)
    # Standard validation still owns supported algorithms/catalogs. Normalize only
    # the scoped frame controls before applying the selected native face mode.
    if (
        isinstance(adapted, dict)
        and isinstance(adapted.get("passes"), list)
        and len(adapted["passes"]) == 1
    ):
        params = adapted["passes"][0].get("parameters")
        if isinstance(params, dict):
            params["coordinate_frame"] = "composition"
            params["composition_mode"] = "continuous"
    job = _build_standard_artwork_job(layout, adapted)
    if mode == "independent":
        params = job["passes"][0]["parameters"]
        params["coordinate_frame"] = "domain"
        for key in ("composition_mode", "composition_window", "seam_margin"):
            params.pop(key, None)
        job.pop("composition_transforms")
    return job


def write_jcard_export(config, output_dir, *, overwrite=False):
    placement = resolve_jcard_placement(config)
    protected = [getattr(config, f"{face}_artwork").template for face in config.selected_faces]

    def write(stage):
        records = []
        for face in config.selected_faces:
            recipe = getattr(config, f"{face}_artwork")
            folder = write_layout_export(
                resolve_jcard_layout(config, face), read_json(recipe.template), stage / face
            )
            records.append(
                {
                    "face": face,
                    "files": {
                        name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                        for name in (
                            "artwork-job.json",
                            "layout-handoff.json",
                            "layout-preview.svg",
                        )
                    },
                }
            )
        p = placement.front_reference
        (stage / "jcard-export.json").write_bytes(
            json_bytes(
                {
                    "schema_version": 1,
                    "profile": config.profile,
                    "flip": config.flip,
                    "front_reference_mm": [p.x_mm, p.y_mm, p.width_mm, p.height_mm],
                    "faces": records,
                }
            )
        )

    return atomic_directory(output_dir, write, overwrite=overwrite, protected=protected)
