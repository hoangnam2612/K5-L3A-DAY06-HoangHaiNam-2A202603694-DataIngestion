"""Read and normalize source data. TODO: implement functions."""
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

from .models import DocumentPage

MIN_CHARS = 200  # a counted page with fewer normalized characters is logged as low_text

# Running headers/footers and feature-box tags printed by the OpenStax layout.
# They are page furniture, not content, so they are removed (and counted in the log).
_FOOTER_PATTERNS = [
    re.compile(r"^Access for free at openstax\.org$"),
    re.compile(r"^\d+\s+\d+\s*•\s*.+$"),            # even footer: "8     1 • An Introduction to Sociology"
    re.compile(r"^\d+\.\d+\s*•\s*.+?\s+\d+$"),      # odd footer:  "1.1 • What Is Sociology?     9"
]
_FEATURE_TAGS = {
    "SOCIOLOGY IN THE REAL WORLD",
    "SOCIOLOGICAL RESEARCH",
    "SOCIAL POLICY AND DEBATE",
    "BIG PICTURE",
}
_TERMINAL = ('.', '?', '!', ':', '"', "'", ')', '”', '’')
_SECTION_HEADING = re.compile(r"^\d+\.\d+ \S.{0,90}$")  # e.g. "1.2 The History of Sociology"
_NUMBERED_HEADING = re.compile(r"^\d+\.\d+ [A-Z][^.]{0,90}$")
_BULLET = re.compile(r"^(•|\d+\.\s|[a-d]\.\s)")


def _clean_lines(text: str, extra_drop_lines: set[str] | None = None) -> tuple[list[tuple[int, str]], int]:
    """Unicode/whitespace-clean every line and drop page furniture.

    Returns ([(source_line_no, line)], removed_count). `source_line_no` is the 1-based line number in the
    text extracted from the page, so chunks can be traced back to "page P, lines X-Y".
    """
    text = unicodedata.normalize("NFC", text).replace(" ", " ").replace("­", "")
    drop = extra_drop_lines or set()
    kept, removed = [], 0
    for number, line in enumerate(text.splitlines(), start=1):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            continue
        if (line in _FEATURE_TAGS or line in drop
                or any(p.match(line) for p in _FOOTER_PATTERNS)):
            removed += 1
            continue
        kept.append((number, line))
    return kept, removed


def _line_map(raw: str, drop: set[str], text: str) -> dict | None:
    """Map offsets in the whitespace-collapsed page text back to source line numbers (None if inconsistent)."""
    kept, _ = _clean_lines(raw, drop)
    flat, starts, pos = " ".join(line for _, line in kept), [], 0
    for number, line in kept:
        starts.append([pos, number])
        pos += len(line) + 1
    if flat != " ".join(text.split()):
        return None
    shown = {n for n, _ in kept}
    all_lines = unicodedata.normalize("NFC", raw).replace(" ", " ").replace("­", "").splitlines()
    return {"flat": flat, "starts": starts, "total": len(all_lines),
            "lines": [[i, l.strip(), i in shown] for i, l in enumerate(all_lines, start=1) if l.strip()]}


def load_pdf(path: Path, document_id: str, source: str,
             pages: Iterable[int] | None = None,
             page_metadata: dict[int, dict] | None = None,
             log: list[dict] | None = None) -> list[DocumentPage]:
    """TODO: extract each physical page; keep its page number and source.

    Detect and record pages with no text. OCR, when needed, is a separate step.
    """
    # Implementation notes (added): `pages` is an optional list of 1-based physical pages
    # (default: all). Empty, near-empty and failed pages are appended to `log`, not dropped silently.
    reader = PdfReader(str(path))
    wanted = list(pages) if pages is not None else list(range(1, len(reader.pages) + 1))
    out: list[DocumentPage] = []
    for number in wanted:
        meta = dict(page_metadata.get(number, {})) if page_metadata else {}
        try:
            raw = reader.pages[number - 1].extract_text() or ""
        except Exception as exc:  # corrupt page: record and continue
            if log is not None:
                log.append({"page": number, "event": "extract_error", "detail": repr(exc)})
            continue
        drop = {meta["chapter_title_footer"]} if "chapter_title_footer" in meta else set()
        text, removed = normalize_text(raw, extra_drop_lines=drop, return_removed=True)
        meta.pop("chapter_title_footer", None)
        meta.update({"page_id": f"{document_id}-p{number:03d}", "raw_chars": len(raw),
                     "chars": len(text), "removed_lines": removed})
        if not text.strip():
            if log is not None:
                log.append({"page": number, "event": "empty_page", "raw_chars": len(raw)})
            continue
        meta["line_map"] = _line_map(raw, drop, text)
        if meta["line_map"] is None and log is not None:
            log.append({"page": number, "event": "line_map_mismatch"})
        if len(text) < MIN_CHARS and log is not None:
            log.append({"page": number, "event": "low_text", "chars": len(text)})
        if "�" in text and log is not None:
            log.append({"page": number, "event": "replacement_chars", "count": text.count("�")})
        out.append(DocumentPage(document_id=document_id, source=source, page=number, text=text, metadata=meta))
    return out


def normalize_text(text: str, extra_drop_lines: set[str] | None = None,
                   return_removed: bool = False):
    """TODO: normalize Unicode and whitespace without discarding useful structure."""
    # Implementation notes (added): also drops page furniture (footers, feature tags) and rebuilds
    # paragraphs: blank line between paragraphs/headings, hard line wraps joined with one space.
    kept, removed = _clean_lines(text, extra_drop_lines)
    lines = [line for _, line in kept]

    # A line clearly shorter than the typical wrapped line ends a block (paragraph or heading).
    width = max((len(l) for l in lines), default=0)
    short = 0.72 * width
    paragraphs, current = [], []
    for line in lines:
        numbered = bool(_NUMBERED_HEADING.match(line))  # "3.3 High, Low, Pop, ..." always stands alone
        starts_new = (bool(_BULLET.match(line)) or numbered) and current
        if starts_new:
            paragraphs.append(" ".join(current))
            current = []
        current.append(line)
        if len(line) < short or numbered:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    result = "\n\n".join(p for p in paragraphs if p.strip())
    return (result, removed) if return_removed else result


def load_corpus(repo_root: Path, manifest_path: Path | None = None) -> tuple[list[DocumentPage], list[dict]]:
    """Load every counted page listed in data/manifest.json with chapter/section metadata.

    Returns (pages, log). Metadata per page: page_id, chapter (int), chapter_title,
    section (section heading at page start, from the manifest), raw_chars, chars, removed_lines.
    """
    manifest_path = manifest_path or repo_root / "data" / "manifest.json"
    source = json.loads(manifest_path.read_text(encoding="utf-8"))["sources"][0]
    pdf = repo_root / "starter" / "data" / "raw" / Path(source["local_path"]).name
    meta = {
        p["physical_page"]: {
            "chapter": p["chapter"],
            "chapter_title": p["chapter_title"],
            "section": p["section_at_page_start"],
            # chapter-opening pages print "<n> <chapter title>" as a footer
            "chapter_title_footer": f'{p["chapter"]} {p["chapter_title"]}',
        }
        for p in source["pages"]
    }
    log: list[dict] = []
    pages = load_pdf(pdf, source["source_id"], source["title"], pages=sorted(meta),
                     page_metadata=meta, log=log)
    # The manifest section comes from PDF bookmarks, so a section that starts at the BOTTOM of a page
    # is credited to the whole page. Recompute the section in force at the START of each page from
    # the numbered headings actually present in the text, carried over from the previous page.
    carry, current_chapter = None, None
    for page in pages:
        if page.metadata["chapter"] != current_chapter:
            current_chapter, carry = page.metadata["chapter"], "Introduction"
        page.metadata["section_bookmark"] = page.metadata["section"]
        page.metadata["section"] = carry
        in_outline = False  # the "CHAPTER OUTLINE" list repeats section titles; it is not a heading
        for paragraph in (p.strip() for p in page.text.split("\n\n")):
            if paragraph == "CHAPTER OUTLINE":
                in_outline = True
            elif in_outline and _SECTION_HEADING.match(paragraph):
                continue
            else:
                in_outline = False
                if _SECTION_HEADING.match(paragraph):
                    carry = paragraph
    return pages, log


def write_log(pages: list[DocumentPage], log: list[dict], out_path: Path) -> dict:
    """Write per-page events plus a summary to a JSON file; return the summary."""
    summary = {
        "pages_loaded": len(pages),
        "total_chars": sum(p.metadata["chars"] for p in pages),
        "removed_furniture_lines": sum(p.metadata["removed_lines"] for p in pages),
        "events": dict(Counter(e["event"] for e in log)),
        "pages_per_chapter": dict(Counter(p.metadata["chapter"] for p in pages)),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"summary": summary, "events": log}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    return summary
