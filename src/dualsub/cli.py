from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .ass import write_ass
from .audio import VIDEO_EXTS, ensure_audio, is_url
from .dual import merge_dual
from .srt import parse_srt, write_srt
from . import progress as progress_mod
from .transcribe import detect_language, transcribe
from .translate import translate_cues
from .vocab import build_deck, write_anki_tsv

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
    url = is_url(args.video)
    workdir = Path.cwd() if url else Path(args.video).parent
    audio, tmp = ensure_audio(args.video, workdir)
    try:
        cues, lang = transcribe(
            audio, engine=args.engine, source=(None if args.source == "auto" else args.source),
            model=args.model, beam_size=args.beam_size, compute_type=args.compute_type,
        )
    finally:
        if tmp and Path(audio).exists():
            Path(audio).unlink()
    lang = lang or (None if args.source == "auto" else args.source) or "src"
    base = Path(audio) if url else Path(args.video)
    out = _sub_path(base, lang)
    write_srt(cues, out)
    print(f"transcribed → {out} ({len(cues)} cues, lang={lang})")
    return out


def cmd_translate(args) -> Path:
    src = Path(args.srt)
    cues = parse_srt(src)
    translated = translate_cues(cues, target=args.to, source=args.source,
                                translator=args.translator)
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
        lang_code = src_out.stem.rsplit(".", 1)[-1] if "." in src_out.stem else (src_lang or "es")
        if args.color:
            cmd_color(_ns(srt=str(src_out), source=lang_code, max_zipf=4.0, output=None))
        if args.vocab and args.to:
            cmd_vocab(_ns(srt=str(src_out), source=lang_code, to=args.to,
                          translator=args.translator, max_zipf=4.5, limit=None))
        if not args.to:
            continue
        tgt_out = cmd_translate(_ns(srt=str(src_out), to=args.to, source="auto",
                                    translator=args.translator))
        if args.dual:
            cmd_dual(_ns(top=str(src_out), bottom=str(tgt_out), output=None))


def cmd_vocab(args) -> Path:
    src = Path(args.srt)
    cues = parse_srt(src)
    deck = build_deck(cues, source=args.source, target=args.to, translator=args.translator,
                      max_zipf=args.max_zipf, limit=args.limit)
    out = src.with_name(_base_name(src) + ".vocab.tsv")
    write_anki_tsv(deck, out)
    print(f"vocab → {out} ({len(deck)} cards; import into Anki as tab-separated)")
    return out


def cmd_color(args) -> Path:
    src = Path(args.srt)
    cues = parse_srt(src)
    out = Path(args.output) if args.output else src.with_name(_base_name(src) + ".color.ass")
    write_ass(cues, out, lang=args.source, max_zipf=args.max_zipf)
    print(f"colored subtitles → {out} (rare words highlighted)")
    return out


def cmd_watch(args):
    video = Path(args.video)
    src_srt = _sub_path(video, args.source)
    tgt_srt = _sub_path(video, args.to)
    if not src_srt.exists() or not tgt_srt.exists():
        print(f"need both tracks first: {src_srt.name} and {tgt_srt.name}\n"
              f"run: dualsub transcribe / translate (or batch) for this episode")
        return
    lua = Path(__file__).parent / "data" / "progress.lua"
    out_json = Path(tempfile.mkstemp(prefix="dualsub_", suffix=".json")[1])
    env = dict(os.environ, DUALSUB_PROGRESS_OUT=str(out_json), DUALSUB_EPISODE=video.stem)
    subprocess.run([
        "mpv", str(video), f"--sub-files={src_srt}:{tgt_srt}",
        "--sub-auto=no", "--sid=1", "--sub-font-size=48", f"--script={lua}",
    ], env=env)

    if not out_json.exists() or not out_json.read_text().strip():
        print("no watch data recorded")
        return
    data = json.loads(out_json.read_text())
    out_json.unlink(missing_ok=True)
    comp = progress_mod.record(data["episode"], data["src_seconds"], data["tgt_seconds"])
    if comp is None:
        print("not enough subtitle time to score")
        return
    print(f"\ncomprehension: {comp * 100:.0f}%  "
          f"({args.source} {data['src_seconds']:.0f}s vs {args.to} {data['tgt_seconds']:.0f}s)")
    s = progress_mod.summary(progress_mod.load())
    if s["avg_comprehension"] is not None:
        print(f"season avg: {s['avg_comprehension'] * 100:.0f}%  over {s['episodes']} episode(s)")


def cmd_progress(args):
    rows = progress_mod.load()
    if not rows:
        print("no watch history yet — use: dualsub watch <video>")
        return
    print(f"{'date':<12}{'episode':<40}{'comprehension':>13}")
    for r in rows:
        c = r.get("comprehension")
        pct = f"{float(c) * 100:.0f}%" if c else "—"
        print(f"{r['date']:<12}{r['episode'][:38]:<40}{pct:>13}")
    s = progress_mod.summary(rows)
    if s["avg_comprehension"] is not None:
        print(f"\naverage: {s['avg_comprehension'] * 100:.0f}%  over {s['episodes']} episode(s)")


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
    tr.add_argument("--translator", choices=["google", "llm"], default="google",
                    help="google (fast, free) or llm (context-aware, needs GROQ_API_KEY)")
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
    b.add_argument("--translator", choices=["google", "llm"], default="google")
    b.add_argument("--dual", action="store_true")
    b.add_argument("--vocab", action="store_true", help="also emit an Anki deck per episode")
    b.add_argument("--color", action="store_true", help="also emit a highlighted .ass per episode")
    b.add_argument("--force", action="store_true")
    add_engine(b)
    b.set_defaults(func=cmd_batch)

    v = sub.add_parser("vocab", help="SRT → Anki flashcard deck of rare words")
    v.add_argument("srt")
    v.add_argument("-s", "--source", default="es", help="language of the subtitle")
    v.add_argument("--to", required=True, help="translation language for card backs")
    v.add_argument("--translator", choices=["google", "llm"], default="google")
    v.add_argument("--max-zipf", type=float, default=4.5,
                   help="keep words with zipf frequency <= this (lower = rarer). default 4.5")
    v.add_argument("--limit", type=int, default=None)
    v.set_defaults(func=cmd_vocab)

    co = sub.add_parser("color", help="SRT → .ass with rare words highlighted")
    co.add_argument("srt")
    co.add_argument("-s", "--source", default="es")
    co.add_argument("--max-zipf", type=float, default=4.0)
    co.add_argument("-o", "--output")
    co.set_defaults(func=cmd_color)

    w = sub.add_parser("watch", help="watch with toggleable subs + score comprehension")
    w.add_argument("video")
    w.add_argument("-s", "--source", default="es")
    w.add_argument("--to", default="ru")
    w.set_defaults(func=cmd_watch)

    pr = sub.add_parser("progress", help="show comprehension history")
    pr.set_defaults(func=cmd_progress)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
