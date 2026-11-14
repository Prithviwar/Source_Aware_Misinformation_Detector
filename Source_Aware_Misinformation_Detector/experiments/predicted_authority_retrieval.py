"""Step 10b: plug the LLM-PREDICTED authorities (authority_resolution.py, condition
L+Wctx, top-3 publisher keys) into the existing reranker as a claim-specific prior:

  prior(url) = 1 if the candidate's publisher key (org domain, or platform/handle
               for social URLs) is one of the claim's predicted top-3 keys, else 0

This is what the oracle prior did with the pilot-primary domains, but with keys
predicted from the claim alone (no gold input), so it measures how much of the
oracle headroom a real resolver recovers.

Evaluated on the 48 claims with a reachable pilot-primary document (all have
predictions). Same rerank(), lambdas and pools as authority_retrieval.py; exact
McNemar vs. the relevance-only base. Writes results/predicted_authority_retrieval.json.
"""
import json
from math import comb

from authority_resolution import RAW, pred_keys, org_domain, social_key
from authority_retrieval import generic_prior, oracle_primary_domains, rerank
from baseline_retrieval import load_rankings
from common import load_sample
from verify_results import truth

KS = (5, 10, 20)


def cand_key(url):
    return social_key(url) or org_domain(url)


def mcnemar(a, b):
    w = sum(y and not x for x, y in zip(a, b))
    l = sum(x and not y for x, y in zip(a, b))
    n = w + l
    return w, l, (1.0 if n == 0 else round(min(1, 2 * sum(comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n), 4))


def gold_all_claims(preds, T):
    """Circularity-free check: human AVeriTeC gold R@K over every claim with a reachable gold
    doc (pilot role labels are not read). Needs predictions for all claims (--all-claims)."""
    claims = [c for c in T if T[c]["gold"]]
    missing = [c for c in claims if c not in preds]
    if missing:
        return {"status": f"skipped: {len(missing)} claims lack predictions (run authority_resolution.py --all-claims)"}
    out = {"n_claims": len(claims), "conditions": {}}
    for base in ("bm25", "dense", "hybrid"):
        rk = {int(c): v for c, v in load_rankings(base).items()}
        ghit = lambda R, c, k: bool(T[c]["gold"] & {u for u, _ in R[c][:k]})
        base_g = {k: [ghit(rk, c, k) for c in claims] for k in KS}
        out["conditions"][base] = {f"R@{k}": round(sum(base_g[k]) / len(claims), 3) for k in KS}
        for lam, pool, tag in ((0.25, 100, "l0.25"), (1.0, 100, "l1.0"), (1.0, None, "l1.0_poolall")):
            gen = {c: rerank(rk[c], generic_prior, lam, pool) for c in claims}
            gen_g = {k: [ghit(gen, c, k) for c in claims] for k in KS}
            pred = {c: rerank(rk[c], lambda u, c=c: float(cand_key(u) in preds[c]), lam, pool) for c in claims}
            for name, R, ref in (("generic", gen, None), ("predicted", pred, gen_g)):
                res = {}
                for k in KS:
                    g = [ghit(R, c, k) for c in claims]
                    w, l, p = mcnemar(base_g[k], g)
                    res[f"R@{k}"] = round(sum(g) / len(claims), 3)
                    res[f"R@{k}_vs_base"] = f"+{w}/-{l} p={p}"
                    if ref:
                        w, l, p = mcnemar(ref[k], g)
                        res[f"R@{k}_vs_generic"] = f"+{w}/-{l} p={p}"
                out["conditions"][f"{base}+{name}_{tag}"] = res
    return out


def main():
    preds = {}
    for line in open(RAW, encoding="utf-8"):
        x = json.loads(line)
        if x["cond"] == "L+Wctx" and x.get("pred"):
            preds[x["claim_id"]] = set().union(*[pred_keys(t) for t in (x["pred"].get("top3") or [])[:3]])
    T = truth(load_sample())
    claims = [c for c in T if T[c]["prim"]]
    assert all(c in preds for c in claims), "missing predictions"
    oracle = oracle_primary_domains()
    out = {"n_claims": len(claims), "conditions": {}}
    for base in ("bm25", "dense", "hybrid"):
        rk = {int(c): v for c, v in load_rankings(base).items()}
        hit = lambda R, c, k: bool(T[c]["prim"] & {u for u, _ in R[c][:k]})
        ghit = lambda R, c, k: bool(T[c]["gold"] & {u for u, _ in R[c][:k]})
        base_h = {k: [hit(rk, c, k) for c in claims] for k in KS}
        base_g = {k: [ghit(rk, c, k) for c in claims] for k in KS}
        out["conditions"][base] = {**{f"PrimR@{k}": round(sum(base_h[k]) / len(claims), 3) for k in KS},
                                   **{f"R@{k}(these claims)": round(sum(base_g[k]) / len(claims), 3) for k in KS}}
        for lam, pool, tag in ((0.25, 100, "l0.25"), (1.0, 100, "l1.0"), (1.0, None, "l1.0_poolall")):
            variants = {
                "predicted": lambda u, c: float(cand_key(u) in preds[c]),
                "generic": lambda u, c: generic_prior(u),
                "predicted+generic": lambda u, c: max(float(cand_key(u) in preds[c]), 0.5 * generic_prior(u)),
                "oracle(leaks)": lambda u, c: float(org_domain(u) in {org_domain(d) for d in oracle.get(c, set())}),
            }
            for name, f in variants.items():
                R = {c: rerank(rk[c], lambda u, c=c: f(u, c), lam, pool) for c in claims}
                res = {}
                for k in KS:
                    h = [hit(R, c, k) for c in claims]
                    g = [ghit(R, c, k) for c in claims]
                    w, l, p = mcnemar(base_h[k], h)
                    res[f"PrimR@{k}"] = round(sum(h) / len(claims), 3)
                    res[f"PrimR@{k}_vs_base"] = f"+{w}/-{l} p={p}"
                    res[f"R@{k}(these claims)"] = round(sum(g) / len(claims), 3)
                out["conditions"][f"{base}+{name}_{tag}"] = res
    out["gold_recall_all_claims"] = gold_all_claims(preds, T)
    json.dump(out, open("../results/predicted_authority_retrieval.json", "w"), indent=1)
    for m, v in out["gold_recall_all_claims"]["conditions"].items():
        print(f"[gold, n={out['gold_recall_all_claims']['n_claims']}] {m:32s}",
              "  ".join(f"{k}={v[k]}" for k in v if k.startswith("R@")))
    for m, v in out["conditions"].items():
        print(f"{m:40s}", "  ".join(f"{k}={v[k]}" for k in v if k.startswith("PrimR") or k.startswith("R@10")))


if __name__ == "__main__":
    main()
