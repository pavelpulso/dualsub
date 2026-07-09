from __future__ import annotations

import re

from wordfreq import zipf_frequency

_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", re.UNICODE)


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def rarity(word: str, lang: str) -> float:
    """Zipf frequency: ~7 = very common, ~1 = rare, 0 = unknown."""
    return zipf_frequency(word, lang)


def is_rare(word: str, lang: str, max_zipf: float) -> bool:
    z = rarity(word, lang)
    return 0 < z <= max_zipf
