from __future__ import annotations

import csv
import datetime
from pathlib import Path

PROGRESS_FILE = Path.home() / ".dualsub" / "progress.csv"
_FIELDS = ["date", "episode", "src_seconds", "tgt_seconds", "comprehension"]


def comprehension(src_seconds: float, tgt_seconds: float) -> float | None:
    total = src_seconds + tgt_seconds
    if total <= 0:
        return None
    return src_seconds / total


def record(episode: str, src_seconds: float, tgt_seconds: float,
           path: Path = PROGRESS_FILE, today: str | None = None) -> float | None:
    comp = comprehension(src_seconds, tgt_seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(_FIELDS)
        w.writerow([today or datetime.date.today().isoformat(), episode,
                    round(src_seconds, 1), round(tgt_seconds, 1),
                    "" if comp is None else round(comp, 4)])
    return comp


def load(path: Path = PROGRESS_FILE) -> list[dict]:
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summary(rows: list[dict]) -> dict:
    comps = [float(r["comprehension"]) for r in rows if r.get("comprehension")]
    return {
        "episodes": len(rows),
        "avg_comprehension": round(sum(comps) / len(comps), 4) if comps else None,
        "last_comprehension": comps[-1] if comps else None,
    }
