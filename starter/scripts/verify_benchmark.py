"""Verify benchmark evidence BEFORE any retrieval run.

For each question: the gold page is a counted page in data/manifest.json, the
evidence_quote appears in that page's normalized text, filter values match the
gold page's chapter, and distractor pages exist but are in a different chapter.
Run:  python -I scripts/verify_benchmark.py
"""
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

STARTER = Path(__file__).resolve().parents[1]
REPO = STARTER.parent
PDF = STARTER / "data" / "raw" / "introduction-sociology-3e.pdf"


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def main() -> int:
    manifest = json.loads((REPO / "data" / "manifest.json").read_text(encoding="utf-8"))["sources"][0]
    chapter_of = {p["physical_page"]: p["chapter"] for p in manifest["pages"]}
    bench = json.loads((REPO / "benchmark" / "benchmark.json").read_text(encoding="utf-8"))["questions"]
    reader = PdfReader(str(PDF))
    page_text = {pg: norm(reader.pages[pg - 1].extract_text() or "") for pg in chapter_of}

    errors = []
    for q in bench:
        pg = q["gold_page"]
        if pg not in chapter_of:
            errors.append((q["id"], f"gold_page {pg} is not a counted page"))
            continue
        quote = norm(q["evidence_quote"])
        if quote not in page_text[pg]:
            errors.append((q["id"], f"evidence quote NOT found on page {pg}"))
        others = [p for p, t in page_text.items() if p != pg and quote in t]
        if others:
            print(f"note {q['id']}: quote also appears on pages {others} (accept as valid)")
        flt = q.get("filter")
        if flt and flt.get("chapter") != chapter_of[pg]:
            errors.append((q["id"], f"filter chapter {flt} != gold chapter {chapter_of[pg]}"))
        for d in q.get("distractor_pages", []):
            if d not in chapter_of:
                errors.append((q["id"], f"distractor {d} not counted"))
            elif chapter_of[d] == chapter_of[pg]:
                errors.append((q["id"], f"distractor {d} is in the same chapter as gold"))
            elif quote in page_text[d]:
                errors.append((q["id"], f"distractor {d} contains the gold evidence"))

    splits = Counter(q["split"] for q in bench)
    filters = [q for q in bench if q.get("filter")]
    ids = [q["id"] for q in bench]
    if len(ids) != len(set(ids)):
        errors.append(("*", "duplicate ids"))
    if splits["dev"] < 15 or splits["test"] < 5:
        errors.append(("*", f"split too small: {dict(splits)}"))
    if len(filters) < 3 or not any(q["split"] == "test" for q in filters):
        errors.append(("*", "need >=3 filter questions with >=1 in test"))

    print("splits:", dict(splits), "| filter questions:", [(q["id"], q["split"]) for q in filters])
    print("by chapter:", dict(Counter(chapter_of[q["gold_page"]] for q in bench if q["gold_page"] in chapter_of)))
    if errors:
        for e in errors:
            print("ERROR", *e)
        return 1
    print(f"OK: all {len(bench)} questions verified against source pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
