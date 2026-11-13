"""Build data/manifest.json for the Nam Cao Markdown corpus (one story = one source unit).

Minimum fields follow GUIDE.md: source_id, title, source URL/path, license/permission, accessed_at,
list of unit IDs with character counts, snapshot/version. Counts come from the same loader the pipeline
uses (src.ingestion.load_markdown_corpus), so the manifest and the pipeline cannot disagree.
Run from starter/:  python -I -X utf8 scripts/build_manifest.py
"""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

STARTER = Path(__file__).resolve().parents[1]
REPO = STARTER.parent
sys.path.insert(0, str(STARTER))

from src.ingestion import MD_MIN_CHARS, PERIOD_LABELS, load_markdown_corpus  # noqa: E402

RAW = STARTER / "data" / "raw" / "nam-cao"
LEFTOVER = re.compile(r"\*|(?<!\w)_|_(?!\w)|<[A-Za-z/]|\[\^|https?://")


def read_source_info() -> dict:
    """SOURCE.txt is written when the repository is cloned; keep it the single place that holds these facts."""
    info = {}
    for line in (RAW / "SOURCE.txt").read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(" ")
        info[key] = value.strip()
    return info


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    info = read_source_info()
    pages, log = load_markdown_corpus(REPO)
    units, issues = [], [dict(e) for e in log]
    for p in pages:
        m = p.metadata
        units.append({
            "unit": p.page, "page_id": m["page_id"], "unit_id": m["unit_id"], "file": m["file"],
            "period": m["period"], "title": m["title"], "title_year_in_heading": m["title_year"],
            "chars": m["chars"], "raw_lines": m["line_map"]["total"] if m["line_map"] else None,
            "file_sha256": sha256(RAW / m["file"]), "removed_lines": m["removed"],
        })
        if LEFTOVER.search(p.text):
            issues.append({"unit": p.page, "file": m["file"], "event": "markdown_marker_left",
                           "detail": "a stray Markdown character remains in the source text; not guessed or edited"})

    chars = [u["chars"] for u in units]
    per_period = {k: {"units": sum(u["period"] == k for u in units),
                      "chars": sum(u["chars"] for u in units if u["period"] == k)} for k in PERIOD_LABELS}
    snapshot_hash = hashlib.sha256("".join(u["file_sha256"] for u in units).encode()).hexdigest()
    manifest = {
        "sources": [{
            "source_id": "namcao",
            "title": "Tuyển tập truyện ngắn Nam Cao (bản số hóa Markdown)",
            "author": "Nam Cao",
            "language": "vi",
            "format": "markdown",
            "source_url": info["url"],
            "local_path": "starter/data/raw/nam-cao/ (not committed; fetch with the commit below)",
            "license_or_permission": {
                "statement_verbatim": (RAW / "LICENSE.md").read_text(encoding="utf-8").strip(),
                "reading": ("Texts are 'believed to be in the public domain in Vietnam' (a belief stated by the "
                            "repository, not a license grant); contributions by the digitizers are CC0. Users "
                            "outside Vietnam must check local law. Edition/source of the printed text is not stated."),
            },
            "accessed_at": info["accessed_at"],
            "snapshot_version": {"git_commit": info["commit"], "commit_date": info["commit_date"],
                                 "unit_files_sha256_of_hashes": snapshot_hash},
            "counting_rule": (
                "Unit = one story file (.md) under truoc-cach-mang/ or sau-cach-mang/ (GUIDE.md: an unpaginated "
                f"source is counted in independent meaningful units of >= {MD_MIN_CHARS} normalized characters). "
                "Unit number = ordinal (truoc-cach-mang sorted by file name, then sau-cach-mang sorted by file name). "
                "Normalized characters = length of the story body after normalize_markdown (title line, rules, "
                "footnote definitions, image lines and HTML tags dropped; inline markers stripped; whitespace "
                "collapsed). Not counted: files/ (merged e-books that repeat the stories), doc.md, README.md, "
                "metadata.yaml, Makefile, minimal.css, LICENSE.md."),
            "excluded_from_repo": info["excluded"],
            "units_total": len(units),
            "units_counted": len(units),
            "units_below_min_chars": sum(c < MD_MIN_CHARS for c in chars),
            "total_chars": sum(chars),
            "chars_min_median_max": [min(chars), sorted(chars)[len(chars) // 2], max(chars)],
            "per_period": per_period,
            "extractor": "src.ingestion.normalize_markdown / load_markdown_corpus",
            "filter_field": {"name": "period", "values": list(PERIOD_LABELS),
                             "source": "folder name in the repository (before / after the August Revolution)"},
            "units": units,
            "issues": issues,
        }],
    }
    out = REPO / "data" / "manifest.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(f"units {len(units)} | chars {sum(chars):,} | min/median/max {min(chars):,}/{sorted(chars)[len(chars)//2]:,}/{max(chars):,}")
    print("per period:", per_period)
    print("issues:", dict(Counter(i["event"] for i in issues)) or "none")
    return 0 if len(units) >= 30 and not any(c < MD_MIN_CHARS for c in chars) else 1


if __name__ == "__main__":
    sys.exit(main())
