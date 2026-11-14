"""Phase-I ESA demonstration: BM25 vs MiniLM vs Hybrid RRF, then authority priors.

  python experiments/esa_nov2026/demo.py --list                      # suggested demo claims
  python experiments/esa_nov2026/demo.py --claim-id 2                # frozen rankings (fast, default)
  python experiments/esa_nov2026/demo.py --claim-id 2 --live         # recompute BM25 + MiniLM + RRF now
  python experiments/esa_nov2026/demo.py --claim-id 2 --query "France cancelled visas of Pakistani citizens"
        # custom query, retrieved LIVE over that claim's knowledge store (LLM prior unavailable: it would
        # need a new LLM call, which this demo never makes)

What it shows, for one of the 320 allowed claims (120 dev + 200 held-out; reserved claims refused):
  1. the claim and its metadata;
  2. top-K documents from BM25, MiniLM dense and Hybrid RRF side by side, with each document's rank
     under the other two methods and the query terms it contains (why the rankings differ);
  3. the existing authority-resolution outputs: frozen LLM top-3 publisher prediction (generated
     in Sept 2026, not re-run), and the hybrid top-100 re-ranked by
        B generic credibility prior, C heuristic claim prior, D LLM publisher prior (lambda = 1);
  4. which documents each prior promoted, from how deep in the pool, and whether they are
     AVeriTeC evidence documents ("gold" = annotator evidence URL: relevance evidence, NOT authority).

Writes results/esa_nov2026/demo/claim_<id>[_live|_query].{json,md,html}. No LLM/API/network calls.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import time

from esa_common import assert_allowed, claims, load_frozen_predictions, load_frozen_rankings, out_dir

POOL = 100
LAMBDA = 1.0

# Chosen from the frozen held-out per-claim results AFTER inspection, for illustration only.
SUGGESTED = {
    268: "Government/health policy. LLM prior helps: best gold rank 28 (hybrid) -> 1 (D).",
    436: "Limitation. Hybrid already had gold at rank 1; D's publisher boost pushes it to 16.",
    2: "No effect: none of the predicted authorities has a document in the pool (D = hybrid).",
    89: "Health/science history. D: best gold rank 21 -> 10.",
    328: "Government statistics. D: best gold rank 43 -> 3.",
    464: "Science/environment. D: best gold rank 18 -> 1.",
    326: "Science/security. D: best gold rank 24 -> 28 (prior promotes non-gold documents).",
}


def doc_texts(cid: int) -> dict[str, str]:
    from baseline_retrieval import retrieval_corpus
    return {d["url_norm"]: d["text"] for d in retrieval_corpus(cid)}


def gold_urls(row: dict, texts: dict[str, str]) -> tuple[set[str], set[str]]:
    """(reachable gold in retrieval corpus, all web gold) for one allowed claim."""
    web = {g["source_url_norm"] for g in row["gold_evidence"] if g["is_web_source"]}
    return web & set(texts), web


def query_terms(q: str) -> list[str]:
    import bm25s
    toks = bm25s.tokenize([q], stopwords="en", return_ids=False, show_progress=False)[0]
    seen, out = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def matched_terms(terms: list[str], text: str) -> list[str]:
    words = set(re.findall(r"\w+", text.lower()))
    return [t for t in terms if t in words]


def live_rankings(query: str, cid: int):
    from baseline_retrieval import rank_bm25, rank_dense, retrieval_corpus
    docs = retrieval_corpus(cid)
    t0 = time.time()
    b = rank_bm25(query, docs)
    t1 = time.time()
    d = rank_dense(query, docs)
    t2 = time.time()
    fused = {}
    for lst in (b, d):
        for rank, (u, _) in enumerate(lst, 1):
            fused[u] = fused.get(u, 0.0) + 1.0 / (60 + rank)
    h = sorted(fused.items(), key=lambda x: -x[1])
    return {"bm25": b, "dense": d, "hybrid": h}, {"bm25_s": round(t1 - t0, 1), "dense_s": round(t2 - t1, 1)}


def rerank(base, prior_fn):
    from authority_retrieval import rerank as frozen_rerank  # frozen: minmax(score in pool) + lambda * prior
    return frozen_rerank(base, prior_fn, LAMBDA, POOL)


def run(cid: int, k: int, live: bool, query: str | None, show_gold: bool):
    from authority_retrieval import claim_entities, entity_keys, full_prior, generic_prior
    from source_targeted import cand_key, primary_authority_candidates

    row = assert_allowed(cid)
    split = row["split"]
    q = query or row["claim"]
    mode = "query" if query else ("live" if live else "frozen")
    texts = doc_texts(cid)
    gold, gold_all = gold_urls(row, texts)
    timing = {}
    if mode == "frozen":
        rk = {m: v[cid] for m, v in load_frozen_rankings(split).items()}
    else:
        rk, timing = live_rankings(q, cid)
    pos = {m: {u: i for i, (u, _) in enumerate(rk[m], 1)} for m in rk}
    terms = query_terms(q)

    # ---------------- retrieval side by side
    retrieval = {}
    for m in ("bm25", "dense", "hybrid"):
        lst = []
        for i, (u, s) in enumerate(rk[m][:k], 1):
            t = texts.get(u, "")
            lst.append({"rank": i, "url": u, "score": round(s, 4), "publisher": cand_key("http://" + u) or "",
                        "rank_bm25": pos["bm25"].get(u), "rank_dense": pos["dense"].get(u),
                        "rank_hybrid": pos["hybrid"].get(u), "matched_terms": matched_terms(terms, t),
                        "dense_sees_chars": min(len(t), 1000), "doc_chars": len(t),
                        "snippet": re.sub(r"\s+", " ", t[:220]).strip(),
                        "gold": (u in gold) if show_gold else None})
        retrieval[m] = lst
    topset = {m: {x["url"] for x in retrieval[m]} for m in retrieval}
    overlap = {"bm25&dense": len(topset["bm25"] & topset["dense"]),
               "bm25&hybrid": len(topset["bm25"] & topset["hybrid"]),
               "dense&hybrid": len(topset["dense"] & topset["hybrid"]),
               "all_three": len(topset["bm25"] & topset["dense"] & topset["hybrid"])}

    # ---------------- authority priors over the hybrid top-100 pool
    hyb = rk["hybrid"]
    pool = hyb[:POOL]
    hrank = {u: i for i, (u, _) in enumerate(pool, 1)}
    ek, iso = entity_keys(claim_entities(row)), row.get("location_ISO_code")
    priors = {"B_generic": ("Generic credibility prior (claim-independent domain type)", generic_prior),
              "C_heuristic": ("Heuristic claim prior (generic + claim-entity / claim-country rules)",
                              lambda u: full_prior(u, ek, iso))}
    pred = None
    llm_note = None
    if mode == "query":
        llm_note = ("LLM prior not shown: the frozen predictions were made for the original claim text. "
                    "A prediction for a new query would need a new LLM call, which requires owner approval.")
    else:
        pred = load_frozen_predictions(split).get(cid)
        if pred:
            pk = set().union(*[set(a["keys"]) for a in primary_authority_candidates(pred)])
            priors["D_llm"] = ("LLM authority prior (frozen Claude Opus 5.5 top-3 publishers, binary)",
                               lambda u, pk=pk: float(cand_key(u) in pk))
        else:
            llm_note = "No frozen LLM prediction exists for this claim."
    pool_pubs = {}
    for u, _ in pool:
        pool_pubs[cand_key(u)] = pool_pubs.get(cand_key(u), 0) + 1

    authority = {}
    for sid, (label, fn) in priors.items():
        rr = rerank(hyb, fn)
        top = []
        for i, (u, s) in enumerate(rr[:k], 1):
            top.append({"rank": i, "url": u, "hybrid_rank": hrank[u], "moved": hrank[u] - i,
                        "prior": round(fn(u), 2), "publisher": cand_key(u) or "", "final_score": round(s, 3),
                        "gold": (u in gold) if show_gold else None,
                        "snippet": re.sub(r"\s+", " ", texts.get(u, "")[:160]).strip()})
        promoted = [x for x in top if x["hybrid_rank"] > k]
        deep = [x for x in top if x["hybrid_rank"] > 50]
        best = lambda ranking: next((i for i, (u, _) in enumerate(ranking[:POOL], 1) if u in gold), None)
        authority[sid] = {"label": label, "top": top,
                          "n_promoted_into_topk_from_below_k": len(promoted),
                          "n_promoted_from_below_rank_50": len(deep),
                          "promoted_from_below_rank_50_non_gold": (sum(not x["gold"] for x in deep) if show_gold else None),
                          "best_gold_rank_in_pool": best(rr) if show_gold else None}
    out = {
        "claim_id": cid, "split": split, "mode": mode, "query": q, "k": k,
        "claim": {f: row.get(f) for f in ("claim", "speaker_or_entity", "claim_date", "location_ISO_code",
                                           "reporting_source", "claim_types")},
        "n_candidates": len(texts), "timing": timing, "query_terms": terms, "top_k_overlap": overlap,
        "retrieval": retrieval,
        "gold_note": ("gold = AVeriTeC annotator evidence URL that is present and non-empty in this claim's "
                      "knowledge store. It is relevance/evidence information, NOT a claim-specific authority label."
                      if show_gold else "gold markers hidden (--no-gold)"),
        "n_gold_reachable": len(gold) if show_gold else None, "n_gold_web_total": len(gold_all) if show_gold else None,
        "best_gold_rank": ({m: next((i for i, (u, _) in enumerate(rk[m], 1) if u in gold), None) for m in rk}
                           if show_gold else None),
        "llm_prediction": ({"source": "frozen file (Sept 2026), not re-generated",
                            "fact_at_issue": pred.get("fact_at_issue"), "claim_kind": pred.get("claim_kind"),
                            "authority_situation": pred.get("authority_situation"),
                            "confidence": pred.get("confidence"),
                            "top3": [{"publisher": t.get("publisher"), "domain": t.get("domain"),
                                      "social_account": t.get("social_account"), "type": t.get("publisher_type"),
                                      "why": t.get("why")} for t in (pred.get("top3") or [])[:3]],
                            "keys_with_docs_in_pool": {kk: pool_pubs.get(kk, 0) for kk in
                                                       sorted(set().union(*[set(a["keys"]) for a in
                                                                            primary_authority_candidates(pred)]))}}
                           if pred else None),
        "llm_note": llm_note,
        "pool_publishers_top10": sorted(pool_pubs.items(), key=lambda x: -x[1])[:10],
        "authority": authority,
    }
    return out


# ------------------------------------------------------------------ rendering

def _g(x):
    return "" if x is None else ("GOLD" if x else "")


def render_text(o: dict) -> str:
    k = o["k"]
    L = []
    c = o["claim"]
    L.append(f"=== Claim {o['claim_id']} ({o['split']}, mode={o['mode']}) ===")
    L.append(f"Claim   : {c['claim']}")
    L.append(f"Speaker : {c['speaker_or_entity']} | date {c['claim_date']} | country {c['location_ISO_code']}")
    if o["mode"] == "query":
        L.append(f"Query   : {o['query']}")
    L.append(f"Candidates in this claim's knowledge store (non-empty, deduplicated): {o['n_candidates']}")
    L.append(f"Query terms used by BM25: {', '.join(o['query_terms'])}")
    if o["timing"]:
        L.append(f"Live timing: BM25 {o['timing']['bm25_s']}s, MiniLM {o['timing']['dense_s']}s")
    L.append("")
    names = {"bm25": "BM25", "dense": "MiniLM dense", "hybrid": "Hybrid RRF (k=60)"}
    for m in ("bm25", "dense", "hybrid"):
        L.append(f"--- {names[m]} top-{k} ---")
        L.append(f"{'#':>2}  {'BM25':>4} {'Dns':>4} {'Hyb':>4}  {'gold':4}  url  [matched query terms]")
        for x in o["retrieval"][m]:
            L.append(f"{x['rank']:>2}  {x['rank_bm25']:>4} {x['rank_dense']:>4} {x['rank_hybrid']:>4}  {_g(x['gold']):4}  "
                     f"{x['url'][:80]}  [{', '.join(x['matched_terms'][:8])}]")
        L.append("")
    ov = o["top_k_overlap"]
    L.append(f"Top-{k} overlap: BM25&Dense {ov['bm25&dense']}, BM25&Hybrid {ov['bm25&hybrid']}, "
             f"Dense&Hybrid {ov['dense&hybrid']}, all three {ov['all_three']}")
    if o["best_gold_rank"]:
        L.append(f"Best rank of a reachable gold document: " +
                 ", ".join(f"{m} {v if v else 'none'}" for m, v in o["best_gold_rank"].items()) +
                 f"   ({o['n_gold_reachable']} reachable of {o['n_gold_web_total']} web gold URLs)")
    L.append("")
    p = o["llm_prediction"]
    if p:
        L.append("--- Existing LLM authority prediction (frozen file; NOT re-generated) ---")
        L.append(f"fact_at_issue: {p['fact_at_issue']}")
        L.append(f"claim_kind: {p['claim_kind']} | authority_situation: {p['authority_situation']} | "
                 f"confidence: {p['confidence']}")
        for i, t in enumerate(p["top3"], 1):
            L.append(f"  {i}. {t['publisher']} | domain={t['domain']} | social={t['social_account']} | {t['type']}")
        L.append(f"Predicted publisher keys -> documents in hybrid top-100: {p['keys_with_docs_in_pool']}")
    if o["llm_note"]:
        L.append(f"NOTE: {o['llm_note']}")
    L.append("")
    for sid, a in o["authority"].items():
        L.append(f"--- {sid}: {a['label']} ---")
        L.append(f"{'#':>2} {'was':>4} {'moved':>6} {'prior':>5} {'gold':4}  publisher | url")
        for x in a["top"]:
            L.append(f"{x['rank']:>2} {x['hybrid_rank']:>4} {x['moved']:>+6} {x['prior']:>5} {_g(x['gold']):4}  "
                     f"{x['publisher'][:28]} | {x['url'][:70]}")
        extra = ""
        if a["promoted_from_below_rank_50_non_gold"] is not None:
            extra = f" ({a['promoted_from_below_rank_50_non_gold']} of them non-gold)"
        L.append(f"Promoted into top-{k} from below rank {k}: {a['n_promoted_into_topk_from_below_k']}; "
                 f"from below rank 50: {a['n_promoted_from_below_rank_50']}{extra}; "
                 f"best gold rank in pool: {a['best_gold_rank_in_pool']}")
        L.append("")
    L.append(o["gold_note"])
    return "\n".join(L)


def render_html(o: dict) -> str:
    e = lambda s: html.escape(str(s if s is not None else ""))
    names = {"bm25": "BM25 (lexical)", "dense": "MiniLM dense (semantic)", "hybrid": "Hybrid RRF k=60"}
    cols = []
    for m in ("bm25", "dense", "hybrid"):
        rows = "".join(
            f"<tr class='{'gold' if x['gold'] else ''}'><td>{x['rank']}</td>"
            f"<td title='{e(x['snippet'])}'>{e(x['url'][:70])}</td>"
            f"<td>{x['rank_bm25']}/{x['rank_dense']}/{x['rank_hybrid']}</td>"
            f"<td>{e(', '.join(x['matched_terms'][:6]))}</td></tr>" for x in o["retrieval"][m])
        cols.append(f"<div class='col'><h3>{names[m]}</h3><table><tr><th>#</th><th>document</th>"
                    f"<th>B/D/H rank</th><th>query terms</th></tr>{rows}</table></div>")
    auth = []
    for sid, a in o["authority"].items():
        rows = "".join(
            f"<tr class='{'gold' if x['gold'] else ''} {'boost' if x['prior'] >= 1 else ''}'><td>{x['rank']}</td>"
            f"<td>{x['hybrid_rank']}</td><td>{x['moved']:+d}</td><td>{x['prior']}</td>"
            f"<td>{e(x['publisher'])}</td><td title='{e(x['snippet'])}'>{e(x['url'][:70])}</td></tr>"
            for x in a["top"])
        auth.append(f"<div class='col'><h3>{e(sid)}</h3><p class='small'>{e(a['label'])}</p><table>"
                    f"<tr><th>#</th><th>was</th><th>moved</th><th>prior</th><th>publisher</th><th>document</th></tr>"
                    f"{rows}</table><p class='small'>Promoted from below rank 50: "
                    f"{a['n_promoted_from_below_rank_50']}"
                    f"{'' if a['promoted_from_below_rank_50_non_gold'] is None else ' (non-gold: ' + str(a['promoted_from_below_rank_50_non_gold']) + ')'}"
                    f" &middot; best gold rank: {e(a['best_gold_rank_in_pool'])}</p></div>")
    p = o["llm_prediction"]
    pred = ""
    if p:
        items = "".join(f"<li>{e(t['publisher'])} &mdash; <code>{e(t['domain'])}</code> "
                        f"<code>{e(t['social_account'])}</code> ({e(t['type'])})</li>" for t in p["top3"])
        pred = (f"<h2>Existing LLM authority prediction <span class='tag'>frozen file, not re-generated</span></h2>"
                f"<p><b>Fact at issue:</b> {e(p['fact_at_issue'])}<br><b>Kind:</b> {e(p['claim_kind'])} &middot; "
                f"<b>Situation:</b> {e(p['authority_situation'])} &middot; <b>Confidence:</b> {e(p['confidence'])}</p>"
                f"<ol>{items}</ol><p class='small'>Predicted keys &rarr; documents in hybrid top-100: "
                f"{e(p['keys_with_docs_in_pool'])}</p>")
    if o["llm_note"]:
        pred += f"<p class='note'>{e(o['llm_note'])}</p>"
    c = o["claim"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ESA demo claim {o['claim_id']}</title>
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#666;--gold:#fff3c4;--boost:#e3f0ff;--line:#ddd}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#e8e8e8;--mut:#a0a0a0;--gold:#4a3f10;--boost:#13304f;--line:#333}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 auto;padding:16px;max-width:1500px}}
.row{{display:flex;gap:12px;flex-wrap:wrap}} .col{{flex:1 1 420px;min-width:0;overflow-x:auto}}
table{{border-collapse:collapse;width:100%;font-size:12px}} td,th{{border-bottom:1px solid var(--line);padding:3px 5px;text-align:left;vertical-align:top}}
tr.gold td{{background:var(--gold)}} tr.boost td:first-child{{box-shadow:inset 4px 0 #3b82f6}}
.small{{color:var(--mut);font-size:12px}} .tag{{font-size:11px;border:1px solid var(--line);padding:1px 6px;border-radius:9px;color:var(--mut)}}
.note{{border-left:3px solid #d97706;padding-left:8px}}
</style></head><body>
<h1>Claim {o['claim_id']} <span class="tag">{e(o['split'])}</span> <span class="tag">mode: {e(o['mode'])}</span></h1>
<p><b>{e(c['claim'])}</b><br><span class="small">Speaker: {e(c['speaker_or_entity'])} &middot; {e(c['claim_date'])} &middot;
country {e(c['location_ISO_code'])} &middot; {o['n_candidates']} candidate documents</span></p>
{'<p><b>Query:</b> ' + e(o['query']) + '</p>' if o['mode'] == 'query' else ''}
<p class="small">Query terms (BM25): {e(', '.join(o['query_terms']))}. Top-{o['k']} overlap: {e(o['top_k_overlap'])}.
Best gold rank: {e(o['best_gold_rank'])}.</p>
<h2>1. Relevance retrieval</h2><div class="row">{''.join(cols)}</div>
{pred}
<h2>2. Authority priors re-ranking the hybrid top-100 (&lambda; = 1)</h2><div class="row">{''.join(auth)}</div>
<p class="small">Highlighted rows: AVeriTeC evidence documents ({e(o['gold_note'])}). Blue bar: document received the full prior (1.0).
B/D/H rank = rank under BM25 / Dense / Hybrid over all {o['n_candidates']} candidates.
Generated from genuine project files by experiments/esa_nov2026/demo.py; no LLM call was made.</p>
</body></html>"""


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claim-id", type=int)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--live", action="store_true", help="recompute BM25 + MiniLM + RRF instead of frozen rankings")
    ap.add_argument("--query", help="custom query text (implies live retrieval over the claim's knowledge store)")
    ap.add_argument("--no-gold", action="store_true", help="hide AVeriTeC gold markers")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list or a.claim_id is None:
        c = claims()
        print("Suggested demo claims (illustrative; chosen after inspecting frozen results):")
        for cid, why in SUGGESTED.items():
            print(f"  {cid:>4} [{c[cid]['split']}] {why}\n       {c[cid]['claim'][:150]}")
        print("Any of the 320 claim ids in data/processed/averitec_{sample,heldout}.jsonl works.")
        return
    o = run(a.claim_id, a.k, a.live, a.query, not a.no_gold)
    txt = render_text(o)
    print(txt)
    stem = f"claim_{a.claim_id}" + {"frozen": "", "live": "_live", "query": "_query"}[o["mode"]]
    d = out_dir("demo")
    json.dump(o, open(d / f"{stem}.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    (d / f"{stem}.md").write_text("```text\n" + txt + "\n```\n", encoding="utf-8")
    (d / f"{stem}.html").write_text(render_html(o), encoding="utf-8")
    print(f"\n-> {d / (stem + '.html')}  (also .json, .md)")


if __name__ == "__main__":
    main()
