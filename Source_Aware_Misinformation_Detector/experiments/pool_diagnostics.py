"""Sanity checks for the retrieval numbers: rank of gold docs in the FULL ranking,
coverage of the top-100 rerank pool (ceiling for every reranker), and the
expected Hit@K of a random ranking over the same candidates."""
import json
import statistics
import sys

from baseline_retrieval import load_rankings, retrieval_corpus
from common import RESULTS, load_sample
from evaluate_retrieval import claim_context, load_roles


def main():
    sample, roles = load_sample(), load_roles()
    ctx, _ = claim_context(sample, roles)
    out = {}
    for base in sys.argv[1:] or ["bm25"]:
        rk = load_rankings(base)
        g_ranks, p_ranks, rand = [], [], {5: [], 10: [], 20: []}
        pool_g = pool_p = n_g = n_p = 0
        for r in sample:
            cid, c = r["claim_id"], ctx[r["claim_id"]]
            order = {u: i for i, (u, _) in enumerate(rk[cid], 1)}
            n = len(order)
            if c["gold_reach"]:
                n_g += 1
                best = min(order[u] for u in c["gold_reach"])
                g_ranks.append(best)
                pool_g += best <= 100
                m = len(c["gold_reach"])
                for k in rand:  # P(>=1 of m gold in a random top-k of n)
                    p_none = 1.0
                    for i in range(k):
                        p_none *= (n - m - i) / (n - i)
                    rand[k].append(1 - p_none)
            if c["primary_reach"]:
                n_p += 1
                best = min(order[u] for u in c["primary_reach"])
                p_ranks.append(best)
                pool_p += best <= 100
        q = lambda xs: {"median": statistics.median(xs), "p25": sorted(xs)[len(xs) // 4], "p75": sorted(xs)[3 * len(xs) // 4]}
        out[base] = {
            "claims_reachable_gold": n_g, "best_gold_rank": q(g_ranks),
            "gold_in_top100_pool": f"{pool_g}/{n_g}",
            "claims_reachable_primary": n_p, "best_primary_rank": q(p_ranks),
            "primary_in_top100_pool": f"{pool_p}/{n_p}",
            "random_ranking_expected_R@K": {k: round(sum(v) / len(v), 4) for k, v in rand.items()},
            "mean_candidates_per_claim": round(statistics.mean(len(rk[r["claim_id"]]) for r in sample), 1),
        }
    print(json.dumps(out, indent=1))
    json.dump(out, open(RESULTS / "pool_diagnostics.json", "w"), indent=1)


if __name__ == "__main__":
    main()
