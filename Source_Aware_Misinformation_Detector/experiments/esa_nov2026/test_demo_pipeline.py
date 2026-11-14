"""Tests for the Monday demo pipeline (offline; no LLM; no network with HF_HUB_OFFLINE=1).

  python experiments/esa_nov2026/test_demo_pipeline.py          # fast tests (~2-3 min, mostly imports)
  python experiments/esa_nov2026/test_demo_pipeline.py --live   # + live BM25/MiniLM/RRF == frozen order (~3 min more)

Writes results/esa_nov2026/demo/test_report.json.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_pipeline as P  # noqa: E402
from esa_common import out_dir  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        def wrapped():
            t0 = time.time()
            try:
                detail = fn()
                RESULTS.append({"test": name, "status": "PASS", "detail": detail, "s": round(time.time() - t0, 1)})
                print(f"PASS  {name}  {detail or ''}")
            except Exception as e:  # noqa: BLE001
                RESULTS.append({"test": name, "status": "FAIL", "detail": repr(e), "s": round(time.time() - t0, 1),
                                "trace": traceback.format_exc()})
                print(f"FAIL  {name}  {e!r}")
        return wrapped
    return deco


@check("allowed claim set is exactly 120 dev + 200 held-out")
def t_claims():
    ch = P.claim_choices()
    n = {"dev120": 0, "heldout200": 0}
    for c in ch:
        n[c["split"]] += 1
    assert n == {"dev120": 120, "heldout200": 200}, n
    return n


@check("reserved / unknown claim ids are refused before any file is opened")
def t_refuse():
    allowed = {c["claim_id"] for c in P.claim_choices()}
    bad = next(i for i in range(500) if i not in allowed)  # some AVeriTeC dev id outside the 320 (reserved)
    try:
        P.run(bad)
    except PermissionError:
        return f"claim {bad} refused"
    raise AssertionError("reserved claim was not refused")


@check("rerank_components gives the same order as the frozen authority_retrieval.rerank (B, C, D; 5 claims)")
def t_rerank_equivalence():
    from authority_retrieval import claim_entities, entity_keys, full_prior, generic_prior, rerank
    from esa_common import assert_allowed
    from source_targeted import cand_key, primary_authority_candidates
    n = 0
    for cid in (268, 436, 2, 89, 328):
        row = assert_allowed(cid)
        hyb = P.frozen_rankings(row["split"])["hybrid"][cid]
        ek, iso = entity_keys(claim_entities(row)), row.get("location_ISO_code")
        pred = P.frozen_predictions(row["split"])[cid]
        pk = set().union(*[set(a["keys"]) for a in primary_authority_candidates(pred)])
        for fn in (generic_prior, lambda u: full_prior(u, ek, iso), lambda u: float(cand_key(u) in pk)):
            a = [u for u, _ in rerank(hyb, fn, 1.0, 100)]
            b = [r["url"] for r in P.rerank_components(hyb, fn)]
            assert a == b, f"order differs for claim {cid}"
            n += 1
    return f"{n}/15 rankings identical"


@check("claim 268 (frozen): documented ranks reproduced (evidence hybrid 28 -> D 1; B lifts senate.gov to 2)")
def t_268():
    o = P.run(268)
    assert o["best_evidence_rank"]["hybrid"] == 28, o["best_evidence_rank"]
    assert o["authority"]["D"]["best_evidence_rank_in_pool"] == 1
    assert o["authority"]["D"]["top"][0]["url"].startswith("trumpwhitehouse.archives.gov/presidential-actions")
    assert o["authority"]["B"]["top"][1]["publisher"] == "senate.gov"
    assert o["llm_prediction"]["top3"][0]["domain"] == "federalregister.gov"
    for m in ("bm25", "dense", "hybrid"):
        assert len(o["retrieval"][m]["top"]) == 10 and all(x["url"] for x in o["retrieval"][m]["top"])
    return {"best_evidence_rank": o["best_evidence_rank"], "D_best": 1}


@check("evidence markers never influence rankings (show_gold on/off give identical outputs)")
def t_gold_independent():
    a, b = P.run(436, show_gold=True), P.run(436, show_gold=False)
    for m in ("bm25", "dense", "hybrid"):
        assert [x["url"] for x in a["retrieval"][m]["top"]] == [x["url"] for x in b["retrieval"][m]["top"]]
    for s in a["authority"]:
        assert [x["url"] for x in a["authority"][s]["top"]] == [x["url"] for x in b["authority"][s]["top"]]
    assert all(x["evidence_marker"] is None for x in b["retrieval"]["hybrid"]["top"])
    return "identical"


@check("claim with no predicted authority in pool (claim 2): D equals hybrid order")
def t_2():
    o = P.run(2)
    assert all(v == 0 for v in o["llm_prediction"]["keys_docs_in_pool"].values())
    assert [x["url"] for x in o["authority"]["D"]["top"]] == [x["url"] for x in o["retrieval"]["hybrid"]["top"]]
    return "D == hybrid"


@check("custom-query mode turns the LLM prior OFF and says why")
def t_query_mode():
    from demo_pipeline import live_rankings  # noqa: F401
    import demo_pipeline as M
    # do not spend 2 min on MiniLM here: stub only the live retrieval with the frozen lists
    orig = M.live_rankings
    M.live_rankings = lambda cid, q, use_cache=True, progress=None: (
        {m: v[cid] for m, v in M.frozen_rankings("heldout200").items()}, {"stub": True})
    try:
        o = M.run(268, mode="query", query="Trump executive order pre-existing conditions")
    finally:
        M.live_rankings = orig
    assert "D" not in o["authority"] and o["llm_prediction"] is None and "never makes" in o["llm_note"]
    assert o["final_system"] == "C"
    return "D absent, C used as final ranking"


@check("empty custom query is rejected with a readable message")
def t_empty_query():
    try:
        P.run(268, mode="query", query="   ")
    except ValueError as e:
        return str(e)
    raise AssertionError("empty query accepted")


@check("every suggested demo claim runs in frozen mode")
def t_suggested():
    out = {}
    for cid in P.SUGGESTED:
        o = P.run(cid)
        out[cid] = (o["best_evidence_rank"] or {}).get("hybrid"), o["authority"].get("D", {}).get("best_evidence_rank_in_pool")
    return {str(k): f"hybrid {v[0]} -> D {v[1]}" for k, v in out.items()}


def t_live():
    @check("LIVE: BM25 / MiniLM / RRF recomputed now give the frozen top-100 order (claim 268)")
    def inner():
        rk, meta = P.live_rankings(268, P.assert_allowed(268)["claim"].strip(), use_cache=False)
        fr = {m: v[268] for m, v in P.frozen_rankings("heldout200").items()}
        res = {m: [u for u, _ in rk[m][:100]] == [u for u, _ in fr[m][:100]] for m in fr}
        assert all(res.values()), res
        return {"identical_top100": res, "timing_s": meta["timing_s"]}
    inner()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for t in (t_claims, t_refuse, t_rerank_equivalence, t_268, t_gold_independent, t_2, t_query_mode,
              t_empty_query, t_suggested):
        t()
    if "--live" in sys.argv:
        t_live()
    ok = all(r["status"] == "PASS" for r in RESULTS)
    rep = {"run_at": datetime.now().isoformat(timespec="seconds"), "all_pass": ok,
           "n_pass": sum(r["status"] == "PASS" for r in RESULTS), "n": len(RESULTS), "results": RESULTS}
    p = out_dir("demo") / "test_report.json"
    json.dump(rep, open(p, "w", encoding="utf-8"), indent=1, default=str)
    print(f"\n{rep['n_pass']}/{rep['n']} passed -> {p}")
    sys.exit(0 if ok else 1)
