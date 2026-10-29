"""Verified, immutable manufacturer geometry; panel count is not a recipe."""

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from types import MappingProxyType

DEFAULT_PROFILE = "nac-jcard-8-panel-v1"
MM_PER_INCH = Fraction(127, 5)


@dataclass(frozen=True)
class JCardProfile:
    profile_id: str
    widths_inch: tuple[Fraction, ...]
    height_inch: Fraction
    roles: tuple[str, ...]
    safe_inset_mm: Decimal
    bleed_reference_mm: Decimal
    source_urls: tuple[str, str]
    source_sha256: tuple[str, str]

    @property
    def panel_widths_mm(self):
        return tuple(float(w * MM_PER_INCH) for w in self.widths_inch)

    @property
    def trim_size_mm(self):
        return float(sum(self.widths_inch) * MM_PER_INCH), float(self.height_inch * MM_PER_INCH)

    @property
    def panel_count(self):
        return len(self.widths_inch)


def _standard(number, sixteenths, digest):
    url = f"https://standardcassette.com/templates/{number}-Panel-J-Card-Template.pdf"
    return JCardProfile(
        f"standard-jcard-{number}-panel-v1",
        tuple(Fraction(n, 16) for n in sixteenths),
        Fraction(4),
        ("tracklisting", "title-spine", "front-art")
        + tuple(f"extension-{i}" for i in range(1, number - 2)),
        Decimal("1.5875"),
        Decimal("3.175"),
        (url + "#page=1", url + "#page=2"),
        (digest, digest),
    )


_RECORDS = (
    _standard(3, (16, 8, 41), "13d838d64f7021af1864bc470e5ba7ef9913a4d9901b3b77726f95a014161d61"),
    _standard(
        4, (17, 8, 41, 40), "c20395b4b160874c118407a369fb1248e9c2ade27bee946bca37299a23a467ca"
    ),
    _standard(
        5, (17, 8, 41, 40, 39), "e6b0d3079205bd1e1c36131fd25aca0c323b760c9d700523e239419bf6660111"
    ),
    _standard(
        6,
        (17, 8, 41, 40, 39, 38),
        "597b3aabf78e500a0a4f67bda0f338feb0bafae19461cabe7b7f68b0c3d2349a",
    ),
    _standard(
        7,
        (17, 8, 41, 40, 39, 38, 37),
        "00dd73b19dec097175e5e77ecae43d0abb02dc99d3c7f59108ec5dd9cc310180",
    ),
    _standard(
        8,
        (17, 8, 41, 40, 39, 38, 37, 36),
        "7c0d2e1bbe00c0c327fe1f64efaba6ba6ee8485a02e07f9422d9d0b369b325ee",
    ),
    JCardProfile(
        DEFAULT_PROFILE,
        tuple(Fraction(n, 16) for n in (17, 8, 41, 40, 39, 38, 37, 36)),
        Fraction(4),
        ("tracklisting", "title-spine", "front-art") + tuple(f"extension-{i}" for i in range(1, 6)),
        Decimal("1.5875"),
        Decimal("3.175"),
        tuple(
            f"https://nationalaudiocompany.com/wp-content/uploads/2017/08/NAC_Jcard_8-Panel_{face}_Template_AI5.pdf"
            for face in ("FRONT", "BACK")
        ),
        (
            "8dfe10291a646e884b4c317ed1cc6b847d9db53a3590c9c6eb47c193f08a5e80",
            "8552dd0c28befa0c4fc2d435df7691e2d4df10e9ae00560c63340c008d6fad0b",
        ),
    ),
)
PROFILES = MappingProxyType({profile.profile_id: profile for profile in _RECORDS})


def get_jcard_profile(profile_id: str) -> JCardProfile:
    if not isinstance(profile_id, str) or profile_id not in PROFILES:
        raise ValueError("Unsupported J-card profile")
    return PROFILES[profile_id]
