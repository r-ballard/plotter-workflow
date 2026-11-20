"""Declarative physical imposition objects."""

from .cootie_catcher import (
    COOTIE_CATCHER,
    EXPECTED_SLOTS,
    LEGACY_ROTATIONS,
    PANEL_POLYGONS,
    SELECTOR_REVEAL_PAIRS,
    SUPPORTED_SHEETS,
    CootieCatcher,
    CootieCatcherError,
)
from .kaleidocycle import Kaleidocycle
from .pocketmod8 import POCKETMOD8, PocketMod8

__all__ = [
    "COOTIE_CATCHER",
    "EXPECTED_SLOTS",
    "LEGACY_ROTATIONS",
    "PANEL_POLYGONS",
    "POCKETMOD8",
    "SELECTOR_REVEAL_PAIRS",
    "SUPPORTED_SHEETS",
    "CootieCatcher",
    "CootieCatcherError",
    "Kaleidocycle",
    "PocketMod8",
]
