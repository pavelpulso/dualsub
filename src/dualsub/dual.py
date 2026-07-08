from __future__ import annotations

from .srt import Cue


def merge_dual(top: list[Cue], bottom: list[Cue]) -> list[Cue]:
    if len(top) == len(bottom):
        pairs = zip(top, bottom)
    else:
        pairs = ((t, _nearest(t, bottom)) for t in top)

    merged = []
    for i, (t, b) in enumerate(pairs, start=1):
        text = t.text if b is None else f"{t.text}\n{b.text}"
        merged.append(Cue(index=i, start=t.start, end=t.end, text=text))
    return merged


def _nearest(cue: Cue, others: list[Cue]) -> Cue | None:
    if not others:
        return None
    return min(others, key=lambda o: abs(o.start - cue.start))
