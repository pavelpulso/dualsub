from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from deep_translator import GoogleTranslator
from tqdm import tqdm

from .srt import Cue

_WORKERS = 16


def _translate_one(text: str, target: str, source: str, retries: int) -> str:
    if not text:
        return ""
    translator = GoogleTranslator(source=source, target=target)
    for attempt in range(retries):
        try:
            return translator.translate(text) or text
        except Exception as e:
            if attempt == retries - 1:
                print(f"\ntranslate failed, keeping source: {e}")
                return text
            time.sleep(1.5 * (attempt + 1))
    return text


def translate_cues(cues: list[Cue], target: str, source: str = "auto",
                   retries: int = 3, workers: int = _WORKERS) -> list[Cue]:
    texts = [c.text.replace("\n", " ").strip() for c in cues]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        translated = list(
            tqdm(
                pool.map(lambda t: _translate_one(t, target, source, retries), texts),
                total=len(texts), desc=f"translate→{target}", unit="line",
            )
        )
    return [replace(c, text=translated[i]) for i, c in enumerate(cues)]
