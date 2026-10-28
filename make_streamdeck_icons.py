#!/usr/bin/env python3
"""Ustvari ikone za Stream Deck / Stream Dock v videzu mmix.

Izpis:
    streamdeck/icons/                144 x 144 PNG, s slovenskimi podnapisi
    streamdeck/icons_clean/          144 x 144 PNG, brez podnapisov
    streamdeck/preview.png           pregledna plosca obeh kompletov
    streamdeck/mmix.streamDeckIconPack        paket za Elgato Stream Deck (144 px)
    streamdeck/streamdock/mmix.sdIconPack     paket za SOOMFON Stream Controller
    streamdeck/streamdock/mmix.sdIconPack.zip isti paket, pripravljen za prenos

Ikone so narisane 4x vecje in pomanjsane (LANCZOS), enako kot gumbi v mmix.py.
Barve so prepisane iz mmix.py, da skripta ne uvozi pycaw/comtypes.

Zagon:
    python make_streamdeck_icons.py
"""
from __future__ import annotations

import json
import math
import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "streamdeck"

# --- paleta mmix.py -------------------------------------------------------
BG = "#0b0d12"
CARD_TOP = "#171c25"
CARD_BOTTOM = "#0d1117"
CARD_DEEP = "#0a0e14"
EDGE = "#2b3546"
TEXT = "#eef1f7"
SUBTEXT = "#7d879a"
ACCENT = "#38bdf8"
ACCENT_SOFT = "#7dd3fc"
GREEN = "#34d399"
RED = "#fb7185"
RED_STRONG = "#ef4444"
TRACK = "#3c4658"
LABEL = "#98a3b5"

FONT_SEMIBOLD = "C:/Windows/Fonts/seguisb.ttf"
FONT_REGULAR = "C:/Windows/Fonts/segoeui.ttf"

SZ = 144          # ciljna velikost (Stream Deck 2x)
SS = 4            # nadvzorcenje
W = SZ * SS


# --- pomocniki ------------------------------------------------------------
def sc(v: float) -> int:
    """Logične pike -> pike visoke ločljivosti."""
    return int(round(v * SS))


def rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    return (*rgb(hex_color), alpha)


def mix(c1: str, c2: str, t: float) -> tuple[int, int, int]:
    a, b = rgb(c1), rgb(c2)
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def rounded_mask(radius: float = 24) -> Image.Image:
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, W - 1, W - 1], radius=sc(radius), fill=255
    )
    return mask


def gradient_card() -> Image.Image:
    img = Image.new("RGB", (W, W))
    px = img.load()
    for y in range(W):
        c = mix(CARD_TOP, CARD_BOTTOM, y / (W - 1))
        for x in range(W):
            px[x, y] = c
    return img.convert("RGBA")


def clip_alpha(layer: Image.Image, mask: Image.Image) -> Image.Image:
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return layer


def tri(d: ImageDraw.ImageDraw, tip: tuple[float, float], angle: float,
        length: float, width: float, color) -> None:
    """Trikotna konica puščice z vrhom v ``tip`` in smerjo ``angle`` (°)."""
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    bx, by = tip[0] - dx * length, tip[1] - dy * length
    px, py = -dy, dx
    d.polygon([
        tip,
        (bx + px * width / 2, by + py * width / 2),
        (bx - px * width / 2, by - py * width / 2),
    ], fill=color)


def dot(d: ImageDraw.ImageDraw, p: tuple[float, float], r: float, color) -> None:
    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)


# --- glifi ----------------------------------------------------------------
def speaker(d: ImageDraw.ImageDraw, cx: float, cy: float, u: float,
            color=TEXT, waves: int = 3, wave_color=None) -> None:
    """Zvočnik z valovi. ``u`` je 1 logična pika v pikslih visoke ločljivosti."""
    wave_color = wave_color or color
    x = cx - 30 * u
    body = [
        (x, cy - 10 * u),
        (x + 10 * u, cy - 10 * u),
        (x + 24 * u, cy - 25 * u),
        (x + 24 * u, cy + 25 * u),
        (x + 10 * u, cy + 10 * u),
        (x, cy + 10 * u),
    ]
    d.polygon(body, fill=rgba(color) if isinstance(color, str) else color)
    d.line(body + [body[0]], fill=rgba(color) if isinstance(color, str) else color,
           width=max(1, round(3 * u)), joint="curve")
    for i in range(waves):
        r = (13 + 10 * i) * u
        d.arc(
            [x + 24 * u - r, cy - r, x + 24 * u + r, cy + r],
            start=-48, end=48,
            fill=rgba(wave_color) if isinstance(wave_color, str) else wave_color,
            width=max(1, round(3.2 * u)),
        )


def chevron(d: ImageDraw.ImageDraw, cx: float, cy: float, u: float,
            color: str, up: bool = True) -> None:
    """Debela puščica ^ / v za glasneje/tišje."""
    w, h = 8.5 * u, 5.5 * u
    if up:
        pts = [(cx - w, cy + h), (cx, cy - h), (cx + w, cy + h)]
    else:
        pts = [(cx - w, cy - h), (cx, cy + h), (cx + w, cy - h)]
    lw = max(1, round(3.8 * u))
    d.line(pts, fill=rgba(color), width=lw, joint="curve")
    dot(d, pts[0], lw / 2, rgba(color))
    dot(d, pts[2], lw / 2, rgba(color))


def glyph_volume_up(d, cx, cy, size, accent):
    u = size / 64
    speaker(d, cx - 6 * u, cy + 1 * u, u, TEXT, waves=2, wave_color=accent)
    chevron(d, cx + 27 * u, cy - 19 * u, u, accent, up=True)


def glyph_volume_down(d, cx, cy, size, accent):
    u = size / 64
    speaker(d, cx - 6 * u, cy + 1 * u, u, TEXT, waves=2, wave_color=accent)
    chevron(d, cx + 27 * u, cy + 20 * u, u, accent, up=False)


def glyph_mute(d, cx, cy, size, accent):
    u = size / 64
    speaker(d, cx - 2 * u, cy, u, TEXT, waves=0)
    p1 = (cx - 30 * u, cy + 30 * u)
    p2 = (cx + 28 * u, cy - 28 * u)
    d.line([p1, p2], fill=rgba(CARD_DEEP), width=max(1, round(9 * u)))
    d.line([p1, p2], fill=rgba(RED_STRONG), width=max(1, round(5 * u)))
    dot(d, p1, 4.5 * u, rgba(RED_STRONG))
    dot(d, p2, 4.5 * u, rgba(RED_STRONG))


def glyph_sound(d, cx, cy, size, accent):
    u = size / 64
    speaker(d, cx - 2 * u, cy, u, TEXT, waves=3, wave_color=GREEN)


def glyph_master(d, cx, cy, size, accent):
    u = size / 64
    for xoff, knob, col in ((-19, -8, TEXT), (0, 7, accent), (19, -3, TEXT)):
        x = cx + xoff * u
        d.rounded_rectangle(
            [x - 2 * u, cy - 29 * u, x + 2 * u, cy + 29 * u],
            radius=2 * u, fill=rgba(TRACK),
        )
        d.rounded_rectangle(
            [x - 9 * u, cy + (knob - 5) * u, x + 9 * u, cy + (knob + 5) * u],
            radius=3 * u, fill=rgba(col),
        )


def glyph_device(d, cx, cy, size, accent):
    u = size / 64
    d.arc([cx - 26 * u, cy - 33 * u, cx + 26 * u, cy + 19 * u],
          start=180, end=360, fill=rgba(TEXT), width=max(1, round(5 * u)))
    d.rounded_rectangle([cx - 31 * u, cy - 8 * u, cx - 16 * u, cy + 19 * u],
                        radius=6 * u, fill=rgba(TEXT))
    d.rounded_rectangle([cx + 16 * u, cy - 8 * u, cx + 31 * u, cy + 19 * u],
                        radius=6 * u, fill=rgba(TEXT))
    y = cy + 28 * u
    d.line([cx - 22 * u, y, cx + 22 * u, y], fill=rgba(accent),
           width=max(1, round(3.6 * u)))
    tri(d, (cx - 26 * u, y), 180, 10 * u, 10 * u, rgba(accent))
    tri(d, (cx + 26 * u, y), 0, 10 * u, 10 * u, rgba(accent))


def glyph_refresh(d, cx, cy, size, accent):
    u = size / 64
    r = 24 * u
    box = [cx - r, cy - r, cx + r, cy + r]
    d.arc(box, start=40, end=322, fill=rgba(accent),
          width=max(1, round(5 * u)))
    a = math.radians(322)
    tip = (cx + math.cos(a) * r, cy + math.sin(a) * r)
    tri(d, tip, 322 + 90, 13 * u, 13 * u, rgba(accent))


def glyph_apps(d, cx, cy, size, accent):
    u = size / 64
    tile = 24 * u
    gap = 5 * u
    x0, y0 = cx - (2 * tile + gap) / 2, cy - (2 * tile + gap) / 2
    for row in range(2):
        for col in range(2):
            x, y = x0 + col * (tile + gap), y0 + row * (tile + gap)
            box = [x, y, x + tile, y + tile]
            if row == 0 and col == 1:
                d.rounded_rectangle(box, radius=5 * u, fill=rgba(accent))
                px = x + tile / 2
                py = y + tile / 2
                d.polygon([
                    (px - 3.5 * u, py - 6 * u),
                    (px + 6 * u, py),
                    (px - 3.5 * u, py + 6 * u),
                ], fill=rgba(CARD_DEEP))
            else:
                d.rounded_rectangle(
                    box, radius=5 * u, outline=rgba(TEXT, 210),
                    width=max(1, round(2.6 * u)),
                )


def glyph_open(d, cx, cy, size, accent):
    u = size / 64
    heights = (18, 32, 48, 32, 18)
    bw, gap = 8 * u, 4 * u
    total = len(heights) * bw + (len(heights) - 1) * gap
    x = cx - total / 2
    for i, h in enumerate(heights):
        col = accent if i == 2 else TEXT
        y0 = cy - h * u / 2
        d.rounded_rectangle(
            [x + i * (bw + gap), y0, x + i * (bw + gap) + bw, y0 + h * u],
            radius=bw / 2, fill=rgba(col),
        )


def glyph_ch_headphones(d, cx, cy, size, accent):
    u = size / 64
    d.arc([cx - 27 * u, cy - 34 * u, cx + 27 * u, cy + 20 * u],
          start=180, end=360, fill=rgba(TEXT), width=max(1, round(5 * u)))
    for x0, x1 in ((cx - 33 * u, cx - 18 * u), (cx + 18 * u, cx + 33 * u)):
        d.rounded_rectangle([x0, cy - 8 * u, x1, cy + 20 * u],
                            radius=7 * u, fill=rgba(TEXT))
    for x0, x1 in ((cx - 30 * u, cx - 21 * u), (cx + 21 * u, cx + 30 * u)):
        d.rounded_rectangle([x0, cy - 3 * u, x1, cy + 16 * u],
                            radius=4 * u, fill=rgba(accent))


def glyph_ch_monitor(d, cx, cy, size, accent):
    u = size / 64
    d.rounded_rectangle([cx - 31 * u, cy - 27 * u, cx + 31 * u, cy + 13 * u],
                        radius=6 * u, outline=rgba(TEXT),
                        width=max(1, round(4 * u)))
    d.rectangle([cx - 24 * u, cy - 20 * u, cx + 24 * u, cy + 5 * u],
                fill=rgba(accent, 55))
    d.line([cx, cy + 13 * u, cx, cy + 24 * u], fill=rgba(TEXT),
           width=max(1, round(4 * u)))
    d.line([cx - 15 * u, cy + 26 * u, cx + 15 * u, cy + 26 * u],
           fill=rgba(TEXT), width=max(1, round(4 * u)))


def action_badge(d, cx, cy, u, accent, symbol):
    """Barvna značka s +, - ali × v spodnjem desnem kotu glifa."""
    r = 13 * u
    d.ellipse([cx - r - 3 * u, cy - r - 3 * u,
               cx + r + 3 * u, cy + r + 3 * u], fill=rgba(CARD_DEEP))
    fill = RED_STRONG if symbol == "×" else accent
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgba(fill))
    fg = TEXT if symbol == "×" else CARD_DEEP
    font = ImageFont.truetype(FONT_SEMIBOLD, max(1, round(21 * u)))
    d.text((cx, cy + 0.5 * u), symbol, font=font, fill=rgba(fg), anchor="mm")


def channel_glyph(kind, symbol):
    def draw(d, cx, cy, size, accent):
        u = size / 64
        k = 0.82
        gx, gy = cx - 8 * u, cy - 8 * u
        if kind == "speakers":
            speaker(d, gx, gy, u * k, TEXT, waves=2, wave_color=accent)
        elif kind == "headphones":
            glyph_ch_headphones(d, gx, gy, size * k, accent)
        elif kind == "monitor":
            glyph_ch_monitor(d, gx, gy, size * k, accent)
        action_badge(d, cx + 25 * u, cy + 26 * u, u, accent, symbol)
    return draw


CHANNEL_PROFILES = (
    ("speakers", "ZVOČNIKI", ("zvočniki", "zvocniki", "speakers", "speaker")),
    ("headphones", "SLUŠALKE", ("slušalke", "slusalke", "headphones",
                                "headset")),
    ("monitor", "ZASLON", ("zaslon", "monitor", "display", "hdmi")),
)
CHANNEL_ACTIONS = (
    ("up", "+", "glasneje", ("volume up", "up", "plus"), ACCENT, ACCENT),
    ("down", "-", "tišje", ("volume down", "down", "minus"), ACCENT, ACCENT),
    ("mute", "×", "utišaj", ("mute", "x"), RED, RED_STRONG),
)

BASE_GLYPHS = {
    "volume_up": glyph_volume_up,
    "volume_down": glyph_volume_down,
    "mute": glyph_mute,
    "sound": glyph_sound,
    "master": glyph_master,
    "device": glyph_device,
    "refresh": glyph_refresh,
    "apps": glyph_apps,
    "open": glyph_open,
    "blank": None,
}
GLYPHS = dict(BASE_GLYPHS)
CHANNEL_ICONS = []
for _profile, _plabel, _aliases in CHANNEL_PROFILES:
    for _kind, _symbol, _alabel, _atags, _accent, _glow in CHANNEL_ACTIONS:
        _slug = f"ch_{_profile}_{_kind}"
        GLYPHS[_slug] = channel_glyph(_profile, _symbol)
        CHANNEL_ICONS.append((_slug, f"{_plabel} {_symbol}",
                              _accent, _glow))

BASE_ICONS = [
    ("volume_up", "GLASNEJE", ACCENT, ACCENT),
    ("volume_down", "TIŠJE", ACCENT, ACCENT),
    ("mute", "UTIŠAJ", RED, RED_STRONG),
    ("sound", "ZVOK", GREEN, GREEN),
    ("master", "MASTER", ACCENT, ACCENT),
    ("device", "NAPRAVA", ACCENT, ACCENT),
    ("refresh", "OSVEŽI", ACCENT, ACCENT),
    ("apps", "APLIKACIJE", ACCENT, ACCENT),
    ("open", "MMIX", ACCENT, ACCENT),
    ("blank", "", LABEL, ACCENT),
]

# Kanalske ikone sledijo ikoni MASTER, da so v knjižnici skupaj.
ICONS = []
for _item in BASE_ICONS:
    ICONS.append(_item)
    if _item[0] == "master":
        ICONS.extend(CHANNEL_ICONS)

# Imena in oznake za knjižnico Stream Deck (iskalnik po njih filtrira).
PACK_ID = "mmix"
PACK_VERSION = "1.5.0"
PACK_FILE = OUT / "mmix.streamDeckIconPack"
SD_DIR = OUT / "streamdock"
SD_ICON_SIZE = 128       # uradna priporocena velikost za Stream Dock
SD_PACK_ICON = 64        # ikona paketa v knjiznici
SD_PACK_COLOR = "#c8c8c8"
PACK_NAMES = {
    "volume_up": ("Glasneje", ["mmix", "glasnost", "glasneje", "volume up"]),
    "volume_down": ("Tišje", ["mmix", "glasnost", "tišje", "volume down"]),
    "mute": ("Utišaj", ["mmix", "glasnost", "utišaj", "mute"]),
    "sound": ("Zvok", ["mmix", "glasnost", "zvok", "sound", "unmute"]),
    "master": ("Master", ["mmix", "glasnost", "master", "vsi izhodi"]),
    "device": ("Naprava", ["mmix", "naprava", "izhod", "device"]),
    "refresh": ("Osveži", ["mmix", "osveži", "refresh", "naprave"]),
    "apps": ("Aplikacije", ["mmix", "aplikacije", "apps", "usmerjanje"]),
    "open": ("mmix", ["mmix", "odpri", "show", "aplikacija"]),
    "blank": ("Prazno", ["mmix", "prazno", "blank", "ozadje"]),
}

# Imena kanalskih ikon: iskalnik najde tudi po vrsti kanala in dejanju.
for _profile, _plabel, _aliases in CHANNEL_PROFILES:
    for _kind, _symbol, _alabel, _atags, _accent, _glow in CHANNEL_ACTIONS:
        _slug = f"ch_{_profile}_{_kind}"
        PACK_NAMES[_slug] = (
            f"{_plabel} {_symbol}",
            ["mmix", "kanal", "channel", _plabel.lower(), *_aliases,
             _alabel, *_atags],
        )
PACK_LICENSE = """mmix · ikone za Stream Deck
================================

Ikone so del projekta mmix in so namenjene uporabi z aplikacijo mmix.
Vse pravice pridrzane. Barve in oblike sledijo videzu mmix.

Privzete globalne bliznjice v mmix:
  Ctrl+Alt+Shift+Up     glasneje
  Ctrl+Alt+Shift+Down   tisje
  Ctrl+Alt+Shift+M      utisaj / vklopi zvok
  Ctrl+Alt+Shift+O      prikazi mmix
  Ctrl+Alt+Shift+R      osvezi naprave

Kanalske bliznjice (mmix > Bliznjice > Kanali):
  Za vsak kanal (MASTER, zvocniki, slusalke, zaslon ...) nastavis svoje
  tri kombinacije: glasneje, tisje in utisaj. Vsaki tipki na Stream
  Controllerju dodelis svojo kombinacijo, ikona pa pove, kateri kanal
  in katero dejanje tipka upravlja.
"""


# --- sestavljanje ikone ---------------------------------------------------
def draw_label(img: Image.Image, text: str, color: str) -> None:
    if not text:
        return
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_SEMIBOLD, sc(15.5))
    tracking = sc(1.8)
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (W - total) / 2
    baseline = sc(129)
    for ch, w in zip(text, widths):
        d.text((x, baseline), ch, font=font, fill=rgba(color), anchor="ls")
        x += w + tracking


def render(slug: str, label: str, accent: str, glow: str, *,
           labelled: bool = True) -> Image.Image:
    mask = rounded_mask()
    base = gradient_card()

    glow_layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.ellipse([W * 0.20, -sc(34), W * 0.80, sc(112)],
               fill=rgba(glow, 46 if labelled else 38))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(sc(26)))
    base.alpha_composite(clip_alpha(glow_layer, mask))

    sheen = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sheen)
    sd.polygon([(0, 0), (W * 0.64, 0), (W * 0.30, W * 0.62), (0, W * 0.62)],
               fill=(255, 255, 255, 7))
    sheen = sheen.filter(ImageFilter.GaussianBlur(sc(14)))
    base.alpha_composite(clip_alpha(sheen, mask))

    glyph = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    if GLYPHS[slug] is not None:
        g = ImageDraw.Draw(glyph)
        cy, size = (56, 67) if labelled else (72, 82)
        GLYPHS[slug](g, sc(72), sc(cy), sc(size), accent)

        shadow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        shadow.putalpha(glyph.getchannel("A").filter(ImageFilter.GaussianBlur(sc(3))))
        base.alpha_composite(shadow, (0, sc(2)))
        base.alpha_composite(glyph)

    border = ImageDraw.Draw(base)
    border.rounded_rectangle(
        [sc(1.5), sc(1.5), W - sc(1.5), W - sc(1.5)],
        radius=sc(23), outline=rgba(EDGE), width=sc(2),
    )

    if labelled:
        label_color = (accent if (slug in ("master", "mute", "sound")
                                  or slug.startswith("ch_")) else LABEL)
        draw_label(base, label, label_color)

    base.putalpha(mask)
    return base.resize((SZ, SZ), Image.Resampling.LANCZOS)


# --- pregled --------------------------------------------------------------
def make_preview() -> Image.Image:
    cols = 5
    cell_w, cell_h = 176, 194
    margin = 30
    rows = (len(ICONS) + cols - 1) // cols
    section_h = 42 + rows * cell_h + 20
    width = margin * 2 + cols * cell_w
    height = 126 + 2 * section_h + 60
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    f_title = ImageFont.truetype(FONT_SEMIBOLD, 34)
    f_sub = ImageFont.truetype(FONT_REGULAR, 14)
    f_section = ImageFont.truetype(FONT_SEMIBOLD, 16)
    f_cap = ImageFont.truetype(FONT_REGULAR, 13)

    d.text((margin, 40), "mmix", font=f_title, fill=ACCENT)
    d.text((margin + 92, 52), "STREAM DECK · DOCK", font=f_title, fill=TEXT)
    d.text((margin, 84), "Ikone za nadzor mmix · temna tema mmix · 144 px / 128 px",
           font=f_sub, fill=SUBTEXT)

    sections = [(True, "S PODNAPISI", 126),
                (False, "BREZ PODNAPISOV", 126 + section_h)]
    for labelled, title, y in sections:
        d.text((margin, y), title, font=f_section, fill=SUBTEXT)
        d.line([margin, y + 26, width - margin, y + 26], fill="#1e2532", width=1)
        for i, (slug, label, accent, _glow) in enumerate(ICONS):
            icon = render(slug, label, accent, _glow, labelled=labelled)
            col, row = i % cols, i // cols
            x = margin + col * cell_w + (cell_w - SZ) // 2
            yy = y + 42 + row * cell_h
            img.paste(icon, (x, yy), icon)
            tw = d.textlength(slug, font=f_cap)
            d.text((x + (SZ - tw) / 2, yy + SZ + 8), slug, font=f_cap, fill=SUBTEXT)

    footer = ("SOOMFON Stream Controller: mapo streamdock/mmix.sdIconPack kopiraj "
              "v mapo icons.  Elgato: dvoklikni mmix.streamDeckIconPack.")
    d.text((margin, height - 30), footer, font=f_sub, fill="#4a5366")
    return img


# --- paketi ---------------------------------------------------------------
def pack_entries(suffix: str) -> list[dict]:
    """Vsebina icons.json: vsak motiv z napisom in brez njega."""
    entries = []
    for slug, _label, _accent, _glow in ICONS:
        name, tags = PACK_NAMES[slug]
        pairs = (
            (name, f"{slug}.png", [suffix]),
            (f"{name} (brez napisa)", f"{slug}_clean.png",
             ["brez napisa", suffix]),
        )
        for label, filename, extra in pairs:
            seen: list[str] = []
            for tag in (*tags, *extra):
                if tag not in seen:
                    seen.append(tag)
            entries.append({"path": filename, "name": label, "tags": seen})
    return entries


def make_pack_icon(size: int, background: str | None = None) -> Image.Image:
    """Ikona paketa za knjiznico.

    Stream Dock priporoca 64 x 64 px na podlagi #c8c8c8, zato je kartica mmix
    tam pomanjsana in sedi na svetlem kvadratu. Brez podlage (Elgato) je
    kartica cez celo sliko.
    """
    card = render("open", "MMIX", ACCENT, ACCENT, labelled=False)
    if background is None:
        return card.resize((size, size), Image.Resampling.LANCZOS)
    inner = round(size * 0.75)
    card = card.resize((inner, inner), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=size // 6,
        fill=rgba(background),
    )
    canvas.alpha_composite(card, ((size - inner) // 2, (size - inner) // 2))
    return canvas


PACK_DESCRIPTION = ("Ikone za nadzor glasnosti mmix: glasneje, tišje, utišaj, "
                    "master, kanali (zvočniki, slušalke, zaslon), naprave in "
                    "osvežitev.")


def make_icon_pack() -> Path:
    """Zgradi .streamDeckIconPack (ZIP z mapo mmix.sdIconPack).

    Struktura sledi Elgatinemu formatu: manifest.json, icons.json, icon.png,
    license.txt in icons/ s slikami 144 x 144. Poleg ZIP-a ostane tudi
    razpakirana mapa mmix.sdIconPack za ročno namestitev v IconPacks.
    """
    root = f"{PACK_ID}.sdIconPack"
    pack_dir = OUT / root
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    (pack_dir / "icons").mkdir(parents=True)

    manifest = {
        "Name": "mmix",
        "Version": PACK_VERSION,
        "Description": PACK_DESCRIPTION,
        "Author": "JBJ",
        "Icon": "icon.png",
        "License": "license.txt",
    }

    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (pack_dir / "icons.json").write_text(
        json.dumps(pack_entries("stream deck"), ensure_ascii=False, indent=2),
        encoding="utf-8")
    (pack_dir / "license.txt").write_text(PACK_LICENSE, encoding="utf-8")
    make_pack_icon(56).save(pack_dir / "icon.png", "PNG")
    for slug, _label, _accent, _glow in ICONS:
        shutil.copy2(OUT / "icons" / f"{slug}.png",
                     pack_dir / "icons" / f"{slug}.png")
        shutil.copy2(OUT / "icons_clean" / f"{slug}.png",
                     pack_dir / "icons" / f"{slug}_clean.png")

    with zipfile.ZipFile(PACK_FILE, "w", zipfile.ZIP_DEFLATED) as pack:
        for path in sorted(pack_dir.rglob("*")):
            if path.is_file():
                pack.write(path, path.relative_to(OUT).as_posix())
    return PACK_FILE


def make_streamdock_pack() -> Path:
    """Zgradi paket za SOOMFON Stream Controller / Stream Dock.

    Za razliko od Elgata velja:

      * ikone so 128 x 128 px (uradno priporocilo),
      * ikona paketa je 64 x 64 px na podlagi #c8c8c8,
      * manifest ima "Images": "icons",
      * JSON je zapisan kot ASCII (\\u0161 ...), da ga aplikacija prebere
        enako ne glede na kodno stran sistema.
    """
    root = f"{PACK_ID}.sdIconPack"
    pack_dir = SD_DIR / root
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    (pack_dir / "icons").mkdir(parents=True)

    manifest = {
        "Name": "mmix",
        "Version": PACK_VERSION,
        "Description": PACK_DESCRIPTION,
        "Author": "JBJ",
        "URL": "",
        "Icon": "icon.png",
        "Images": "icons",
        "License": "license.txt",
    }
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    (pack_dir / "icons.json").write_text(
        json.dumps(pack_entries("stream dock"), ensure_ascii=True, indent=2),
        encoding="utf-8")
    (pack_dir / "license.txt").write_text(PACK_LICENSE, encoding="utf-8")
    make_pack_icon(SD_PACK_ICON, SD_PACK_COLOR).save(
        pack_dir / "icon.png", "PNG", optimize=True)

    for slug, label, accent, glow in ICONS:
        for labelled, filename in ((True, f"{slug}.png"),
                                   (False, f"{slug}_clean.png")):
            icon = render(slug, label, accent, glow, labelled=labelled)
            icon.resize((SD_ICON_SIZE, SD_ICON_SIZE),
                        Image.Resampling.LANCZOS).save(
                pack_dir / "icons" / filename, "PNG", optimize=True)

    archive = SD_DIR / f"{root}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as pack:
        for path in sorted(pack_dir.rglob("*")):
            if path.is_file():
                pack.write(path, path.relative_to(SD_DIR).as_posix())
    return archive


# --- main -----------------------------------------------------------------
def main() -> None:
    (OUT / "icons").mkdir(parents=True, exist_ok=True)
    (OUT / "icons_clean").mkdir(parents=True, exist_ok=True)
    SD_DIR.mkdir(parents=True, exist_ok=True)

    for slug, label, accent, glow in ICONS:
        render(slug, label, accent, glow, labelled=True).save(
            OUT / "icons" / f"{slug}.png"
        )
        render(slug, label, accent, glow, labelled=False).save(
            OUT / "icons_clean" / f"{slug}.png"
        )

    make_preview().save(OUT / "preview.png")
    elgato = make_icon_pack()
    streamdock = make_streamdock_pack()
    print(f"Gotovo: {len(ICONS)} ikon × 2 kompleta + preview -> {OUT}")
    print(f"Elgato Stream Deck   -> {elgato}")
    print(f"SOOMFON Stream Dock  -> {SD_DIR / 'mmix.sdIconPack'}")
    print(f"  zip za prenos      -> {streamdock}")


if __name__ == "__main__":
    main()
