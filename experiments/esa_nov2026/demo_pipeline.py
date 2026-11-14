"""Monday-review (16 Nov 2026) demo pipeline: one claim -> BM25 / MiniLM / Hybrid RRF -> authority resolution.

NEW FILE (2026-11-14). It wraps the FROZEN project functions; it does not change them:
  * corpus, BM25, MiniLM dense ............ experiments/baseline_retrieval.py (frozen)
  * Hybrid RRF (k = 60) ................... same formula as validation_heldout.cmd_rank / demo.live_rankings
  * authority priors B / C ................ experiments/authority_retrieval.py (frozen)
  * LLM authority prior D ................. FROZEN Sept-2026 predictions + source_targeted.primary_authority_candidates
  * rerank ................................ minmax(hybrid score in top-100) + lambda * prior, lambda = 1
                                            (verified identical to the frozen authority_retrieval.rerank, see
                                            test_demo_pipeline.py)

Safety (inherited from esa_common): only the 120 dev-sample + 200 held-out claims can be loaded; the 180
reserved authority-v2 claims are refused; no sealed file is opened; no LLM/API call is made; with
HF_HUB_OFFLINE=1 no network call is made. AVeriTeC TEST labels are never read.

"Gold" = public AVeriTeC DEV annotators' evidence URLs (relevance/citation evidence), shown only as an
evaluation marker. It is never an input to any ranking or prior. It is NOT a claim-specific authority label.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
from datetime import datetime
from functools import lru_cache

from esa_common import assert_allowed, claims, load_frozen_predictions, load_frozen_rankings, out_dir

POOL = 100
LAMBDA = 1.0
RRF_K = 60

SUGGESTED = {
    268: ("Government / health policy",
          "Authority differs from credibility. The LLM prior lifts the executive order itself from hybrid rank 28 to 1."),
    328: ("Government statistics", "The statistics producer (NCES) is promoted: best evidence rank 43 -> 3."),
    89: ("Health / science history", "Predicted authorities: NIAID/NIH, J. Infectious Diseases. Evidence rank 21 -> 10."),
    464: ("Science / environment", "Predicted authorities: US National Park Service, FWS. Evidence rank 18 -> 1."),
    436: ("Limitation", "Hybrid already had evidence at rank 1; the publisher boost pushes it down to 16."),
    326: ("Failure case", "Predicted authority boosted, but evidence moves 24 -> 28 (off-topic pages promoted)."),
    2: ("No effect", "No predicted authority has a document in the pool, so the LLM prior changes nothing."),
}

DOMAIN_TYPE_LABEL = {
    "gov": "Government / intergovernmental", "academic": "Academic / journal", "news": "Major news outlet",
    "reference": "Reference (encyclopedia)", "platform": "Social platform / blog / archive", "other": "Other / unknown",
}


# ------------------------------------------------------------------ cached loaders (heavy, load once)

@lru_cache(maxsize=None)
def frozen_rankings(split: str):
    return load_frozen_rankings(split)


@lru_cache(maxsize=None)
def frozen_predictions(split: str):
    return load_frozen_predictions(split)


def claim_choices() -> list[dict]:
    out = []
    for cid, r in sorted(claims().items()):
        out.append({"claim_id": cid, "split": r["split"], "claim": r["claim"],
                    "suggested": cid in SUGGESTED})
    return out


@lru_cache(maxsize=64)
def corpus(cid: int) -> tuple:
    from baseline_retrieval import retrieval_corpus
    return tuple((d["url_norm"], d["text"]) for d in retrieval_corpus(cid))


# ------------------------------------------------------------------ step 2: claim processing

def process_claim(text: str, row: dict) -> dict:
    """Exactly what the implemented pipeline does to the claim (no hidden rewriting)."""
    import bm25s
    from authority_retrieval import claim_entities, entity_keys
    from common import tokenize_query
    q = tokenize_query(text)
    toks = bm25s.tokenize([q], stopwords="en", return_ids=False, show_progress=False)[0]
    ents = claim_entities({"claim": q, "speaker_or_entity": row.get("speaker_or_entity")})
    return {"normalized_query": q,
            "bm25_tokens": list(dict.fromkeys(toks)),
            "dense_input": q,
            "entities": [{"mention": m, "label": l} for m, l in ents],
            "entity_keys": sorted(entity_keys(ents)),
            "country_iso": row.get("location_ISO_code")}


# ------------------------------------------------------------------ step 3: retrieval

def _rrf(b, d):
    fused = {}
    for lst in (b, d):
        for rank, (u, _) in enumerate(lst, 1):
            fused[u] = fused.get(u, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(fused.items(), key=lambda x: -x[1])


def _live_cache_path(cid: int, query: str):
    h = hashlib.sha1(query.encode("utf-8")).hexdigest()[:12]
    return out_dir("demo", "live_cache") / f"claim_{cid}_{h}.json.gz"


def live_rankings(cid: int, query: str, use_cache: bool = True, progress=None):
    """Recompute BM25 + MiniLM + RRF now with the frozen functions. Results are stored on disk so a
    re-run is instant; the record keeps the time it was computed (shown in the UI)."""
    p = _live_cache_path(cid, query)
    if use_cache and p.exists():
        rec = json.load(gzip.open(p, "rt", encoding="utf-8"))
        if rec.get("query") == query and rec.get("claim_id") == cid:
            rec["from_cache"] = True
            return {m: [tuple(x) for x in rec["rankings"][m]] for m in ("bm25", "dense", "hybrid")}, rec
    from baseline_retrieval import rank_bm25, rank_dense
    docs = [{"url_norm": u, "text": t} for u, t in corpus(cid)]
    if progress:
        progress("BM25 indexing and scoring ...")
    t0 = time.time()
    b = rank_bm25(query, docs)
    t1 = time.time()
    if progress:
        progress(f"BM25 done in {t1 - t0:.1f}s. MiniLM encoding {len(docs)} documents on CPU (2-8 min on this laptop) ...")
    d = rank_dense(query, docs)
    t2 = time.time()
    h = _rrf(b, d)
    rec = {"claim_id": cid, "query": query, "computed_at": datetime.now().isoformat(timespec="seconds"),
           "n_docs": len(docs), "timing_s": {"bm25": round(t1 - t0, 1), "dense": round(t2 - t1, 1)},
           "rankings": {"bm25": b, "dense": d, "hybrid": h}}
    json.dump(rec, gzip.open(p, "wt", encoding="utf-8"))
    rec["from_cache"] = False
    return {"bm25": b, "dense": d, "hybrid": h}, rec


# ------------------------------------------------------------------ step 4: authority features

def domain_type(url: str) -> str:
    """Same decision order as the frozen authority_retrieval.generic_prior."""
    from authority_retrieval import ACADEMIC_HOSTS, INTERGOV, MAJOR_NEWS, PLATFORMS, REFERENCE, is_gov
    from common import full_host, registered_domain
    host, dom = full_host(url), registered_domain(url)
    if is_gov(host) or dom in INTERGOV or host.endswith(".int"):
        return "gov"
    if dom in ACADEMIC_HOSTS or ".edu" in host or ".ac." in host:
        return "academic"
    if dom in MAJOR_NEWS:
        return "news"
    if dom in REFERENCE:
        return "reference"
    if dom in PLATFORMS:
        return "platform"
    return "other"


def authority_features(url: str, ekeys: set, iso, llm_keys: set | None) -> dict:
    from authority_retrieval import ISO_TO_TLD, country_of, entity_match, full_prior, generic_prior, is_gov
    from common import full_host
    from source_targeted import cand_key
    host = full_host(url)
    gov = is_gov(host)
    want = ISO_TO_TLD.get(iso, iso.lower()) if iso else None
    ctry = country_of(host) if gov else None
    return {
        "publisher": cand_key(url) or "",
        "domain_type": DOMAIN_TYPE_LABEL[domain_type(url)],
        "generic_prior": generic_prior(url),
        "entity_match": bool(entity_match(url, ekeys)),
        "claim_country_gov": bool(gov and want and ctry == want),
        "other_country_gov": bool(gov and want and ctry not in (None, want)),
        "heuristic_prior": full_prior(url, ekeys, iso),
        "llm_predicted_publisher": (None if llm_keys is None else (cand_key(url) in llm_keys)),
    }


def explain(f: dict) -> str:
    bits = [f"{f['domain_type']} (generic {f['generic_prior']:.1f})"]
    if f["entity_match"]:
        bits.append("domain/handle matches a claim entity")
    if f["claim_country_gov"]:
        bits.append("government of the claim's country")
    if f["other_country_gov"]:
        bits.append("government of ANOTHER country (capped at 0.6)")
    if f["llm_predicted_publisher"]:
        bits.append("publisher predicted by the LLM as an authority")
    return "; ".join(bits)


def rerank_components(hybrid, prior_fn, lam=LAMBDA, pool_size=POOL):
    """Same formula and stable sort as frozen authority_retrieval.rerank, but keeps the two parts."""
    pool = hybrid[:pool_size]
    hi, lo = max(s for _, s in pool), min(s for _, s in pool)
    span = (hi - lo) or 1.0
    rows = []
    for i, (u, s) in enumerate(pool, 1):
        rel = (s - lo) / span
        pr = prior_fn(u)
        rows.append({"url": u, "hybrid_rank": i, "relevance": rel, "prior": pr, "final": rel + lam * pr})
    rows.sort(key=lambda x: -x["final"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["moved"] = r["hybrid_rank"] - i
    return rows


# ------------------------------------------------------------------ full pipeline

def snippet(t: str, n=260) -> str:
    return re.sub(r"\s+", " ", t[:n * 2]).strip()[:n]


def pseudo_title(t: str) -> str:
    s = re.sub(r"\s+", " ", t[:400]).strip()
    m = re.match(r"(.{20,140}?[.!?|])\s", s)
    return (m.group(1) if m else s[:120]).strip()


def run(cid: int, mode: str = "frozen", query: str | None = None, k: int = 10, show_gold: bool = True,
        use_cache: bool = True, progress=None) -> dict:
    """mode: 'frozen' (stored Sept-2026 rankings, exact), 'live' (recompute now), 'query' (custom text, live)."""
    from source_targeted import cand_key, primary_authority_candidates
    row = assert_allowed(cid)
    split = row["split"]
    if mode == "query":
        if not (query or "").strip():
            raise ValueError("Custom query mode needs some query text.")
    q = (query or row["claim"]).strip()
    proc = process_claim(q, row)
    q = proc["normalized_query"]

    texts = dict(corpus(cid))
    web_gold = {g["source_url_norm"] for g in row["gold_evidence"] if g["is_web_source"]}
    gold = web_gold & set(texts)

    live_meta = None
    if mode == "frozen":
        if progress:
            progress("Loading frozen BM25 / MiniLM / Hybrid rankings ...")
        rk = {m: v[cid] for m, v in frozen_rankings(split).items()}
    else:
        rk, live_meta = live_rankings(cid, q, use_cache=use_cache, progress=progress)
        live_meta = {k2: v for k2, v in live_meta.items() if k2 != "rankings"}
    pos = {m: {u: i for i, (u, _) in enumerate(rk[m], 1)} for m in rk}

    # LLM prediction: only for the ORIGINAL claim text (frozen file); never generated here.
    pred, llm_keys, llm_note = None, None, None
    if mode == "query":
        llm_note = ("The stored LLM prediction belongs to the original claim text. A prediction for a new query "
                    "would need a new LLM call, which this demo never makes. The LLM prior is therefore OFF.")
    else:
        pred = frozen_predictions(split).get(cid)
        if pred:
            llm_keys = set().union(*[set(a["keys"]) for a in primary_authority_candidates(pred)])
        else:
            llm_note = "No stored LLM prediction exists for this claim."

    ekeys, iso = set(proc["entity_keys"]), proc["country_iso"]
    feat_cache = {}

    def feats(u):
        if u not in feat_cache:
            feat_cache[u] = authority_features(u, ekeys, iso, llm_keys)
        return feat_cache[u]

    names = {"bm25": "BM25 (lexical)", "dense": "MiniLM dense (semantic)", "hybrid": "Hybrid RRF (k=60)"}
    retrieval = {}
    for m in ("bm25", "dense", "hybrid"):
        lst = []
        for i, (u, s) in enumerate(rk[m][:k], 1):
            t = texts.get(u, "")
            words = set(re.findall(r"\w+", t.lower()))
            lst.append({"rank": i, "score": round(float(s), 4), "publisher": feats(u)["publisher"],
                        "title_guess": pseudo_title(t), "url": u,
                        "rank_bm25": pos["bm25"].get(u), "rank_dense": pos["dense"].get(u),
                        "rank_hybrid": pos["hybrid"].get(u),
                        "matched_terms": [w for w in proc["bm25_tokens"] if w in words],
                        "snippet": snippet(t), "evidence_marker": (u in gold) if show_gold else None})
        retrieval[m] = {"label": names[m], "top": lst}
    tops = {m: {x["url"] for x in retrieval[m]["top"]} for m in retrieval}
    overlap = {"BM25 & MiniLM": len(tops["bm25"] & tops["dense"]), "BM25 & Hybrid": len(tops["bm25"] & tops["hybrid"]),
               "MiniLM & Hybrid": len(tops["dense"] & tops["hybrid"]),
               "all three": len(tops["bm25"] & tops["dense"] & tops["hybrid"])}

    hyb = rk["hybrid"]
    priors = {"B": ("B  Generic credibility prior", "claim-independent domain type", lambda u: feats(u)["generic_prior"]),
              "C": ("C  Heuristic claim-specific prior", "generic + claim-entity / claim-country rules",
                    lambda u: feats(u)["heuristic_prior"])}
    if llm_keys is not None:
        priors["D"] = ("D  LLM authority prior", "stored Claude Opus 5.5 top-3 publishers (Sept 2026), binary",
                       lambda u: float(bool(feats(u)["llm_predicted_publisher"])))
    authority = {}
    for sid, (label, desc, fn) in priors.items():
        rows = rerank_components(hyb, fn)
        top = []
        for r in rows[:k]:
            f = feats(r["url"])
            top.append({**{kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in r.items()},
                        "publisher": f["publisher"], "domain_type": f["domain_type"], "why": explain(f),
                        "title_guess": pseudo_title(texts.get(r["url"], "")),
                        "evidence_marker": (r["url"] in gold) if show_gold else None})
        best = next((r["rank"] for r in rows if r["url"] in gold), None) if show_gold else None
        authority[sid] = {"label": label, "desc": desc, "top": top,
                          "n_from_below_k": sum(x["hybrid_rank"] > k for x in top),
                          "n_from_below_50": sum(x["hybrid_rank"] > 50 for x in top),
                          "best_evidence_rank_in_pool": best}

    pool_pubs = {}
    for u, _ in hyb[:POOL]:
        pool_pubs[cand_key(u)] = pool_pubs.get(cand_key(u), 0) + 1
    final_sid = "D" if "D" in authority else "C"
    return {
        "claim_id": cid, "split": split, "mode": mode, "k": k,
        "claim": {f: row.get(f) for f in ("claim", "speaker_or_entity", "claim_date", "location_ISO_code",
                                           "reporting_source")},
        "processing": proc, "n_candidates": len(texts), "live_meta": live_meta,
        "retrieval": retrieval, "overlap": overlap,
        "best_evidence_rank": ({m: min((pos[m][u] for u in gold if u in pos[m]), default=None) for m in rk}
                               if (show_gold and gold) else None),
        "n_evidence_reachable": len(gold) if show_gold else None, "n_evidence_web": len(web_gold) if show_gold else None,
        "llm_prediction": ({"provenance": "stored file results/" + ("heldout/authority_raw.jsonl" if split == "heldout200"
                                                                    else "authority_resolution_raw.jsonl")
                                          + " (generated Sept 2026; NOT re-generated in this demo)",
                            "fact_at_issue": pred.get("fact_at_issue"), "claim_kind": pred.get("claim_kind"),
                            "authority_situation": pred.get("authority_situation"), "confidence": pred.get("confidence"),
                            "top3": [{"publisher": t.get("publisher"), "domain": t.get("domain"),
                                      "social_account": t.get("social_account"), "type": t.get("publisher_type"),
                                      "why": t.get("why")} for t in (pred.get("top3") or [])[:3]],
                            "keys_docs_in_pool": {kk: pool_pubs.get(kk, 0) for kk in sorted(llm_keys)}}
                           if pred else None),
        "llm_note": llm_note,
        "authority": authority, "final_system": final_sid,
        "evidence_note": ("Evidence marker = an AVeriTeC dev annotator evidence URL present (non-empty) in this claim's "
                          "store. It is RELEVANCE/citation evidence used only for evaluation; it is never an input to any "
                          "ranking, and it is NOT a claim-specific authority label." if show_gold else "Evidence markers hidden."),
    }
