from __future__ import annotations

import subprocess
from pathlib import Path

VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv"}


def is_url(path) -> bool:
    return str(path).startswith(("http://", "https://"))


def download_audio(url: str, workdir, sample_rate: int = 16000) -> Path:
    import yt_dlp

    out_tmpl = str(Path(workdir) / "%(id)s.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        "postprocessor_args": ["-ar", str(sample_rate), "-ac", "1"],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return Path(workdir) / f"{info['id']}.mp3"


def probe_duration(path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        stderr=subprocess.DEVNULL,
    )
    return float(out.decode().strip())


def extract_audio(video_path, out_path, sample_rate: int = 16000, start: float | None = None,
                  duration: float | None = None) -> Path:
    cmd = ["ffmpeg", "-y"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(video_path)]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-vn", "-ac", "1", "-ar", str(sample_rate),
            "-c:a", "libmp3lame", "-q:a", "5", str(out_path)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return Path(out_path)


def ensure_audio(source_path, workdir, sample_rate: int = 16000) -> tuple[Path, bool]:
    if is_url(source_path):
        return download_audio(str(source_path), workdir, sample_rate=sample_rate), True
    src = Path(source_path)
    if src.suffix.lower() not in VIDEO_EXTS:
        return src, False
    out = Path(workdir) / (src.stem + ".16k.mp3")
    extract_audio(src, out, sample_rate=sample_rate)
    return out, True
