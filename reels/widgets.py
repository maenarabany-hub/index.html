"""Widgets animés façon interface (notification, barre de recherche, bulle de commentaire).

Rendus avec PIL, collés image par image au-dessus de la vidéo (sous les sous-titres).
Chaque widget fournit aussi ses bruitages (sfx.py) pour les hooks auditifs.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import sfx
from editorial import SERIF, hex_rgb, over

INTER = "/usr/share/fonts/opentype/inter/Inter-{}.otf"


def font(weight, size):
    return ImageFont.truetype(INTER.format(weight), size)


def ease_out_back(x, s=1.4):
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def card(w, h, radius, fill=(255, 255, 255, 245), shadow=True):
    pad = 40 if shadow else 0
    img = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 10, pad + w, pad + h + 10), radius, fill=(0, 0, 0, 90))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(18)))
    ImageDraw.Draw(img).rounded_rectangle((pad, pad, pad + w, pad + h), radius, fill=fill)
    return img, pad


class Widget:
    def __init__(self, e, st):
        self.start, self.end = e["start"], e["end"]
        self.e, self.st = e, st
        self.W = st["width"]
        self.box = hex_rgb(st.get("ed_word_color", "#5A1419"))
        self.pink = hex_rgb(st.get("ed_pink", "#E7ABAF"))

    def alive(self, t):
        return self.start <= t <= self.end + 0.3

    def sfx(self):
        return []


class Notification(Widget):
    """Notification iOS qui glisse du haut."""

    def __init__(self, e, st):
        super().__init__(e, st)
        w, h = 960, 190
        img, pad = card(w, h, 44, fill=(250, 246, 244, 240))
        d = ImageDraw.Draw(img)
        # icône de l'app : carré bordeaux avec « her » en serif
        ix, iy = pad + 34, pad + 40
        d.rounded_rectangle((ix, iy, ix + 110, iy + 110), 26, fill=self.box + (255,))
        d.text((ix + 55, iy + 52), "her", font=ImageFont.truetype(SERIF, 54), fill=self.pink + (255,), anchor="mm")
        d.text((ix + 140, iy + 4), e.get("app", "BECOMING HER"), font=font("SemiBold", 30), fill=(90, 90, 90, 255))
        d.text((pad + w - 34, iy + 4), "maintenant", font=font("Regular", 28), fill=(140, 140, 140, 255), anchor="ra")
        d.text((ix + 140, iy + 46), e["title"], font=font("SemiBold", 40), fill=(20, 20, 20, 255))
        d.text((ix + 140, iy + 96), e["text"], font=font("Regular", 36), fill=(50, 50, 50, 255))
        self.img = np.array(img)

    def draw(self, canvas, t):
        if not self.alive(t):
            return
        y_on = self.e.get("y", 230)
        if t < self.start + 0.45:
            y = -150 + (y_on + 150) * ease_out_back((t - self.start) / 0.45, 1.1)
        elif t > self.end:
            y = y_on - (y_on + 200) * ease_out((t - self.end) / 0.3)
        else:
            y = y_on
        over(canvas, self.img, self.W / 2, y, 1.0)

    def sfx(self):
        return [(self.start + 0.05, sfx.ding(), -9), (self.end, sfx.whoosh(0.3, up=False), -24)]


class SearchBar(Widget):
    """Barre de recherche qui s'écrit, avec curseur."""

    def __init__(self, e, st):
        super().__init__(e, st)
        self.text = e["text"]
        self.t_type = e.get("type_end", self.start + 1.2)
        self.f = font("Medium", 46)

    def _render(self, shown, cursor):
        w, h = 900, 130
        img, pad = card(w, h, 65)
        d = ImageDraw.Draw(img)
        cx, cy = pad + 72, pad + h // 2
        d.ellipse((cx - 22, cy - 26, cx + 14, cy + 10), outline=self.box + (255,), width=7)  # loupe
        d.line((cx + 9, cy + 5, cx + 26, cy + 22), fill=self.box + (255,), width=8)
        tx = pad + 125
        d.text((tx, cy), shown, font=self.f, fill=(25, 25, 25, 255), anchor="lm")
        if cursor:
            x = tx + self.f.getlength(shown) + 6
            d.rectangle((x, cy - 28, x + 4, cy + 28), fill=self.box + (255,))
        return np.array(img)

    def n_chars(self, t):
        p = (t - self.start - 0.25) / max(self.t_type - self.start - 0.25, 0.1)
        return int(len(self.text) * min(max(p, 0), 1))

    def draw(self, canvas, t):
        if not self.alive(t):
            return
        shown = self.text[:self.n_chars(t)]
        cursor = int(t * 2.5) % 2 == 0 or t < self.t_type
        img = self._render(shown, cursor)
        p = ease_out_back((t - self.start) / 0.35)
        a = 1 - ease_out((t - self.end) / 0.25) if t > self.end else min(1, (t - self.start) / 0.12)
        over(canvas, img, self.W / 2, self.e.get("y", 420), a, 0.7 + 0.3 * p)

    def sfx(self):
        ev = [(self.start, sfx.pop(700), -14)]
        last = 0
        for k in range(int((self.t_type - self.start) * 30) + 2):
            t = self.start + k / 30
            n = self.n_chars(t)
            if n > last and self.text[n - 1] != " ":
                ev.append((t, sfx.key(), -17))
            last = n
        return ev


class CommentBubble(Widget):
    """Bulle « Ajouter un commentaire » qui s'écrit, avec un cœur qui bat."""

    def __init__(self, e, st):
        super().__init__(e, st)
        self.text = e["text"]
        self.t_type = e.get("type_end", self.start + 1.6)
        self.f = font("Regular", 40)

    def _render(self, shown, cursor, beat):
        w, h = 940, 150
        img, pad = card(w, h, 75, fill=(255, 255, 255, 240))
        d = ImageDraw.Draw(img)
        ax, cy = pad + 80, pad + h // 2
        d.ellipse((ax - 44, cy - 44, ax + 44, cy + 44), fill=self.pink + (255,))
        d.text((ax, cy), "toi", font=font("SemiBold", 30), fill=self.box + (255,), anchor="mm")
        tx = pad + 150
        d.text((tx, cy), shown or " ", font=self.f, fill=(30, 30, 30, 255), anchor="lm")
        if cursor:
            x = tx + self.f.getlength(shown) + 6
            d.rectangle((x, cy - 26, x + 4, cy + 26), fill=self.box + (255,))
        # cœur
        hx, hy, r = pad + w - 80, cy, 22 * beat
        d.ellipse((hx - 2 * r, hy - 1.6 * r, hx, hy + 0.4 * r), fill=self.box + (255,))
        d.ellipse((hx, hy - 1.6 * r, hx + 2 * r, hy + 0.4 * r), fill=self.box + (255,))
        d.polygon([(hx - 1.95 * r, hy - 0.3 * r), (hx + 1.95 * r, hy - 0.3 * r), (hx, hy + 1.9 * r)], fill=self.box + (255,))
        return np.array(img)

    def draw(self, canvas, t):
        if not self.alive(t):
            return
        p = (t - self.start - 0.3) / max(self.t_type - self.start - 0.3, 0.1)
        shown = self.text[:int(len(self.text) * min(max(p, 0), 1))]
        cursor = int(t * 2.5) % 2 == 0 or t < self.t_type
        beat = 1 + 0.18 * max(0, math.sin((t - self.start) * 2 * math.pi * 1.2)) ** 6
        img = self._render(shown, cursor, beat)
        q = ease_out_back((t - self.start) / 0.4)
        a = 1 - ease_out((t - self.end) / 0.25) if t > self.end else min(1, (t - self.start) / 0.12)
        over(canvas, img, self.W / 2, self.e.get("y", 1430) + 120 * (1 - q), a)

    def sfx(self):
        ev = [(self.start, sfx.pop(900), -13)]
        n = len(self.text)
        for k in range(n):
            if self.text[k] != " ":
                ev.append((self.start + 0.3 + (self.t_type - self.start - 0.3) * k / n, sfx.key(), -19))
        return ev


KINDS = {"notification": Notification, "search": SearchBar, "comment": CommentBubble}


def load(spec, st):
    return [KINDS[e["kind"]](e, st) for e in spec]
