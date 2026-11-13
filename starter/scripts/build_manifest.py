"""Build data/manifest.json for the OpenStax Introduction to Sociology 3e corpus.

Counting rule (decided before reading any benchmark results):
  * Physical page = 1-based PDF page index.
  * Counted pages = body of Chapters 1-3: from the chapter Introduction page up to the
    page BEFORE that chapter's "Key Terms" page (outline bookmarks give the boundaries).
  * Excluded: front matter, Key Terms, Section Summary, Section Quiz, Short Answer,
    Further Research, References, other chapters.
  * A counted page is flagged (not silently dropped) if it is empty or has few chars.
Run:  python -I scripts/build_manifest.py
"""
import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pypdf
from pypdf import PdfReader

STARTER = Path(__file__).resolve().parents[1]
REPO = STARTER.parent
PDF = STARTER / "data" / "raw" / "introduction-sociology-3e.pdf"
OUT = REPO / "data" / "manifest.json"
CHAPTERS = {1: "An Introduction to Sociology", 2: "Sociological Research", 3: "Culture"}
MIN_CHARS = 200  # below this a counted page is flagged as near-empty


def bookmarks(reader):
    found = []
    def walk(items):
        for it in items:
            if isinstance(it, list):
                walk(it)
            else:
                found.append((it.title.strip(), reader.get_destination_page_number(it) + 1))
    walk(reader.outline)
    return found


def main():
    reader = PdfReader(str(PDF))
    marks = bookmarks(reader)
    sha = hashlib.sha256(PDF.read_bytes()).hexdigest()
    pages, issues = [], []
    for ch, title in CHAPTERS.items():
        start = next(p for t, p in marks if t == f"Chapter {ch} {title}")
        # first "Key Terms" bookmark after this chapter's start is the end boundary
        end = min(p for t, p in marks if t == "Key Terms" and p > start) - 1
        sections = sorted(
            (p, t) for t, p in marks
            if t.startswith(f"{ch}.") and start <= p <= end
        )
        for phys in range(start, end + 1):
            text = unicodedata.normalize("NFC", reader.pages[phys - 1].extract_text() or "")
            section = "Introduction"
            for p, t in sections:
                if p <= phys:
                    section = t
            bad = text.count("\ufffd")
            rec = {
                "page_id": f"soc3e-p{phys:03d}",
                "physical_page": phys,
                "chapter": ch,
                "chapter_title": title,
                "section_at_page_start": section,
                "chars": len(text),
                "replacement_chars": bad,
            }
            if len(text.strip()) < MIN_CHARS:
                issues.append({"page_id": rec["page_id"], "issue": "empty_or_near_empty", "chars": len(text)})
            if bad:
                issues.append({"page_id": rec["page_id"], "issue": "replacement_char_U+FFFD", "count": bad})
            pages.append(rec)
    manifest = {
        "sources": [{
            "source_id": "soc3e",
            "title": "Introduction to Sociology 3e",
            "authors": "Tonja R. Conerly, Kathleen Holmes, Asha Lal Tamang (OpenStax)",
            "source_path_or_url": "https://openstax.org/details/books/introduction-sociology-3e",
            "local_path": "starter/data/raw/introduction-sociology-3e.pdf",
            "license_or_permission": "CC BY-NC-SA 4.0 (per OpenStax book page; confirm on the PDF copyright page)",
            "accessed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "snapshot_version": {
                "pdf_title": reader.metadata.title,
                "pdf_creation_date": reader.metadata.get("/CreationDate"),
                "file_bytes": PDF.stat().st_size,
                "sha256": sha,
            },
            "physical_pages_total": len(reader.pages),
            "counting_rule": "Body pages of Chapters 1-3 (chapter intro up to the page before 'Key Terms'). "
                             "Excluded: front matter, Key Terms, Section Summary, Section Quiz, Short Answer, "
                             "Further Research, References, Chapters 4+. Physical page = 1-based PDF index.",
            "counted_pages": len(pages),
            "counted_page_ranges": {str(c): [min(p["physical_page"] for p in pages if p["chapter"] == c),
                                             max(p["physical_page"] for p in pages if p["chapter"] == c)]
                                    for c in CHAPTERS},
            "total_chars": sum(p["chars"] for p in pages),
            "extractor": f"pypdf {pypdf.__version__}",
            "pages": pages,
            "issues": issues,
        }],
    }
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    s = manifest["sources"][0]
    print("counted_pages", s["counted_pages"], "ranges", s["counted_page_ranges"], "chars", s["total_chars"])
    print("issues", len(issues), "pages_with_U+FFFD", sum(1 for i in issues if i["issue"].startswith("replacement")))


if __name__ == "__main__":
    main()
