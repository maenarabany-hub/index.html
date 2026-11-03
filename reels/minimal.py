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


def smooth(x):
    """Courbe douce (entrée et sortie lentes)."""
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


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


def _wrap(txt, n):
    lines, cur = [], ""
    for w in txt.split():
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + [cur]


def _stack(lines, path, size, color, align, **kw):
    """Plusieurs lignes empilées (alignées à gauche ou à droite) -> (RGBA, pad)."""
    imgs = [_text_img(l, path, size, color, **kw) for l in lines]
    if len(imgs) == 1:
        return imgs[0]
    pad = imgs[0][1]
    gap = int(size * 0.12)
    inner = [(im[pad:im.shape[0] - pad], im) for im, _ in imgs]
    w_max = max(im.shape[1] for _, im in inner)
    H_ = sum(c.shape[0] for c, _ in inner) + gap * (len(inner) - 1) + 2 * pad
    out = np.zeros((H_, w_max, 4), np.uint8)
    y = pad
    for c, im in inner:
        x = 0 if align == "left" else w_max - im.shape[1]
        reg = out[y:y + c.shape[0], x:x + im.shape[1]]
        out[y:y + c.shape[0], x:x + im.shape[1]] = np.maximum(reg, c)
        y += c.shape[0] + gap
    return out, pad


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
    # fusion des morceaux trop courts pour être lus (même phrase, même morceau du montage)
    MIN_DUR, merged = 1.8, []
    for c in chunks:
        if merged:
            p = merged[-1]
            dur = c[0]["start"] - p[0]["start"]
            same_seg = p[0].get("_seg") == c[0].get("_seg")
            sentence_end = re.search(r"[.!?]$", p[-1]["w"])
            if same_seg and len(p) + len(c) <= 9 and (dur < MIN_DUR and not sentence_end or dur < 1.0):
                merged[-1] = p + c
                continue
        merged.append(c)
    ph = [p.split() for p in phrases]
    out = []
    for g in merged:
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
            k = max(keys, key=lambda k: len(clean(g[k]["w"]))) if keys else digits[0] if digits else \
                max(range(len(g)), key=lambda k: len(clean(g[k]["w"])))
            span = (k, k + 1)
        a, b = span
        out.append({"before": g[:a], "key": g[a:b], "after": g[b:], "start": g[0]["start"], "end": g[-1]["end"]})
    EXIT = 0.3
    LEAD = 0.18   # chaque bloc arrive un peu avant la voix : plus de temps pour lire
    prev_end = -1.0
    for g in out:
        g["start"] = max(g["start"] - LEAD, prev_end)
        prev_end = g["end"]
    for i, g in enumerate(out):   # la sortie se termine AVANT le bloc suivant (pas de fantôme)
        nxt = out[i + 1] if i + 1 < len(out) else None
        ns = nxt["start"] if nxt else g["end"] + 1.0
        g["until"] = max(g["key"][-1]["start"] + 0.45, min(ns - EXIT, g["end"] + 0.8))
        g["fade"] = EXIT
        if nxt and nxt["start"] < g["until"] + g["fade"]:    # jamais deux blocs en même temps
            nxt["start"] = g["until"] + g["fade"]
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
            if not txt:
                self.cache[key] = None
            elif part == "before":   # serif droit, aligné à gauche, 2 lignes si besoin
                self.cache[key] = _stack(_wrap(txt, 28), SMALL, 74, self.color, "left", track=-0.02, condense=0.88)
            else:                    # italique, aligné à droite
                self.cache[key] = _stack(_wrap(txt, 30), ITAL, 68, self.color, "right", track=-0.01)
        return self.cache[key]

    def active(self, t):
        return any(g["start"] - 0.02 <= t <= g["until"] + g["fade"] for g in self.groups)

    def draw(self, canvas, t, front_mask=None, base=None):
        """Placement fixe (marges constantes) et mouvements lents : entrée en fondu qui monte,
        sortie en fondu qui continue de monter, sans saut d'un bloc à l'autre."""
        W = self.W
        ENTER = 0.45
        left, right = 110, W - 110            # ancrages fixes : les lignes ne sautent plus
        for g in self.groups:
            if not (g["start"] - 0.02 <= t <= g["until"] + g["fade"]):
                continue
            out_p = smooth((t - g["until"]) / g["fade"]) if t > g["until"] else 0.0
            fade, lift = 1 - out_p, -18 * out_p
            big, bpad, size = self._big(g)
            bh = big.shape[0] - 2 * bpad
            yb = self.y
            if g["before"]:
                im = self._small(g, "before", len(g["before"]))
                if im:
                    img, pad = im
                    q = smooth((t - g["start"]) / ENTER)
                    sh, sw = img.shape[0] - 2 * pad, img.shape[1] - 2 * pad
                    over(canvas, img, left + sw / 2, yb - bh / 2 - sh / 2 - 22 + 16 * (1 - q) + lift, fade * q)
            ks = max(g["key"][0]["start"], g["start"])
            if t >= ks - 0.02:
                p = smooth((t - ks) / ENTER)
                img = big
                if p < 0.97:   # légère mise au point
                    import cv2
                    k = int(1 + 6 * (1 - p)) * 2 + 1
                    img = cv2.GaussianBlur(big, (k, k), 0)
                over(canvas, img, W / 2, yb + 16 * (1 - p) + lift, p * fade, 1.02 - 0.02 * p)
            as_ = max(g["after"][0]["start"], g["start"]) if g["after"] else 0
            if g["after"] and t >= as_ - 0.02:
                im = self._small(g, "after", len(g["after"]))
                if im:
                    img, pad = im
                    q = smooth((t - as_) / ENTER)
                    sh, sw = img.shape[0] - 2 * pad, img.shape[1] - 2 * pad
                    cx = max(right - sw / 2, left + sw / 2)
                    over(canvas, img, cx, yb + bh / 2 + sh / 2 + 26 + 16 * (1 - q) + lift, fade * q)
        if front_mask is not None and base is not None:   # les mains repassent devant le texte
            canvas[:] = canvas * (1 - front_mask) + base * front_mask
