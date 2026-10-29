"""Rigid paired-face placement in a shared front-reference sheet datum."""

from dataclasses import dataclass

from .model import Guide, ObjectPlacement
from .objects.cassette_jcard import JCard


@dataclass(frozen=True)
class JCardPlacement:
    front_reference: ObjectPlacement
    matrices: tuple
    plot_guides: tuple
    diagnostic_guides: tuple

    def face_matrix(self, face):
        try:
            return dict(self.matrices)[face]
        except KeyError as exc:
            raise ValueError("Face is not selected") from exc

    def face_guides(self, face):
        self.face_matrix(face)
        return dict(self.plot_guides)[face]


def transform(matrix, point):
    a, b, c, d, e, f = matrix
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def resolve_jcard_placement(config):
    sw, sh = config.sheet.width_mm, config.sheet.height_mm
    w, h = JCard(profile=config.profile).trim_size_mm
    x, y = config.origin_mm if config.origin_mm is not None else ((sw - w) / 2, (sh - h) / 2)
    margin = config.margin_mm
    if x < margin or y < margin or x + w > sw - margin or y + h > sh - margin:
        raise ValueError("J-card trim does not fit drawable sheet at exact scale")
    front = ObjectPlacement(config.sheet, x, y, w, h)
    matrices, plotted, diagnostics = [], [], []
    for face in config.selected_faces:
        matrix = (1, 0, 0, 1, x, y)
        if face == "back":
            matrix = (
                (1, 0, 0, 1, sw - x - w, y)
                if config.flip == "left-right"
                else (-1, 0, 0, -1, x + w, sh - y)
            )
        matrices.append((face, matrix))
        guides = [
            Guide(g.kind, tuple(transform(matrix, p) for p in g.points), g.closed)
            for g in JCard(face, config.profile).native_guides()
            if g.kind in config.guides
        ]
        if "registration" in config.guides:
            for cx, cy in ((x - 2, y - 2), (x + w + 2, y - 2), (x - 2, y + h + 2)):
                if face == "back":
                    cx, cy = (sw - cx, cy) if config.flip == "left-right" else (cx, sh - cy)
                guides.extend(
                    (
                        Guide("registration", ((cx - 1, cy), (cx + 1, cy))),
                        Guide("registration", ((cx, cy - 1), (cx, cy + 1))),
                    )
                )
        if any(
            not (margin <= px <= sw - margin and margin <= py <= sh - margin)
            for g in guides
            for px, py in g.points
        ):
            raise ValueError("J-card guide or registration mark exceeds drawable sheet")
        plotted.append((face, tuple(guides)))
        safe = []
        inset = config.safe_inset_mm
        for slot in JCard(face, config.profile).slots:
            left, right = slot.polygon[0][0] * w, slot.polygon[1][0] * w
            safe.append(
                Guide(
                    "safe",
                    tuple(
                        transform(matrix, p)
                        for p in (
                            (left + inset, inset),
                            (right - inset, inset),
                            (right - inset, h - inset),
                            (left + inset, h - inset),
                        )
                    ),
                    True,
                )
            )
        diagnostics.append((face, tuple(safe)))
    return JCardPlacement(front, tuple(matrices), tuple(plotted), tuple(diagnostics))
