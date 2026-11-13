"""Verify benchmark evidence BEFORE any retrieval run (Markdown corpus: one story = one unit).

Checks what BENCHMARK.md asks for: every required field is present, the evidence exists in the gold unit,
filter values match the gold unit's metadata, and the split / filter minimums are met.
Run from starter/:  python -I -X utf8 scripts/verify_benchmark.py
"""
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

STARTER = Path(__file__).resolve().parents[1]
REPO = STARTER.parent
sys.path.insert(0, str(STARTER))

from src.ingestion import load_markdown_corpus  # noqa: E402

REQUIRED = ("id", "split", "question", "expected_answer", "gold_source_id", "gold_page", "evidence_quote")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def main() -> int:
    bench = json.loads((REPO / "benchmark" / "benchmark.json").read_text(encoding="utf-8"))
    pages, _ = load_markdown_corpus(REPO)
    by_unit = {p.page: p for p in pages}
    text = {n: norm(p.text) for n, p in by_unit.items()}

    errors = []
    for q in bench:
        missing = [k for k in REQUIRED if not q.get(k) and q.get(k) != 0]
        if missing:
            errors.append((q.get("id"), f"missing fields {missing}"))
            continue
        n = q["gold_page"]
        if n not in by_unit:
            errors.append((q["id"], f"gold_page {n} is not a unit of the corpus"))
            continue
        if norm(q["evidence_quote"]) not in text[n]:
            errors.append((q["id"], f"evidence quote NOT found in unit {n}"))
        others = [m for m, t in text.items() if m != n and norm(q["evidence_quote"]) in t]
        if others:
            print(f"note {q['id']}: quote also appears in units {others} (accept as valid)")
        flt = q.get("filter")
        if flt and flt.get("period") != by_unit[n].metadata["period"]:
            errors.append((q["id"], f"filter {flt} != period of unit {n}"))

    splits = Counter(q["split"] for q in bench)
    filters = [q for q in bench if q.get("filter")]
    if len({q["id"] for q in bench}) != len(bench):
        errors.append(("*", "duplicate ids"))
    if len(bench) < 20 or splits["dev"] < 15 or splits["test"] < 5:
        errors.append(("*", f"need >=20 questions with >=15 dev / >=5 test, got {dict(splits)}"))
    if len(filters) < 3 or not any(q["split"] == "test" for q in filters):
        errors.append(("*", "need >=3 filter questions with >=1 in test"))

    print("splits:", dict(splits), "| filter questions:", [(q["id"], q["split"]) for q in filters])
    if errors:
        for e in errors:
            print("ERROR", *e)
        return 1
    print(f"OK: all {len(bench)} questions verified against the source stories")
    return 0


if __name__ == "__main__":
    sys.exit(main())
