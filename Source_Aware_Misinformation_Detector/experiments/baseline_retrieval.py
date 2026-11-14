"""Step 4: plain retrieval baselines over each claim's AVeriTeC knowledge store.

  bm25   : bm25s (English stop words, no stemming) over full document text
  dense  : sentence-transformers all-MiniLM-L6-v2 over the first 1,000 chars
           of each document, max 128 word pieces (the length the model was
           trained with). CPU budget: this laptop encodes ~10 docs/s at 256
           tokens, which would take 3-5 h for the ~100k candidate documents.
  hybrid : reciprocal-rank fusion (k=60) of the bm25 and dense rankings

Query = claim text only. No LLM.

Leakage controls (see docs/experiment_results.md, "Leakage controls"):
  * the retriever only sees `retrieval_corpus()` objects = {url_norm, text}.
    `ks_type`/`ks_query` (gold markers), `doc_idx` (gold docs are stored FIRST
    in every KS file) and the raw `url` (gold URLs are 15x more often
    web.archive.org-wrapped) are stripped; url_norm is the un-archived URL.
  * candidates are shuffled with a fixed per-claim seed, so score ties can no
    longer be broken by file order (which would favour gold documents).
  * documents with empty text are excluded from the candidate pool (they cannot
    be read by a verifier); how many gold documents that removes is reported.

Writes results/rankings_<method>.jsonl.gz (top 100 per claim). Metrics are
computed separately by evaluate_retrieval.py.
"""
import argparse
import gzip
import json
import random
import time

import bm25s
import numpy as np

from common import RESULTS, load_ks, load_sample, normalize_url

TOP_N = 100
SEED = 2026


def claim_docs(claim_id: int, audit: bool = False) -> list[dict]:
    """Knowledge-store docs deduplicated by normalised URL (keep the longest text),
    in a seeded random order. Only url_norm + text unless audit=True."""
    best: dict[str, dict] = {}
    for d in load_ks(claim_id):
        key = normalize_url(d["url"])  # recomputed: do not trust the stored url_norm
        if key not in best or len(d["text"]) > len(best[key]["text"]):
            best[key] = {"url_norm": key, "text": d["text"]}
            if audit:
                best[key].update(url=d["url"], ks_type=d["ks_type"])
    docs = sorted(best.values(), key=lambda d: d["url_norm"])
    random.Random(SEED * 100_003 + claim_id).shuffle(docs)
    return docs


def retrieval_corpus(claim_id: int) -> list[dict]:
    """Exactly what every retrieval condition may read: non-empty docs, {url_norm, text}."""
    return [d for d in claim_docs(claim_id) if d["text"].strip()]


def rank_bm25(query: str, docs: list[dict]) -> list[tuple[str, float]]:
    texts = [d["text"] for d in docs]
    retriever = bm25s.BM25()
    retriever.index(bm25s.tokenize(texts, stopwords="en", show_progress=False), show_progress=False)
    scores = retriever.get_scores(_query_tokens(query, retriever))
    order = np.argsort(-scores, kind="stable")
    return [(docs[i]["url_norm"], float(scores[i])) for i in order]


def _query_tokens(query: str, retriever: "bm25s.BM25") -> list[str]:
    toks = bm25s.tokenize([query], stopwords="en", return_ids=False, show_progress=False)[0]
    return [t for t in toks if t in retriever.vocab_dict]


_ST = None


def rank_dense(query: str, docs: list[dict]) -> list[tuple[str, float]]:
    global _ST
    if _ST is None:
        from sentence_transformers import SentenceTransformer
        _ST = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
        _ST.max_seq_length = 128
    emb = _ST.encode([d["text"][:1000] for d in docs], batch_size=32, normalize_embeddings=True)
    qv = _ST.encode([query], normalize_embeddings=True)[0]
    scores = emb @ qv
    order = np.argsort(-scores, kind="stable")
    return [(docs[i]["url_norm"], float(scores[i])) for i in order]


def save_rankings(method: str, rankings: dict[int, list[tuple[str, float]]], top_n: int | None = TOP_N) -> None:
    """top_n=None keeps the full ranking (needed for RRF fusion of bm25 and dense)."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    with gzip.open(RESULTS / f"rankings_{method}.jsonl.gz", "wt", encoding="utf-8") as fh:
        for cid, ranked in rankings.items():
            fh.write(json.dumps({"claim_id": cid, "ranked": ranked[:top_n]}) + "\n")


def load_rankings(method: str) -> dict[int, list[tuple[str, float]]]:
    with gzip.open(RESULTS / f"rankings_{method}.jsonl.gz", "rt", encoding="utf-8") as fh:
        return {r["claim_id"]: [tuple(x) for x in r["ranked"]] for r in map(json.loads, fh)}


def rank_hybrid(cid: int, k: int = 60) -> list[tuple[str, float]]:
    """RRF of the saved bm25 and dense rankings (full candidate lists are saved for both)."""
    fused: dict[str, float] = {}
    for m in ("bm25", "dense"):
        for rank, (u, _) in enumerate(_saved[m][cid], 1):
            fused[u] = fused.get(u, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda x: -x[1])


_saved: dict = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["bm25", "dense", "hybrid"], required=True)
    args = ap.parse_args()
    sample = load_sample()
    if args.method == "hybrid":
        _saved.update(bm25=load_rankings("bm25"), dense=load_rankings("dense"))
        save_rankings("hybrid", {r["claim_id"]: rank_hybrid(r["claim_id"]) for r in sample}, top_n=None)
        return
    rank = rank_bm25 if args.method == "bm25" else rank_dense
    rankings, t0 = {}, time.time()
    for i, r in enumerate(sample, 1):
        docs = retrieval_corpus(r["claim_id"])
        rankings[r["claim_id"]] = rank(r["claim"], docs)
        print(f"[{i}/{len(sample)}] claim {r['claim_id']} ({len(docs)} docs, {time.time() - t0:.0f}s)", flush=True)
    save_rankings(args.method, rankings, top_n=None)


if __name__ == "__main__":
    main()
