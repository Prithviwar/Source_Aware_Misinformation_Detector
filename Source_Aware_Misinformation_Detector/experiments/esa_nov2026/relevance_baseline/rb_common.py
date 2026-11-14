"""Relevance baseline (NOT an authority model): shared paths, split rules and leakage rules.

TARGET (positive-unlabelled). s = 1 ("labelled") if the knowledge-store document's normalised URL
is one of the claim's AVeriTeC annotator evidence URLs and its text is non-empty: a WEAK POSITIVE
relevance label. Every other document is UNLABELLED (s = 0 means "not labelled", never "irrelevant").
This is NOT a claim-specific authority label: AVeriTeC evidence contains news and fact-check pages.

DATA. AVeriTeC TRAIN split only (data/raw/averitec/train.json + train knowledge-store extracts).
Never: dev claims (120 dev sample, 200 held-out, 180 reserved), sealed gold, test split.
Train and dev claim ids are separate index spaces, so train ids are namespaced "train:<idx>".

STORAGE. Train knowledge-store extracts live under capstone/storage (storage rule, 2026-11-03):
  C:/Users/Lenovo/Downloads/capstone/storage/datasets/averitec_train_ks_sample/<idx>.jsonl.gz
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ESA = HERE.parent
EXP = ESA.parent
ROOT = EXP.parent
for p in (str(EXP), str(ESA)):
    if p not in sys.path:
        sys.path.insert(0, p)

from common import RAW, RESULTS  # noqa: E402  (frozen)

TRAIN_JSON = RAW / "train.json"
STORAGE = ROOT.parent / "storage"
TRAIN_KS_DIR = STORAGE / "datasets" / "averitec_train_ks_sample"
OUT = RESULTS / "esa_nov2026" / "relevance_baseline"
SPLIT_MANIFEST = OUT / "train_sample_split.json"

SEED_SAMPLE = 2051      # new seed, never used by earlier project experiments (2026, 2027, 2029-2048 used)
N_SAMPLE = 300          # train claims to extract; split 60/20/20 by claim
SPLIT_FRACTIONS = (0.6, 0.2, 0.2)
POOL = 100              # rerank pool for ranking evaluation = hybrid top-100 (same as frozen study)
N_UNLABELLED_PER_CLAIM = 30   # PU: unlabelled documents sampled per fit claim
SEED_UNLABELLED = 2052        # new seed (2051 = split); rng = random.Random(SEED_UNLABELLED * 100_003 + train_idx)
SAMPLING_POLICY = (
    "Per FIT claim only: U = all non-empty documents in the claim's deduplicated knowledge-store corpus "
    "(build_corpus) whose url_norm is not a labelled evidence URL. Candidates are sorted by url_norm, then "
    "min(N_UNLABELLED_PER_CLAIM, |U|) are drawn uniformly without replacement with "
    "random.Random(SEED_UNLABELLED * 100_003 + train_idx). No rank-based (top-100 / hard-negative) selection.")


def sample_unlabelled(train_idx: int, doc_urls, labelled, n: int = N_UNLABELLED_PER_CLAIM,
                      seed: int = SEED_UNLABELLED) -> list:
    """Deterministic, claim-specific uniform sample of unlabelled documents (see SAMPLING_POLICY)."""
    import random
    cand = sorted(set(doc_urls) - set(labelled))
    return sorted(random.Random(seed * 100_003 + train_idx).sample(cand, min(n, len(cand))))

# Fields / signals that must NEVER become model features (asserted in features.py).
FORBIDDEN_FEATURE_SOURCES = {
    "questions", "answers", "answer", "justification", "label", "gold_label", "fact_checking_article",
    "boolean_explanation", "cached_source_url", "cached_original_claim_url", "original_claim_url",
    "ks_type", "ks_query", "doc_idx", "url",          # raw url: archive-wrapping correlates with gold
    "is_gold", "gold", "claim_types", "fact_checking_strategies", "required_reannotation",
    "pool_publisher_count",                            # KS built from gold-derived queries -> may encode gold
}
