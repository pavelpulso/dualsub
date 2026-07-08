<h1 align="center">dualsub</h1>

<p align="center">
  <b>Turn any video into study-ready, dual-language subtitles — transcribe the spoken language, translate it, and watch with both tracks toggleable.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="license">
  <img src="https://img.shields.io/badge/ASR-Whisper%20large--v3-orange.svg" alt="whisper">
  <img src="https://img.shields.io/badge/engines-Groq%20%7C%20WhisperX%20%7C%20faster--whisper-purple.svg" alt="engines">
</p>

---

## Why I built this

I'm learning **Spanish**, and the best way I've found is to watch a show I already love — *Friends* — dubbed in Spanish, with my native **Russian** as a safety net for the lines I don't catch yet.

The catch: downloaded Spanish subtitles never match a *dub* (they're timed to a different track and drift out of sync), and off-the-shelf machine translation of them is often gibberish. My first attempt a year ago produced 60-second runaway subtitle blocks and broken translations like *"Доверие Exal"*.

So I rebuilt it properly. `dualsub` transcribes the **actual audio** of an episode with a modern Whisper model, translates it with sane batching, and lets me watch in Spanish while revealing the Russian line only when I'm stuck. Nothing is hardcoded to those two languages — `--source` and `--to` take any language code.

## What it does

- 🎧 **Transcribe** any video/audio to `.srt`, synced to what's actually spoken.
- 🔌 **Pluggable ASR engines** — choose per run with `--engine`:
  | Engine | Best for | Notes |
  |--------|----------|-------|
  | `groq` *(default)* | Speed, no local GPU | Cloud Whisper `large-v3` / `turbo`, ~200× real-time, free tier |
  | `whisperx` | Tightest timestamps | Local faster-whisper + forced alignment (~±50 ms), works offline |
  | `faster-whisper` | Minimal local fallback | Simple, dependency-light |
- 🌍 **Translate** subtitles to any language (Google Translate via `deep-translator`, multi-threaded).
- 🎬 **Dual subtitles** for language learning — keep both tracks separate and **toggle** them, or merge into one file.
- 📦 **Batch** a whole season, resumable (skips work already done).

## Proof it works

Real comparison on *Friends* S01E02, my old pipeline vs this one (same episode, same audio):

| | Old attempt | dualsub |
|---|---|---|
| Longest subtitle cue | **60.3 s** 😱 | 30.0 s |
| Runaway cues (>10 s) | 13 | 6 |
| Sample line | *"cuello de l**útero**"* (wrong) | *"cuello del **útero**"* ✓ |
| Translation speed (≈400 lines) | ~10 min | **~17 s** |

## Quickstart

```bash
git clone https://github.com/<you>/dualsub.git
cd dualsub
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .            # default (Groq) engine
# pip install -e '.[local]'   # + faster-whisper
# pip install -e '.[align]'   # + whisperx

export GROQ_API_KEY=...     # for the default engine — free key at console.groq.com
```

`ffmpeg` and `ffprobe` must be on your `PATH`.

## Usage

```bash
# detect the spoken language
dualsub detect episode.mp4

# transcribe (auto-detect language)
dualsub transcribe episode.mp4

# force source + a local engine
dualsub transcribe episode.mp4 --source es --engine whisperx

# translate an existing subtitle to Russian
dualsub translate episode.es.srt --to ru

# merge two tracks into one dual-language file
dualsub dual episode.es.srt episode.ru.srt

# whole folder: transcribe → translate → dual, resumable
dualsub batch ./season1 --source es --to ru --dual
```

Outputs: `name.<lang>.srt` per track, `name.dual.srt` merged.

## Watching to actually learn

Don't burn both languages onto the screen — you'll just read your native line. Load both tracks and **toggle** instead:

```bash
mpv episode.mp4 \
  --sub-files="episode.es.srt:episode.ru.srt" \
  --sid=1 --sub-font-size=48
```

- **`j`** — cycle subtitle track (Spanish ↔ Russian). Default Spanish.
- **`v`** — hide/show subtitles.

Watch in Spanish, tap `j` only when a line loses you. For per-word popup translations while staying in Spanish, pair it with [interSubs](https://github.com/oltodosel/interSubs).

## How it works

```
video ──ffmpeg──▶ 16 kHz mono audio ──ASR engine──▶ source .srt
                                                        │
                                        deep-translator │──▶ target .srt
                                                        │
                                               merge ───┴──▶ dual .srt
```

| Module | Role |
|--------|------|
| `audio.py` | ffmpeg/ffprobe audio extraction + duration probe |
| `transcribe.py` | pluggable ASR backends → `Cue` list |
| `translate.py` | multi-threaded translation of cues |
| `srt.py` | SRT parse / format / timestamps |
| `dual.py` | merge two tracks into one |
| `cli.py` | `detect` / `transcribe` / `translate` / `dual` / `batch` |

## Roadmap

- [ ] Word-level karaoke timing from WhisperX alignment
- [ ] Optional context-aware translation (LLM) for idioms and names
- [ ] `.ass` styled output (colored source/target lines)
- [ ] Per-episode glossary (character names) to stabilize translations

## License

MIT © 2026

---

<sub>Keywords: speech-to-text · Whisper · Groq · subtitle generator · SRT · language learning · Spanish · dual subtitles · mpv · interSubs</sub>
