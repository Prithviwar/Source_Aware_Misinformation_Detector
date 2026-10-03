"""Step 7b: export rank-1 documents for a BLIND pilot role annotation (Metric 3).

Only 3.4% of top-5 documents carry a role label (the pilot annotation covers gold
URLs only), so the derived/secondary rate cannot be measured from it. For the
claims with a reachable pilot-primary gold document we pool the rank-1 document
of each method below, deduplicate, and sort by (claim_id, url) so the annotator
does not see which method retrieved which item. Gold status is not shown either.

Writes data/annotations/top1_blind_items.csv (items to label) and
results/top1_method_map.json (item -> methods; used only AFTER annotation).
"""
import csv
import json

from baseline_retrieval import load_rankings, retrieval_corpus
from common import ANNOTATIONS, RESULTS, load_sample, registered_domain
from evaluate_retrieval import claim_context, load_roles

METHODS = ["bm25", "dense", "hybrid", "bm25+generic_l0.25", "bm25+full_l0.25", "bm25+wikidata_l0.25",
           "bm25+full_l1.0_poolall"]


def main():
    sample, roles = load_sample(), load_roles()
    ctx, _ = claim_context(sample, roles)
    rk = {m: load_rankings(m) for m in METHODS}
    items, where = {}, {}
    for r in sample:
        cid = r["claim_id"]
        if not ctx[cid]["primary_reach"]:
            continue
        text = {d["url_norm"]: d["text"] for d in retrieval_corpus(cid)}
        for m in METHODS:
            u = rk[m][cid][0][0]
            key = f"{cid}|{u}"
            where.setdefault(key, []).append(m)
            items[key] = {"claim_id": cid, "claim": r["claim"], "speaker": r.get("speaker_or_entity") or "",
                          "iso": r.get("location_ISO_code") or "", "url": u, "domain": registered_domain(u),
                          "text_head": " ".join(text[u][:400].split())}
    rows = sorted(items.values(), key=lambda x: (x["claim_id"], x["url"]))
    for i, x in enumerate(rows, 1):
        x["item_id"] = i
    with open(ANNOTATIONS / "top1_blind_items.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["item_id", "claim_id", "claim", "speaker", "iso", "url", "domain", "text_head"])
        w.writeheader()
        w.writerows(rows)
    json.dump(where, open(RESULTS / "top1_method_map.json", "w", encoding="utf-8"), indent=1)
    print(f"{len(rows)} unique rank-1 items from {len(METHODS)} methods over "
          f"{sum(bool(ctx[c]['primary_reach']) for c in ctx)} claims")


if __name__ == "__main__":
    main()
