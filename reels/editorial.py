"""Preset « éditorial » @maenarbny (inspiré des edits haut de gamme) :

- Grand mot en serif italique rose DERRIÈRE la personne (détourage mediapipe)
- Étiquette bordeaux en capitales grotesk qui chevauche le grand mot
- Sous-titres fins par groupes de mots, apparition mot à mot ; mots clés en serif italique rose
- Cuts calés sur les blancs, cadrages variés, transitions aux raccords (repris de motion.py)
- Étalonnage légèrement contrasté + vignette, signature @maenarbny
"""
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np

import motion

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
SERIF = str(FONTS / "NotoSerifDisplay-500-italic.ttf")
GROTESK = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


# ------------------------------------------------------------ rendu PIL
def render_word(text, color, max_w, size, condense=0.86):
    """Grand mot serif italique -> image RGBA (rétrécie si trop large)."""
    from PIL import Image, ImageDraw, ImageFont
    while True:
        f = ImageFont.truetype(SERIF, size)
        l, t, r, b = f.getbbox(text)
        w = int((r - l) * condense)
        if w <= max_w or size < 80:
            break
        size = int(size * 0.94)
    img = Image.new("RGBA", (r - l + 40, b - t + 40), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((20 - l, 20 - t), text, font=f, fill=color + (255,))
    img = img.resize((int(img.width * condense), img.height), Image.LANCZOS)
    return np.array(img)


def render_label(text, fg, bg, size=58, pad=(26, 14)):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(GROTESK, size)
    l, t, r, b = f.getbbox(text)
    img = Image.new("RGBA", (r - l + 2 * pad[0], int(size * 0.78) + 2 * pad[1] + 8), bg + (255,))
    ImageDraw.Draw(img).text((pad[0] - l, pad[1] - t + 2), text, font=f, fill=fg + (255,))
    return np.array(img)


def over(dst, src_rgba, x, y, alpha=1.0, scale=1.0):
    """Colle src (RGBA, centré en x,y) sur dst (float32 BGR) avec échelle et opacité."""
    import cv2
    if alpha <= 0.001:
        return
    s = src_rgba
    if abs(scale - 1) > 0.002:
        s = cv2.resize(s, (max(1, int(s.shape[1] * scale)), max(1, int(s.shape[0] * scale))),
                       interpolation=cv2.INTER_LINEAR)
    h, w = s.shape[:2]
    x0, y0 = int(x - w / 2), int(y - h / 2)
    H, W = dst.shape[:2]
    ax0, ay0, ax1, ay1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if ax1 <= ax0 or ay1 <= ay0:
        return
    crop = s[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0].astype(np.float32)
    a = crop[:, :, 3:4] / 255.0 * alpha
    rgb = crop[:, :, 2::-1]  # RGBA -> BGR
    region = dst[ay0:ay1, ax0:ax1]
    region[:] = region * (1 - a) + rgb * a


# ------------------------------------------------------------ lockups
class Lockups:
    """Grands mots (derrière) + étiquettes, d'après projets/<nom>/editorial.json."""

    def __init__(self, spec, st):
        W = st["width"]
        pink = hex_rgb(st.get("ed_word_color", st["ed_pink"]))
        box = hex_rgb(st["ed_box"])
        white = hex_rgb(st.get("ed_label_text", "#FFFFFF"))
        self.items = []
        for e in spec:
            words = []
            for w in e["words"]:      # [{"text","start"}] : le mot change au fil de la phrase
                words.append((w["start"], render_word(w["text"], pink, int(W * 0.92), e.get("size", 330))))
            label = render_label(e["label"].upper(), white, box) if e.get("label") else None
            self.items.append({"start": e["start"], "end": e["end"], "y": e.get("y", 560),
                               "words": words, "label": label})

    def active(self, t):
        return any(it["start"] - 0.01 <= t <= it["end"] + 0.2 for it in self.items)

    def draw_behind(self, canvas, t, W, head_top=None):
        for it in self.items:
            if not (it["start"] - 0.01 <= t <= it["end"] + 0.2):
                it.pop("locked", None)
                continue
            out_a = 1 - ease_out((t - it["end"]) / 0.18) if t > it["end"] else 1.0
            cur = [w for w in it["words"] if w[0] <= t + 1e-3]
            if not cur:
                continue
            ws, img = cur[-1]
            # position calée sur le haut de la tête : ~45 % du mot passe derrière les cheveux,
            # figée à l'apparition du mot pour éviter que le texte bouge
            locked = it.setdefault("locked", {})
            if ws not in locked:
                h = img.shape[0]
                y = it["y"] if head_top is None else head_top - 0.05 * h
                locked[ws] = max(h / 2 + 150, min(y, it["y"] + 200))
            it["cur_y"], it["cur_h"] = locked[ws], img.shape[0]
            p = ease_out((t - ws) / 0.35)
            scale = (1.18 - 0.18 * p) * (1 + 0.03 * (t - ws) / 3)   # arrive en dézoomant + dérive
            alpha = min(1.0, (t - ws) / 0.12) * out_a
            over(canvas, img, W / 2, it["cur_y"] + 30 * (1 - p), alpha, scale)

    def draw_front(self, canvas, t, W):
        for it in self.items:
            if it["label"] is None or not (it["start"] <= t <= it["end"] + 0.2):
                continue
            out_a = 1 - ease_out((t - it["end"]) / 0.18) if t > it["end"] else 1.0
            p = ease_out((t - it["start"]) / 0.3)
            lab = it["label"]
            # révélation de la boîte de gauche à droite
            vis = max(1, int(lab.shape[1] * p))
            cut = lab[:, :vis]
            if "cur_y" not in it:
                continue
            x = W / 2 - (lab.shape[1] - vis) / 2
            over(canvas, cut, x, max(lab.shape[0] / 2 + 120, it["cur_y"] - it["cur_h"] * 0.42), out_a)


# ------------------------------------------------------------ sous-titres
def phrase_groups(words, kw_test, max_words=4, max_gap=0.5):
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end_punct = re.search(r"[.,!?;:]$", w["w"])
        if (len(cur) >= max_words or end_punct or nxt is None or nxt["start"] - w["end"] > max_gap
                or kw_test(w)):
            groups.append(cur)
            cur = []
    return groups


def build_front_ass(words, out_ass, st, kw_test, total, cta=None):
    """Sous-titres fins par groupes, mots révélés un à un ; mots clés en serif italique rose."""
    W, H = st["width"], st["height"]
    pink = motion.ass_c(st["ed_pink"])
    y = st.get("ed_sub_y", 1300)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Inter Medium,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,0,3,5,60,60,0,1
Style: Handle,Inter Medium,38,&H60FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,2,0,1,0,0,2,0,0,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for g in phrase_groups(words, kw_test):
        g0 = g[0]["start"]
        g1 = max(g[-1]["end"] + 0.15, g0 + 0.3)
        nxt = [w for w in words if w["start"] > g[-1]["start"]]
        if nxt:
            g1 = min(g1 + 0.35, nxt[0]["start"])
        parts = []
        for w in g:
            txt = re.sub(r"[.,;:…—]+$", "", w["w"]).replace("{", "(").replace("}", ")")
            d = int((w["start"] - g0) * 1000)
            reveal = f"\\alpha&HFF&\\t({d},{d + 90},\\alpha&H00&)"
            if kw_test(w):
                parts.append(f"{{\\fnNoto Serif Display Medium\\i1\\fs126\\c{pink}{reveal}}}{txt}{{\\r}}")
            else:
                parts.append(f"{{{reveal}}}{txt}")
        line = " ".join(parts)
        ev.append(f"Dialogue: 1,{motion._ts(g0)},{motion._ts(g1)},Sub,,0,0,0,,"
                  f"{{\\an5\\pos({W // 2},{y})\\fad(0,80)}}{line}")
    if st.get("handle"):
        ev.append(f"Dialogue: 0,{motion._ts(0)},{motion._ts(total)},Handle,,0,0,0,,{st['handle']}")
    Path(out_ass).write_text(head + "\n".join(ev) + "\n", encoding="utf-8")


# ------------------------------------------------------------ détourage
class Segmenter:
    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        self.mp = mp
        opt = vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=str(ROOT / "models" / "selfie_multiclass_256x256.tflite")),
            output_confidence_masks=True, output_category_mask=False)
        self.seg = vision.ImageSegmenter.create_from_options(opt)
        self.prev = None

    def person(self, bgr):
        import cv2
        small = cv2.resize(bgr, (bgr.shape[1] // 2, bgr.shape[0] // 2), interpolation=cv2.INTER_AREA)
        rgb = np.ascontiguousarray(small[:, :, ::-1])
        r = self.seg.segment(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb))
        m = 1.0 - r.confidence_masks[0].numpy_view().reshape(small.shape[:2])
        m = np.clip((m - 0.25) / 0.5, 0, 1).astype(np.float32)            # bords plus nets
        if self.prev is not None:
            m = 0.55 * m + 0.45 * self.prev                                # lissage temporel
        self.prev = m
        m = cv2.GaussianBlur(m, (5, 5), 0)
        return cv2.resize(m, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_LINEAR)[:, :, None]


# ------------------------------------------------------------ rendu
def grade(img, W, H, _cache={}):
    """Contraste doux + vignette (img float32 BGR 0..255)."""
    if (W, H) not in _cache:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2)
        _cache[(W, H)] = (1 - 0.32 * np.clip(d - 0.35, 0, 1) ** 1.5)[:, :, None].astype(np.float32)
    img = (img - 128) * 1.06 + 124
    return img * _cache[(W, H)]


def top_of_head(mask, prev=None):
    """Première ligne où la personne occupe le centre de l'image (lissée dans le temps)."""
    m = mask[:, :, 0]
    W = m.shape[1]
    band = m[:, int(W * 0.3):int(W * 0.7)].mean(axis=1)
    rows = np.where(band > 0.35)[0]
    y = float(rows[0]) if len(rows) else (prev or m.shape[0] * 0.25)
    return y if prev is None else 0.7 * prev + 0.3 * y


def dim_background(img, st):
    """Fond assombri et désaturé pour que le rose ressorte (look sombre de la référence)."""
    k = st.get("ed_bg_dim", 1.0)
    if k >= 0.999:
        return img.copy()
    gray = img.mean(axis=2, keepdims=True)
    return (img * 0.6 + gray * 0.4) * k


class BRoll:
    """Plan d'illustration : remplace l'image (le son de la voix continue)."""

    def __init__(self, e, W, H, fps):
        self.file, self.start, self.end = e["file"], e["start"], e["end"]
        self.offset, self.W, self.H, self.fps = e.get("offset", 0.0), W, H, fps
        self.zoom = e.get("zoom", [1.0, 1.08])
        self.proc, self.last = None, None

    def covers(self, t):
        return self.start <= t < self.end

    def frame(self):
        if self.proc is None:
            vf = (f"scale={self.W}:{self.H}:force_original_aspect_ratio=increase,crop={self.W}:{self.H},"
                  f"fps={self.fps}")
            self.proc = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-ss", str(self.offset), "-i", self.file, "-an", "-vf", vf,
                 "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
        buf = self.proc.stdout.read(self.W * self.H * 3)
        if len(buf) == self.W * self.H * 3:
            self.last = np.frombuffer(buf, np.uint8).reshape(self.H, self.W, 3)
        return self.last  # si le clip est trop court : on fige la dernière image

    def close(self):
        if self.proc:
            self.proc.kill()


WIDE = [(1.00, 0.0, 0.0), (1.05, 0.02, -0.01), (1.03, -0.02, 0.0)]
TIGHT = [(1.00, 0.0, 0.0), (1.12, 0.0, -0.03), (1.06, 0.03, -0.01), (1.15, -0.02, -0.04)]


class EdCamera:
    """Cadrage stable : changements de zoom UNIQUEMENT sur les cuts (aux fins de phrase),
    plans larges pendant les grands titres, rien pendant les illustrations."""

    def __init__(self, words, total, joins, lock, brolls, kw_times, st):
        every = st.get("ed_cut_every", 3.0)
        gaps = [(words[i]["end"] + words[i + 1]["start"]) / 2 for i in range(len(words) - 1)]
        strong = [g for i, g in enumerate(gaps) if re.search(r"[.,!?;:]$", words[i]["w"])]
        busy = [(b.start - 0.5, b.end + 0.5) for b in brolls]
        cuts, last = [], 0.0
        for g in strong + gaps:  # d'abord les fins de phrase, puis les autres blancs si besoin
            if g - last < every * 0.8 or any(a <= g <= b for a, b in busy):
                continue
            if all(abs(g - c) >= every * 0.8 for c in cuts):
                cuts.append(g)
        self.bounds = [0.0] + sorted(c for c in cuts if c < total - 1.0) + [total]
        self.framing = []
        for i in range(len(self.bounds) - 1):
            a, b = self.bounds[i], self.bounds[i + 1]
            titled = any(it["start"] < b and it["end"] > a for it in lock.items)
            pool = WIDE if titled else TIGHT
            self.framing.append(pool[i % len(pool)])
        self.joins = [j for j in joins if not any(br.start - 0.05 <= j <= br.end + 0.05 for br in brolls)]
        self.kw = kw_times
        self.drift = st.get("motion_drift", 0.02)

    def at(self, t):
        i = max(k for k, b in enumerate(self.bounds[:-1]) if b <= t + 1e-6)
        a, b = self.bounds[i], self.bounds[i + 1]
        z, dx, dy = self.framing[i]
        z *= 1 + self.drift * (t - a) / max(b - a, 0.01)
        for k in self.kw:
            if 0 <= t - k < 0.35:
                x = (t - k) / 0.35
                z *= 1 + 0.025 * math.sin(math.pi * min(x * 2.2, 1)) * (1 - x) ** 0.5
        blur = 0.0
        for j in self.joins:   # raccord non couvert : zoom flou court, sans flash
            d = t - j
            if -0.15 < d < 0.18:
                p = ease_out(1 - abs(d) / (0.15 if d < 0 else 0.18))
                z *= 1 + 0.18 * p
                blur = max(blur, p)
        return z, dx, dy, blur


def sound_events(lock, brolls, cam, widgets):
    import sfx
    ev = [(0.0, sfx.impact(), -8)]                                  # hook : boom d'entrée
    for it in lock.items:
        ev.append((max(0.0, it["start"] - 0.12), sfx.whoosh(0.35), -21))
        for ws, _ in it["words"][1:]:
            ev.append((ws, sfx.tick(), -22))
    for b in brolls:
        ev.append((b.start - 0.15, sfx.whoosh(0.4), -17))
    for j in cam.joins:
        ev.append((j - 0.2, sfx.whoosh(0.45), -16))
    for w in widgets:
        ev += w.sfx()
    return ev


def render_editorial(src, front_ass, dst, words, joins, keyword_times, spec, st, has_audio=True, broll_spec=(),
                     widget_spec=()):
    import cv2
    import sfx
    import widgets as wmod

    W, H, fps = st["width"], st["height"], st["fps"]
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", src], capture_output=True, text=True).stdout)
    lock = Lockups(spec, st)
    brolls = [BRoll(e, W, H, fps) for e in broll_spec]
    cam = EdCamera(words, total, joins, lock, brolls, keyword_times, st)
    seg = Segmenter()
    wids = wmod.load(widget_spec, st)
    sfx_path = Path(dst).with_suffix(".sfx.wav")
    sfx.build_track(sound_events(lock, brolls, cam, wids), total, sfx_path)
    print(f"  {len(wids)} widgets, bruitages -> {sfx_path.name}")
    print(f"  {len(cam.bounds) - 2} cuts, {len(brolls)} illustrations, {len(spec)} grands titres, "
          f"{len(cam.joins)} raccord(s) visibles")

    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf",
                            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}",
                            "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    ass_esc = str(front_ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    enc_cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-"]
    if has_audio:
        enc_cmd += ["-i", src, "-i", str(sfx_path), "-filter_complex",
                    f"[0:v]ass='{ass_esc}'[v];"
                    "[1:a]aresample=48000,loudnorm=I=-14:TP=-1.5:LRA=11[voix];"
                    "[voix][2:a]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]",
                    "-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        enc_cmd += ["-vf", f"ass='{ass_esc}'"]
    enc_cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19",
                "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", "-shortest", dst]
    enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)

    size, n, head_top, source = W * H * 3, 0, None, None
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        t = n / fps
        br = next((b for b in brolls if b.covers(t)), None)
        if br is not None:
            frame = br.frame()
            p = (t - br.start) / max(br.end - br.start, 0.01)
            z, dx, dy, blur = br.zoom[0] + (br.zoom[1] - br.zoom[0]) * p, 0.0, 0.0, 0.0
        else:
            frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            z, dx, dy, blur = cam.at(t)
        if source is not br:            # changement de source : on repart à zéro pour le détourage
            seg.prev, head_top, source = None, None, br
        cx, cy = W * (0.5 + dx), H * (0.40 + dy)

        def warp(zz):
            M = np.float32([[zz, 0, (1 - zz) * cx], [0, zz, (1 - zz) * cy]])
            return cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        if blur > 0.05:
            acc = np.zeros((H, W, 3), np.float32)
            for s in range(5):
                acc += warp(z * (1 + 0.05 * blur * s / 4))
            base8 = (acc / 5).astype(np.uint8)
        else:
            base8 = warp(z)
        base = base8.astype(np.float32)
        if st.get("ed_grade", False):
            base = grade(base, W, H)

        if lock.active(t):
            mask = seg.person(base8)
            head_top = top_of_head(mask, head_top)
            behind = dim_background(base, st)
            lock.draw_behind(behind, t, W, head_top)
            out = base * mask + behind * (1 - mask)
            lock.draw_front(out, t, W)
        else:
            seg.prev, head_top = None, None
            out = base
        for w in wids:
            w.draw(out, t)
        enc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
        n += 1
        if n % (fps * 5) == 0:
            print(f"    {t:5.1f}s", flush=True)
    for b in brolls:
        b.close()
    enc.stdin.close()
    enc.wait()
    dec.wait()
    if enc.returncode:
        raise SystemExit("Échec de l'encodage")
