"""Motion design pour les Reels @maenarbny.

- Cuts calés sur les blancs entre les mots (jamais en pleine syllabe), toutes les ~1.5 s
- Recadrages variés (zoom + léger décalage) avec une dérive lente dans chaque plan
- "Bump" de zoom sur chaque mot clé
- Transition zoom + flou + flash aux raccords entre rushes
- Calques texte (titres, puces, chapitres, CTA) et barre de progression en ASS
"""
import json
import math
import subprocess
from pathlib import Path

# ------------------------------------------------------------------ cuts
def plan_cuts(words, total, every, joins, window=0.45):
    """Un cut toutes les ~`every` s, déplacé vers le blanc entre deux mots le plus proche."""
    gaps = [0.0] + [(words[i]["end"] + words[i + 1]["start"]) / 2 for i in range(len(words) - 1)] + [total]
    cuts, t = [], every
    while t < total - every * 0.6:
        near = min(gaps, key=lambda g: abs(g - t))
        c = near if abs(near - t) <= window else t
        ok = all(abs(c - j) > 0.4 for j in joins) and (not cuts or c - cuts[-1] > every * 0.6)
        if ok:
            cuts.append(round(c, 3))
        t = (cuts[-1] if ok else t) + every   # avance toujours
    return sorted(cuts + list(joins))


# Cadrages (zoom, décalage x, décalage y) en proportion de l'image ; visage vers le tiers haut
FRAMINGS = [(1.00, 0.0, 0.0), (1.16, 0.0, -0.04), (1.07, 0.03, -0.02), (1.22, -0.02, -0.05),
            (1.04, -0.03, 0.0), (1.13, 0.02, -0.03)]


def ease_out(x):
    return 1 - (1 - x) ** 3


class Camera:
    def __init__(self, cuts, total, keyword_times, joins, st):
        self.bounds = [0.0] + cuts + [total]
        self.kw = keyword_times
        self.joins = joins
        self.drift = st.get("motion_drift", 0.035)
        self.bump = st.get("motion_keyword_bump", 0.045)

    def at(self, t):
        """Renvoie (zoom, dx, dy, flou, flash) au temps t."""
        i = max(k for k, b in enumerate(self.bounds[:-1]) if b <= t + 1e-6)
        a, b = self.bounds[i], self.bounds[i + 1]
        z, dx, dy = FRAMINGS[i % len(FRAMINGS)]
        z *= 1 + self.drift * (t - a) / max(b - a, 0.01)          # dérive lente
        for k in self.kw:                                           # bump mot clé
            if 0 <= t - k < 0.35:
                x = (t - k) / 0.35
                z *= 1 + self.bump * math.sin(math.pi * min(x * 2.2, 1)) * (1 - x) ** 0.5
        blur = flash = 0.0
        for j in self.joins:                                        # raccord rush
            d = t - j
            if -0.18 < d < 0.22:
                p = 1 - abs(d) / (0.18 if d < 0 else 0.22)
                p = ease_out(p)
                z *= 1 + 0.28 * p
                blur = max(blur, p)
                if abs(d) < 0.05:
                    flash = max(flash, 0.55 * (1 - abs(d) / 0.05))
        return z, dx, dy, blur, flash


def render_motion(src, ass, dst, words, joins, keyword_times, st, has_audio=True):
    import cv2
    import numpy as np

    W, H, fps = st["width"], st["height"], st["fps"]
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", src], capture_output=True, text=True).stdout)
    cuts = plan_cuts(words, total, st["cut_every"], joins)
    cam = Camera(cuts, total, keyword_times, joins, st)
    print(f"  {len(cuts)} cuts calés sur les blancs, {len(joins)} transitions de raccord")

    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf",
                            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}",
                            "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    ass_esc = str(ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    enc_cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-"]
    if has_audio:
        enc_cmd += ["-i", src, "-map", "0:v", "-map", "1:a", "-af", "loudnorm=I=-14:TP=-1:LRA=11",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    enc_cmd += ["-vf", f"ass='{ass_esc}'", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", "-shortest", dst]
    enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)

    size = W * H * 3
    n = 0
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

        if blur > 0.05:   # flou de zoom : moyenne de plusieurs échelles
            acc = np.zeros((H, W, 3), np.float32)
            steps = 5
            for s in range(steps):
                acc += warp(z * (1 + 0.06 * blur * s / (steps - 1)))
            out = acc / steps
        else:
            out = warp(z).astype(np.float32)
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


# --------------------------------------------------------------- calques
def ass_c(hex_rgb, alpha="00"):
    h = hex_rgb.lstrip("#")
    return f"&H{alpha}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def overlay_styles(st):
    red, white = ass_c(st["color_highlight"]), ass_c(st["color_text"])
    f = st.get("font_title", "Inter Black")
    return [
        # boîte pleine rouge (BorderStyle 3 : la couleur de contour = la boîte)
        f"Style: Title,{f},84,{white},{white},{red},&H00000000,0,0,0,0,100,100,1,0,3,22,0,8,80,80,300,1",
        f"Style: Chip,{f},62,{white},{white},{red},&H00000000,0,0,0,0,100,100,1,0,3,16,0,8,80,80,300,1",
        f"Style: Tag,{f},54,{ass_c('#111111')},{white},{white},&H00000000,0,0,0,0,100,100,1,0,3,14,0,8,80,80,300,1",
        f"Style: Big,{f},150,{white},{white},&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,8,4,8,60,60,300,1",
        "Style: Bar,Inter,10,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
    ]


def _ts(t):
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def overlay_events(spec, total, st):
    """spec : liste d'éléments {"text","start","end","style","y","anim"} (cf. projets/*/motion.json)."""
    W = st["width"]
    ev = []
    if st.get("progress_bar", True):
        red = ass_c(st["color_highlight"])
        ev.append(f"Dialogue: 5,{_ts(0)},{_ts(total)},Bar,,0,0,0,,"
                  f"{{\\an7\\pos(0,0)\\bord0\\shad0\\1c{red}\\fscx0\\t(0,{int(total * 1000)},\\fscx100)\\p1}}"
                  f"m 0 0 l {W} 0 {W} 12 0 12{{\\p0}}")
    for e in spec:
        style = e.get("style", "Title")
        y = e.get("y", 330)
        x = W // 2
        a, b = e["start"], e["end"]
        anim = e.get("anim", "drop")
        if anim == "drop":      # descend + rebond
            tags = (f"\\an8\\move({x},{y - 60},{x},{y},0,180)\\fad(60,160)"
                    f"\\fscx80\\fscy80\\t(0,140,\\fscx106\\fscy106)\\t(140,230,\\fscx100\\fscy100)")
        elif anim == "slide":   # glisse depuis la gauche
            tags = f"\\an8\\move({x - 380},{y},{x},{y},0,220)\\fad(40,160)\\frz4\\t(0,220,\\frz0)"
        elif anim == "slam":    # gros mot qui claque
            tags = (f"\\an8\\pos({x},{y})\\fad(0,140)\\fscx160\\fscy160\\alpha&HFF&"
                    f"\\t(0,110,\\fscx95\\fscy95\\alpha&H00&)\\t(110,200,\\fscx100\\fscy100)")
        elif anim == "pulse":   # CTA qui pulse
            tags = (f"\\an8\\pos({x},{y})\\fad(120,0)\\t(0,400,\\fscx106\\fscy106)\\t(400,800,\\fscx100\\fscy100)"
                    f"\\t(800,1200,\\fscx106\\fscy106)\\t(1200,1600,\\fscx100\\fscy100)"
                    f"\\t(1600,2000,\\fscx106\\fscy106)\\t(2000,2400,\\fscx100\\fscy100)")
        else:
            tags = f"\\an8\\pos({x},{y})\\fad(80,120)"
        text = e["text"].replace("\n", "\\N")
        ev.append(f"Dialogue: 3,{_ts(a)},{_ts(b)},{style},,0,0,0,,{{{tags}}}{text}")
    return ev


def load_spec(path):
    return json.loads(Path(path).read_text()) if path else []
