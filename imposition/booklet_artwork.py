"""Reading-spread composition using PocketMod8 without importing a CLI."""

from .artwork_layout import MM_TO_PX, ArtworkLayout, PanelLayout, finite, rect
from .objects.pocketmod8 import POCKETMOD8, SUPPORTED_SHEETS


def resolve_booklet_spread(*, sheet_size, pages, margin_mm, gutter_mm):
    if sheet_size not in SUPPORTED_SHEETS:
        raise ValueError("unsupported sheet size")
    if (
        not isinstance(pages, (tuple, list))
        or len(pages) != 2
        or any(type(p) is not int for p in pages)
        or tuple(pages) not in POCKETMOD8.facing_spreads
    ):
        raise ValueError("unsupported reading spread")
    margin = finite(margin_mm, "margin_mm")
    gutter = finite(gutter_mm, "gutter_mm")
    if min(margin, gutter) < 0:
        raise ValueError("margins/gutter must be nonnegative")
    placement = POCKETMOD8.resolve_placement(SUPPORTED_SHEETS[sheet_size], {})
    # Retain the existing arithmetic order to preserve crop/transformation bytes.
    cell_width_mm, cell_height_mm = POCKETMOD8.cell_size(placement)
    W = cell_width_mm * MM_TO_PX
    H = cell_height_mm * MM_TO_PX
    M = margin * MM_TO_PX
    G = gutter * MM_TO_PX
    full = rect(0.0, 0.0, W, H)
    crops = (rect(M, M, W - G / 2, H - M), rect(G / 2, M, W - M, H - M))
    panels = tuple(
        PanelLayout(
            f"page-{page}",
            full,
            crops[i],
            (1.0, 0.0, 0.0, 1.0, i * W, 0.0),
            {"kind": "booklet-page", "page": page},
        )
        for i, page in enumerate(pages)
    )
    return ArtworkLayout(
        f"pocketmod8-{pages[0]}-{pages[1]}",
        "svg-px",
        (0.0, 0.0, 2 * W, H),
        panels,
        "validated",
        {
            "layout": "booklet-spread",
            "sheet_size": sheet_size,
            "pages": list(pages),
            "margin_mm": margin,
            "gutter_mm": gutter,
            "mm_to_px": MM_TO_PX,
        },
    )
