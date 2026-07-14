from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from .audio import extract_audio, probe_duration
from .srt import Cue, clamp_durations

GROQ_MODELS = {"large-v3": "whisper-large-v3", "large-v3-turbo": "whisper-large-v3-turbo"}
GROQ_WINDOW = 15.0
GROQ_OVERLAP = 4.0


def transcribe(audio_path, engine: str = "groq", source: str | None = None,
               model: str = "large-v3", beam_size: int = 5,
               compute_type: str = "int8") -> tuple[list[Cue], str]:
    if engine == "groq":
        cues, lang = _groq(audio_path, source, model)
    elif engine == "whisperx":
        cues, lang = _whisperx(audio_path, source, model, compute_type)
    elif engine == "faster-whisper":
        cues, lang = _faster_whisper(audio_path, source, model, beam_size, compute_type)
    else:
        raise ValueError(f"unknown engine: {engine}")
    return clamp_durations(cues), lang


def _segments_to_cues(segments) -> list[Cue]:
    cues = []
    for seg in segments:
        text = (seg["text"] if isinstance(seg, dict) else seg.text).strip()
        if not text:
            continue
        start = seg["start"] if isinstance(seg, dict) else seg.start
        end = seg["end"] if isinstance(seg, dict) else seg.end
        cues.append(Cue(index=len(cues) + 1, start=float(start), end=float(end), text=text))
    return cues


def _groq(audio_path, source, model):
    from groq import Groq

    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY not set")
    client = Groq()
    groq_model = GROQ_MODELS.get(model, model)

    duration = probe_duration(audio_path)
    tmpdir = Path(tempfile.mkdtemp(prefix="dualsub_"))
    cues: list[Cue] = []
    detected = source or ""
    for i, (start, length) in enumerate(_windows(duration)):
        chunk = tmpdir / f"w{i:04}.mp3"
        extract_audio(audio_path, chunk, start=start, duration=length)
        resp = _groq_call(client, chunk, groq_model, source)
        detected = detected or getattr(resp, "language", "") or ""
        for seg in resp.segments:
            text = (seg["text"] if isinstance(seg, dict) else seg.text).strip()
            if not text:
                continue
            s = (seg["start"] if isinstance(seg, dict) else seg.start) + start
            e = (seg["end"] if isinstance(seg, dict) else seg.end) + start
            cues.append(Cue(0, float(s), float(e), text))
    return _dedup(cues), detected


def _groq_call(client, chunk, groq_model, source, retries=4):
    for attempt in range(retries):
        try:
            with open(chunk, "rb") as f:
                return client.audio.transcriptions.create(
                    file=(Path(chunk).name, f.read()),
                    model=groq_model,
                    language=source,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def _windows(duration, window=GROQ_WINDOW, overlap=GROQ_OVERLAP):
    hop = window - overlap
    out = []
    start = 0.0
    while start < duration:
        end = min(start + window, duration)
        out.append((start, end - start))
        if end >= duration:
            break
        start += hop
    return out


def _norm_words(text):
    return [w for w in "".join(c.lower() if c.isalnum() or c.isspace() else " "
                                for c in text).split() if w]


def _dedup(cues):
    cues = sorted(cues, key=lambda c: (c.start, c.end))
    out: list[Cue] = []
    for c in cues:
        if out:
            p = out[-1]
            overlap = min(p.end, c.end) - max(p.start, c.start)
            if overlap > 0:
                short, long = (c, p) if len(c.text) <= len(p.text) else (p, c)
                sw = set(_norm_words(short.text))
                if sw and len(sw & set(_norm_words(long.text))) / len(sw) >= 0.7:
                    if long is c:
                        out[-1] = c
                    continue
                if c.start < p.end:
                    c.start = p.end
                    if c.end - c.start < 0.3:
                        continue
        out.append(c)
    for i, c in enumerate(out, 1):
        c.index = i
    return out


def _whisperx(audio_path, source, model, compute_type):
    import whisperx

    device = "cpu"
    wmodel = whisperx.load_model(model, device, compute_type=compute_type, language=source)
    audio = whisperx.load_audio(str(audio_path))
    result = wmodel.transcribe(audio, language=source)
    lang = result.get("language", source or "")
    try:
        model_a, meta = whisperx.load_align_model(language_code=lang, device=device)
        result = whisperx.align(result["segments"], model_a, meta, audio, device,
                                return_char_alignments=False)
    except Exception:
        pass
    return _segments_to_cues(result["segments"]), lang


def _faster_whisper(audio_path, source, model, beam_size, compute_type):
    from faster_whisper import WhisperModel

    wmodel = WhisperModel(model, device="cpu", compute_type=compute_type)
    segments, info = wmodel.transcribe(
        str(audio_path), language=source, beam_size=beam_size,
        condition_on_previous_text=True,
    )
    return _segments_to_cues(segments), info.language


def detect_language(audio_path, engine: str = "groq", model: str = "large-v3",
                    sample_seconds: float = 60.0) -> str:
    tmpdir = Path(tempfile.mkdtemp(prefix="dualsub_detect_"))
    sample = tmpdir / "sample.mp3"
    extract_audio(audio_path, sample, start=0, duration=sample_seconds)
    _, lang = transcribe(sample, engine=engine, source=None, model=model)
    return lang
