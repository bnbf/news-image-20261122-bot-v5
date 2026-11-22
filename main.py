#!/usr/bin/env python3
"""Sunday 22 November 2026 — one front page (make.fun news-image-20261122).

Self-contained stdlib-only generator: pure-Python PNG encoder, a hand-typed
5x7 pixel font for display type, and drawn scenes for every pictured story.
No PIL, no base64, no file reads. Deterministic: two runs are byte-identical.

35 stories = 3 leads + 12 picture cards + 20 ALSO briefs, 7 regions,
UTC timeline, world map with numbered pins, DATE CHECK footer.
"""
import math
import os
import struct
import sys
import zlib

W = 1024
H = 1860

# ---------------------------------------------------------------- palette
PAPER = (247, 241, 222)
PAPER_DK = (238, 230, 203)
INK = (20, 20, 20)
INK_SOFT = (60, 58, 52)
NAVY = (22, 30, 64)
NAVY_LT = (38, 50, 96)
RED = (179, 39, 30)
RED_DK = (140, 28, 22)
GOLD = (212, 160, 60)
CREAM = (250, 246, 232)
WHITE = (250, 250, 246)
GREY = (110, 108, 100)

REGION_COLORS = {
    "EUROPE": (37, 99, 160),
    "MIDDLE EAST": (179, 39, 30),
    "ASIA-PAC": (217, 123, 41),
    "AMERICAS": (46, 125, 91),
    "AFRICA": (138, 109, 59),
    "OCEANIA": (123, 94, 167),
    "WORLD": (90, 90, 90),
}


def blend(c1, c2, t):
    """Mix two RGB colors; t=0 -> c1, t=1 -> c2."""
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def vgrad(c_top, c_bot, n):
    """List of n colors forming a vertical gradient."""
    if n <= 1:
        return [c_top]
    return [blend(c_top, c_bot, i / (n - 1)) for i in range(n)]


# ------------------------------------------------------------------- RNG
class LCG:
    """Deterministic pseudo-random generator (fixed seed -> fixed page)."""

    def __init__(self, seed=20261122):
        self.s = seed

    def next(self):
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s

    def rand(self, n):
        return self.next() % n

    def frand(self):
        return self.next() / 2147483647.0


# ---------------------------------------------------------------- PNG out
def _chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return c


def png_bytes(w, h, px):
    """px: bytes of RGB rows, w*3 per row. Returns a PNG file as bytes."""
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", comp) + _chunk(b"IEND", b""))


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg=PAPER):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.rect(0, 0, w, h, bg)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return (self.px[i], self.px[i + 1], self.px[i + 2])

    def rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def rect_blend(self, x, y, w, h, c, t):
        """Fill rect with color c mixed t toward the existing pixel."""
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                self.set(xx, yy, blend(self.get(xx, yy), c, t))

    def hline(self, x, y, w, c, t=1):
        for xx in range(x, x + w):
            self.set(xx, y, c)

    def vline(self, x, y, h, c):
        for yy in range(y, y + h):
            self.set(x, yy, c)

    def line(self, x0, y0, x1, y1, c):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            self.set(x, y, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, c, fill=True):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d = (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy)
                if fill:
                    if d <= r * r:
                        self.set(xx, yy, c)
                else:
                    if r * r - 2 * r <= d <= r * r:
                        self.set(xx, yy, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for yy in range(cy - ry, cy + ry + 1):
            for xx in range(cx - rx, cx + rx + 1):
                if ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0:
                    self.set(xx, yy, c)

    def triangle(self, p0, p1, p2, c):
        """Filled triangle, scanline fill."""
        pts = sorted([p0, p1, p2], key=lambda p: p[1])
        (x0, y0), (x1, y1), (x2, y2) = pts
        if y2 == y0:
            return
        for y in range(max(0, y0), min(self.h, y2 + 1)):
            xa = x0 + (x2 - x0) * (y - y0) / (y2 - y0)
            if y < y1:
                xb = x0 + (x1 - x0) * (y - y0) / (y1 - y0) if y1 != y0 else x0
            else:
                xb = x1 + (x2 - x1) * (y - y1) / (y2 - y1) if y2 != y1 else x1
            lo, hi = (xa, xb) if xa <= xb else (xb, xa)
            for x in range(max(0, int(lo)), min(self.w, int(hi) + 1)):
                self.set(x, y, c)

    def poly(self, pts, c):
        """Filled polygon (convex or concave) via scanline fill."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                for x in range(max(0, int(xs[k])), min(self.w, int(xs[k + 1]) + 1)):
                    self.set(x, y, c)

    def vgrad_rect(self, x, y, w, h, c_top, c_bot):
        grad = vgrad(c_top, c_bot, h)
        for i in range(h):
            self.rect(x, y + i, w, 1, grad[i])

    def stipple(self, x, y, w, h, c, density, seed):
        """Deterministic speckle texture inside a rect (adds drawn detail)."""
        rng = LCG(seed)
        n = int(w * h * density)
        for _ in range(n):
            self.set(x + rng.rand(w), y + rng.rand(h), c)

    def dots_grid(self, x, y, w, h, c, step=6, off=3):
        """Regular dot texture (ocean stipple etc.)."""
        for yy in range(y + off, y + h, step):
            for xx in range(x + off, x + w, step):
                self.set(xx, yy, c)

# -------------------------------------------------------------------- font
# Hand-typed 5x7 pixel font. '#' = ink, '.' = empty. Typed from scratch
# in-session; every glyph is seven rows of five cells.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "b": ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    "c": ("00000", "00000", "01110", "10000", "10000", "10001", "01110"),
    "d": ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    "f": ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    "g": ("00000", "01111", "10001", "10001", "01111", "00001", "01110"),
    "h": ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    "i": ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    "j": ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    "k": ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    "m": ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    "n": ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    "p": ("00000", "00000", "11110", "10001", "10001", "11110", "10000"),
    "q": ("00000", "00000", "01111", "10001", "10001", "01111", "00001"),
    "r": ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    "t": ("01000", "01000", "11100", "01000", "01000", "01000", "00110"),
    "u": ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    "v": ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    "w": ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    "x": ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    "y": ("00000", "00000", "10001", "10001", "01111", "00001", "01110"),
    "z": ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "—": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "–": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "’": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "·": ("00000", "00000", "00000", "01100", "01100", "00000", "00000"),
    "~": ("00000", "00000", "01001", "10110", "00000", "00000", "00000"),
    ">": ("10000", "01000", "00100", "00010", "00100", "01000", "10000"),
    "<": ("00001", "00010", "00100", "01000", "00100", "00010", "00001"),
    "[": ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "]": ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "*": ("00000", "00100", "10101", "01110", "10101", "00100", "00000"),
    "@": ("01110", "10001", "10111", "10101", "10110", "10000", "01110"),
    "^": ("00100", "01010", "10001", "00000", "00000", "00000", "00000"),
    "|": ("00100", "00100", "00100", "00100", "00100", "00100", "00100"),
    "\\": ("10000", "01000", "01000", "00100", "00010", "00010", "00001"),
}


def text_w(s, scale):
    """Pixel width of string s at the given scale."""
    return len(s) * 6 * scale - scale


def draw_text(cv, x, y, s, scale, color):
    """Draw string s with its top-left at (x, y). Unknown chars -> space."""
    cx = x
    for ch in s:
        g = FONT.get(ch, FONT[" "])
        for r in range(7):
            row = g[r]
            for c in range(5):
                if row[c] == "1":
                    cv.rect(cx + c * scale, y + r * scale, scale, scale, color)
        cx += 6 * scale
    return cx


def draw_text_center(cv, cx, y, s, scale, color):
    draw_text(cv, cx - text_w(s, scale) // 2, y, s, scale, color)


def wrap(s, scale, max_w):
    """Greedy word wrap; returns a list of lines fitting max_w."""
    adv = 6 * scale
    words = s.split(" ")
    lines = []
    cur = ""
    for w in words:
        trial = w if not cur else cur + " " + w
        if len(trial) * adv - scale <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_para(cv, x, y, s, scale, color, max_w, lh=None):
    """Draw wrapped paragraph; returns the y just below the last line."""
    if lh is None:
        lh = 7 * scale + 2
    yy = y
    for line in wrap(s, scale, max_w):
        draw_text(cv, x, yy, line, scale, color)
        yy += lh
    return yy


def tag_box(cv, x, y, label, bg, fg=WHITE, scale=1):
    """Small confidence-tag chip; returns width used."""
    w = text_w(label, scale) + 8
    h = 7 * scale + 6
    cv.rect(x, y, w, h, bg)
    draw_text(cv, x + 4, y + 3, label, scale, fg)
    return w

# ------------------------------------------------------------ scene tools
def stars(cv, x, y, w, h, n, seed, color=WHITE):
    rng = LCG(seed)
    for _ in range(n):
        sx = x + rng.rand(w)
        sy = y + rng.rand(h)
        s = 1 + rng.rand(2)
        cv.rect(sx, sy, s, s, color)


def skyline(cv, x, base_y, w, h_max, color, win_color, seed, win_p=45):
    """Row of buildings rising from base_y, with lit windows."""
    rng = LCG(seed)
    bx = x
    while bx < x + w - 8:
        bw = 14 + rng.rand(22)
        bh = 18 + rng.rand(h_max - 18)
        top = base_y - bh
        cv.rect(bx, top, bw, bh, color)
        # roof details: antenna or water tank
        if rng.rand(3) == 0:
            cv.vline(bx + bw // 2, top - 6, 6, color)
            cv.rect(bx + bw // 2 - 1, top - 8, 3, 3, win_color)
        # lit windows grid
        for wy in range(top + 5, base_y - 5, 8):
            for wx in range(bx + 3, bx + bw - 4, 7):
                if rng.rand(100) < win_p:
                    cv.rect(wx, wy, 3, 4,
                            win_color if rng.rand(4) else blend(win_color, color, 0.5))
        bx += bw + 2


def sea_waves(cv, x, y, w, h, c1, c2, seed):
    """Layered wave lines across a sea band."""
    rng = LCG(seed)
    for yy in range(y + 3, y + h, 6):
        xx = x + rng.rand(20)
        while xx < x + w:
            ln = 8 + rng.rand(18)
            cv.hline(xx, yy, ln, c1 if rng.rand(2) else c2)
            xx += ln + 6 + rng.rand(10)


def smoke(cv, x, y, n, seed, c1, c2):
    """Rising smoke puffs drifting right."""
    rng = LCG(seed)
    for i in range(n):
        r = 4 + rng.rand(7)
        cv.circle(x + i * 5 + rng.rand(6), y - i * 6 - rng.rand(4), r,
                  c1 if i % 2 == 0 else c2)


def flame(cv, x, y, s):
    """A flame of height s at (x, y) base; orange outer, yellow core."""
    cv.triangle((x - s // 2, y), (x + s // 2, y), (x, y - s),
                (232, 110, 30))
    cv.triangle((x - s // 4, y), (x + s // 4, y), (x, y - s * 2 // 3),
                (250, 200, 60))
    cv.circle(x, y - s // 4, max(2, s // 6), (255, 235, 130))


def clouds(cv, x, y, n, seed, c):
    """A small cluster of soft cloud puffs."""
    rng = LCG(seed)
    for _ in range(n):
        cx = x + rng.rand(90)
        cy = y + rng.rand(10)
        r = 6 + rng.rand(8)
        cv.ellipse(cx, cy, r + 6, r // 2 + 3, c)
        cv.ellipse(cx + 8, cy - 3, r, r // 2 + 2, c)


# ---------------------------------------------------------------- heroes
def hero_cop31(cv, x, y, w, h):
    """Dusk in Antalya: mountains, conference hall, clock, delegates."""
    cv.vgrad_rect(x, y, w, h, (242, 166, 90), (122, 74, 107))
    # sun low on the horizon
    cv.circle(x + w - 52, y + 52, 20, (255, 214, 130))
    cv.circle(x + w - 52, y + 52, 13, (255, 232, 170))
    clouds(cv, x + 12, y + 14, 3, 301, (250, 196, 150))
    clouds(cv, x + 180, y + 26, 2, 303, (238, 170, 140))
    # mountain ranges
    cv.poly([(x, y + 118), (x + 60, y + 74), (x + 110, y + 112),
             (x + 170, y + 66), (x + 230, y + 110), (x + 290, y + 78),
             (x + w, y + 116), (x + w, y + h), (x, y + h)], (94, 62, 92))
    cv.poly([(x, y + 132), (x + 80, y + 98), (x + 150, y + 130),
             (x + 220, y + 96), (x + w, y + 128), (x + w, y + h),
             (x, y + h)], (72, 46, 74))
    # conference hall: pediment, columns, flag on top, clock on the face
    hx, hy, hw, hh = x + 42, y + 108, 246, 58
    cv.rect(hx, hy, hw, hh, (242, 227, 192))
    cv.triangle((hx - 8, hy), (hx + hw + 8, hy), (hx + hw // 2, hy - 22),
                (232, 210, 168))
    cv.vline(hx + hw // 2, hy - 40, 18, (60, 50, 40))
    cv.rect(hx + hw // 2, hy - 40, 20, 11, (179, 39, 30))
    for i in range(6):
        cx = hx + 18 + i * 40
        cv.rect(cx, hy + 6, 8, hh - 6, (210, 190, 150))
        cv.rect(cx - 2, hy + 2, 12, 4, (200, 178, 138))
    # glowing windows between columns
    for i in range(5):
        cv.rect(hx + 34 + i * 40, hy + 14, 14, 22, (255, 214, 130))
    # clock on the pediment
    cv.circle(hx + hw // 2, hy - 8, 9, WHITE)
    cv.circle(hx + hw // 2, hy - 8, 7, (30, 30, 30))
    cv.line(hx + hw // 2, hy - 8, hx + hw // 2, hy - 13, WHITE)
    cv.line(hx + hw // 2, hy - 8, hx + hw // 2 + 4, hy - 6, WHITE)
    # delegates at the long table, in front of the hall
    ty = y + h - 26
    cv.rect(x + 18, ty, w - 36, 12, (96, 62, 40))
    cv.rect(x + 18, ty, w - 36, 3, (140, 96, 58))
    suits = [(30, 40, 70), (90, 30, 40), (40, 70, 50), (70, 60, 30),
             (50, 50, 90), (30, 40, 70)]
    for i, sc in enumerate(suits):
        dx = x + 40 + i * 46
        cv.circle(dx, ty - 13, 9, (222, 178, 140))
        cv.rect(dx - 11, ty - 6, 22, 8, sc)
        cv.rect(dx - 3, ty - 6, 6, 12, WHITE)
        cv.rect(dx - 1, ty - 6, 2, 8, RED)
    # flags behind the table
    for i, fc in enumerate([(179, 39, 30), (37, 99, 160), (46, 125, 91),
                            (212, 160, 60), (123, 94, 167)]):
        fx = x + 30 + i * 58
        cv.vline(fx, y + h - 62, 38, (60, 50, 40))
        cv.rect(fx, y + h - 62, 22, 12, fc)
    # ground texture + foreground grass
    cv.rect(x, y + h - 14, w, 14, (58, 74, 52))
    cv.stipple(x, y + h - 14, w, 14, (90, 110, 80), 0.08, 77)


def hero_bahrain(cv, x, y, w, h):
    """Night over Manama: radar base, flames, smoke, sea and a ship."""
    cv.vgrad_rect(x, y, w, h, (16, 30, 60), (30, 52, 92))
    stars(cv, x, y, w, 70, 34, 41)
    clouds(cv, x + 20, y + 44, 2, 305, (44, 62, 100))
    clouds(cv, x + 200, y + 18, 2, 307, (44, 62, 100))
    cv.circle(x + w - 46, y + 30, 15, (242, 232, 201))
    cv.circle(x + w - 52, y + 26, 12, (30, 52, 92))
    # radar base platform
    by = y + 108
    cv.rect(x + 16, by, w - 32, 16, (96, 100, 110))
    cv.rect(x + 16, by, w - 32, 3, (140, 144, 154))
    # two radar dishes on masts
    for dx in (x + 78, x + w - 96):
        cv.rect(dx - 3, by - 34, 6, 34, (70, 74, 84))
        cv.circle(dx, by - 40, 16, (150, 154, 164))
        cv.circle(dx, by - 40, 11, (110, 114, 124))
        cv.line(dx - 14, by - 52, dx + 14, by - 30, (200, 204, 214))
    # bunker blocks with lit slits
    for bx in (x + 130, x + 176, x + 222):
        cv.rect(bx, by - 22, 34, 22, (80, 84, 94))
        cv.rect(bx + 5, by - 16, 24, 4, (255, 214, 130))
    # flames on the base + smoke
    flame(cv, x + 60, by, 22)
    flame(cv, x + w - 60, by, 26)
    smoke(cv, x + 58, by - 30, 5, 91, (120, 120, 124), (150, 150, 154))
    smoke(cv, x + w - 62, by - 34, 5, 93, (120, 120, 124), (150, 150, 154))
    # sea with waves and a ship
    sy = by + 16
    cv.vgrad_rect(x, sy, w, y + h - sy, (24, 58, 96), (16, 40, 72))
    sea_waves(cv, x, sy + 4, w, y + h - sy - 4, (90, 140, 190), (60, 110, 160), 55)
    cv.rect(x + 118, y + h - 30, 110, 14, (18, 24, 40))
    cv.triangle((x + 118, y + h - 30), (x + 228, y + h - 30),
                (x + 226, y + h - 44), (18, 24, 40))
    cv.rect(x + 158, y + h - 52, 5, 24, (18, 24, 40))
    cv.rect(x + 140, y + h - 26, 8, 5, (255, 214, 130))
    cv.rect(x + 168, y + h - 26, 8, 5, (255, 214, 130))
    cv.rect(x + 196, y + h - 26, 8, 5, (255, 214, 130))
    # searchlight beam from the base (narrow)
    cv.triangle((x + 254, by - 10), (x + 264, by - 10),
                (x + w - 8, y + 18), blend((242, 232, 201), (30, 52, 92), 0.55))


def hero_kyiv(cv, x, y, w, h):
    """Night over Kyiv: lit skyline, searchlights, drones, fires."""
    cv.vgrad_rect(x, y, w, h, (12, 24, 48), (26, 44, 78))
    stars(cv, x, y, w, 60, 40, 61)
    clouds(cv, x + 90, y + 40, 2, 309, (40, 56, 92))
    clouds(cv, x + 220, y + 16, 2, 311, (40, 56, 92))
    cv.circle(x + 46, y + 30, 17, (242, 232, 201))
    cv.circle(x + 40, y + 26, 14, (26, 44, 78))
    # skyline with many lit windows
    skyline(cv, x, y + h - 22, w, 92, (14, 20, 38), (242, 193, 78), 71, 55)
    # fires + smoke on two buildings
    flame(cv, x + 90, y + h - 66, 20)
    flame(cv, x + 250, y + h - 84, 24)
    smoke(cv, x + 88, y + h - 92, 5, 97, (90, 92, 100), (120, 122, 130))
    smoke(cv, x + 248, y + h - 110, 5, 99, (90, 92, 100), (120, 122, 130))
    # searchlight cones (blended pale yellow over the night sky)
    cone = blend((242, 232, 201), (26, 44, 78), 0.45)
    cv.triangle((x + 120, y + h - 22), (x + 136, y + h - 22),
                (x + 60, y + 8), cone)
    cv.triangle((x + 210, y + h - 22), (x + 224, y + h - 22),
                (x + 300, y + 6), cone)
    # drones: small X shapes with dashed trails
    rng = LCG(101)
    for _ in range(7):
        dx = x + 30 + rng.rand(w - 60)
        dy = y + 14 + rng.rand(46)
        cv.line(dx - 4, dy - 4, dx + 4, dy + 4, (240, 240, 235))
        cv.line(dx - 4, dy + 4, dx + 4, dy - 4, (240, 240, 235))
        for k in range(1, 5):
            cv.set(dx - 4 - k * 4, dy + k * 2, (180, 180, 175))
    # ground strip
    cv.rect(x, y + h - 22, w, 22, (10, 14, 26))
    cv.rect(x, y + h - 22, w, 2, (40, 52, 80))

# ------------------------------------------------------------ card scenes
# Every card scene fills its box: sky + ground + a recognisable scene.
def card_hk(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (214, 226, 238), (180, 196, 214))
    cv.rect(x, y + h - 26, w, 26, (120, 90, 70))
    cv.rect(x, y + h - 26, w, 3, (90, 66, 50))
    # voting booths + ballot box
    for bx in (x + 24, x + 120, x + 216):
        cv.rect(bx, y + 22, 62, 44, (250, 246, 232))
        cv.rect(bx + 4, y + 26, 54, 6, (179, 39, 30))
        cv.rect(bx + 10, y + 38, 42, 20, (238, 232, 216))
    cv.rect(x + w // 2 - 26, y + 8, 52, 30, (179, 39, 30))
    cv.rect(x + w // 2 - 26, y + 8, 52, 6, (140, 28, 22))
    cv.rect(x + w // 2 - 8, y + 2, 16, 8, WHITE)
    # voters: heads + shoulders
    rng = LCG(201)
    for i in range(9):
        vx = x + 16 + i * 34
        cv.circle(vx, y + h - 34, 7, (222, 178, 140))
        cv.rect(vx - 9, y + h - 28, 18, 10, (40, 60, 90) if i % 2 else (90, 40, 50))


def card_vegas(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (30, 16, 60), (90, 30, 110))
    stars(cv, x, y, w, 30, 16, 203)
    # grandstand
    cv.rect(x + 10, y + 14, w - 20, 26, (70, 70, 90))
    for i in range(12):
        cv.rect(x + 16 + i * 26, y + 18, 14, 18, (200, 200, 210))
    # track + F1 car
    cv.rect(x, y + h - 30, w, 30, (40, 40, 46))
    cv.rect(x, y + h - 30, w, 3, (250, 250, 250))
    for xx in range(x, x + w, 24):
        cv.rect(xx, y + h - 16, 12, 3, (250, 200, 40))
    cv.rect(x + 120, y + h - 48, 92, 12, (200, 30, 30))
    cv.rect(x + 132, y + h - 58, 40, 10, (200, 30, 30))
    cv.circle(x + 140, y + h - 34, 7, (20, 20, 20))
    cv.circle(x + 192, y + h - 34, 7, (20, 20, 20))
    cv.circle(x + 140, y + h - 34, 3, (180, 180, 180))
    cv.circle(x + 192, y + h - 34, 3, (180, 180, 180))
    # checkered flag
    cv.vline(x + w - 34, y + 6, 40, (240, 240, 240))
    for r in range(4):
        for c in range(4):
            col = (20, 20, 20) if (r + c) % 2 == 0 else WHITE
            cv.rect(x + w - 34 + c * 6, y + 8 + r * 6, 6, 6, col)


def card_cricket(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (140, 190, 230), (200, 220, 240))
    cv.rect(x, y + h - 40, w, 40, (60, 140, 70))
    cv.rect(x + 20, y + h - 40, w - 40, 10, (190, 170, 120))
    # stumps + bails
    for sx in (x + 60, x + 66, x + 72):
        cv.rect(sx, y + h - 66, 3, 26, (220, 190, 120))
    cv.rect(x + 60, y + h - 69, 15, 3, (220, 190, 120))
    # batsman silhouette + bat
    cv.circle(x + 150, y + h - 62, 8, (222, 178, 140))
    cv.rect(x + 142, y + h - 56, 16, 18, WHITE)
    cv.line(x + 158, y + h - 48, x + 178, y + h - 30, (200, 170, 110))
    cv.rect(x + 176, y + h - 32, 5, 6, (200, 170, 110))
    # red ball + fielders
    cv.circle(x + 240, y + h - 30, 6, (179, 39, 30))
    for fx in (x + 30, x + 250, x + 300):
        cv.circle(fx, y + h - 50, 6, (222, 178, 140))
        cv.rect(fx - 7, y + h - 45, 14, 8, (30, 60, 120))
    # scoreboard
    cv.rect(x + w - 92, y + 8, 84, 22, (20, 30, 40))
    draw_text(cv, x + w - 86, y + 12, "720/9", 2, (255, 214, 130))


def card_boat(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (200, 220, 235), (160, 190, 210))
    cv.vgrad_rect(x, y + 48, w, h - 48, (40, 100, 140), (24, 70, 110))
    sea_waves(cv, x, y + 52, w, h - 52, (160, 200, 230), (120, 170, 210), 207)
    # capsized boat: hull up, keel in the air
    cv.ellipse(x + w // 2, y + 52, 70, 12, (120, 80, 50))
    cv.rect(x + w // 2 - 70, y + 48, 140, 6, (90, 58, 36))
    cv.rect(x + w // 2 - 8, y + 30, 16, 18, (120, 80, 50))
    # people in the water + life rings
    for px in (x + 60, x + 110, x + 250, x + 290):
        cv.circle(px, y + 66, 6, (222, 178, 140))
        cv.circle(px + 16, y + 70, 7, (250, 200, 60))
        cv.circle(px + 16, y + 70, 3, (40, 100, 140))
    # rescue boat
    cv.rect(x + 210, y + 76, 80, 10, (200, 60, 40))
    cv.rect(x + 230, y + 66, 30, 10, (240, 240, 240))


def card_iran(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (24, 28, 52), (60, 56, 80))
    # dark city, most windows out
    skyline(cv, x, y + h - 18, w, 46, (12, 14, 28), (242, 193, 78), 209, 12)
    # power pylon
    cv.line(x + 60, y + h - 18, x + 60, y + 8, (180, 180, 180))
    cv.line(x + 40, y + 18, x + 80, y + 18, (180, 180, 180))
    cv.line(x + 44, y + 30, x + 76, y + 30, (180, 180, 180))
    cv.line(x + 60, y + 8, x + 40, y + 18, (180, 180, 180))
    cv.line(x + 60, y + 8, x + 80, y + 18, (180, 180, 180))
    # lightning bolt
    cv.poly([(x + 210, y + 6), (x + 224, y + 6), (x + 214, y + 34),
             (x + 226, y + 34), (x + 204, y + 66), (x + 212, y + 38),
             (x + 202, y + 38)], (250, 220, 60))
    # one lit window, the rest dark
    cv.rect(x + 250, y + h - 44, 10, 8, (255, 214, 130))


def card_chapo(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (240, 200, 140), (220, 170, 100))
    # desert mountains + cacti
    cv.poly([(x, y + 52), (x + 70, y + 20), (x + 140, y + 52),
             (x + 210, y + 18), (x + 280, y + 52), (x + w, y + 52),
             (x + w, y + h), (x, y + h)], (180, 130, 80))
    cv.rect(x, y + 52, w, h - 52, (214, 164, 96))
    for cx in (x + 30, x + 290):
        cv.rect(cx, y + 58, 5, 18, (40, 110, 50))
        cv.rect(cx - 6, y + 64, 6, 4, (40, 110, 50))
        cv.rect(cx + 5, y + 62, 6, 4, (40, 110, 50))
    # police car
    cv.rect(x + 110, y + h - 34, 110, 16, (20, 40, 90))
    cv.rect(x + 130, y + h - 46, 60, 12, (20, 40, 90))
    cv.circle(x + 132, y + h - 16, 7, (20, 20, 20))
    cv.circle(x + 198, y + h - 16, 7, (20, 20, 20))
    cv.rect(x + 152, y + h - 52, 10, 6, (250, 40, 40))
    cv.rect(x + 164, y + h - 52, 10, 6, (40, 80, 250))
    # star badge
    cv.circle(x + 260, y + 22, 12, (250, 200, 60))
    cv.circle(x + 260, y + 22, 8, (200, 160, 30))
    draw_text(cv, x + 256, y + 18, "*", 1, (90, 60, 10))


def card_gaza(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (220, 200, 170), (190, 170, 140))
    # buildings
    cv.rect(x + 12, y + 26, 60, 50, (150, 140, 120))
    cv.rect(x + 84, y + 14, 70, 62, (165, 155, 135))
    cv.rect(x + 166, y + 30, 56, 46, (150, 140, 120))
    for bx, by in ((x + 20, y + 34), (x + 96, y + 24), (x + 176, y + 38)):
        cv.rect(bx, by, 8, 8, (90, 84, 70))
        cv.rect(bx + 16, by, 8, 8, (90, 84, 70))
    # aid truck
    cv.rect(x + 120, y + h - 30, 90, 16, (240, 240, 235))
    cv.rect(x + 210, y + h - 34, 30, 20, (200, 60, 40))
    cv.circle(x + 140, y + h - 12, 7, (20, 20, 20))
    cv.circle(x + 196, y + h - 12, 7, (20, 20, 20))
    cv.rect(x + 150, y + h - 26, 30, 8, (46, 125, 91))
    # drone above + smoke
    cv.rect(x + 250, y + 12, 34, 6, (60, 60, 64))
    cv.circle(x + 256, y + 15, 4, (60, 60, 64))
    cv.circle(x + 278, y + 15, 4, (60, 60, 64))
    smoke(cv, x + 230, y + 40, 4, 211, (120, 116, 108), (150, 146, 138))


def card_wemby(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (30, 40, 90), (60, 70, 130))
    # court floor
    cv.rect(x, y + h - 34, w, 34, (190, 130, 70))
    cv.ellipse(x + w // 2, y + h - 18, 90, 10, (220, 160, 90))
    cv.rect(x, y + h - 34, w, 2, WHITE)
    # hoop + backboard
    cv.rect(x + w - 60, y + 10, 6, 44, (200, 200, 200))
    cv.rect(x + w - 78, y + 10, 24, 20, WHITE)
    cv.circle(x + w - 66, y + 36, 9, (250, 120, 40))
    cv.circle(x + w - 66, y + 36, 6, (30, 40, 90))
    # tall player shooting
    cv.circle(x + 150, y + 30, 9, (120, 80, 50))
    cv.rect(x + 141, y + 38, 18, 30, (20, 40, 90))
    cv.line(x + 156, y + 42, x + 176, y + 26, (120, 80, 50))
    cv.line(x + 144, y + 42, x + 132, y + 30, (120, 80, 50))
    cv.rect(x + 143, y + 66, 6, 16, (20, 40, 90))
    cv.rect(x + 151, y + 66, 6, 16, (20, 40, 90))
    # ball mid-flight + big 50
    cv.circle(x + 210, y + 22, 8, (240, 130, 50))
    cv.line(x + 206, y + 16, x + 214, y + 28, (160, 80, 20))
    draw_text(cv, x + 16, y + 8, "50", 4, (255, 214, 130))


def card_belgium(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (150, 180, 210), (210, 220, 230))
    # runway + terminal
    cv.rect(x, y + h - 26, w, 26, (110, 110, 116))
    cv.rect(x, y + h - 26, w, 3, WHITE)
    for xx in range(x + 10, x + w, 30):
        cv.rect(xx, y + h - 14, 16, 3, (255, 214, 130))
    cv.rect(x + 12, y + 34, 110, 30, (200, 205, 215))
    for i in range(5):
        cv.rect(x + 20 + i * 20, y + 40, 12, 16, (90, 120, 160))
    # control tower
    cv.rect(x + 220, y + 16, 14, 50, (150, 155, 165))
    cv.ellipse(x + 227, y + 14, 22, 10, (90, 120, 160))
    # grounded plane
    cv.rect(x + 130, y + h - 44, 120, 10, WHITE)
    cv.rect(x + 170, y + h - 58, 40, 14, WHITE)
    cv.triangle((x + 250, y + h - 44), (x + 250, y + h - 44),
                (x + 262, y + h - 52), WHITE)
    cv.rect(x + 130, y + h - 44, 120, 3, (179, 39, 30))
    # strike sign
    cv.rect(x + 250, y + 8, 62, 18, (179, 39, 30))
    draw_text(cv, x + 254, y + 12, "STRIKE", 1, WHITE)


def card_bepi(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (8, 10, 28), (30, 24, 60))
    stars(cv, x, y, w, h, 30, 213)
    # Mercury: cratered disc
    cv.circle(x + 250, y + 44, 30, (180, 160, 130))
    cv.circle(x + 240, y + 36, 7, (150, 130, 100))
    cv.circle(x + 260, y + 52, 5, (150, 130, 100))
    cv.circle(x + 252, y + 28, 4, (150, 130, 100))
    cv.circle(x + 238, y + 54, 4, (150, 130, 100))
    # spacecraft with solar panels
    cv.rect(x + 70, y + 34, 34, 22, (200, 200, 210))
    cv.rect(x + 40, y + 38, 30, 14, (40, 80, 160))
    cv.rect(x + 104, y + 38, 30, 14, (40, 80, 160))
    for i in range(3):
        cv.vline(x + 46 + i * 10, y + 38, 14, (90, 140, 220))
        cv.vline(x + 110 + i * 10, y + 38, 14, (90, 140, 220))
    cv.circle(x + 87, y + 45, 6, (255, 214, 130))
    # trajectory dots to Mercury
    for i in range(6):
        cv.circle(x + 120 + i * 20, y + 45 + i * 2, 2, (255, 214, 130))


def card_nvidia(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (230, 235, 240), (200, 210, 220))
    # falling chart: white panel, grid, red line down + arrow
    cv.rect(x + 14, y + 12, w - 28, h - 40, WHITE)
    for gy in range(y + 18, y + h - 30, 12):
        cv.hline(x + 18, gy, w - 36, (220, 225, 230))
    pts = [(x + 20, y + 24), (x + 80, y + 30), (x + 140, y + 28),
           (x + 200, y + 44), (x + 260, y + 52), (x + 296, y + 60)]
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], (179, 39, 30))
        cv.line(pts[i][0], pts[i][1] + 1, pts[i + 1][0], pts[i + 1][1] + 1,
                (179, 39, 30))
    for px, py in pts:
        cv.circle(px, py, 3, (179, 39, 30))
    cv.triangle((x + 296, y + 60), (x + 284, y + 52), (x + 284, y + 66),
                (179, 39, 30))
    # chip
    cv.rect(x + 130, y + h - 34, 60, 22, (30, 40, 50))
    cv.rect(x + 146, y + h - 28, 28, 10, (46, 125, 91))
    for i in range(4):
        cv.hline(x + 122, y + h - 30 + i * 5, 8, (120, 120, 120))
        cv.hline(x + 190, y + h - 30 + i * 5, 8, (120, 120, 120))
    # magnifier
    cv.circle(x + 270, y + 20, 12, (60, 60, 60))
    cv.circle(x + 270, y + 20, 8, (230, 235, 240))
    cv.line(x + 278, y + 28, x + 292, y + 42, (60, 60, 60))


def card_bolsonaro(cv, x, y, w, h):
    cv.vgrad_rect(x, y, w, h, (220, 235, 230), (190, 210, 200))
    # hospital wall + floor
    cv.rect(x, y + h - 20, w, 20, (160, 175, 170))
    # bed
    cv.rect(x + 60, y + h - 44, 150, 10, (90, 110, 120))
    cv.rect(x + 60, y + h - 34, 6, 14, (90, 110, 120))
    cv.rect(x + 204, y + h - 34, 6, 14, (90, 110, 120))
    cv.rect(x + 66, y + h - 52, 138, 10, WHITE)
    cv.circle(x + 80, y + h - 58, 8, (222, 178, 140))
    cv.rect(x + 84, y + h - 54, 60, 8, (200, 220, 230))
    # monitor with heartbeat
    cv.rect(x + 240, y + 12, 64, 44, (30, 40, 50))
    cv.rect(x + 246, y + 18, 52, 32, (16, 26, 20))
    cv.poly([(x + 248, y + 36), (x + 258, y + 36), (x + 264, y + 24),
             (x + 270, y + 44), (x + 276, y + 30), (x + 282, y + 36),
             (x + 296, y + 36)], (80, 220, 120))
    # red cross sign
    cv.rect(x + 16, y + 12, 30, 30, WHITE)
    cv.rect(x + 27, y + 16, 8, 22, (179, 39, 30))
    cv.rect(x + 20, y + 23, 22, 8, (179, 39, 30))


# -------------------------------------------------------------------- map
# Simplified continent outlines as (lon, lat) points.
CONTINENTS = [
    [(-168, 66), (-150, 70), (-135, 69), (-125, 71), (-110, 73), (-95, 80),
     (-85, 76), (-75, 72), (-65, 62), (-55, 52), (-60, 47), (-70, 44),
     (-75, 38), (-76, 34), (-81, 26), (-84, 30), (-90, 21), (-95, 16),
     (-100, 18), (-105, 22), (-112, 28), (-117, 33), (-122, 38),
     (-125, 45), (-125, 50), (-130, 55), (-140, 60), (-152, 58),
     (-162, 58), (-168, 66)],
    [(-58, 64), (-48, 60), (-40, 60), (-32, 68), (-22, 70), (-28, 76),
     (-40, 78), (-55, 76), (-62, 74), (-58, 64)],
    [(-79, 9), (-72, 12), (-64, 11), (-56, 6), (-50, 4), (-44, -2),
     (-38, -5), (-35, -9), (-39, -15), (-41, -22), (-48, -27), (-55, -34),
     (-62, -39), (-66, -45), (-69, -52), (-73, -46), (-73, -36), (-72, -22),
     (-75, -15), (-80, -6), (-81, 0), (-79, 9)],
    [(-10, 36), (-9, 38), (-9, 43), (-2, 44), (-2, 48), (0, 50), (2, 51),
     (5, 53), (8, 55), (8, 57), (11, 59), (18, 56), (21, 55), (24, 58),
     (28, 59), (30, 61), (32, 66), (30, 70), (25, 71), (20, 70), (16, 69),
     (12, 66), (10, 62), (5, 60), (2, 58), (-3, 58), (-6, 57), (-8, 54),
     (-10, 51), (-11, 48), (-10, 43), (-10, 36)],
    [(-17, 15), (-17, 21), (-16, 27), (-11, 30), (-6, 34), (0, 36),
     (10, 37), (12, 34), (20, 32), (30, 31), (33, 28), (35, 28), (38, 22),
     (43, 12), (48, 11), (51, 11), (51, 4), (46, -2), (41, -8), (38, -15),
     (35, -20), (33, -26), (28, -32), (20, -35), (17, -30), (14, -24),
     (12, -17), (12, -10), (9, -2), (9, 4), (-4, 5), (-8, 5), (-13, 8),
     (-17, 12), (-17, 15)],
    [(26, 36), (30, 36), (36, 36), (36, 41), (41, 41), (44, 39), (48, 39),
     (50, 37), (54, 37), (54, 31), (57, 27), (58, 25), (61, 25), (66, 25),
     (68, 24), (72, 21), (73, 19), (76, 10), (77, 8), (80, 10), (80, 15),
     (85, 19), (88, 22), (91, 22), (93, 17), (95, 16), (98, 10), (100, 8),
     (101, 6), (103, 2), (104, 8), (107, 11), (109, 14), (108, 17),
     (107, 20), (109, 21), (112, 22), (114, 22), (117, 24), (120, 28),
     (121, 30), (122, 32), (124, 36), (126, 38), (127, 40), (130, 42),
     (132, 43), (135, 44), (138, 46), (141, 50), (142, 54), (142, 59),
     (150, 60), (156, 59), (158, 56), (162, 56), (160, 52), (156, 51),
     (150, 48), (142, 46), (141, 42), (140, 39), (137, 37), (134, 35),
     (131, 34), (129, 32), (127, 33), (124, 33), (122, 32), (120, 34),
     (118, 31), (115, 30), (112, 28), (109, 26), (105, 22), (102, 20),
     (99, 18), (96, 17), (93, 20), (90, 22), (87, 22), (84, 19), (81, 16),
     (78, 15), (75, 18), (72, 20), (70, 22), (67, 24), (64, 25), (61, 25),
     (58, 26), (55, 26), (52, 27), (50, 29), (48, 30), (46, 30), (44, 29),
     (41, 31), (39, 32), (36, 36), (33, 36), (30, 36), (26, 36)],
    [(114, -22), (113, -26), (114, -30), (115, -34), (118, -35),
     (124, -33), (129, -32), (132, -32), (136, -35), (140, -38),
     (146, -39), (150, -37), (153, -32), (153, -27), (150, -23),
     (146, -19), (142, -15), (142, -11), (137, -12), (135, -14),
     (132, -12), (130, -13), (126, -14), (122, -17), (118, -20),
     (114, -22)],
    [(129, 31), (131, 33), (134, 34), (137, 35), (139, 37), (140, 39),
     (141, 42), (143, 42), (144, 44), (142, 45), (140, 42), (139, 39),
     (137, 36), (134, 34), (131, 33), (129, 31)],
    [(95, -2), (98, -2), (101, -1), (104, -2), (106, -6), (104, -8),
     (100, -6), (97, -4), (95, -2)],
    [(100, 14), (101, 12), (103, 10), (104, 8), (102, 8), (100, 10),
     (100, 14)],
]

PINS = [  # (number, lat, lon)
    (1, 36.9, 30.7), (2, 26.2, 50.6), (3, 50.5, 30.5), (4, 22.3, 114.2),
    (5, 36.2, -115.1), (6, -41.3, 174.8), (7, 4.9, 6.3), (8, 35.7, 51.4),
    (9, 25.6, -108.5), (10, 31.5, 34.5), (11, 29.4, -98.5),
    (12, 50.85, 4.35), (14, 38.9, -77.0), (15, -15.8, -47.9),
]


def draw_map(cv, x, y, w, h):
    """World map: dotted navy sea, filled continents, numbered pins."""
    cv.rect(x, y, w, h, NAVY)
    cv.dots_grid(x, y, w, h, (52, 66, 116), step=7, off=3)
    # graticule
    for gx in range(x + w // 6, x + w, w // 6):
        cv.vline(gx, y, h, (38, 50, 92))
    for gy in range(y + h // 4, y + h, h // 4):
        cv.hline(x, gy, w, (38, 50, 92))

    def proj(lon, lat):
        px = x + int((lon + 180) / 360 * w)
        py = y + int((90 - lat) / 180 * h)
        return (px, py)

    for cont in CONTINENTS:
        pts = [proj(lon, lat) for lon, lat in cont]
        cv.poly(pts, (232, 220, 188))
        # coastline: darker outline via short segments
        for i in range(len(pts)):
            cv.line(pts[i][0], pts[i][1], pts[(i + 1) % len(pts)][0],
                    pts[(i + 1) % len(pts)][1], (190, 176, 140))
    # pins (small, so the Europe / Middle East cluster stays readable)
    for num, lat, lon in PINS:
        px, py = proj(lon, lat)
        cv.circle(px, py, 6, RED)
        cv.circle(px, py, 6, WHITE, fill=False)
        draw_text(cv, px - 2 if num < 10 else px - 5, py - 3, str(num), 1, WHITE)

# ------------------------------------------------------------------ content
HEROES = [
    {
        "num": 1, "place": "ANTALYA, TURKIYE", "region": "WORLD",
        "tag": "REPORTED",
        "headline": "COP31's final text lands at dawn — with no mention of fossil fuels",
        "deck": "Ten-page package drops the $120bn target and admits 1.5C will be overshot.",
        "sources": "Sources: BBC · Reuters · Guardian",
        "scene": "cop31",
    },
    {
        "num": 2, "place": "MANAMA, BAHRAIN", "region": "MIDDLE EAST",
        "tag": "CLAIM",
        "headline": "Iran claims strikes on US bases in Bahrain",
        "deck": "IRGC says it hit two Patriot radars; Bahrain says defences intercepted it. No casualties.",
        "sources": "Sources: Al Jazeera · Reuters · IRGC statement",
        "scene": "bahrain",
    },
    {
        "num": 3, "place": "KYIV, UKRAINE", "region": "EUROPE",
        "tag": "REPORTED",
        "headline": "Russia's overnight barrage: 186 drones, 161 downed",
        "deck": "186 drones and three ballistic missiles overnight; defences down or jam 161.",
        "sources": "Sources: Ukrainian Air Force · Kyiv Independent",
        "scene": "kyiv",
    },
]

CARDS = [
    {"num": 4, "place": "HONG KONG", "region": "ASIA-PAC", "tag": "CONFIRMED",
     "headline": "Hong Kong elects its Election Committee",
     "deck": "856 candidates for 723 seats; turnout 93.55%.",
     "sources": "CONFIRMED SCMP", "scene": "hk"},
    {"num": 5, "place": "LAS VEGAS GP", "region": "AMERICAS", "tag": "CONFIRMED",
     "headline": "Verstappen wins the Las Vegas GP",
     "deck": "Beats Norris and Piastri; Russell 9th.",
     "sources": "CONFIRMED Reuters · F1", "scene": "vegas"},
    {"num": 6, "place": "WELLINGTON", "region": "OCEANIA", "tag": "CONFIRMED",
     "headline": "India declare 720/9 — a record in NZ",
     "deck": "Pant 128, Rahul 136; highest total ever in NZ.",
     "sources": "CONFIRMED Reuters · AP", "scene": "cricket"},
    {"num": 7, "place": "BAYELSA", "region": "AFRICA", "tag": "REPORTED",
     "headline": "Bayelsa boat toll rises to 26",
     "deck": "Mourners' boat capsized Friday; recovery goes on.",
     "sources": "REPORTED RIA · Vanguard", "scene": "boat"},
    {"num": 8, "place": "TEHRAN", "region": "MIDDLE EAST", "tag": "REPORTED",
     "headline": "Iran starts rationing electricity",
     "deck": "Two-hour daily cuts begin as gas output falls.",
     "sources": "REPORTED Tavani · RFE/RL", "scene": "iran"},
    {"num": 9, "place": "SINALOA", "region": "AMERICAS", "tag": "CONFIRMED",
     "headline": "'El Chapo Isidro' caught in Sinaloa",
     "deck": "FBI top-ten fugitive held; 11 dead in shoot-out.",
     "sources": "CONFIRMED Sky News · BBC", "scene": "chapo"},
    {"num": 10, "place": "GAZA CITY", "region": "MIDDLE EAST", "tag": "REPORTED",
     "headline": "Hamas seeks urgent talks after aid strike",
     "deck": "Three die in a drone strike on a food vehicle.",
     "sources": "REPORTED Al Jazeera · Anadolu", "scene": "gaza"},
    {"num": 11, "place": "SAN ANTONIO", "region": "AMERICAS", "tag": "CONFIRMED",
     "headline": "Wembanyama drops 50 — a first in NBA history",
     "deck": "50 pts, 19 reb, 5 blocks; first ever 50/15/5/4.",
     "sources": "CONFIRMED Reuters · AP", "scene": "wemby"},
    {"num": 12, "place": "BRUSSELS", "region": "EUROPE", "tag": "REPORTED",
     "headline": "Belgian controllers join Monday's strike",
     "deck": "Most Brussels flights cancelled; 59,500 hit.",
     "sources": "REPORTED Belga · AFP", "scene": "belgium"},
    {"num": 13, "place": "MERCURY", "region": "WORLD", "tag": "REPORTED",
     "headline": "BepiColombo enters Mercury orbit",
     "deck": "Eight-year journey ends; first X-ray readings.",
     "sources": "REPORTED AP · ESA", "scene": "bepi"},
    {"num": 14, "place": "WASHINGTON", "region": "AMERICAS", "tag": "REPORTED",
     "headline": "Nvidia faces an SEC probe",
     "deck": "Early-stage accounting inquiry; AI shares slide.",
     "sources": "REPORTED Straits Times · CNBC", "scene": "nvidia"},
    {"num": 15, "place": "BRASILIA", "region": "AMERICAS", "tag": "CONFIRMED",
     "headline": "Bolsonaro in intensive care",
     "deck": "Bowel obstruction, stable, breathing on his own.",
     "sources": "CONFIRMED Al Jazeera · Reuters", "scene": "bolsonaro"},
]

ALSO = [
    (16, "Kryvyi Rih missile: 2 killed, 58 hurt — BBC"),
    (17, "Russian cargo ship Sparta II ablaze; all 16 crew off; Finland blames Ukraine — Reuters"),
    (18, "Saudi downs Houthi missile aimed at Riyadh; intercepted 01:42 local — Anadolu"),
    (19, "EU and Indonesia sign trade deal after ten years — DW"),
    (20, "Germany's coalition talks grind on"),
    (21, "England hammer New Zealand 37-12 at Twickenham — Reuters"),
    (22, "Premier League: Leeds 4-1 Chelsea; Arsenal 2-2 Newcastle"),
    (23, "Sanchez faces TV debate before Spain votes 29 Nov"),
    (24, "Lebanon: Aoun demands Israel withdrawal — Al Jazeera"),
    (25, "Israel: Eisenkot invites Likud to coalition talks — Straits Times"),
    (26, "West Bank killing probed"),
    (27, "Cikande factory fire: 3 dead, 36 missing — Reuters"),
    (28, "Pakistan FM hopes for US-Iran deal"),
    (29, "Japan Tobacco books $8.9bn Russia loss"),
    (30, "Manipur toxic-liquor toll rises to 19; 600+ in hospital"),
    (31, "St Johns River breaks flood record; crest expected Sunday — Forecasters"),
    (32, "Peru quake toll rises to 1 dead, 16 hurt — 170 homes damaged in Junin"),
    (33, "Sudan: army seizes Bau district in Blue Nile"),
    (34, "Congo: leaders meet in Oyo on Sunday"),
    (35, "UNICEF: 1,144 children killed or hurt in Ukraine in 2026"),
]

NUMBERS = [
    ("~200", "NATIONS AT THE COP31 TALKS"),
    ("03:00", "GMT OBJECTIONS DEADLINE"),
    ("186", "DRONES FIRED OVERNIGHT"),
    ("2", "US BASES HIT IN BAHRAIN"),
    ("856", "HONG KONG CANDIDATES"),
    ("720/9", "INDIA'S RECORD TOTAL IN NZ"),
]

REGIONS = [("EUROPE", 9), ("MIDDLE EAST", 7), ("ASIA-PAC", 5), ("AMERICAS", 7),
           ("AFRICA", 3), ("OCEANIA", 1), ("WORLD", 3)]

UTC_EVENTS = [
    ("03:00", "COP31 objections"),
    ("05:11", "Hamas seeks talks"),
    ("05:30", "Vegas GP ends"),
    ("06:00", "COP31 approval"),
    ("08:00", "161/186 downed"),
    ("14:00", "HK turnout 93.55%"),
]

TAG_COLORS = {"CONFIRMED": (46, 125, 91), "REPORTED": (179, 39, 30),
              "CLAIM": (140, 28, 22)}

COL_X = [8, 345, 682]
COL_W = 330


def draw_tag_line(cv, x, y, num, place, region, tag):
    """'N PLACE · REGION' left, confidence tag chip right."""
    draw_text(cv, x, y, "%d %s · %s" % (num, place, region), 1, INK)
    tw = text_w(tag, 1) + 8
    tag_box(cv, x + COL_W - tw, y - 2, tag, TAG_COLORS[tag])


def draw_hero(cv, x, y, hero):
    scene = {"cop31": hero_cop31, "bahrain": hero_bahrain,
             "kyiv": hero_kyiv}[hero["scene"]]
    scene(cv, x, y, COL_W, 150)
    draw_tag_line(cv, x, y + 156, hero["num"], hero["place"], hero["region"],
                  hero["tag"])
    draw_para(cv, x, y + 176, hero["headline"], 2, INK, COL_W, lh=16)
    draw_para(cv, x, y + 228, hero["deck"], 2, INK_SOFT, COL_W, lh=16)
    draw_text(cv, x, y + 296, hero["sources"], 1, GREY)


def draw_card(cv, x, y, card):
    scene = {"hk": card_hk, "vegas": card_vegas, "cricket": card_cricket,
             "boat": card_boat, "iran": card_iran, "chapo": card_chapo,
             "gaza": card_gaza, "wemby": card_wemby, "belgium": card_belgium,
             "bepi": card_bepi, "nvidia": card_nvidia,
             "bolsonaro": card_bolsonaro}[card["scene"]]
    scene(cv, x, y, COL_W, 90)
    draw_tag_line(cv, x, y + 96, card["num"], card["place"], card["region"],
                  card["tag"])
    draw_para(cv, x, y + 114, card["headline"], 2, INK, COL_W, lh=16)
    draw_para(cv, x, y + 148, card["deck"], 2, INK_SOFT, COL_W, lh=16)
    draw_text(cv, x, y + 182, card["sources"], 1, GREY)


def build_page():
    cv = Canvas(W, H, PAPER)
    # paper grain: faint deterministic stipple over the whole page
    cv.stipple(0, 0, W, H, (232, 224, 200), 0.02, 4242)
    cv.stipple(0, 0, W, H, (250, 246, 228), 0.016, 5151)

    # ---- kicker bar
    cv.rect(0, 0, W, 28, NAVY)
    draw_text(cv, 10, 10, "THE WORLD IN ONE DAY", 2, GOLD)
    draw_text(cv, W - 10 - text_w("35 STORIES · 7 REGIONS · SUNDAY 22 NOVEMBER 2026", 2),
              10, "35 STORIES · 7 REGIONS · SUNDAY 22 NOVEMBER 2026",
              2, CREAM)

    # ---- masthead: fat pixel display type (v3's proven face)
    draw_text_center(cv, W // 2, 34, "Sunday 22 November 2026", 7, INK)
    cv.hline(8, 92, W - 16, INK)
    draw_text_center(cv, W // 2, 98,
                     "COP31's final text lands at dawn · Iran claims strikes", 2, RED)
    draw_text_center(cv, W // 2, 116,
                     "on US bases in Bahrain · 186 drones over Ukraine overnight", 2, RED)

    # ---- numbers strip
    cell = W // 6
    for i, (num, label) in enumerate(NUMBERS):
        x0 = i * cell
        if i:
            cv.vline(x0, 136, 62, (200, 192, 168))
        draw_text_center(cv, x0 + cell // 2, 138, num, 5, RED)
        ly = 178
        for ln in wrap(label, 1, cell - 12):
            draw_text_center(cv, x0 + cell // 2, ly, ln, 1, INK_SOFT)
            ly += 9
    cv.hline(8, 202, W - 16, (200, 192, 168))

    # ---- region bar (proportional segments)
    total = sum(n for _, n in REGIONS)
    rx = 0
    for name, n in REGIONS:
        seg = int(round(W * n / total))
        cv.rect(rx, 208, seg, 26, REGION_COLORS[name])
        lab = "%s %d" % (name, n)
        draw_text_center(cv, rx + seg // 2, 217, lab, 1, WHITE)
        rx += seg

    # ---- UTC strip
    cv.rect(0, 240, W, 26, NAVY)
    ux = 10
    ux = draw_text(cv, ux, 249, "THE DAY IN UTC", 1, GOLD) + 12
    for t, ev in UTC_EVENTS:
        ux = draw_text(cv, ux, 249, t + " ", 1, GOLD) + 2
        ux = draw_text(cv, ux, 249, ev, 1, CREAM) + 16
        if (t, ev) != UTC_EVENTS[-1]:
            ux = draw_text(cv, ux - 8, 249, "·", 1, (140, 150, 190)) + 8

    # ---- heroes
    for i, hero in enumerate(HEROES):
        draw_hero(cv, COL_X[i], 272, hero)

    # ---- section header
    draw_text(cv, 8, 592, "THE DAY IN TWELVE", 3, INK)
    draw_text(cv, W - 8 - text_w("THE STORIES THAT MOVED THE WORLD TODAY", 1),
              600, "THE STORIES THAT MOVED THE WORLD TODAY", 1, INK_SOFT)
    cv.hline(8, 616, W - 16, INK)

    # ---- picture cards, 3 x 4
    for r in range(4):
        for c in range(3):
            draw_card(cv, COL_X[c], 624 + r * 196, CARDS[r * 3 + c])

    # ---- map + ALSO
    draw_text(cv, 8, 1416, "WHERE IT HAPPENED", 2, INK)
    draw_text(cv, 345, 1416, "ALSO ON SUNDAY 22 NOVEMBER — 20 MORE STORIES", 2, RED)
    draw_map(cv, 8, 1440, COL_W, 210)
    draw_text(cv, 8, 1656, "Pins match story numbers. 13 BepiColombo is at Mercury — no pin on Earth.", 1, INK_SOFT)
    ax = 345
    col_w = 330
    for k, (num, txt) in enumerate(ALSO):
        cx = ax + (k // 10) * (col_w + 12)
        cy = 1440 + (k % 10) * 21
        draw_text(cv, cx, cy, "%d" % num, 1, RED)
        draw_para(cv, cx + 20, cy, txt, 1, INK, col_w - 20, lh=10)

    # ---- DATE CHECK
    cv.rect(8, 1684, W - 16, 118, (253, 244, 228))
    for xx in (8, W - 9):
        cv.vline(xx, 1684, 118, RED)
    cv.hline(8, 1684, W - 16, RED)
    cv.hline(8, 1801, W - 16, RED)
    draw_text(cv, 16, 1692, "DATE CHECK — READ THIS FIRST", 2, RED)
    draw_para(cv, 16, 1714,
              "WIRES READ UP TO 14:00 UTC. Every story here was reported, or still developing, on 22 November in at least one time zone. Left out on purpose: the Peru quake (Fri 20 Nov), Russia's 400-drone barrage (19-20 Nov), the Shenzhen summit (19 Nov). Tonight's barrage was 186, not 400.",
              2, INK, W - 32, lh=16)
    draw_text(cv, 16, 1782,
              "NOT YET: COP31 adoption vote (plenary slipped past 11:00 Antalya) · Spain votes 29 Nov · G20 peace talks ahead · Killer-robot rules by 2028.",
              1, RED_DK)

    # ---- legend + footer
    draw_para(cv, 8, 1812,
              "HOW TO READ THE TAGS — CONFIRMED = reported by the named source · REPORTED = wire-reported, not yet confirmed · CLAIM = one side's account, contested.",
              1, INK_SOFT, W - 16, lh=10)
    draw_para(cv, 8, 1832,
              "SCENES ARE DRAWN ILLUSTRATIONS OF REPORTED EVENTS, NOT PHOTOGRAPHS. SOURCES: BBC · REUTERS · AL JAZEERA · THE GUARDIAN · AP · SCMP · DW · UPI · FT · UKRAINIAN AIR FORCE · ESA",
              1, GREY, W - 16, lh=10)
    cv.rect(0, H - 8, W, 8, NAVY)
    return cv

# --------------------------------------------------------------------- main
def main():
    cv = build_page()
    data = png_bytes(cv.w, cv.h, bytes(cv.px))
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    try:
        os.makedirs(outdir, exist_ok=True)
    except OSError:
        outdir = "."
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    import hashlib
    print("wrote %s %d bytes sha256 %s" % (path, len(data),
                                           hashlib.sha256(data).hexdigest()))
    print("canvas %dx%d" % (cv.w, cv.h))


if __name__ == "__main__":
    main()
