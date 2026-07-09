from __future__ import annotations

from pathlib import Path

from .srt import Cue
from .tokenize import _WORD, rarity

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginV
Style: Default,Arial,64,&H00FFFFFF,&H00000000,&H64000000,0,3,1,2,60

[Events]
Format: Layer, Start, End, Style, Text
"""


def _ass_time(seconds: float) -> str:
    cs = round(seconds * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def _colorize(text: str, lang: str, max_zipf: float, color: str) -> str:
    def repl(m):
        w = m.group(0)
        z = rarity(w.lower(), lang)
        if 0 < z <= max_zipf:
            return f"{{\\c{color}}}{w}{{\\r}}"
        return w

    return _WORD.sub(repl, text).replace("\n", "\\N")


def write_ass(cues: list[Cue], path, lang: str, max_zipf: float = 4.0,
              color: str = "&H00D7FF&") -> Path:
    lines = [_HEADER]
    for c in cues:
        text = _colorize(c.text, lang, max_zipf, color)
        lines.append(f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Default,,{text}")
    path = Path(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
