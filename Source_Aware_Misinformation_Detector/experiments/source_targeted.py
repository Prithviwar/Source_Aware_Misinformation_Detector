"""Source-targeted retrieval: CLAIM -> PREDICTED AUTHORITY -> TARGETED QUERY -> KS SEARCH.

The AVeriTeC knowledge store (KS) is a fixed per-claim document set with no search
engine behind it, so a web-style query such as

    site:ncdc.gov.ng  "Nigeria Centre for Disease Control" COVID-19 cases in Lagos

is executed *offline* as its corpus-compatible equivalent:

    1. site filter  : keep KS docs whose publisher key (registered domain, or
                      platform/handle for social URLs; `cand_key`) equals one of
                      the query's authority keys;
    2. text query   : BM25 over the claim's whole retrieval corpus (idf from all
                      docs) with the query text, restricted to the filtered docs;
    3. semantic     : the frozen dense (MiniLM) claim-query score, restricted to
                      the filtered docs;
    4. targeted rank: RRF(k=60) of 2 and 3 inside the filtered set.

Everything is offline and deterministic. Inputs are ONLY: the claim text, the
LLM authority prediction made from the claim (authority_resolution L+Wctx prompt;
gold never enters it) and the retrieval corpus {url_norm, text}. Gold evidence is
read only in evaluation code (source_targeted_eval.py), and oracle keys only
enter through the explicitly labelled `oracle` path there.

Representation: an authority prediction is turned into
`primary_authority_candidates` = ranked list of {rank, publisher, keys, type},
not a single winner (the predictor already reports multiple legitimate
authorities for most claims).
"""
from __future__ import annotations

import re

import bm25s
import numpy as np

from authority_resolution import org_domain, pred_keys, social_key

RRF_K = 60


def cand_key(url: str) -> str:
    """Publisher key of a candidate document (same definition as the frozen validation)."""
    return social_key(url) or org_domain(url)


# ------------------------------------------------------------------ authority representation

def primary_authority_candidates(pred: dict | None, max_n: int = 3) -> list[dict]:
    """Ranked authority candidates from one predictor output (top3 list)."""
    out = []
    for i, t in enumerate(((pred or {}).get("top3") or [])[:max_n], 1):
        keys = pred_keys(t)
        if keys:
            out.append({"rank": i, "publisher": t.get("publisher") or "", "keys": sorted(keys),
                        "type": t.get("publisher_type"), "why": t.get("why")})
    return out


def oracle_candidates(keys: set[str]) -> list[dict]:
    """ORACLE (diagnostic only): authority keys supplied from gold, one pseudo-candidate."""
    return [{"rank": 1, "publisher": "ORACLE", "keys": sorted(keys), "type": "oracle", "why": "oracle"}] if keys else []


# ------------------------------------------------------------------ query generation

def make_queries(claim: str, pred: dict | None, text_mode: str = "claim+entity",
                 candidates: list[dict] | None = None) -> list[dict]:
    """One targeted query per authority candidate.

    text_mode: 'claim'          -> claim text
               'claim+entity'   -> claim text + relevant_entity + publisher name
               'fact+entity'    -> predictor's fact_at_issue + relevant_entity + publisher name
    Returns dicts with the executable parts (site keys, text) and a human-readable
    web-style string ('site:<key> <text>') for logging / a future live-web run.
    """
    pred = pred or {}
    cands = candidates if candidates is not None else primary_authority_candidates(pred)
    ent = str(pred.get("relevant_entity") or "")
    fact = str(pred.get("fact_at_issue") or "")
    qs = []
    for c in cands:
        pub = "" if c["publisher"] == "ORACLE" else c["publisher"]
        if text_mode == "claim":
            text = claim
        elif text_mode == "fact+entity":
            text = " ".join(x for x in (fact or claim, ent, pub) if x)
        else:
            text = " ".join(x for x in (claim, ent, pub) if x)
        text = re.sub(r"\s+", " ", text).strip()
        qs.append({"authority_rank": c["rank"], "publisher": c["publisher"], "site": c["keys"], "text": text,
                   "web_query": " OR ".join(f"site:{k}" for k in c["keys"]) + f" {text}"})
    return qs


# ------------------------------------------------------------------ corpus search

class ClaimIndex:
    """BM25 index over one claim's retrieval corpus (built once, queried many times)."""

    def __init__(self, docs: list[dict]):
        self.urls = [d["url_norm"] for d in docs]
        self.keys = [cand_key(u) for u in self.urls]
        self.bm = bm25s.BM25()
        self.bm.index(bm25s.tokenize([d["text"] for d in docs], stopwords="en", show_progress=False),
                      show_progress=False)

    def bm25_scores(self, text: str) -> np.ndarray:
        toks = bm25s.tokenize([text], stopwords="en", return_ids=False, show_progress=False)[0]
        toks = [t for t in toks if t in self.bm.vocab_dict]
        if not toks:
            return np.zeros(len(self.urls))
        return self.bm.get_scores(toks)


def targeted_rank(index: ClaimIndex, queries: list[dict], dense_rank: list[tuple[str, float]],
                  order: str = "rrf") -> list[tuple[str, float]]:
    """Execute the targeted queries against the KS.

    order: 'rrf'          -> one list, RRF(bm25-in-subset, dense-in-subset), authorities pooled
           'authority'    -> authority rank first (all docs of candidate 1, then 2, ...), RRF inside
    A doc matching several candidates is kept once, under its best authority rank.
    """
    arank: dict[str, int] = {}
    lex: dict[str, float] = {}
    for q in queries:
        site = set(q["site"])
        sc = index.bm25_scores(q["text"])
        for i, (u, k) in enumerate(zip(index.urls, index.keys)):
            if k in site:
                if u not in arank or q["authority_rank"] < arank[u]:
                    arank[u] = q["authority_rank"]
                lex[u] = max(lex.get(u, -1.0), float(sc[i]))
    if not arank:
        return []
    subset = set(arank)
    lex_order = sorted(subset, key=lambda u: (-lex[u], u))
    dense_order = [u for u, _ in dense_rank if u in subset]
    rrf = {u: 0.0 for u in subset}
    for lst in (lex_order, dense_order):
        for r, u in enumerate(lst, 1):
            rrf[u] += 1.0 / (RRF_K + r)
    if order == "authority":
        ranked = sorted(subset, key=lambda u: (arank[u], -rrf[u], u))
    else:
        ranked = sorted(subset, key=lambda u: (-rrf[u], u))
    return [(u, rrf[u]) for u in ranked]


# ------------------------------------------------------------------ fusion with semantic retrieval

def fuse(hybrid: list[tuple[str, float]], targeted: list[tuple[str, float]], pool: int = 100,
         m: int | None = 20) -> list[tuple[str, float]]:
    """Candidate pool = hybrid top-`pool` UNION targeted top-`m`; ranked by RRF of the two ranks
    (a list contributes nothing for docs it does not contain)."""
    h = hybrid[:pool]
    t = targeted[:m] if m else targeted
    s: dict[str, float] = {}
    for lst in (h, t):
        for r, (u, _) in enumerate(lst, 1):
            s[u] = s.get(u, 0.0) + 1.0 / (RRF_K + r)
    hr = {u: r for r, (u, _) in enumerate(h, 1)}
    return sorted(s.items(), key=lambda x: (-x[1], hr.get(x[0], 10**6), x[0]))


def rerank_prior(ranked: list[tuple[str, float]], prior, lam: float = 1.0) -> list[tuple[str, float]]:
    """minmax(score within the given pool) + lam * prior(url), stable (same form as the frozen rerank)."""
    if not ranked:
        return []
    hi, lo = max(s for _, s in ranked), min(s for _, s in ranked)
    span = (hi - lo) or 1.0
    out = [(u, (s - lo) / span + lam * prior(u)) for u, s in ranked]
    out.sort(key=lambda x: -x[1])
    return out
