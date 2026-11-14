"""Step 9 (independent verification, added in a second session): re-derive the
headline numbers without evaluate_retrieval.py, and probe two residual risks.

  1. Independent recomputation of hit@K / primary_hit@K (reachable denominators)
     directly from results/rankings_*.jsonl.gz, the raw KS files and
     data/annotations/source_roles.csv.
  2. Prior-list contamination: the hand-written INTERGOV / ACADEMIC / MAJOR_NEWS /
     REFERENCE lists were written by an agent that had seen this sample. Measure
     their overlap with the sample's gold domains and re-score the generic / full
     priors with every overlapping domain removed (structural rules such as
     .gov / .edu / .int / .ac. are kept: they need no list).
  3. Artifact rankers: rank candidates by text length or URL shape only. If these
     beat random by a lot, gold documents are distinguishable by form, not content.

Writes results/verification.json.
"""
import csv
import gzip
import json
import random
from statistics import median

import authority_retrieval as ar
from baseline_retrieval import load_rankings, retrieval_corpus
from common import ANNOTATIONS, RESULTS, load_ks, load_sample, normalize_url, registered_domain

KS = (5, 10, 20)


def truth(sample):
    roles = {}
    with open(ANNOTATIONS / "source_roles.csv", encoding="utf-8") as fh:
        for x in csv.DictReader(fh):
            roles[(int(x["claim_id"]), normalize_url(x["evidence_url"]))] = x["source_role"]
    out = {}
    for r in sample:
        cid = int(r["claim_id"])
        nonempty = {normalize_url(d["url"]) for d in load_ks(cid) if d["text"].strip()}
        gold = {g["source_url_norm"] for g in r["gold_evidence"] if g["is_web_source"]}
        prim = {u for u in gold if roles.get((cid, u)) == "A_primary"}
        out[cid] = {"gold": gold & nonempty, "prim": prim & nonempty, "gold_all": gold, "prim_all": prim}
    return out


def score(rankings, T):
    res = {}
    for key, name in (("gold", "R"), ("prim", "PrimR")):
        cl = [c for c in T if T[c][key]]
        for k in KS:
            hits = [bool(T[c][key] & {u for u, _ in rankings[c][:k]}) for c in cl]
            res[f"{name}@{k}"] = round(sum(hits) / len(cl), 3)
        res[f"n_{key}"] = len(cl)
    return res


def main():
    sample = load_sample()
    T = truth(sample)
    out = {}

    # 1. independent recomputation
    heads = ["bm25", "dense", "hybrid", "bm25+generic_l0.25", "bm25+full_l0.25", "dense+generic_l0.25",
             "dense+full_l0.25", "hybrid+full_l0.25", "bm25+full_l1.0_poolall", "bm25+oracle_l1.0_poolall"]
    out["recomputed"] = {m: score({int(c): v for c, v in load_rankings(m).items()}, T) for m in heads}

    # 2. list contamination
    gold_doms = {registered_domain(u) for t in T.values() for u in t["gold_all"]}
    prim_doms = {registered_domain(u) for t in T.values() for u in t["prim_all"]}
    lists = {"INTERGOV": ar.INTERGOV, "ACADEMIC_HOSTS": ar.ACADEMIC_HOSTS, "MAJOR_NEWS": ar.MAJOR_NEWS,
             "REFERENCE": ar.REFERENCE, "PLATFORMS": ar.PLATFORMS}
    out["list_overlap"] = {n: {"size": len(s), "in_sample_gold": sorted(s & gold_doms),
                               "in_sample_primary": sorted(s & prim_doms)} for n, s in lists.items()}
    for n in ("INTERGOV", "ACADEMIC_HOSTS", "MAJOR_NEWS", "REFERENCE"):
        setattr(ar, n, getattr(ar, n) - gold_doms)  # decontaminate in place (generic_prior reads module globals)
    info = {int(r["claim_id"]): (ar.entity_keys(ar.claim_entities(r)), r.get("location_ISO_code")) for r in sample}
    decon = {}
    for base in ("bm25", "dense", "hybrid"):
        rk = {int(c): v for c, v in load_rankings(base).items()}
        for lam, pool, tag in ((0.25, 100, "l0.25"), (1.0, None, "l1.0_poolall")):
            decon[f"{base}+generic_{tag}"] = score({c: ar.rerank(v, ar.generic_prior, lam, pool) for c, v in rk.items()}, T)
            decon[f"{base}+full_{tag}"] = score(
                {c: ar.rerank(v, lambda u, k=info[c][0], i=info[c][1]: ar.full_prior(u, k, i), lam, pool)
                 for c, v in rk.items()}, T)
    out["decontaminated_priors"] = decon

    # 3. artifact rankers over the exact retrieval corpus
    arts = {"longest_text": {}, "shortest_text": {}, "shortest_url": {}, "random": {}}
    glen, olen = [], []
    for r in sample:
        cid = int(r["claim_id"])
        docs = retrieval_corpus(cid)
        for d in docs:
            (glen if d["url_norm"] in T[cid]["gold"] else olen).append(len(d["text"]))
        arts["longest_text"][cid] = [(d["url_norm"], 0) for d in sorted(docs, key=lambda d: -len(d["text"]))]
        arts["shortest_text"][cid] = [(d["url_norm"], 0) for d in sorted(docs, key=lambda d: len(d["text"]))]
        arts["shortest_url"][cid] = [(d["url_norm"], 0) for d in sorted(docs, key=lambda d: len(d["url_norm"]))]
        sh = docs[:]; random.Random(cid).shuffle(sh)
        arts["random"][cid] = [(d["url_norm"], 0) for d in sh]
    out["artifact_rankers"] = {n: score(v, T) for n, v in arts.items()}
    out["text_len_median"] = {"gold": median(glen), "non_gold": median(olen)}
    json.dump(out, open(RESULTS / "verification.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
