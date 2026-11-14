"""Step 7: manually inspectable error analysis.

Selection rules (deterministic, stated up front):
  bm25_finds_primary    : BM25 has a pilot-primary gold doc in its top 10 (else: any gold in top 10)
  bm25_secondary_instead: claim has a reachable primary gold doc, BM25 has none in its top 10;
                          sorted so that claims whose BM25 top-1 is an annotated secondary/derived
                          gold doc, or a same-publisher page of one, come first
  authority_improves    : largest increase in primary reciprocal rank (then gold RR), AUTH vs BM25
  authority_hurts       : largest decrease in gold RR (then primary RR), AUTH vs BM25
AUTH = bm25+full_l0.25 (pre-specified headline claim-conditioned variant); the
entity-only and Wikidata variants are shown alongside.

Writes results/error_analysis.csv (5 claims per group).
"""
import csv
import json

from authority_retrieval import (claim_entities, claim_prior, entity_keys, entity_match, full_prior,
                                 generic_prior)
from baseline_retrieval import load_rankings
from common import RESULTS, load_sample
from evaluate_retrieval import claim_context, doc_role, load_roles

AUTH = "bm25+full_l0.25"
SHOW = {"bm25": "bm25", "dense": "dense", "generic": "bm25+generic_l0.25", "auth_full": AUTH,
        "auth_entity": "bm25+entity_l0.25", "wikidata": "bm25+wikidata_l0.25"}
N = 5


def rr(ranked, target):
    return next((1 / i for i, u in enumerate(ranked, 1) if u in target), 0.0)


def first_rank(ranked, target):
    return next((i for i, u in enumerate(ranked, 1) if u in target), None)


def main():
    sample, roles = {r["claim_id"]: r for r in load_sample()}, load_roles()
    ctx, _ = claim_context(list(sample.values()), roles)
    rk = {k: {c: [u for u, _ in v] for c, v in load_rankings(m).items()} for k, m in SHOW.items()}
    wd = json.load(open(RESULTS / "wikidata_claim_authorities.json", encoding="utf-8"))

    def why(cid, u):
        r = sample[cid]
        keys = entity_keys(claim_entities(r))
        return (f"generic={generic_prior(u):.1f} entity_match={int(entity_match(u, keys))} "
                f"claim_prior={claim_prior(u, keys, r.get('location_ISO_code')):.0f} "
                f"full={full_prior(u, keys, r.get('location_ISO_code')):.1f}")

    reach_p = [c for c in ctx if ctx[c]["primary_reach"]]
    reach_g = [c for c in ctx if ctx[c]["gold_reach"]]
    groups = {}
    hit_p = [c for c in reach_p if first_rank(rk["bm25"][c], ctx[c]["primary"]) and first_rank(rk["bm25"][c], ctx[c]["primary"]) <= 10]
    hit_g = [c for c in reach_g if c not in hit_p and (first_rank(rk["bm25"][c], ctx[c]["gold"]) or 999) <= 10]
    groups["bm25_finds_primary_or_gold"] = (sorted(hit_p, key=lambda c: first_rank(rk["bm25"][c], ctx[c]["primary"]))
                                            + sorted(hit_g, key=lambda c: first_rank(rk["bm25"][c], ctx[c]["gold"])))[:N]
    miss = [c for c in reach_p if c not in hit_p]
    pri = lambda c: 0 if doc_role(rk["bm25"][c][0], ctx[c]) != "unannotated" else 1
    groups["bm25_secondary_instead"] = sorted(miss, key=lambda c: (pri(c), c))[:N]
    delta = {c: (rr(rk["auth_full"][c], ctx[c]["primary"]) - rr(rk["bm25"][c], ctx[c]["primary"]),
                 rr(rk["auth_full"][c], ctx[c]["gold"]) - rr(rk["bm25"][c], ctx[c]["gold"])) for c in reach_g}
    groups["authority_improves"] = [c for c in sorted(delta, key=lambda c: (-delta[c][0], -delta[c][1])) if delta[c][0] > 0 or delta[c][1] > 0][:N]
    groups["authority_hurts"] = [c for c in sorted(delta, key=lambda c: (delta[c][1], delta[c][0])) if delta[c][1] < 0 or delta[c][0] < 0][:N]

    rows = []
    for g, cids in groups.items():
        for c in cids:
            r, x = sample[c], ctx[c]
            row = {"group": g, "claim_id": c, "gold_label": r["gold_label"], "claim": r["claim"],
                   "speaker": r.get("speaker_or_entity"), "iso": r.get("location_ISO_code"),
                   "gold_evidence(role)": " | ".join(f"{u} ({x['role_of'][u]}{'' if u in x['gold_reach'] else ', EMPTY/unreachable'})" for u in sorted(x["gold"])),
                   "wikidata_official_domains": " ".join(wd[str(c)]["domains"] + wd[str(c)]["handles"])}
            for k in SHOW:
                top = rk[k][c][0]
                row[f"{k}_top1"] = top
                row[f"{k}_top1_role"] = doc_role(top, x)
                row[f"{k}_first_gold_rank"] = first_rank(rk[k][c], x["gold"])
                row[f"{k}_first_primary_rank"] = first_rank(rk[k][c], x["primary"])
            row["auth_top1_prior_breakdown"] = why(c, row["auth_full_top1"])
            row["auth_first_primary_prior_breakdown"] = (why(c, next(iter(sorted(x["primary_reach"])))) if x["primary_reach"] else "")
            rows.append(row)
    with open(RESULTS / "error_analysis.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for row in rows:
        print(f"\n=== {row['group']} | claim {row['claim_id']} ({row['gold_label']}) speaker={row['speaker']} iso={row['iso']}")
        print("  CLAIM:", row["claim"][:220])
        print("  GOLD:", row["gold_evidence(role)"][:500])
        print("  WIKIDATA:", row["wikidata_official_domains"][:200])
        for k in SHOW:
            print(f"  {k:12s} top1={row[k + '_top1'][:95]} [{row[k + '_top1_role']}] gold@{row[k + '_first_gold_rank']} prim@{row[k + '_first_primary_rank']}")
        print("  auth top1 prior:", row["auth_top1_prior_breakdown"], "| primary-doc prior:", row["auth_first_primary_prior_breakdown"])


if __name__ == "__main__":
    main()
