# Montage Reels @maenarbny

Pipeline automatique pour Reels verticaux **1080x1920**.

## Style (dans `style.json`)
- Sous-titres **mot par mot**, police **Inter ExtraBold blanche**, contour noir, petit effet "pop"
- Mots importants en **rouge cerise #D2042D** (liste dans `keywords.txt`, plus les chiffres, %, € et $ en automatique)
- Rythme rapide : silences coupés (jump cuts) + **un cut toutes les 1.5 s** (alternance plan normal / punch-in 112 %)
- Son normalisé à -14 LUFS (niveau Instagram)

## Utilisation
```bash
# 1. Déposer le rush dans rush/
python3 reel.py rush/mon_rush.mp4
# -> output/mon_rush_reel.mp4  (+ work/mon_rush/words.json et subs.ass)

# 2. Corriger une faute de transcription ou forcer un mot en rouge ("hl": true) dans words.json, puis :
python3 reel.py rush/mon_rush.mp4 --words work/mon_rush/words.json
```

## Plusieurs rushes + script
```bash
python3 reel.py rush/rush_1.mp4 rush/rush_2.mp4 rush/rush_3.mp4 --name becoming_her_intro \
  --script projets/becoming_her_intro/script.txt --keywords projets/becoming_her_intro/keywords.txt
```
- Les rushes sont montés dans l'ordre donné.
- `--script` : whisper donne les timings, le script donne l'orthographe (Maïna -> Maena, Bicomy Heard -> Becoming Her).
  Les impros dites à l'oral mais absentes du script sont gardées.
- `--keywords` : mots en couleur propres à cette vidéo (en plus de `keywords.txt`).

## Dépendances
- ffmpeg (avec libass), polices Inter (déjà installées)
- `pip install faster-whisper` ; modèle whisper `small` dans `models/whisper-small/` (non versionné).
  Si huggingface.co est autorisé, mettre `"whisper_model": "medium"` dans `style.json` pour plus de précision.
