#!/usr/bin/env python3
"""Generate key-style icons for the mmix Stream Controller plugin.

Writes 144x144 PNGs into:
    %APPDATA%\\HotSpot\\StreamDock\\plugins\\com.jbj.mmix.sdPlugin\\icon\\

Icons follow mmix styling: dark card, blue accent, red mute.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------- constants
PLUGIN_DIR = (
    Path(os.environ["APPDATA"])
    / "HotSpot"
    / "StreamDock"
    / "plugins"
    / "com.jbj.mmix.sdPlugin"
)
ICON_DIR = PLUGIN_DIR / "icon"

SIZE = 144
SS = 4               # supersampling
W = SIZE * SS

ACCENT = "#38bdf8"
RED = "#ef4444"
BG_TOP = "#1b2230"
BG_BOTTOM = "#121722"
BORDER = "#3a4458"


def sc(v: float) -> int:
    """Scale a value from output space to supersampled space."""
    return int(round(v * SS))


def rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def mix(c1: str, c2: str, t: float) -> tuple[int, int, int]:
    a, b = rgba(c1), rgba(c2)
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))  # type: ignore[return-value]


# ---------------------------------------------------------------- base card
def card_mask(radius: float = 14.0) -> Image.Image:
    mask = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle(
        [sc(6), sc(6), W - sc(6) - 1, W - sc(6) - 1],
        radius=sc(radius),
        fill=255,
    )
    return mask


def make_base() -> Image.Image:
    mask = card_mask()

    # vertical gradient body
    body = Image.new("RGB", (W, W))
    px = body.load()
    for y in range(W):
        color = mix(BG_TOP, BG_BOTTOM, y / (W - 1))
        for x in range(W):
            px[x, y] = color
    body = body.convert("RGBA")
    body.putalpha(mask)

    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    img.alpha_composite(body)

    # soft top highlight
    hl = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle(
        [sc(8), sc(8), W - sc(8), sc(34)],
        radius=sc(10),
        fill=rgba("#ffffff", 10),
    )
    hl = hl.filter(ImageFilter.GaussianBlur(sc(4)))
    hl.putalpha(Image.composite(hl.getchannel("A"), Image.new("L", (W, W), 0), mask))
    img.alpha_composite(hl)

    # border
    border = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        [sc(6), sc(6), W - sc(6) - 1, W - sc(6) - 1],
        radius=sc(14),
        outline=rgba(BORDER, 215),
        width=sc(1.6),
    )
    img.alpha_composite(border)
    return img


# ---------------------------------------------------------------- glyphs
def draw_plus(d: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color):
    arm = size // 2
    width = max(sc(3), size // 5)
    d.rounded_rectangle(
        [cx - width // 2, cy - arm, cx + width // 2, cy + arm],
        radius=width // 2,
        fill=color,
    )
    d.rounded_rectangle(
        [cx - arm, cy - width // 2, cx + arm, cy + width // 2],
        radius=width // 2,
        fill=color,
    )


def draw_minus(d: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color):
    arm = size // 2
    width = max(sc(3), size // 5)
    d.rounded_rectangle(
        [cx - arm, cy - width // 2, cx + arm, cy + width // 2],
        radius=width // 2,
        fill=color,
    )


def draw_speaker(
    d: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color, muted: bool
) -> None:
    """Speaker box + cone (+ optional red slash)."""
    s = size
    # box
    d.rounded_rectangle(
        [cx - s // 2, cy - s // 6, cx - s // 4, cy + s // 6],
        radius=max(sc(1), s // 20),
        fill=color,
    )
    # cone
    d.polygon(
        [
            (cx - s // 4, cy - s // 6),
            (cx + s // 12, cy - s // 2),
            (cx + s // 12, cy + s // 2),
            (cx - s // 4, cy + s // 6),
        ],
        fill=color,
    )
    if not muted:
        # sound waves
        for i, r in enumerate((s // 3, s // 2)):
            d.arc(
                [cx + s // 10 - r, cy - r, cx + s // 10 + r, cy + r],
                start=-55,
                end=55,
                fill=color,
                width=max(sc(2), s // 12),
            )
    else:
        # red slash
        d.line(
            [(cx - s // 2, cy + s // 2), (cx + s // 2, cy - s // 2)],
            fill=rgba(RED),
            width=max(sc(3), s // 9),
        )


def draw_headphones(
    d: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color, muted: bool
) -> None:
    s = size
    width = max(sc(2), s // 10)
    d.arc(
        [cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2],
        start=180,
        end=360,
        fill=color,
        width=width,
    )
    cup_w = s // 5
    cup_h = s // 3
    d.rounded_rectangle(
        [cx - s // 2, cy - s // 12, cx - s // 2 + cup_w, cy - s // 12 + cup_h],
        radius=max(sc(2), cup_w // 3),
        fill=color,
    )
    d.rounded_rectangle(
        [cx + s // 2 - cup_w, cy - s // 12, cx + s // 2, cy - s // 12 + cup_h],
        radius=max(sc(2), cup_w // 3),
        fill=color,
    )
    if muted:
        d.line(
            [(cx - s // 2, cy + s // 2), (cx + s // 2, cy - s // 2)],
            fill=rgba(RED),
            width=max(sc(3), s // 9),
        )


def draw_monitor(
    d: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color, muted: bool
) -> None:
    s = size
    width = max(sc(3), s // 12)
    d.rounded_rectangle(
        [cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 6],
        radius=max(sc(3), s // 12),
        outline=color,
        width=width,
    )
    d.rounded_rectangle(
        [cx - s // 14, cy + s // 6, cx + s // 14, cy + s // 2],
        radius=max(sc(1), s // 30),
        fill=color,
    )
    if muted:
        d.line(
            [(cx - s // 2, cy + s // 2), (cx + s // 2, cy - s // 2)],
            fill=rgba(RED),
            width=max(sc(3), s // 9),
        )


def draw_master(d: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color):
    """Three sliders - master/general look."""
    s = size
    width = max(sc(2), s // 15)
    step = s // 3
    heights = (s // 6, s // 2, s // 3)
    for i, h in enumerate(heights):
        x = cx - s // 3 + i * step
        d.line([(x, cy - s // 2), (x, cy + s // 2)], fill=rgba(BORDER, 255), width=width)
        d.ellipse(
            [x - width * 1.4, cy - s // 2 + h - width * 1.4,
             x + width * 1.4, cy - s // 2 + h + width * 1.4],
            fill=color,
        )


def draw_open(d: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color):
    s = size
    width = max(sc(3), s // 12)
    d.rounded_rectangle(
        [cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2],
        radius=max(sc(3), s // 10),
        outline=color,
        width=width,
    )
    d.rounded_rectangle(
        [cx - s // 6, cy - s // 6, cx + s // 6, cy + s // 6],
        radius=max(sc(1), s // 30),
        fill=color,
    )


def draw_refresh(d: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color):
    s = size
    width = max(sc(3), s // 12)
    r = s // 2
    d.arc([cx - r, cy - r, cx + r, cy + r], start=200, end=340, fill=color, width=width)
    d.polygon(
        [
            (cx + s // 4, cy - s // 3),
            (cx + s // 2, cy - s // 6),
            (cx + s // 6, cy - s // 12),
        ],
        fill=color,
    )


# ---------------------------------------------------------------- render
def render(symbol: str, color: str, muted_slash: bool = False) -> Image.Image:
    img = make_base()
    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    cx = cy = W // 2
    size = sc(62)
    col = rgba(color)

    if symbol == "plus":
        draw_plus(d, cx, cy, size, col)
    elif symbol == "minus":
        draw_minus(d, cx, cy, size, col)
    elif symbol == "speaker":
        draw_speaker(d, cx, cy, size, col, muted_slash)
    elif symbol == "headphones":
        draw_headphones(d, cx, cy, size, col, muted_slash)
    elif symbol == "monitor":
        draw_monitor(d, cx, cy, size, col, muted_slash)
    elif symbol == "master":
        draw_master(d, cx, cy, size, col)
    elif symbol == "open":
        draw_open(d, cx, cy, size, col)
    elif symbol == "refresh":
        draw_refresh(d, cx, cy, size, col)
    else:
        raise ValueError(f"unknown symbol: {symbol}")

    # soft glow behind the glyph
    glow = layer.filter(ImageFilter.GaussianBlur(sc(3)))
    glow.putalpha(glow.getchannel("A").point(lambda a: int(a * 0.55)))
    img.alpha_composite(glow)
    img.alpha_composite(layer)

    img.putalpha(card_mask())
    return img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


# ---------------------------------------------------------------- outputs
VARIANTS = [
    ("master_up", "plus", ACCENT, False),
    ("master_down", "minus", ACCENT, False),
    ("master_mute", "speaker", ACCENT, True),
    ("speakers_up", "speaker", ACCENT, False),
    ("speakers_down", "minus", ACCENT, False),
    ("speakers_mute", "speaker", ACCENT, True),
    ("headphones_up", "headphones", ACCENT, False),
    ("headphones_down", "minus", ACCENT, False),
    ("headphones_mute", "headphones", ACCENT, True),
    ("monitor_up", "monitor", ACCENT, False),
    ("monitor_down", "minus", ACCENT, False),
    ("monitor_mute", "monitor", ACCENT, True),
    ("open", "open", ACCENT, False),
    ("refresh", "refresh", ACCENT, False),
    ("plugin", "master", ACCENT, False),
    ("category", "master", ACCENT, False),
]


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    for name, symbol, color, slash in VARIANTS:
        img = render(symbol, color, slash)
        out = ICON_DIR / f"{name}.png"
        img.save(out)
        print(f"saved: {out.name} ({out.stat().st_size} B)")
    print(f"DONE - {len(VARIANTS)} icons in {ICON_DIR}")


if __name__ == "__main__":
    main()
