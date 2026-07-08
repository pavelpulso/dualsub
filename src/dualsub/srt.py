import re
from dataclasses import dataclass
from pathlib import Path

_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})")
_ARROW = re.compile(
    r"(\d+:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d+:\d{2}:\d{2}[,.]\d{1,3})"
)


@dataclass
class Cue:
    index: int
    start: float
    end: float
    text: str


def format_timestamp(seconds: float) -> str:
    ms = round(seconds * 1000.0)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def parse_timestamp(ts: str) -> float:
    h, m, s, ms = _TIME.match(ts.strip()).groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def parse_srt(path) -> list[Cue]:
    raw = Path(path).read_text(encoding="utf-8-sig")
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip() != ""]
        arrow_idx = next((i for i, ln in enumerate(lines) if _ARROW.search(ln)), None)
        if arrow_idx is None:
            continue
        start_s, end_s = _ARROW.search(lines[arrow_idx]).groups()
        text = "\n".join(lines[arrow_idx + 1:]).strip()
        cues.append(
            Cue(
                index=len(cues) + 1,
                start=parse_timestamp(start_s),
                end=parse_timestamp(end_s),
                text=text,
            )
        )
    return cues


def format_srt(cues: list[Cue]) -> str:
    out = []
    for i, cue in enumerate(cues, start=1):
        out.append(str(i))
        out.append(f"{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}")
        out.append(cue.text)
        out.append("")
    return "\n".join(out) + "\n"


def write_srt(cues: list[Cue], path) -> Path:
    path = Path(path)
    path.write_text(format_srt(cues), encoding="utf-8")
    return path
