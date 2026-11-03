#!/usr/bin/env python3
"""Pipeline de montage Reels @maenarbny (vertical 1080x1920).

Étapes :
  1. Suppression des silences (jump cuts sur les blancs)
  2. Transcription mot par mot (faster-whisper)       -> work/<nom>/words.json
  3. Sous-titres mot par mot, Inter blanc, mots clés en rouge cerise -> work/<nom>/subs.ass
  4. Rendu final : recadrage 9:16, punch-in alterné toutes les 1.5 s,
     sous-titres incrustés                             -> output/<nom>_reel.mp4

Usage :
  python3 reel.py rush/mon_rush.mp4
  python3 reel.py rush/r1.mp4 rush/r2.mp4 rush/r3.mp4 --name intro --script scripts/intro.txt
  python3 reel.py rush/mon_rush.mp4 --words work/mon_rush/words.json   # transcription déjà corrigée
  python3 reel.py rush/mon_rush.mp4 --no-silence-cut
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd, capture=False):
    print("  $", " ".join(str(c) for c in cmd)[:200], flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-3000:])
        sys.exit(f"Commande échouée ({cmd[0]})")
    return r.stderr if capture else None


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout.strip()
    return float(out)


def has_audio(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    return bool(out)


# ---------------------------------------------------------------- 1. silences
def cut_silences(src, dst, st):
    total = duration(src)
    log = run(["ffmpeg", "-hide_banner", "-i", src, "-af",
               f"silencedetect=noise={st['silence_threshold_db']}dB:d={st['silence_min_duration']}",
               "-f", "null", "-"], capture=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    if len(ends) < len(starts):
        ends.append(total)
    pad = st["silence_padding"]
    keep, cur = [], 0.0
    for s, e in zip(starts, ends):
        if s + pad > cur:
            keep.append((cur, min(s + pad, total)))
        cur = max(cur, e - pad)
    if cur < total:
        keep.append((cur, total))
    keep = [(a, b) for a, b in keep if b - a > 0.05]
    if not keep or (len(keep) == 1 and keep[0][1] - keep[0][0] > total - 0.1):
        print("  Aucun silence à couper.")
        return src
    removed = total - sum(b - a for a, b in keep)
    print(f"  {len(keep)} segments gardés, {removed:.1f}s de silence retirées")
    parts, labels = [], []
    for i, (a, b) in enumerate(keep):
        parts.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{i}];")
        labels.append(f"[v{i}][a{i}]")
    fc = "".join(parts) + "".join(labels) + f"concat=n={len(keep)}:v=1:a=1[v][a]"
    script = Path(dst).with_suffix(".filter")
    script.write_text(fc)
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src,
         "-filter_complex_script", str(script), "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", dst])
    return dst


# ---------------------------------------------------------- 2. transcription
def load_audio(path):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def merge_tokens(words):
    """Recolle les morceaux de whisper : J + 'ai -> J'ai, laisse + -moi -> laisse-moi."""
    out = []
    for w in words:
        if out and (w["w"][:1] in "'’-" or w["w"] in "?!:;" or out[-1]["w"][-1:] in "'’"):
            out[-1]["w"] += w["w"] if w["w"] not in "?!:;" else " " + w["w"]
            out[-1]["end"] = w["end"]
        else:
            out.append(dict(w))
    return out


def transcribe(src, out_json, st):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper n'est pas installé : pip install faster-whisper")
    model_name = st["whisper_model"]
    local = ROOT / "models" / f"whisper-{model_name}"
    if local.exists():
        model_name = str(local)
    print(f"  Modèle whisper '{model_name}' (CPU int8)…")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(load_audio(src), language=st["language"], word_timestamps=True,
                                   beam_size=5)
    words = []
    for seg in segments:
        for w in seg.words:
            t = w.word.strip()
            if t:
                words.append({"w": t, "start": round(w.start, 3), "end": round(w.end, 3)})
    words = merge_tokens(words)
    for w in words:
        print(f"    {w['start']:6.2f}  {w['w']}")
    Path(out_json).write_text(json.dumps(words, ensure_ascii=False, indent=1))
    return words


def norm(t):
    import unicodedata
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def script_tokens(text):
    """Découpe le script en mots ; la ponctuation isolée (? ! :) se colle au mot d'avant, les tirets sautent."""
    toks = []
    for t in text.split():
        if not norm(t):
            if toks and t in "?!:;":
                toks[-1] += " " + t
            continue
        toks.append(t)
    return toks


def align_to_script(words, script_text):
    """Remplace le texte de whisper par celui du script en gardant les timings.
    Alignement mot à mot tolérant (Needleman-Wunsch + similarité de caractères) :
    - mots mal entendus (Maïna -> Maena) : texte du script, timing de whisper
    - impros (dites mais absentes du script) : gardées telles que whisper les a entendues
    - mots du script non prononcés : ignorés"""
    from difflib import SequenceMatcher
    script = script_tokens(script_text)
    A, B = [norm(w) for w in script], [norm(w["w"]) for w in words]
    n, m = len(A), len(B)

    def sim(x, y):
        return 1.0 if x == y else SequenceMatcher(None, x, y).ratio()

    GAP = -0.5
    S = [[0.0] * (m + 1) for _ in range(n + 1)]
    T = [[0] * (m + 1) for _ in range(n + 1)]  # 0 diag, 1 up (script seul), 2 left (whisper seul)
    for i in range(1, n + 1):
        S[i][0], T[i][0] = i * GAP, 1
    for j in range(1, m + 1):
        S[0][j], T[0][j] = j * GAP, 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            r = sim(A[i - 1], B[j - 1])
            d = S[i - 1][j - 1] + (2 * r if r >= 0.5 else -1.0)
            u, l = S[i - 1][j] + GAP, S[i][j - 1] + GAP
            S[i][j], T[i][j] = max((d, 0), (u, 1), (l, 2))
    pairs, i, j = [], n, m
    while i or j:
        t = T[i][j]
        if t == 0:
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif t == 1:
            pairs.append((i - 1, None)); i -= 1
        else:
            pairs.append((None, j - 1)); j -= 1
    pairs.reverse()

    # Regroupe entre "ancres" (mots identiques ou très proches) et répartit le temps.
    out, si, wj = [], [], []

    def flush():
        if wj and si:
            t0, t1 = words[wj[0]]["start"], words[wj[-1]]["end"]
            total = sum(len(A[k]) for k in si)
            t = t0
            for k in si:
                d = (t1 - t0) * len(A[k]) / total
                out.append({"w": script[k], "start": round(t, 3), "end": round(t + d, 3), "_s": k})
                t += d
        elif wj:
            out.extend(dict(words[k], impro=True) for k in wj)
        si.clear(); wj.clear()

    for a, b in pairs:
        if a is not None and b is not None and sim(A[a], B[b]) >= 0.8:
            flush()
            out.append({"w": script[a], "start": words[b]["start"], "end": words[b]["end"], "_s": a})
        else:
            if a is not None:
                si.append(a)
            if b is not None:
                wj.append(b)
    flush()

    # Majuscule de début de phrase du script qui n'en est plus une à l'oral
    for k, w in enumerate(out):
        s_idx = w.pop("_s", None)
        if k and s_idx and script[s_idx - 1][-1:] in ".?!" and out[k - 1]["w"][-1:] not in ".?!" \
                and w["w"][:1].isupper() and not w["w"].isupper():
            w["w"] = w["w"][0].lower() + w["w"][1:]
        elif k and out[k - 1]["w"][-1:] in ".?!" and w["w"][:1].islower():
            w["w"] = w["w"][0].upper() + w["w"][1:]
    return out


# ----------------------------------------------------------- 3. sous-titres
def ass_color(hex_rgb):
    h = hex_rgb.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def ts(t):
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def load_keywords(extra=None):
    kw = set()
    for f in [ROOT / "keywords.txt"] + ([Path(extra)] if extra else []):
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                kw.add(norm(line))
    return kw


def is_highlight(word, kw):
    if word.get("hl") is not None:
        return bool(word["hl"])
    return norm(word["w"]) in kw or bool(re.search(r"\d|%|€|\$", word["w"]))


def fix_timings(words, min_dur=0.12):
    """Évite les mots qui clignotent : départs strictement croissants, durée mini."""
    words = [dict(w) for w in words]
    i = 0
    while i < len(words):
        j = i
        while j + 1 < len(words) and words[j + 1]["start"] - words[i]["start"] < min_dur * (j + 1 - i):
            j += 1
        if j > i:  # plusieurs mots collés : on les étale jusqu'au mot suivant
            t0 = words[i]["start"]
            t1 = max(words[j + 1]["start"] if j + 1 < len(words) else words[j]["end"], t0 + min_dur * (j - i + 1))
            step = (t1 - t0) / (j - i + 1)
            for k in range(i, j + 1):
                words[k]["start"] = round(t0 + step * (k - i), 3)
                words[k]["end"] = max(words[k]["end"], round(words[k]["start"] + step, 3))
        i = j + 1
    return words


def build_ass(words, out_ass, st, keywords=None, overlays=None, total=None):
    kw = load_keywords(keywords)
    words = fix_timings(words)
    white, pink = ass_color(st["color_text"]), ass_color(st["color_highlight"])
    import motion
    extra_styles = "\n".join(motion.overlay_styles(st)) if overlays is not None else ""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {st['width']}
PlayResY: {st['height']}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{st['font']},{st['font_size']},{white},{white},&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,{st['outline']},{st['shadow']},2,60,60,{st['subtitle_margin_bottom']},1
{extra_styles}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for i, w in enumerate(words):
        start = w["start"]
        nxt = words[i + 1]["start"] if i + 1 < len(words) else w["end"] + 0.4
        end = nxt if nxt - w["end"] < 0.6 else w["end"] + 0.25  # reste affiché jusqu'au mot suivant
        if end <= start:
            end = start + 0.08
        text = w["w"].upper() if st["uppercase"] else w["w"]
        if st.get("strip_punctuation"):
            text = re.sub(r"[.,;:…—]+$", "", text).strip() or text
        text = text.replace("{", "(").replace("}", ")")
        tags = ""
        hl = is_highlight(w, kw)
        if hl:
            tags += f"\\c{pink}"
        if st["pop_animation"] and hl:       # mot clé : plus gros, rebond + petite rotation
            tags += ("\\frz-5\\fscx70\\fscy70\\t(0,90,\\fscx132\\fscy132\\frz2)"
                     "\\t(90,180,\\fscx118\\fscy118\\frz0)")
        elif st["pop_animation"]:            # mot normal : pop rapide
            tags += "\\fscx75\\fscy75\\t(0,70,\\fscx108\\fscy108)\\t(70,130,\\fscx100\\fscy100)"
        lines.append(f"Dialogue: 1,{ts(start)},{ts(end)},Word,,0,0,0,,{{{tags}}}{text}")
    if overlays is not None:
        lines += motion.overlay_events(overlays, total or words[-1]["end"] + 0.5, st)
    Path(out_ass).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return [w["start"] for w in words if is_highlight(w, kw)]


# ----------------------------------------------------------- 0. assemblage
def concat_rushes(rushes, dst, st):
    W, H, fps = st["width"], st["height"], st["fps"]
    parts = "".join(
        f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={fps},"
        f"format=yuv420p[v{i}];[{i}:a]aresample=48000,aformat=channel_layouts=stereo,"
        f"afade=t=in:d=0.02,afade=t=out:st={duration(rushes[i]) - 0.04:.3f}:d=0.04[a{i}];"
        for i in range(len(rushes)))
    labels = "".join(f"[v{i}][a{i}]" for i in range(len(rushes)))
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for r in rushes:
        cmd += ["-i", r]
    cmd += ["-filter_complex", parts + labels + f"concat=n={len(rushes)}:v=1:a=1[v][a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
            "-c:a", "aac", "-b:a", "256k", dst]
    run(cmd)
    joins, t = [], 0.0
    for r in rushes[:-1]:
        t += duration(r)
        joins.append(round(t, 3))
    return dst, joins


# ---------------------------------------------------------------- 4. rendu
def render(src, ass, dst, st):
    W, H, z, c = st["width"], st["height"], st["punch_in_zoom"], st["cut_every"]
    ZW, ZH = int(W * z) // 2 * 2, int(H * z) // 2 * 2
    ass_esc = str(ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    vf = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"setsar=1,fps={st['fps']},split[base][zin];"
        f"[zin]scale={ZW}:{ZH},crop={W}:{H}[zoom];"
        f"[base][zoom]overlay=0:0:enable='mod(floor(t/{c}),2)'[cut];"
        f"[cut]ass='{ass_esc}'[v]"
    )
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src,
           "-filter_complex", vf, "-map", "[v]"]
    if has_audio(src):
        cmd += ["-map", "0:a", "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-movflags", "+faststart", dst]
    run(cmd)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rush", nargs="+", help="un ou plusieurs rushes (montés dans l'ordre)")
    ap.add_argument("--name", help="nom du projet (défaut : nom du premier rush)")
    ap.add_argument("--script", help="texte du script : corrige l'orthographe de la transcription")
    ap.add_argument("--keywords", help="mots clés en couleur propres à cette vidéo (un par ligne)")
    ap.add_argument("--words", help="words.json existant (saute la transcription)")
    ap.add_argument("--motion", help="calques motion design (projets/<nom>/motion.json)")
    ap.add_argument("--editorial", help="preset éditorial : grands mots derrière la personne (projets/<nom>/editorial.json)")
    ap.add_argument("--broll", help="illustrations : projets/<nom>/broll.json")
    ap.add_argument("--simple", action="store_true", help="rendu simple sans motion design")
    ap.add_argument("--no-silence-cut", action="store_true")
    a = ap.parse_args()

    st = json.loads((ROOT / "style.json").read_text())
    rushes = [str(Path(r).resolve()) for r in a.rush]
    name = a.name or Path(rushes[0]).stem
    work = ROOT / "work" / name
    work.mkdir(parents=True, exist_ok=True)
    (ROOT / "output").mkdir(exist_ok=True)

    src, joins = rushes[0], []
    if len(rushes) > 1:
        print(f"0/4 Assemblage de {len(rushes)} rushes")
        src, joins = concat_rushes(rushes, str(work / "concat.mp4"), st)

    if st["remove_silences"] and not a.no_silence_cut and has_audio(src):
        print("1/4 Suppression des silences")
        tight = cut_silences(src, str(work / "tight.mp4"), st)
        if tight != src:
            joins = []  # les raccords ont bougé : pas de transition
        src = tight
    else:
        print("1/4 Suppression des silences : ignorée")

    if a.words:
        print(f"2/4 Transcription : {a.words}")
        words = json.loads(Path(a.words).read_text())
    else:
        print("2/4 Transcription mot par mot")
        words = transcribe(src, work / "words_raw.json", st)
        if a.script:
            words = align_to_script(words, Path(a.script).read_text())
            print("  Texte calé sur le script")
        (work / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=1))

    print("3/4 Sous-titres")
    ass = work / "subs.ass"
    if a.editorial:
        import editorial
        kw = load_keywords(a.keywords)
        fixed = fix_timings(words)
        test = lambda w: is_highlight(w, kw)
        editorial.build_front_ass(fixed, ass, st, test, total := duration(src))
        print("4/4 Rendu 1080x1920 éditorial")
        out = ROOT / "output" / f"{name}_editorial.mp4"
        editorial.render_editorial(src, ass, str(out), fixed, joins, [w["start"] for w in fixed if test(w)],
                                   json.loads(Path(a.editorial).read_text()), st, has_audio(src),
                                   json.loads(Path(a.broll).read_text()) if a.broll else ())
        print(f"\n✅ {out}  ({duration(out):.1f}s)")
        return

    use_motion = st.get("motion", True) and not a.simple
    total = duration(src)
    if use_motion:
        import motion
        overlays = motion.load_spec(a.motion)
        kw_times = build_ass(words, ass, st, a.keywords, overlays, total)
    else:
        build_ass(words, ass, st, a.keywords)

    print("4/4 Rendu 1080x1920" + (" + motion design" if use_motion else ""))
    out = ROOT / "output" / f"{name}_reel.mp4"
    if use_motion:
        motion.render_motion(src, ass, str(out), fix_timings(words), joins, kw_times, st, has_audio(src))
    else:
        render(src, ass, str(out), st)
    print(f"\n✅ {out}  ({duration(out):.1f}s)")


if __name__ == "__main__":
    main()
