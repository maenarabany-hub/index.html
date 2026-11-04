"""Style « carte » : étiquette pastille + titre Inter très gras + mot clé surligné + sous-ligne grise.

Utilisable seul (image de couverture / carte) ou sur la vidéo (sous-titres).
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

INTER = "/usr/share/fonts/opentype/inter/Inter-{}.otf"


def F(weight, size):
    return ImageFont.truetype(INTER.format(weight), size)


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


THEME = {
    "ink": "#151515", "highlight": "#F2C14E", "sub": "#727786",
    "pill_bg": "#F6EFD6", "pill_fg": "#9A873A", "dot": "#4CAF50", "bg": "#F9F8F5",
}


def tracked(d, xy, text, font, fill, track):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + track
    return x


def tracked_len(text, font, track):
    return sum(font.getlength(c) + track for c in text) - track


def layout_title(lines, size, track):
    """lines : liste de lignes ; chaque ligne = liste de (texte, surligné?)."""
    f = F("ExtraBold", size)
    out = []
    for line in lines:
        w = sum(tracked_len(t, f, track) for t, _ in line) + f.getlength(" ") * (len(line) - 1)
        out.append((line, w))
    return f, out


def render(tag=None, title=(), sub=None, width=1080, theme=THEME, size=118, bg=True, hl_progress=1.0,
           title_alpha=1.0, sub_alpha=1.0, tag_alpha=1.0):
    """Renvoie une image RGBA (width x hauteur utile). hl_progress : 0..1 pour animer le surligneur."""
    th = {k: rgb(v) for k, v in theme.items()}
    while True:   # la taille s'adapte pour que chaque ligne tienne dans la largeur
        track = -0.035 * size
        f, lines = layout_title(title, size, track)
        if max((w for _, w in lines), default=0) <= width - 110 or size < 40:
            break
        size = int(size * 0.94)
    line_h = int(size * 1.12)
    H = 60 + (90 if tag else 0) + line_h * len(lines) + (40 + 2 * int(size * 0.4) if sub else 0) + 60
    img = Image.new("RGBA", (width, H), th["bg"] + (255,) if bg else (0, 0, 0, 0))
    hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    txt = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dh, dt = ImageDraw.Draw(hl), ImageDraw.Draw(txt)
    y = 60
    if tag:   # pastille
        ft = F("SemiBold", 30)
        tw = tracked_len(tag, ft, 6)
        pw, ph = tw + 110, 62
        x0 = (width - pw) / 2
        dt.rounded_rectangle((x0, y, x0 + pw, y + ph), ph // 2, fill=th["pill_bg"] + (int(255 * tag_alpha),))
        cx, cy = x0 + 40, y + ph / 2
        dt.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=th["dot"] + (int(70 * tag_alpha),))
        dt.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=th["dot"] + (int(255 * tag_alpha),))
        tracked(dt, (x0 + 72, y + 14), tag, ft, th["pill_fg"] + (int(255 * tag_alpha),), 6)
        y += 90
    sp = f.getlength(" ")
    for line, w in lines:
        x = (width - w) / 2
        for k, (t, is_hl) in enumerate(line):
            tw = tracked_len(t, f, track)
            if is_hl:   # bloc surligneur (se déroule de gauche à droite)
                pad_x, top, bot = size * 0.16, size * 0.14, size * 0.12
                x1 = x - pad_x + (tw + 2 * pad_x) * hl_progress
                if hl_progress > 0.01:
                    dh.rounded_rectangle((x - pad_x, y + top, x1, y + line_h + bot), int(size * 0.12),
                                         fill=th["highlight"] + (int(255 * title_alpha),))
            tracked(dt, (x, y), t, f, th["ink"] + (int(255 * title_alpha),), track)
            x += tw + sp
        y += line_h
    if sub:
        fs = F("Bold", int(size * 0.42))
        y += 40
        for sl in _wrap(sub, fs, width - 240):
            sw = tracked_len(sl, fs, -1)
            tracked(dt, ((width - sw) / 2, y), sl, fs, th["sub"] + (int(255 * sub_alpha),), -1)
            y += int(size * 0.52)
    return Image.alpha_composite(Image.alpha_composite(img, hl), txt)


def _wrap(text, font, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if cur and font.getlength(t) > maxw:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + [cur]
