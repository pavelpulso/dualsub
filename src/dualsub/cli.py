from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .audio import VIDEO_EXTS, ensure_audio
from .dual import merge_dual
from .srt import parse_srt, write_srt
from .transcribe import detect_language, transcribe
from .translate import translate_cues

ENGINES = ["groq", "whisperx", "faster-whisper"]


def _sub_path(video: Path, lang: str) -> Path:
    return video.parent / f"{video.stem}.{lang}.srt"


def _base_name(srt: Path) -> str:
    stem = srt.name[:-4] if srt.name.lower().endswith(".srt") else srt.name
    parts = stem.rsplit(".", 1)
    if len(parts) == 2 and 1 <= len(parts[1]) <= 5 and parts[1].isalpha():
        return parts[0]
    return stem


def cmd_detect(args):
    lang = detect_language(args.video, engine=args.engine, model=args.model)
    print(lang)


def cmd_transcribe(args) -> Path:
    video = Path(args.video)
    audio, tmp = ensure_audio(video, video.parent)
    try:
        cues, lang = transcribe(
            audio, engine=args.engine, source=(None if args.source == "auto" else args.source),
            model=args.model, beam_size=args.beam_size, compute_type=args.compute_type,
        )
    finally:
        if tmp and Path(audio).exists():
            Path(audio).unlink()
    lang = lang or args.source
    out = _sub_path(video, lang)
    write_srt(cues, out)
    print(f"transcribed → {out} ({len(cues)} cues, lang={lang})")
    return out


def cmd_translate(args) -> Path:
    src = Path(args.srt)
    cues = parse_srt(src)
    translated = translate_cues(cues, target=args.to, source=args.source)
    out = src.with_name(_base_name(src) + "." + args.to + ".srt")
    write_srt(translated, out)
    print(f"translated → {out} ({len(translated)} cues)")
    return out


def cmd_dual(args) -> Path:
    top = parse_srt(args.top)
    bottom = parse_srt(args.bottom)
    merged = merge_dual(top, bottom)
    top_path = Path(args.top)
    out = top_path.with_name(_base_name(top_path) + ".dual.srt")
    if args.output:
        out = Path(args.output)
    write_srt(merged, out)
    print(f"dual → {out} ({len(merged)} cues)")
    return out


def cmd_batch(args):
    root = Path(args.dir)
    videos = sorted(p for p in root.iterdir() if p.suffix.lower() in VIDEO_EXTS)
    if not videos:
        print(f"no video files in {root}")
        return
    print(f"batch: {len(videos)} file(s)")
    for video in videos:
        src_lang = None if args.source == "auto" else args.source
        src_out = _sub_path(video, src_lang or "src")
        existing = list(video.parent.glob(video.stem + ".*.srt"))
        base_srt = next((p for p in existing if p.name.endswith(".srt")
                         and not p.name.endswith(".dual.srt")
                         and (src_lang is None or f".{src_lang}.srt" in p.name)), None)

        if base_srt and not args.force:
            print(f"skip transcribe (exists): {base_srt.name}")
            src_out = base_srt
        else:
            src_out = cmd_transcribe(_ns(video=str(video), engine=args.engine, source=args.source,
                                         model=args.model, beam_size=args.beam_size,
                                         compute_type=args.compute_type))
        if not args.to:
            continue
        tgt_out = cmd_translate(_ns(srt=str(src_out), to=args.to, source="auto"))
        if args.dual:
            cmd_dual(_ns(top=str(src_out), bottom=str(tgt_out), output=None))


class _ns:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def build_parser():
    p = argparse.ArgumentParser(prog="dualsub", description="Universal transcription + dual subtitles")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_engine(sp):
        sp.add_argument("-e", "--engine", choices=ENGINES, default="groq")
        sp.add_argument("-m", "--model", default="large-v3")
        sp.add_argument("--beam-size", type=int, default=5)
        sp.add_argument("--compute-type", default="int8")

    d = sub.add_parser("detect", help="detect audio language")
    d.add_argument("video")
    add_engine(d)
    d.set_defaults(func=cmd_detect)

    t = sub.add_parser("transcribe", help="video/audio → SRT")
    t.add_argument("video")
    t.add_argument("-s", "--source", default="auto")
    add_engine(t)
    t.set_defaults(func=cmd_transcribe)

    tr = sub.add_parser("translate", help="SRT → translated SRT")
    tr.add_argument("srt")
    tr.add_argument("--to", required=True)
    tr.add_argument("-s", "--source", default="auto")
    tr.set_defaults(func=cmd_translate)

    du = sub.add_parser("dual", help="merge two SRTs into dual-language SRT")
    du.add_argument("top")
    du.add_argument("bottom")
    du.add_argument("-o", "--output")
    du.set_defaults(func=cmd_dual)

    b = sub.add_parser("batch", help="transcribe+translate+dual over a folder")
    b.add_argument("dir")
    b.add_argument("-s", "--source", default="auto")
    b.add_argument("--to", default=None)
    b.add_argument("--dual", action="store_true")
    b.add_argument("--force", action="store_true")
    add_engine(b)
    b.set_defaults(func=cmd_batch)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
