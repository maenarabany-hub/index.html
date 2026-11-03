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
def transcribe(src, out_json, st):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper n'est pas installé : pip install faster-whisper")
    print(f"  Modèle whisper '{st['whisper_model']}' (CPU int8)…")
    model = WhisperModel(st["whisper_model"], device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(src), language=st["language"], word_timestamps=True,
                                   vad_filter=True)
    words = []
    for seg in segments:
        for w in seg.words:
            t = w.word.strip()
            if t:
                words.append({"w": t, "start": round(w.start, 3), "end": round(w.end, 3)})
                print(f"    {w.start:6.2f}  {t}")
    Path(out_json).write_text(json.dumps(words, ensure_ascii=False, indent=1))
    return words


# ----------------------------------------------------------- 3. sous-titres
def ass_color(hex_rgb):
    h = hex_rgb.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def ts(t):
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def load_keywords():
    kw = set()
    f = ROOT / "keywords.txt"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                kw.add(line.lower())
    return kw


def is_highlight(word, kw):
    if word.get("hl") is not None:
        return bool(word["hl"])
    clean = re.sub(r"[^\w%€$'-]", "", word["w"].lower())
    return clean in kw or bool(re.search(r"\d|%|€|\$", clean))


def build_ass(words, out_ass, st):
    kw = load_keywords()
    white, pink = ass_color(st["color_text"]), ass_color(st["color_highlight"])
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {st['width']}
PlayResY: {st['height']}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{st['font']},{st['font_size']},{white},{white},&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,{st['outline']},{st['shadow']},2,60,60,{st['subtitle_margin_bottom']},1

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
        text = text.replace("{", "(").replace("}", ")")
        tags = ""
        if is_highlight(w, kw):
            tags += f"\\c{pink}"
        if st["pop_animation"]:
            tags += "\\fscx85\\fscy85\\t(0,90,\\fscx100\\fscy100)"
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Word,,0,0,0,,{{{tags}}}{text}")
    Path(out_ass).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


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
    ap.add_argument("rush")
    ap.add_argument("--words", help="words.json existant (saute la transcription)")
    ap.add_argument("--no-silence-cut", action="store_true")
    a = ap.parse_args()

    st = json.loads((ROOT / "style.json").read_text())
    rush = Path(a.rush).resolve()
    name = rush.stem
    work = ROOT / "work" / name
    work.mkdir(parents=True, exist_ok=True)
    (ROOT / "output").mkdir(exist_ok=True)

    src = str(rush)
    if st["remove_silences"] and not a.no_silence_cut and has_audio(src):
        print("1/4 Suppression des silences")
        src = cut_silences(src, str(work / "tight.mp4"), st)
    else:
        print("1/4 Suppression des silences : ignorée")

    words_json = work / "words.json"
    if a.words:
        print(f"2/4 Transcription : {a.words}")
        words = json.loads(Path(a.words).read_text())
    else:
        print("2/4 Transcription mot par mot")
        words = transcribe(src, words_json, st)

    print("3/4 Sous-titres")
    ass = work / "subs.ass"
    build_ass(words, ass, st)

    print("4/4 Rendu 1080x1920")
    out = ROOT / "output" / f"{name}_reel.mp4"
    render(src, ass, str(out), st)
    print(f"\n✅ {out}  ({duration(out):.1f}s)")


if __name__ == "__main__":
    main()
