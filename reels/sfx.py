"""Bruitages synthétisés (aucun fichier externe) pour les hooks auditifs.

Chaque fonction renvoie un tableau numpy mono float32 à 48 kHz, crête ~1.0.
"""
import wave

import numpy as np

SR = 48000
rng = np.random.default_rng(7)


def _env(n, attack, decay):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / decay)


def _lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):  # filtre 1 pôle (sons courts : rapide)
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def impact(dur=0.9):
    """Boom grave pour la première seconde (hook)."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = 45 + 90 * np.exp(-t * 18)                 # chute de fréquence
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.5)
    click = rng.standard_normal(n) * np.exp(-t * 120) * 0.5
    x = body + click
    return (x / np.abs(x).max()).astype(np.float32) * 0.9


def whoosh(dur=0.45, up=True):
    """Souffle filtré qui monte puis s'éteint (transitions, titres)."""
    n = int(SR * dur)
    t = np.linspace(0, 1, n)
    noise = rng.standard_normal(n)
    cutoff = (0.02 + 0.25 * t) if up else (0.27 - 0.25 * t)
    y = np.empty(n, np.float32)
    acc = 0.0
    for i in range(n):
        acc += cutoff[i] * (noise[i] - acc)
        y[i] = acc
    shape = np.sin(np.pi * t) ** 1.5
    return (y * shape / (np.abs(y).max() + 1e-6)).astype(np.float32) * 0.8


def pop(freq=900):
    """Petit 'pop' quand un widget apparaît."""
    n = int(SR * 0.12)
    t = np.arange(n) / SR
    f = freq * (1 + 1.5 * np.exp(-t * 60))
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.03)).astype(np.float32)


def tick():
    n = int(SR * 0.04)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 180)).astype(np.float32) * 0.6


def key():
    """Clic de clavier."""
    n = int(SR * 0.035)
    t = np.arange(n) / SR
    x = rng.standard_normal(n) * np.exp(-t * 260) + np.sin(2 * np.pi * (1800 + rng.integers(-300, 300)) * t) * np.exp(-t * 300) * 0.4
    return (x / np.abs(x).max()).astype(np.float32) * 0.5


def ding():
    """Notification (cloche douce : deux notes)."""
    out = np.zeros(int(SR * 1.0), np.float32)
    for k, (f, d) in enumerate([(1318.5, 0.0), (1760.0, 0.11)]):
        n = int(SR * 0.85)
        t = np.arange(n) / SR
        s = sum(a * np.sin(2 * np.pi * f * m * t) for m, a in [(1, 1.0), (2.01, 0.35), (3.02, 0.12)])
        s = s * _env(n, 0.003, 0.25)
        i = int(SR * d)
        out[i:i + n] += s[:len(out) - i].astype(np.float32)
    return out / np.abs(out).max() * 0.8


def build_track(events, total, path):
    """events : liste (t, son, gain_dB). Écrit un WAV stéréo 48 kHz."""
    track = np.zeros(int(SR * (total + 1.5)), np.float32)
    for t, snd, gain_db in events:
        i = int(t * SR)
        if i < 0 or i >= len(track):
            continue
        g = 10 ** (gain_db / 20)
        seg = snd[:len(track) - i] * g
        track[i:i + len(seg)] += seg
    track = np.tanh(track)  # sécurité anti-saturation
    pcm = (np.repeat(track[:, None], 2, axis=1) * 32000).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path
