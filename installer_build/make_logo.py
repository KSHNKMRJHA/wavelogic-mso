"""Generate the WaveLogic MSO wave/signal logo (PNG banner + ICO icon)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import numpy as np

OUT_DIR = Path(__file__).resolve().parent / "src"

BG = (11, 18, 32)
GRID = (28, 42, 68)
GRID_MAJOR = (43, 62, 100)
CYAN = (102, 217, 232)
AMBER = (255, 212, 59)
WHITE = (241, 245, 251)
GRAY = (138, 157, 189)
DIM = (94, 112, 148)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def grid(draw: ImageDraw.ImageDraw, w: int, h: int, x0: int, y0: int,
         x1: int, y1: int, step: int = 44) -> None:
    for x in range(x0, x1 + 1, step):
        color = GRID_MAJOR if (x - x0) % (step * 4) == 0 else GRID
        draw.line([(x, y0), (x, y1)], fill=color, width=1)
    for y in range(y0, y1 + 1, step):
        color = GRID_MAJOR if (y - y0) % (step * 4) == 0 else GRID
        draw.line([(x0, y), (x1, y)], fill=color, width=1)


def poly(xs, ys) -> list[tuple[int, int]]:
    return list(zip([int(round(v)) for v in xs],
                    [int(round(v)) for v in ys]))


def draw_trace(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int,
               chan: str, seed: int, freq: float) -> None:
    n = x1 - x0
    t = np.linspace(0, freq * 2.0 * np.pi, n)
    rng = np.random.default_rng(seed)
    base = np.sin(t) + 0.35 * np.sin(t * 3.31 + 1.2) + 0.15 * np.sin(t * 7.7 + 0.4)
    base += rng.normal(0, 0.03, n)
    base -= base.min()
    base /= base.max()
    if chan == "AMBER":
        base = np.where(base > 0.5, 1.0, -0.06)
        for i in range(1, n):
            prev, cur = base[i - 1], base[i]
            if (prev < 0 < cur) != (prev_rising if False else False):
                pass
            if prev != cur and (prev < 0) != (cur < 0):
                edge = i
                base[max(0, edge - 12):edge + 13] = np.clip(
                    np.linspace(prev * 0.0 + (1 if prev > 0 else -1) * 0.0,
                                cur * 0.0 + 1 if cur > 0 else -1, 25) * 0.0,
                    -1, 1) if False else base[max(0, edge - 12):edge + 13]
    amp = (y1 - y0) * 0.38
    cy = (y0 + y1) / 2.0
    ys = cy - base * amp
    xs = np.linspace(x0, x1, n)
    pts = poly(xs, ys)
    color = AMBER if chan == "AMBER" else CYAN
    draw.line(pts, fill=color + (45,), width=9)

    draw.line(pts, fill=color + (130,), width=4)

    draw.line(pts, fill=color, width=2)


def build_banner() -> Image.Image:
    w, h = 1024, 280
    img = Image.new("RGBA", (w, h), BG)
    d = ImageDraw.Draw(img)

    screen = (398, 26, 996, 254)
    d.rounded_rectangle(screen, radius=14, fill=(15, 24, 44), outline=(43, 62, 100), width=2)
    gx0, gy0, gx1, gy1 = screen[0] + 16, screen[1] + 14, screen[2] - 16, screen[3] - 14
    grid(d, w, h, gx0, gy0, gx1, gy1, step=42)
    d.line([(gx0, gy1), (gx1, gy1)], fill=GRID_MAJOR, width=2)
    draw_trace(d, gx0, gy0, gx1, gy1, "CYAN", seed=17, freq=2.6)
    draw_trace(d, gx0, gy0, gx1, gy1, "AMBER", seed=42, freq=1.6)

    seg = font("C:/Windows/Fonts/segoeuib.ttf", 64)
    mso = font("C:/Windows/Fonts/segoeuib.ttf", 64)
    sub = font("C:/Windows/Fonts/segoeui.ttf", 20)
    small = font("C:/Windows/Fonts/segoeui.ttf", 16)

    d.text((36, 52), "WaveLogic", font=seg, fill=WHITE)
    tw = d.textlength("WaveLogic", font=seg)
    d.text((36 + tw + 16, 52), "MSO", font=mso, fill=AMBER)
    d.text((38, 142), "MULTI-CHANNEL PROTOCOL ANALYZER", font=sub, fill=CYAN)
    d.text((38, 196), "Oscilloscope CSV viewer + protocol decoder pack",
           font=small, fill=DIM)
    return img


def build_icon(size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)

    pad = int(size * 0.045)
    screen = (pad, pad, size - pad, size - pad)
    d.rounded_rectangle(screen, radius=int(size * 0.06), fill=(15, 24, 44),
                        outline=(43, 62, 100), width=max(2, int(size * 0.012)))
    gx0 = screen[0] + int(size * 0.07)
    gy0 = screen[1] + int(size * 0.06)
    gx1 = screen[2] - int(size * 0.06)
    gy1 = screen[3] - int(size * 0.06)
    step = max(8, size // 6)
    grid(d, size, size, gx0, gy0, gx1, gy1, step=step)

    draw_trace(d, gx0, gy0, gx1, gy1, "CYAN", seed=17, freq=2.2)
    draw_trace(d, gx0, gy0, gx1, gy1, "AMBER", seed=42, freq=1.5)
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    banner = build_banner()
    banner.save(OUT_DIR / "wavelogic_logo.png")

    icon = build_icon(256)
    icon.save(
        OUT_DIR / "wavelogic_logo.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("wrote", (OUT_DIR / "wavelogic_logo.png"))
    print("wrote", (OUT_DIR / "wavelogic_logo.ico"))


if __name__ == "__main__":
    main()