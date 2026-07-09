from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .srt import Cue
from .tokenize import rarity, words
from .translate import translate_texts


@dataclass
class VocabItem:
    word: str
    translation: str
    example: str
    zipf: float


def collect_words(cues: list[Cue], source: str, max_zipf: float = 4.5,
                  min_len: int = 3, limit: int | None = None) -> list[tuple[str, str, float]]:
    seen: dict[str, str] = {}
    for c in cues:
        for w in words(c.text):
            if len(w) >= min_len and w not in seen:
                seen[w] = " ".join(c.text.split())
    scored = []
    for w, example in seen.items():
        z = rarity(w, source)
        if 0 < z <= max_zipf:
            scored.append((w, example, z))
    scored.sort(key=lambda x: x[2])
    return scored[:limit] if limit else scored


def build_deck(cues: list[Cue], source: str, target: str, translator: str = "google",
               max_zipf: float = 4.5, limit: int | None = None) -> list[VocabItem]:
    scored = collect_words(cues, source, max_zipf=max_zipf, limit=limit)
    if not scored:
        return []
    translations = translate_texts([w for w, _, _ in scored], target, source,
                                   translator, desc="vocab")
    return [VocabItem(w, translations[i].strip(), ex, round(z, 2))
            for i, (w, ex, z) in enumerate(scored)]


def write_anki_tsv(deck: list[VocabItem], path) -> Path:
    path = Path(path)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        for item in deck:
            writer.writerow([item.word, item.translation, item.example, item.zipf])
    return path
