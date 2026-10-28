"""Native face layouts and scoped Truchet recipes; no sheet transforms."""

import copy
import hashlib
import xml.etree.ElementTree as ET

from .artwork_export import _build_standard_artwork_job, write_layout_export
from .artwork_io import atomic_directory, json_bytes, read_json
from .artwork_layout import MM_TO_PX, ArtworkLayout, PanelLayout, layout_dict, rect
from .jcard_placement import resolve_jcard_placement, transform
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
        if not isinstance(adapted["passes"][0], dict):
            raise ValueError("Artwork pass must be an object")
        params = adapted["passes"][0].get("parameters")
        if isinstance(params, dict):
            if "coordinate_frame" in params and params["coordinate_frame"] not in (
                "domain",
                "composition",
            ):
                raise ValueError("Unsupported coordinate_frame")
            if "composition_mode" in params and params["composition_mode"] not in (
                "continuous",
                "independent-panels",
            ):
                raise ValueError("Unsupported composition_mode")
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


def sheet_preview(config, face, placement):
    """Diagnostic sheet geometry, including safe guides; never plot input."""
    from .artwork_export import SVG_NS

    sheet = config.sheet
    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": f"{sheet.width_mm}mm",
            "height": f"{sheet.height_mm}mm",
            "viewBox": f"0 0 {sheet.width_mm} {sheet.height_mm}",
            "data-jcard-diagnostic": "not-for-plotting",
        },
    )
    ET.SubElement(
        root,
        f"{{{SVG_NS}}}rect",
        {
            "width": str(sheet.width_mm),
            "height": str(sheet.height_mm),
            "fill": "white",
            "stroke": "#999",
            "stroke-width": "0.2",
        },
    )
    matrix = placement.face_matrix(face)
    for slot in JCard(face).slots:
        points = [transform(matrix, (x * 406.4, y * 101.6)) for x, y in slot.polygon]
        ET.SubElement(
            root,
            f"{{{SVG_NS}}}polygon",
            {
                "points": " ".join(f"{x},{y}" for x, y in points),
                "fill": "none",
                "stroke": "#1765a3",
                "stroke-width": "0.2",
            },
        )
        ET.SubElement(
            root,
            f"{{{SVG_NS}}}text",
            {
                "x": str(sum(x for x, y in points) / 4),
                "y": str(sum(y for x, y in points) / 4),
                "text-anchor": "middle",
                "font-size": "2",
            },
        ).text = slot.slot_id
    guides = dict(placement.diagnostic_guides)[face] + placement.face_guides(face)
    for guide in guides:
        ET.SubElement(
            root,
            f"{{{SVG_NS}}}path",
            {
                "data-guide-kind": guide.kind,
                "d": "M "
                + " L ".join(f"{x},{y}" for x, y in guide.points)
                + (" Z" if guide.closed else ""),
                "fill": "none",
                "stroke": "#b02447" if guide.kind == "registration" else "#aaa",
                "stroke-width": "0.15",
                "stroke-dasharray": "1 1" if guide.kind == "safe" else "none",
            },
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


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
            (folder / "sheet-preview.svg").write_bytes(sheet_preview(config, face, placement))
            records.append(
                {
                    "face": face,
                    "files": {
                        name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                        for name in (
                            "artwork-job.json",
                            "layout-handoff.json",
                            "layout-preview.svg",
                            "sheet-preview.svg",
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
                    "sheet": {
                        "name": config.sheet.name,
                        "width_mm": config.sheet.width_mm,
                        "height_mm": config.sheet.height_mm,
                    },
                    "front_reference_mm": [p.x_mm, p.y_mm, p.width_mm, p.height_mm],
                    "faces": records,
                }
            )
        )

    return atomic_directory(output_dir, write, overwrite=overwrite, protected=protected)
