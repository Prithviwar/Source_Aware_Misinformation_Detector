"""Leak-safe claim-document features for the RELEVANCE baseline.

Inputs a feature may read (and nothing else):
  claim side   : claim text, speaker, location_ISO_code (all present even in the AVeriTeC test release)
  document side: normalised URL (url_norm) and document text
  retrieval    : BM25 / MiniLM / RRF scores and ranks computed from the claim text
Never read: AVeriTeC questions/answers/justification/label/fact-checking article, gold indicators,
knowledge-store type/query fields, file order (doc_idx), raw (archive-wrapped) URL, pool publisher
counts. `assert_safe` checks the names of every feature against rb_common.FORBIDDEN_FEATURE_SOURCES.
"""
from __future__ import annotations

import math
import random
import re

import numpy as np

from rb_common import FORBIDDEN_FEATURE_SOURCES

BASE_FEATURES = [
    "bm25_score", "bm25_score_rel", "bm25_rank_log", "dense_cos", "dense_rank_log", "rrf_score", "hybrid_rank_log",
    "doc_len_log", "term_overlap_frac", "number_overlap_frac", "url_generic_prior", "url_is_gov", "url_is_pdf",
    "url_path_depth", "url_is_social", "url_entity_match", "url_claim_country_gov",
]


def assert_safe(names):
    bad = [n for n in names if n in FORBIDDEN_FEATURE_SOURCES or n.startswith(("gold", "ks_", "label"))]
    assert not bad, f"forbidden feature(s): {bad}"


def build_corpus(rows: list[dict], claim_idx: int, seed: int = 2026) -> list[dict]:
    """Identical rule to the frozen baseline_retrieval.claim_docs/retrieval_corpus, for any KS directory:
    dedupe by normalised URL keeping the longest text, sort by url_norm, seeded shuffle, drop empty."""
    from common import normalize_url
    best = {}
    for d in rows:
        key = normalize_url(d["url"])
        if key not in best or len(d["text"]) > len(best[key]["text"]):
            best[key] = {"url_norm": key, "text": d["text"]}
    docs = sorted(best.values(), key=lambda d: d["url_norm"])
    random.Random(seed * 100_003 + claim_idx).shuffle(docs)
    return [d for d in docs if d["text"].strip()]


def rankings(claim: str, docs: list[dict]):
    """Frozen rank functions + RRF k=60 (as validation_heldout.cmd_rank)."""
    from baseline_retrieval import rank_bm25, rank_dense
    b = rank_bm25(claim, docs)
    d = rank_dense(claim, docs)
    fused = {}
    for lst in (b, d):
        for r, (u, _) in enumerate(lst, 1):
            fused[u] = fused.get(u, 0.0) + 1.0 / (60 + r)
    return b, d, sorted(fused.items(), key=lambda x: -x[1])


def _terms(q):
    import bm25s
    return set(bm25s.tokenize([q], stopwords="en", return_ids=False, show_progress=False)[0])


def pair_features(claim_row: dict, docs: list[dict], b, d, h, urls: list[str]) -> np.ndarray:
    from authority_retrieval import claim_entities, claim_prior, entity_keys, entity_match, generic_prior, is_gov
    from common import full_host
    text = {x["url_norm"]: x["text"] for x in docs}
    pos = {name: {u: (i, s) for i, (u, s) in enumerate(lst, 1)} for name, lst in (("b", b), ("d", d), ("h", h))}
    bmax = max((s for _, s in b), default=1.0) or 1.0
    terms = _terms(claim_row["claim"])
    nums = set(re.findall(r"\d[\d,.]*", claim_row["claim"]))
    ek, iso = entity_keys(claim_entities(claim_row)), claim_row.get("location_ISO_code")
    X = []
    for u in urls:
        t = text[u]
        words = set(re.findall(r"\w+", t.lower()))
        br, bs = pos["b"][u]
        dr, ds = pos["d"][u]
        hr, hs = pos["h"][u]
        full = "http://" + u
        X.append([
            bs, bs / bmax, math.log1p(br), ds, math.log1p(dr), hs, math.log1p(hr),
            math.log1p(len(t)), len(terms & words) / max(len(terms), 1),
            (sum(n in t for n in nums) / len(nums)) if nums else 0.0,
            generic_prior(full), float(is_gov(full_host(full))), float(u.lower().endswith(".pdf")),
            u.count("/"), float(u.split("/")[0].endswith(("twitter.com", "x.com", "facebook.com", "instagram.com",
                                                          "youtube.com"))),
            float(entity_match(full, ek)), claim_prior(full, ek, iso),
        ])
    return np.asarray(X, dtype=np.float32)


def minilm_features(claim: str, docs_text: list[str]) -> np.ndarray:
    """Frozen (not fine-tuned) MiniLM: elementwise product of normalised claim and doc embeddings (384-d)."""
    import baseline_retrieval as BR
    if BR._ST is None:
        from sentence_transformers import SentenceTransformer
        BR._ST = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
        BR._ST.max_seq_length = 128
    e = BR._ST.encode([t[:1000] for t in docs_text], batch_size=32, normalize_embeddings=True)
    q = BR._ST.encode([claim], normalize_embeddings=True)[0]
    return (e * q).astype(np.float32)
