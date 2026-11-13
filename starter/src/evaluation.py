"""TODO: evaluate retrieved evidence and preserve per-query traces."""
import re
import unicodedata
from collections import defaultdict
from typing import Any

# Implementation notes (added): a hit = chunk from the gold source AND gold page AND it contains the
# WHOLE evidence quote (same normalization as scripts/verify_benchmark.py). Only automatic, string-level
# labels are produced here; manual coherence / metadata / grounding labels are filled by a human.


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def _gold_options(question: dict[str, Any]) -> list[dict[str, Any]]:
    """Primary gold plus any documented alternative gold evidence ({'source_id','page','evidence_quote'})."""
    options = [{"source_id": question["gold_source_id"], "page": question["gold_page"],
                "quote": question["evidence_quote"]}]
    for alt in question.get("alternative_gold", []):
        options.append({"source_id": alt.get("source_id", question["gold_source_id"]), "page": alt["page"],
                        "quote": alt.get("evidence_quote", question["evidence_quote"])})
    return options


def _fragment_present(quote: str, text: str) -> bool:
    """True if the first or the second half of the quote (by words) is in `text`."""
    words = quote.split()
    if len(words) < 6:
        return False
    half = len(words) // 2
    return " ".join(words[:half]) in text or " ".join(words[half:]) in text


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """TODO: check source/page and enough gold evidence; keep hit@1 and hit@3 trace.

    Accept any documented alternative gold evidence. Do not infer human grounding
    or chunk coherence labels from exact string match.
    """
    options = _gold_options(question)
    flt = question.get("filter")
    per_hit, partial_on_gold_page = [], False
    for rank, hit in enumerate(hits, start=1):
        text = _norm(hit["text"])
        on_gold = [o for o in options if hit["document_id"] == o["source_id"] and hit["page"] == o["page"]]
        has_evidence = any(_norm(o["quote"]) in text for o in on_gold)
        if on_gold and not has_evidence and any(_fragment_present(_norm(o["quote"]), text) for o in on_gold):
            partial_on_gold_page = True
        per_hit.append({
            "rank": rank, "chunk_id": hit["chunk_id"], "page": hit["page"], "score": hit["score"],
            "source_page_match": bool(on_gold), "contains_evidence": has_evidence,
            "hit": bool(on_gold) and has_evidence,
        })
    first_hit = next((h["rank"] for h in per_hit if h["hit"]), None)
    result = {
        "question_id": question["id"], "split": question["split"],
        "question": question["question"], "gold_page": question["gold_page"],
        "gold_source_id": question["gold_source_id"], "evidence_quote": question["evidence_quote"],
        "filter": flt, "first_hit_rank": first_hit,
        "hit1": bool(per_hit) and per_hit[0]["hit"],
        "hit3": first_hit is not None,
        # failure diagnostics (string-level only; a human still decides coherence/grounding)
        "gold_page_in_top3": any(h["source_page_match"] for h in per_hit),
        "evidence_possibly_split": first_hit is None and partial_on_gold_page,
        "per_hit": per_hit,
    }
    if flt:  # filter compliance: every returned hit must satisfy the requested metadata
        result["filter_compliant"] = all(
            all(hit.get("metadata", {}).get(k) == v for k, v in flt.items()) for hit in hits)
    return result


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """TODO: aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for t in traces:
        groups[(t["strategy"], t["split"])].append(t)
    out: dict[str, Any] = {}
    for (strategy, split), items in sorted(groups.items()):
        n = len(items)
        h1, h3 = sum(t["hit1"] for t in items), sum(t["hit3"] for t in items)
        filtered = [t for t in items if t.get("filter")]
        out.setdefault(strategy, {})[split] = {
            "n": n, "hit1": h1, "hit3": h3,
            "hit1_rate": round(h1 / n, 3), "hit3_rate": round(h3 / n, 3),
            "filter_questions": len(filtered),
            "filter_compliant": sum(bool(t.get("filter_compliant")) for t in filtered) if filtered else None,
            "evidence_possibly_split": [t["question_id"] for t in items if t["evidence_possibly_split"]],
            "missed": [t["question_id"] for t in items if not t["hit3"]],
        }
    return out
