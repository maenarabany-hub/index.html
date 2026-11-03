"""Preset « minimal » : le sous-titre EST la typographie.

Chaque groupe de mots devient un bloc à 3 niveaux, en serif ivoire, sans fond ni couleur :
    petits mots avant          (serif droit, aligné à gauche du grand mot)
    GRAND MOT CLÉ              (capitales Didone)
          petits mots après    (serif italique, aligné à droite)
Les mots apparaissent quand ils sont prononcés ; les mains passent devant les lettres.
"""
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from editorial import ease_out, hex_rgb, over

FONTS = Path(__file__).resolve().parent / "fonts"
BIG = str(FONTS / "BodoniModa-700-normal.ttf")      # Didone grasse, lettres serrées (comme la référence)
SMALL = str(FONTS / "BodoniModa-500-normal.ttf")
ITAL = str(FONTS / "BodoniModa-500-italic.ttf")


def clean(w):
    return re.sub(r"[.,;:…—!?]+$", "", w).strip()


def _text_img(text, path, size, color, shadow=True, track=0.0, condense=1.0):
    """Texte -> RGBA. `track` : espacement des lettres en fraction de la taille (négatif = serré)."""
    f = ImageFont.truetype(path, size)
    l, t, r, b = f.getbbox(text)
    adv = [f.getlength(ch) + track * size for ch in text]
    width = int(sum(adv) - track * size + (r - l) - f.getlength(text)) + 4
    pad = 30
    img = Image.new("RGBA", (max(width, 1) + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))

    def draw(d, dy, fill):
        x = pad - l
        for ch, a in zip(text, adv):
            d.text((x, pad - t + dy), ch, font=f, fill=fill)
            x += a
    if shadow:   # ombre très douce, juste pour la lisibilité
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw(ImageDraw.Draw(sh), 4, (0, 0, 0, 110))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(8)))
    draw(ImageDraw.Draw(img), 0, color + (255,))
    if condense != 1.0:
        img = img.resize((int(img.width * condense), img.height), Image.LANCZOS)
    return np.array(img), int(pad * condense)


def _n(w):
    import unicodedata
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z0-9']", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))


def make_groups(words, is_key, phrases=(), max_words=6):
    """Découpe en blocs (propositions de 7 mots max), chacun avec UN mot ou une expression clé.
    `phrases` : expressions clés de plusieurs mots (« nulle part », « UN truc »...)."""
    clauses, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if (re.search(r"[.!?,;:]$", w["w"]) or nxt is None or nxt["start"] - w["end"] > 0.6
                or nxt.get("_seg") != w.get("_seg")):   # jamais à cheval sur deux morceaux du montage
            clauses.append(cur)
            cur = []
    chunks = []
    for c in clauses:   # coupe les longues propositions en morceaux équilibrés
        n = max(1, -(-len(c) // max_words))
        size = -(-len(c) // n)
        chunks += [c[k:k + size] for k in range(0, len(c), size)]
    ph = [p.split() for p in phrases]
    out = []
    for g in chunks:
        toks = [_n(w["w"]) for w in g]
        span = None
        for p in sorted(ph, key=len, reverse=True):     # 1) expression clé
            pn = [_n(x) for x in p]
            for k in range(len(g) - len(p) + 1):
                if toks[k:k + len(p)] == pn:
                    span = (k, k + len(p))
                    break
            if span:
                break
        if not span:                                     # 2) mot clé, sinon chiffre, sinon le plus long
            keys = [k for k, w in enumerate(g) if is_key(w) and not re.search(r"\d", w["w"])]
            digits = [k for k, w in enumerate(g) if re.search(r"\d", w["w"])]
            k = max(keys, key=lambda k: len(clean(g[k]["w"]))) if keys else digits[0] if digits else max(range(len(g)), key=lambda k: len(clean(g[k]["w"])))
            span = (k, k + 1)
        a, b = span
        out.append({"before": g[:a], "key": g[a:b], "after": g[b:], "start": g[0]["start"], "end": g[-1]["end"]})
    FADE = 0.2
    for i, g in enumerate(out):   # le fondu de sortie se termine AVANT le bloc suivant (pas de fantôme)
        nxt = out[i + 1]["start"] if i + 1 < len(out) else g["end"] + 0.8
        g["until"] = max(g["key"][-1]["start"] + 0.25, min(nxt - FADE, g["end"] + 0.5))
        g["fade"] = max(0.05, min(FADE, nxt - g["until"]))
    return out


class Captions:
    def __init__(self, words, is_key, st):
        self.W = st["width"]
        self.color = hex_rgb(st.get("min_color", "#F4EFE6"))
        self.y = st.get("min_y", 1260)
        self.max_w = int(self.W * 0.84)
        self.groups = make_groups(words, is_key, st.get("min_phrases", []))
        self.cache = {}

    def _big(self, g):
        key = ("big", id(g))
        if key not in self.cache:
            txt, size = " ".join(clean(w["w"]) for w in g["key"]).upper(), 270
            while True:
                img, pad = _text_img(txt, BIG, size, self.color, track=-0.045, condense=0.94)
                if img.shape[1] - 2 * pad <= self.max_w or size < 90:
                    break
                size = int(size * 0.93)
            self.cache[key] = (img, pad, size)
        return self.cache[key]

    def _small(self, g, part, n):
        key = (part, id(g), n)
        if key not in self.cache:
            ws = g[part][:n]
            txt = " ".join(clean(w["w"]) if i == len(ws) - 1 and part == "after" else w["w"]
                           for i, w in enumerate(ws)).strip()
            txt = re.sub(r"[.;:…—]+$", "", txt)
            self.cache[key] = (_text_img(txt, SMALL, 74, self.color, track=-0.02, condense=0.88) if part == "before"
                               else _text_img(txt, ITAL, 68, self.color, track=-0.01)) if txt else None
        return self.cache[key]

    def active(self, t):
        return any(g["start"] - 0.02 <= t <= g["until"] + 0.35 for g in self.groups)

    def draw(self, canvas, t, front_mask=None, base=None):
        W = self.W
        for g in self.groups:
            if not (g["start"] - 0.02 <= t <= g["until"] + 0.35):
                continue
            if t > g["until"] + g["fade"]:
                continue
            fade = 1 - ease_out((t - g["until"]) / g["fade"]) if t > g["until"] else 1.0
            big, bpad, size = self._big(g)
            bw = big.shape[1] - 2 * bpad
            bh = big.shape[0] - 2 * bpad
            x0 = (W - bw) / 2                     # bord gauche du grand mot
            yb = self.y
            # 1) petits mots avant, alignés à gauche, au-dessus
            if g["before"] and t >= g["before"][0]["start"] - 0.02:
                im = self._small(g, "before", len(g["before"]))   # la ligne entière, en fondu doux
                if im:
                    img, pad = im
                    q = ease_out((t - g["before"][0]["start"]) / 0.3)
                    sh = img.shape[0] - 2 * pad
                    sw = img.shape[1] - 2 * pad
                    cx = min(max(x0 + sw / 2, 60 + sw / 2), W - 60 - sw / 2)   # reste dans l'écran
                    over(canvas, img, cx, yb - bh / 2 - sh / 2 - 22 + 14 * (1 - q), fade * q)
            # 2) grand mot, quand il est prononcé
            ks = g["key"][0]["start"]
            if t >= ks - 0.02:
                p = ease_out((t - ks) / 0.3)
                img = big
                if p < 0.97:   # arrive légèrement flou puis net (mise au point rapide)
                    import cv2
                    k = int(1 + 9 * (1 - p)) * 2 + 1
                    img = cv2.GaussianBlur(big, (k, k), 0)
                alpha = min(1.0, (t - ks) / 0.15)
                over(canvas, img, W / 2, yb + 14 * (1 - p), alpha * fade, 1.025 - 0.025 * p)
            # 3) petits mots après, en italique, alignés à droite, en dessous
            if g["after"] and t >= g["after"][0]["start"] - 0.02:
                im = self._small(g, "after", len(g["after"]))
                if im:
                    img, pad = im
                    q = ease_out((t - g["after"][0]["start"]) / 0.3)
                    fade_a = fade * q
                    sh = img.shape[0] - 2 * pad
                    sw = img.shape[1] - 2 * pad
                    cx = min(max(x0 + bw - sw / 2, 60 + sw / 2), W - 60 - sw / 2)
                    over(canvas, img, cx, yb + bh / 2 + sh / 2 + 26 + 14 * (1 - q), fade_a)
        if front_mask is not None and base is not None:   # les mains repassent devant le texte
            canvas[:] = canvas * (1 - front_mask) + base * front_mask
