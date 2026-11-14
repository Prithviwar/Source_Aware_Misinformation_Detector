"""Pre-run check (offline, no model): the PU unlabelled sample is deterministic, reproducible and claim-specific.

  python experiments/esa_nov2026/relevance_baseline/verify_unlabelled_sampling.py [--out FILE]

For every FIT claim it rebuilds the corpus (the same build_corpus used in training), samples twice in-process and
checks the following:
  * the same result both times (determinism);
  * no sampled URL is labelled;
  * every sampled URL belongs to the claim's own corpus;
  * the sample size is min(N, |U|).
It also recomputes one claim's draw with a different train_idx to show that the seed is claim-specific.
It writes the per-claim sample hashes and one overall hash. Running it in two separate processes and comparing
the overall hash checks cross-process reproducibility.
"""
import argparse
import hashlib
import json

from rb_common import (N_UNLABELLED_PER_CLAIM, OUT, SAMPLING_POLICY, SEED_UNLABELLED, SPLIT_MANIFEST, TRAIN_JSON,
                       TRAIN_KS_DIR, sample_unlabelled)
from features import build_corpus


def main():
    from build_sample import normalise
    from common import read_jsonl
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT / "unlabelled_sampling_check.json"))
    a = ap.parse_args()
    man = json.load(open(SPLIT_MANIFEST, encoding="utf-8"))
    train = json.load(open(TRAIN_JSON, encoding="utf-8"))
    per, problems = {}, []
    for cid in sorted(man["split"]["fit"]):
        ev = {g["source_url_norm"] for g in normalise(cid, train[cid])["gold_evidence"] if g["is_web_source"]}
        urls = [d["url_norm"] for d in build_corpus(read_jsonl(TRAIN_KS_DIR / f"{cid}.jsonl.gz"), cid)]
        lab = ev & set(urls)
        s1, s2 = sample_unlabelled(cid, urls, lab), sample_unlabelled(cid, urls, lab)
        if s1 != s2:
            problems.append(f"{cid}: non-deterministic")
        if set(s1) & lab:
            problems.append(f"{cid}: labelled URL in unlabelled sample")
        if not set(s1) <= set(urls):
            problems.append(f"{cid}: sampled URL outside claim corpus")
        if len(s1) != min(N_UNLABELLED_PER_CLAIM, len(set(urls) - lab)):
            problems.append(f"{cid}: wrong sample size")
        per[cid] = {"n_docs": len(urls), "n_labelled": len(lab), "n_sampled": len(s1),
                    "sha256": hashlib.sha256("\n".join(s1).encode()).hexdigest()}
        if cid == sorted(man["split"]["fit"])[0]:
            other = sample_unlabelled(cid + 1, urls, lab)
            claim_specific_demo = {"train_idx": cid, "same_corpus_other_idx_differs": other != s1}
    overall = hashlib.sha256("\n".join(f"{c} {v['sha256']}" for c, v in per.items()).encode()).hexdigest()
    rep = {"status": "OK" if not problems else "PROBLEMS", "problems": problems, "policy": SAMPLING_POLICY,
           "seed": SEED_UNLABELLED, "n_per_claim": N_UNLABELLED_PER_CLAIM, "n_fit_claims": len(per),
           "total_sampled": sum(v["n_sampled"] for v in per.values()),
           "claims_with_fewer_than_n_available": sum(v["n_sampled"] < N_UNLABELLED_PER_CLAIM for v in per.values()),
           "claim_specific_demo": claim_specific_demo, "overall_sha256": overall, "per_claim": per}
    json.dump(rep, open(a.out, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "per_claim"}, indent=1))


if __name__ == "__main__":
    main()
