"""Nominal eight-panel cassette geometry, independent of paper placement."""

from dataclasses import dataclass
from fractions import Fraction

from ..jcard_profiles import DEFAULT_PROFILE, get_jcard_profile
from ..model import Guide, ObjectPlacement, OrientationTarget, Slot

PROFILE = DEFAULT_PROFILE


@dataclass(frozen=True)
class JCard:
    face: str = "front"
    profile: str = PROFILE
    object_id = "cassette-jcard"
    schema_version = 1

    def __post_init__(self):
        if self.face not in ("front", "back"):
            raise ValueError("Unsupported J-card face or profile")
        get_jcard_profile(self.profile)

    @property
    def panel_widths_mm(self):
        return get_jcard_profile(self.profile).panel_widths_mm

    @property
    def trim_size_mm(self):
        return get_jcard_profile(self.profile).trim_size_mm

    @property
    def slots(self):
        profile = get_jcard_profile(self.profile)
        numbers = (
            range(profile.panel_count)
            if self.face == "front"
            else range(profile.panel_count - 1, -1, -1)
        )
        x = Fraction(0)
        total = sum(profile.widths_inch)
        slots = []
        for i in numbers:
            end = x + profile.widths_inch[i]
            left, right = float(x / total), float(end / total)
            slots.append(
                Slot(
                    f"{self.face}-panel-{i + 1}",
                    "jcard-slot",
                    ((left, 0), (right, 0), (right, 1), (left, 1)),
                    OrientationTarget((0, -1)),
                )
            )
            x = end
        return tuple(slots)

    def native_guides(self):
        w, h = self.trim_size_mm
        return (Guide("cut", ((0, 0), (w, 0), (w, h), (0, h)), True),) + tuple(
            Guide("fold", ((slot.polygon[1][0] * w, 0), (slot.polygon[1][0] * w, h)))
            for slot in self.slots[:-1]
        )

    def resolve_placement(self, sheet, options):
        if options:
            raise ValueError("Use paired J-card placement for placement controls")
        w, h = self.trim_size_mm
        if sheet.width_mm < w or sheet.height_mm < h:
            raise ValueError("J-card does not fit sheet at exact scale")
        return ObjectPlacement(sheet, (sheet.width_mm - w) / 2, (sheet.height_mm - h) / 2, w, h)

    def guides(self, placement):
        if (placement.width_mm, placement.height_mm) != self.trim_size_mm:
            raise ValueError("J-card guides require exact scale")
        return tuple(
            Guide(
                g.kind,
                tuple((x + placement.x_mm, y + placement.y_mm) for x, y in g.points),
                g.closed,
            )
            for g in self.native_guides()
        )
