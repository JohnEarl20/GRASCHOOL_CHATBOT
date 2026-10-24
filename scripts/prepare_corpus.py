"""One-off data preparation for the Cognitive Campus Assistant.

Two jobs:

1. Extract the starter corpus. The file `STARTERGRASCHOOL_50.csv` in the project
   root is really an .xlsx workbook with the wrong extension (it starts with the
   PK zip header), so the loader has to go through openpyxl, not csv.
2. Merge the two AI-drafted corpus parts into one training file and drop the
   parts, so the training set has a single source of truth.

Run:  python scripts/prepare_corpus.py
"""
from __future__ import annotations

import csv
import io
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

HEADER = ["id", "text", "intent", "source", "status"]
STARTER_SOURCE = "team-written draft (no real people)"
AI_SOURCE = "AI-drafted draft (no real people)"
AI_STATUS = "to be replaced by Member B"


def extract_starter() -> int:
    """Read the mis-named workbook and write a real CSV out of it."""
    import openpyxl

    src = ROOT / "STARTERGRASCHOOL_50.csv"
    if not src.exists():
        print(f"skip: {src.name} not found")
        return 0
    if not src.read_bytes()[:2] == b"PK":
        print(f"skip: {src.name} is not an OOXML package")
        return 0

    wb = openpyxl.load_workbook(io.BytesIO(src.read_bytes()))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h) for h in rows[0]]

    out = DATA / "starter_corpus_50.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows[1:]:
            if r[0] is None:
                continue
            w.writerow(["" if v is None else str(v) for v in r])
    print(f"wrote {out.name}: {len(rows) - 1} rows (sheet '{ws.title}')")
    return len(rows) - 1


def merge_parts() -> int:
    """Concatenate the AI-drafted parts into one training file."""
    parts = [DATA / "intent_corpus_part1.csv", DATA / "intent_corpus_part2.csv"]
    rows: list[list[str]] = []
    for p in parts:
        if not p.exists():
            continue
        with p.open(encoding="utf-8", newline="") as f:
            part = list(csv.reader(f))
        rows.extend(part[1:])
        p.unlink()
        print(f"merged {p.name}")

    if not rows:
        print("skip: no corpus parts found")
        return 0

    out = DATA / "intent_corpus_augmented.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    print(f"wrote {out.name}: {len(rows)} rows")
    return len(rows)


def report() -> None:
    for name in ("starter_corpus_50.csv", "intent_corpus_augmented.csv"):
        p = DATA / name
        if not p.exists():
            continue
        with p.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        counts = Counter(r["intent"] for r in rows)
        texts = [r["text"].strip().lower() for r in rows]
        dupes = [t for t, c in Counter(texts).items() if c > 1]
        print(f"\n{name}: {len(rows)} rows, {len(counts)} intents, {len(dupes)} duplicate texts")
        for intent, n in sorted(counts.items()):
            print(f"  {intent:<28} {n}")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    extract_starter()
    merge_parts()
    report()
