"""Suggested pipeline entry point; TODO: implement the orchestration."""
import csv
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .chunking import by_paragraph, chunk_stats, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_corpus, write_log
from .store import PgVectorStore

# Implementation notes (added). Run from starter/:  python -m src.run
# Strategy configs are fixed here BEFORE any retrieval result was seen (do not tune on test).
REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "starter" / "results"
FIXED = {"size": 500, "overlap": 50}  # A
PARA = {"max_size": 1000}             # B and C
TOP_K = 3
AUDIT_SEED = 20260101                 # seed for the coherence sample
USD_PER_1M_TOKENS = {"text-embedding-3-small": 0.02, "text-embedding-3-large": 0.13}  # published price, verify


def main() -> None:
    """TODO:

    1. Load the corpus and benchmark; validate at least 30 content pages.
    2. Build strategies A (fixed), B (paragraph) and C (B + metadata filter).
    3. Embed with the same model and store vectors/metadata per strategy.
    4. Run the same dev/test questions and save full top-3 traces.
    5. Report retrieval metrics and prepare samples for manual assessment.

    Follow the five dimensions in ../../BENCHMARK.md.
    """
    load_dotenv()
    started = datetime.now(timezone.utc)
    t0 = time.time()

    # 1. corpus + benchmark
    pages, log = load_corpus(REPO)
    if len(pages) < 30:
        raise SystemExit(f"only {len(pages)} content pages; need at least 30")
    ingestion_summary = write_log(pages, log, RESULTS / "ingestion_log.json")
    bench = json.loads((REPO / "benchmark" / "benchmark.json").read_text(encoding="utf-8"))["questions"]

    # 2. chunking: A = fixed windows, B = paragraphs; C reuses B's chunks and adds a metadata filter at query time
    chunks = {
        "A": [c for p in pages for c in fixed_size(p, **FIXED)],
        "B": [c for p in pages for c in by_paragraph(p, **PARA)],
    }
    stats = {k: chunk_stats(v) for k, v in chunks.items()}

    # 3. embed (same model for A, B and the questions) + store
    embedder = MyEmbedder(os.getenv("EMBEDDING_MODEL") or None)
    store = PgVectorStore(os.environ["DATABASE_URL"], embedder.dimensions)
    store.create_schema()
    ingest_seconds, db_rows = {}, {}
    for strategy, items in chunks.items():
        t1 = time.time()
        vectors = embedder.embed_documents([c.text for c in items])
        store.upsert(strategy, items, vectors)
        ingest_seconds[strategy] = round(time.time() - t1, 1)  # embed + store time
        db_rows[strategy] = store.count(strategy)
        assert db_rows[strategy] == len(items), f"{strategy}: {db_rows[strategy]} rows in DB for {len(items)} chunks"
        print(f"{strategy}: stored {len(items)} chunks, DB rows {db_rows[strategy]}, {ingest_seconds[strategy]}s")
    question_vectors = {q["id"]: embedder.embed_query(q["question"]) for q in bench}

    # 4. retrieval: same questions for A, B, C. C = B + chapter filter, only on questions that supply one.
    plan = {"A": ("A", False), "B": ("B", False), "C": ("B", True)}
    traces = []
    for name, (store_key, use_filter) in plan.items():
        for q in bench:
            flt = q.get("filter") if use_filter else None
            hits = store.search(store_key, question_vectors[q["id"]], TOP_K, flt)
            trace = evaluate_query(q, hits)
            trace.update({"strategy": name, "applied_filter": flt,
                          "hits": [{k: h[k] for k in ("chunk_id", "document_id", "text", "score", "page", "metadata")} for h in hits]})
            traces.append(trace)

    # 5. metrics, resource log and manual-audit templates
    metrics = summarize(traces)
    elapsed = round(time.time() - t0, 1)
    cost = embedder.tokens_used / 1e6 * USD_PER_1M_TOKENS.get(embedder.model_name, float("nan"))
    run_info = {
        "started_utc": started.isoformat(timespec="seconds"), "elapsed_seconds": elapsed,
        "embedding_model": embedder.model_name, "dimensions": embedder.dimensions,
        "embedding_tokens": embedder.tokens_used, "embedding_requests": embedder.requests,
        "estimated_cost_usd": round(cost, 5), "top_k": TOP_K, "configs": {"A": FIXED, "B": PARA, "C": PARA},
        "embed_and_store_seconds": ingest_seconds, "db_rows_after_run": db_rows,
        "chunk_stats": stats, "ingestion": ingestion_summary, "questions": len(bench),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    for name, obj in (("traces.json", traces), ("metrics.json", metrics), ("run_info.json", run_info)):
        (RESULTS / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    write_audit_templates(pages, chunks, traces)
    update_experiment_log(metrics, stats, run_info)

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"tokens={embedder.tokens_used} est_cost=${cost:.4f} elapsed={elapsed}s")


def _write_if_new(path: Path, header: list[str], rows: list[list]) -> None:
    """Never overwrite a file that may already contain human labels."""
    if path.exists():
        print(f"kept existing {path.name} (may hold manual labels)")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def write_audit_templates(pages: list, chunks: dict, traces: list[dict]) -> None:
    """Blank sheets for the HUMAN labels: coherence (10 positions), metadata (test top-3), grounding (test)."""
    # Same 10 source positions for A and B, fixed by a seed before any score is looked at.
    # Position = (page, character offset); each strategy contributes the chunk that covers it.
    rng = random.Random(AUDIT_SEED)
    coherence = []
    for pos_no, page in enumerate(sorted(rng.sample(pages, 10), key=lambda p: p.page), start=1):
        offset = int(len(page.text) * rng.uniform(0.1, 0.9))
        anchor = page.text[offset:offset + 40]
        for strategy in ("A", "B"):
            found = None
            for c in chunks[strategy]:
                if c.page != page.page:
                    continue
                if strategy == "A":
                    covers = c.metadata["char_start"] <= offset < c.metadata["char_end"]
                else:
                    covers = anchor in c.text or anchor[:15] in c.text
                if covers:
                    found = c
                    break
            if found is None:
                raise RuntimeError(f"no {strategy} chunk covers page {page.page} offset {offset}")
            coherence.append([pos_no, f"p{page.page} @char {offset}", strategy, found.chunk_id,
                              found.metadata.get("section"), found.text, "", ""])
    _write_if_new(RESULTS / "manual_coherence.csv",
                  ["position", "source_position", "strategy", "chunk_id", "section", "text",
                   "coherence(0-2)", "reason"], coherence)

    meta_rows, grounding_rows = [], []
    for t in traces:
        if t["split"] != "test":
            continue
        grounding_rows.append([t["strategy"], t["question_id"], t["question"], t["evidence_quote"],
                               "", ""])
        for h in t["hits"]:
            m = h["metadata"]
            meta_rows.append([t["strategy"], t["question_id"], h["chunk_id"], h["document_id"], h["page"],
                              m.get("chapter"), m.get("section"), m.get("line_start"), m.get("line_end"),
                              t["gold_page"], "", ""])
    _write_if_new(RESULTS / "manual_metadata.csv",
                  ["strategy", "question_id", "chunk_id", "document_id", "page", "chapter", "section",
                   "line_start", "line_end", "gold_page", "metadata_correct_and_complete(0/1)", "error_note"], meta_rows)
    _write_if_new(RESULTS / "manual_grounding.csv",
                  ["strategy", "question_id", "question", "gold_evidence", "grounding(0-2)", "reason"],
                  grounding_rows)


def update_experiment_log(metrics: dict, stats: dict, run_info: dict) -> None:
    """Fill measured columns of artifacts/experiment_log.csv; keep hypothesis/notes the student wrote."""
    path = REPO / "artifacts" / "experiment_log.csv"
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    vectorizer = f"{run_info['embedding_model']} ({run_info['dimensions']}d)"
    spec = {
        "A": ("fixed_size", FIXED["size"], FIXED["overlap"], "document_id,source,page,chapter,section", "none"),
        "B": ("by_paragraph", PARA["max_size"], 0, "document_id,source,page,chapter,section", "none"),
        "C": ("by_paragraph", PARA["max_size"], 0, "document_id,source,page,chapter,section",
              "chapter (only on questions that supply one)"),
    }
    for row in rows:
        k = row["strategy"]
        if k not in spec:
            continue
        row.update(zip(("chunking", "chunk_size", "overlap", "metadata", "filter"), spec[k]))
        row["vectorizer"] = vectorizer
        for split in ("dev", "test"):
            m = metrics[k][split]
            row[f"{split}_hit1"] = f"{m['hit1']}/{m['n']}"
            row[f"{split}_hit3"] = f"{m['hit3']}/{m['n']}"
        if not row.get("notes"):
            src = "B" if k == "C" else k
            row["notes"] = f"{stats[src]['chunks']} chunks (store {src}); run {run_info['started_utc']}"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
