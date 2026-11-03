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
        pink, box, white = hex_rgb(st["ed_pink"]), hex_rgb(st["ed_box"]), (255, 255, 255)
        self.items = []
        for e in spec:
            words = []
            for w in e["words"]:      # [{"text","start"}] : le mot change au fil de la phrase
                words.append((w["start"], render_word(w["text"], pink, int(W * 0.92), e.get("size", 330))))
            label = render_label(e["label"].upper(), white, box) if e.get("label") else None
            self.items.append({"start": e["start"], "end": e["end"], "y": e.get("y", 560),
                               "words": words, "label": label})

    def draw_behind(self, canvas, t, W):
        for it in self.items:
            if not (it["start"] - 0.01 <= t <= it["end"] + 0.2):
                continue
            out_a = 1 - ease_out((t - it["end"]) / 0.18) if t > it["end"] else 1.0
            cur = [w for w in it["words"] if w[0] <= t + 1e-3]
            if not cur:
                continue
            ws, img = cur[-1]
            p = ease_out((t - ws) / 0.35)
            scale = (1.18 - 0.18 * p) * (1 + 0.03 * (t - ws) / 3)   # arrive en dézoomant + dérive
            alpha = min(1.0, (t - ws) / 0.12) * out_a
            over(canvas, img, W / 2, it["y"] + 30 * (1 - p), alpha, scale)

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
            h_word = it["words"][0][1].shape[0]
            x = W / 2 - (lab.shape[1] - vis) / 2
            over(canvas, cut, x, it["y"] - h_word * 0.42, out_a)


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
Style: Sub,Inter Medium,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,0,3,5,60,60,0,1
Style: Handle,Inter Medium,34,&H60FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,2,0,1,0,0,2,0,0,250,1

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
                parts.append(f"{{\\fnNoto Serif Display Medium\\i1\\fs104\\c{pink}{reveal}}}{txt}{{\\r}}")
            else:
                parts.append(f"{{{reveal}}}{txt}")
        line = " ".join(parts)
        ev.append(f"Dialogue: 1,{motion._ts(g0)},{motion._ts(g1)},Sub,,0,0,0,,"
                  f"{{\\an5\\pos({W // 2},{y})\\fad(0,80)}}{line}")
    ev.append(f"Dialogue: 0,{motion._ts(0)},{motion._ts(total)},Handle,,0,0,0,,{st.get('handle', '@maenarbny')}")
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


def dim_background(img, st):
    """Fond assombri et désaturé pour que le rose ressorte (look sombre de la référence)."""
    k = st.get("ed_bg_dim", 0.5)
    gray = img.mean(axis=2, keepdims=True)
    return (img * 0.6 + gray * 0.4) * k


def render_editorial(src, front_ass, dst, words, joins, keyword_times, spec, st, has_audio=True):
    import cv2

    W, H, fps = st["width"], st["height"], st["fps"]
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", src], capture_output=True, text=True).stdout)
    cuts = motion.plan_cuts(words, total, st["cut_every"], joins)
    cam = motion.Camera(cuts, total, keyword_times, joins, st)
    lock = Lockups(spec, st)
    seg = Segmenter()
    print(f"  {len(cuts)} cuts, {len(spec)} grands titres derrière, détourage mediapipe")

    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf",
                            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}",
                            "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    ass_esc = str(front_ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    enc_cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-"]
    if has_audio:
        enc_cmd += ["-i", src, "-map", "0:v", "-map", "1:a", "-af", "loudnorm=I=-14:TP=-1:LRA=11",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    enc_cmd += ["-vf", f"ass='{ass_esc}'", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", "-shortest", dst]
    enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)

    size, n = W * H * 3, 0
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        t = n / fps
        z, dx, dy, blur, flash = cam.at(t)
        cx, cy = W * (0.5 + dx), H * (0.40 + dy)

        def warp(zz):
            M = np.float32([[zz, 0, (1 - zz) * cx], [0, zz, (1 - zz) * cy]])
            return cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        if blur > 0.05:
            acc = np.zeros((H, W, 3), np.float32)
            for s in range(5):
                acc += warp(z * (1 + 0.06 * blur * s / 4))
            base8 = (acc / 5).astype(np.uint8)
        else:
            base8 = warp(z)
        base = grade(base8.astype(np.float32), W, H)

        mask = seg.person(base8)
        behind = dim_background(base, st)
        lock.draw_behind(behind, t, W)
        out = base * mask + behind * (1 - mask)
        lock.draw_front(out, t, W)
        if flash > 0:
            out = out * (1 - flash) + 255 * flash
        enc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
        n += 1
        if n % (fps * 5) == 0:
            print(f"    {t:5.1f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.wait()
    if enc.returncode:
        raise SystemExit("Échec de l'encodage")
