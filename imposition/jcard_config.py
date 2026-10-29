"""Strict, resolved configuration for separate cassette face jobs."""

from dataclasses import dataclass
from pathlib import Path

from .artwork_layout import finite
from .jcard_profiles import get_jcard_profile
from .model import SheetSpec
from .objects.cassette_jcard import PROFILE
from .objects.cootie_catcher import SUPPORTED_SHEETS


def record(value, allowed, name):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f"Invalid {name} fields")
    return value


@dataclass(frozen=True)
class FaceArtwork:
    template: Path
    mode: str
    blank_panels: tuple[str, ...]


@dataclass(frozen=True)
class JCardConfig:
    profile: str
    faces: str
    sheet: SheetSpec
    margin_mm: float
    origin_mm: tuple[float, float] | None
    flip: str
    safe_inset_mm: float
    guides: tuple[str, ...]
    front_artwork: FaceArtwork | None
    back_artwork: FaceArtwork | None

    @property
    def selected_faces(self):
        return ("front", "back") if self.faces == "both" else (self.faces,)


def load_jcard_config(payload, *, base_dir):
    p = record(
        payload,
        (
            "schema_version",
            "profile",
            "faces",
            "sheet",
            "margin_mm",
            "origin_mm",
            "flip",
            "safe_inset_mm",
            "guides",
            "front_artwork",
            "back_artwork",
        ),
        "J-card",
    )
    if type(p.get("schema_version")) is not int or p["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    profile, faces = p.get("profile", PROFILE), p.get("faces", "front")
    flip = p.get("flip", "left-right")
    if faces not in ("front", "back", "both") or flip not in ("left-right", "top-bottom"):
        raise ValueError("Unsupported profile, faces or flip")
    descriptor = get_jcard_profile(profile)
    raw_sheet = p.get("sheet")
    if isinstance(raw_sheet, str):
        if raw_sheet not in SUPPORTED_SHEETS:
            raise ValueError("Unknown sheet")
        sheet = SUPPORTED_SHEETS[raw_sheet]
    else:
        s = record(raw_sheet, ("width_mm", "height_mm"), "sheet")
        width, height = (finite(s.get(k), k) for k in ("width_mm", "height_mm"))
        if not 0 < height <= width <= 1e6:
            raise ValueError("Sheet must have positive landscape dimensions <= 1e6 mm")
        sheet = SheetSpec("custom", width, height, "landscape")
    margin = finite(p.get("margin_mm", 0), "margin_mm")
    inset = finite(p.get("safe_inset_mm", float(descriptor.safe_inset_mm)), "safe_inset_mm")
    safe_limit = min(*descriptor.panel_widths_mm, descriptor.trim_size_mm[1]) / 2
    if not 0 <= margin < min(sheet.width_mm, sheet.height_mm) / 2 or not 0 <= inset < safe_limit:
        raise ValueError("Margin or safe inset collapses drawable area")
    origin = None
    if "origin_mm" in p:
        raw = p["origin_mm"]
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise ValueError("origin_mm must be an XY pair")
        origin = tuple(finite(v, "origin_mm") for v in raw)
    guides = record(p.get("guides", {}), ("cut", "fold", "registration"), "guides")
    if any(type(v) is not bool for v in guides.values()):
        raise ValueError("Guide controls must be booleans")
    selected = ("front", "back") if faces == "both" else (faces,)
    artwork = {}
    for face in ("front", "back"):
        key = f"{face}_artwork"
        if face not in selected:
            if key in p:
                raise ValueError("Artwork assigned to unselected face")
            artwork[key] = None
            continue
        item = record(p.get(key), ("template", "mode", "blank_panels"), key)
        path, mode = item.get("template"), item.get("mode", "independent")
        blanks = item.get("blank_panels", [])
        if (
            not isinstance(path, str)
            or not path.strip()
            or mode not in ("independent", "continuous")
        ):
            raise ValueError("Selected face requires a template and valid mode")
        if (
            not isinstance(blanks, list)
            or any(
                not isinstance(v, str)
                or v not in {f"{face}-panel-{i}" for i in range(1, descriptor.panel_count + 1)}
                for v in blanks
            )
            or len(set(blanks)) != len(blanks)
        ):
            raise ValueError("Invalid blank panel assignments")
        artwork[key] = FaceArtwork((Path(base_dir) / path).resolve(), mode, tuple(blanks))
    return JCardConfig(
        profile,
        faces,
        sheet,
        margin,
        origin,
        flip,
        inset,
        tuple(k for k in ("cut", "fold", "registration") if guides.get(k, False)),
        **artwork,
    )
