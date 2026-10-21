import math
import pytest
import scripts.booklet_impose as booklet


@pytest.mark.parametrize("pages", [(2, 3), (4, 5), (6, 7), (8, 1)])
def test_reading_spread_geometry_and_crop(pages):
    from imposition.artwork_layout import resolve_booklet_spread

    layout = resolve_booklet_spread(
        sheet_size="letter", pages=pages, margin_mm=3.0, gutter_mm=2.0
    )
    W = 279.4 / 4 * booklet.MM_TO_PX
    H = 215.9 / 2 * booklet.MM_TO_PX
    M = 3 * booklet.MM_TO_PX
    G = 2 * booklet.MM_TO_PX
    assert layout.window == pytest.approx((0, 0, 2 * W, H))
    assert [p.panel_id for p in layout.panels] == [f"page-{p}" for p in pages]

    class Recorder:
        def __init__(self):
            self.crops = []

        def scale(self, *a):
            pass

        def translate(self, *a):
            pass

        def crop(self, *a):
            self.crops.append(a)

    for i, p in enumerate(layout.panels):
        assert p.canvas_polygon == ((0.0, 0.0), (W, 0.0), (W, H), (0.0, H))
        assert p.assembled_matrix == (1.0, 0.0, 0.0, 1.0, i * W, 0.0)
        recorder = Recorder()
        booklet._render_spread_half(
            recorder,
            2 * W,
            H,
            page=pages[i],
            half="left" if i == 0 else "right",
            cell_width=W,
            cell_height=H,
            margin=M,
            gutter=G,
            fit="contain",
        )
        x0, y0, x1, y1 = recorder.crops[-1]
        expected = (
            (x0 - i * W, y0),
            (x1 - i * W, y0),
            (x1 - i * W, y1),
            (x0 - i * W, y1),
        )
        for a, b in zip(p.crop_polygon, expected):
            assert a == pytest.approx(b)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(pages=(1, 2)),
        dict(pages=(2, 2)),
        dict(pages=(True, 3)),
        *[dict(margin_mm=v) for v in [-1.0, True, "1", math.inf, math.nan, 1000.0]],
        *[dict(gutter_mm=v) for v in [-1.0, True, "1", math.inf, 1000.0]],
    ],
)
def test_invalid_and_collapsed_spreads(kwargs):
    from imposition.artwork_layout import resolve_booklet_spread

    with pytest.raises(ValueError):
        resolve_booklet_spread(
            **(
                dict(sheet_size="letter", pages=(2, 3), margin_mm=0.0, gutter_mm=0.0)
                | kwargs
            )
        )
