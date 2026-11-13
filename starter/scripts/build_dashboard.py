"""Build results/dashboard.html: a self-contained page to browse the experiment visually.

Reads the files already produced by `python -m src.run` (traces, metrics, run_info, manual_*.csv),
re-chunks the corpus locally (no API call, no cost) so chunk boundaries can be shown, and inlines
everything into one HTML file that opens offline.
Run from starter/:  python -I scripts/build_dashboard.py
"""
import csv
import json
import sys
from pathlib import Path

STARTER = Path(__file__).resolve().parents[1]
REPO = STARTER.parent
sys.path.insert(0, str(STARTER))

from src.chunking import by_paragraph, fixed_size  # noqa: E402
from src.ingestion import load_markdown_corpus  # noqa: E402
from src.run import FIXED, PARA  # noqa: E402

RESULTS = REPO / "results"


def read_csv(name: str) -> list[dict]:
    path = RESULTS / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def chunk_row(c) -> dict:
    m = c.metadata
    return {"id": c.chunk_id, "text": c.text, "section": m.get("section"),
            "line_start": m.get("line_start"), "line_end": m.get("line_end")}


def main() -> None:
    pages, _ = load_markdown_corpus(REPO)
    page_data = []
    for p in pages:
        a, b = fixed_size(p, **FIXED), by_paragraph(p, **PARA)
        page_data.append({
            "page": p.page, "unit_id": p.metadata["unit_id"], "title": p.metadata["title"],
            "period": p.metadata["period"], "text": p.text,
            "lines": (p.metadata.get("line_map") or {}).get("lines", []),
            "A": [chunk_row(c) for c in a],
            "B": [chunk_row(c) for c in b],
        })
    bench = json.loads((REPO / "benchmark" / "benchmark.json").read_text(encoding="utf-8"))
    data = {
        "run": json.loads((RESULTS / "run_info.json").read_text(encoding="utf-8")),
        "metrics": json.loads((RESULTS / "metrics.json").read_text(encoding="utf-8")),
        "traces": json.loads((RESULTS / "traces.json").read_text(encoding="utf-8")),
        "questions": bench,
        "pages": page_data,
        "manual": {name: read_csv(f"manual_{name}.csv") for name in ("coherence", "metadata", "grounding")},
    }
    template = (STARTER / "scripts" / "dashboard_template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = RESULTS / "dashboard.html"
    out.write_text(template.replace("/*__DATA__*/null", payload), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
