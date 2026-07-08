from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

from .audio import extract_audio, probe_duration
from .srt import Cue

GROQ_MODELS = {"large-v3": "whisper-large-v3", "large-v3-turbo": "whisper-large-v3-turbo"}
GROQ_SIZE_LIMIT = 24 * 1024 * 1024


def transcribe(audio_path, engine: str = "groq", source: str | None = None,
               model: str = "large-v3", beam_size: int = 5,
               compute_type: str = "int8") -> tuple[list[Cue], str]:
    if engine == "groq":
        return _groq(audio_path, source, model)
    if engine == "whisperx":
        return _whisperx(audio_path, source, model, compute_type)
    if engine == "faster-whisper":
        return _faster_whisper(audio_path, source, model, beam_size, compute_type)
    raise ValueError(f"unknown engine: {engine}")


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

    chunks = _split_for_groq(audio_path)
    all_cues: list[Cue] = []
    detected = source or ""
    for offset, chunk in chunks:
        with open(chunk, "rb") as f:
            resp = client.audio.transcriptions.create(
                file=(Path(chunk).name, f.read()),
                model=groq_model,
                language=source,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        detected = detected or getattr(resp, "language", "") or ""
        for seg in resp.segments:
            text = (seg["text"] if isinstance(seg, dict) else seg.text).strip()
            if not text:
                continue
            start = (seg["start"] if isinstance(seg, dict) else seg.start) + offset
            end = (seg["end"] if isinstance(seg, dict) else seg.end) + offset
            all_cues.append(Cue(len(all_cues) + 1, float(start), float(end), text))
    return all_cues, detected


def _split_for_groq(audio_path):
    audio_path = Path(audio_path)
    size = audio_path.stat().st_size
    if size <= GROQ_SIZE_LIMIT:
        return [(0.0, audio_path)]
    duration = probe_duration(audio_path)
    n = math.ceil(size / GROQ_SIZE_LIMIT)
    chunk_len = duration / n
    tmpdir = Path(tempfile.mkdtemp(prefix="dualsub_"))
    chunks = []
    for i in range(n):
        start = i * chunk_len
        out = tmpdir / f"chunk_{i:02}.mp3"
        extract_audio(audio_path, out, start=start, duration=chunk_len)
        chunks.append((start, out))
    return chunks


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
