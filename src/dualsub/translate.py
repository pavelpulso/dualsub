from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from deep_translator import GoogleTranslator
from tqdm import tqdm

from .srt import Cue

_WORKERS = 16
_LLM_MODEL = "llama-3.3-70b-versatile"
_LLM_CHUNK = 20

_LANG_NAMES = {
    "es": "Spanish", "ru": "Russian", "en": "English", "de": "German",
    "fr": "French", "it": "Italian", "pt": "Portuguese", "auto": "the source language",
}


def _lang_name(code: str) -> str:
    return _LANG_NAMES.get(code, code)


def translate_texts(texts: list[str], target: str, source: str = "auto",
                    translator: str = "google", retries: int = 3,
                    workers: int = _WORKERS, desc: str = "translate") -> list[str]:
    if translator == "llm":
        return _llm(texts, target, source, desc)
    return _google(texts, target, source, retries, workers, desc)


def translate_cues(cues: list[Cue], target: str, source: str = "auto",
                   translator: str = "google", **kw) -> list[Cue]:
    texts = [c.text.replace("\n", " ").strip() for c in cues]
    out = translate_texts(texts, target, source, translator,
                          desc=f"{translator}→{target}", **kw)
    return [replace(c, text=out[i]) for i, c in enumerate(cues)]


def _google(texts, target, source, retries, workers, desc):
    def one(text):
        if not text:
            return ""
        gt = GoogleTranslator(source=source, target=target)
        for attempt in range(retries):
            try:
                return gt.translate(text) or text
            except Exception as e:
                if attempt == retries - 1:
                    print(f"\ntranslate failed, keeping source: {e}")
                    return text
                time.sleep(1.5 * (attempt + 1))
        return text

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(tqdm(pool.map(one, texts), total=len(texts), desc=desc, unit="line"))


def _llm(texts, target, source, desc):
    from groq import Groq

    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY not set (required for --translator llm)")
    client = Groq()
    src_name, tgt_name = _lang_name(source), _lang_name(target)

    system = (
        f"You translate TV-series subtitle dialogue from {src_name} to natural, colloquial "
        f"{tgt_name}. Use the surrounding lines as context so gender, tense, idioms and meaning "
        f"are correct (e.g. Spanish 'claro' means 'конечно/ясно', never 'прозрачный'). "
        f"Keep each translation short enough to read as a subtitle. "
        f'Input is a JSON object mapping id->{src_name} text. Return ONLY a JSON object with the '
        f"SAME ids, each mapped to its {tgt_name} translation. Translate every id independently; "
        f"never move a translation to a different id, and never merge or drop ids."
    )

    out = list(texts)
    missing: list[int] = []
    chunks = [list(range(i, min(i + _LLM_CHUNK, len(texts))))
              for i in range(0, len(texts), _LLM_CHUNK)]
    for idxs in tqdm(chunks, desc=desc, unit="chunk"):
        payload = json.dumps({str(n): texts[n] for n in idxs}, ensure_ascii=False)
        try:
            resp = client.chat.completions.create(
                model=_LLM_MODEL, temperature=0.2,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": payload}],
            )
            parsed = json.loads(resp.choices[0].message.content)
        except Exception as e:
            print(f"\nllm chunk failed, will fall back: {e}")
            parsed = {}
        for n in idxs:
            val = parsed.get(str(n))
            if isinstance(val, str) and val.strip():
                out[n] = val.strip()
            elif texts[n]:
                missing.append(n)

    if missing:
        print(f"\nllm dropped {len(missing)} line(s); filling via Google")
        gt = GoogleTranslator(source=source, target=target)
        for n in missing:
            try:
                out[n] = gt.translate(texts[n]) or texts[n]
            except Exception:
                pass
    return out
