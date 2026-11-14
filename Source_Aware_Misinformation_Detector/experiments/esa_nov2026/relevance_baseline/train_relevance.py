"""Step R3: Positive-Unlabelled (PU) RELEVANCE ranking baseline (claim-document evidence relevance; NOT authority).

  python experiments/esa_nov2026/relevance_baseline/train_relevance.py --synthetic   # code smoke test (fake data)
  python experiments/esa_nov2026/relevance_baseline/train_relevance.py               # real run (needs R1 + R2)

Labels (PU, see rb_common): s = 1 for documents whose normalised URL is an AVeriTeC evidence URL of the claim
and whose text is non-empty (WEAK POSITIVE). Every other document is UNLABELLED. No document is ever treated as
a confirmed negative.

Protocol:
  * claims: the frozen R1 split of AVeriTeC TRAIN claims (fit 179 / validation 60 / test 61, claim-disjoint);
  * fit pairs: per fit claim, all labelled documents (s=1) + a uniform sample of unlabelled documents (s=0)
    drawn from the claim's whole document collection (rb_common.SAMPLING_POLICY; no top-100 hard negatives);
  * classifier = "labelled vs unlabelled" (Elkan & Noto 2008 non-traditional classifier). Its score is used ONLY
    to RANK documents; under the SCAR assumption it is monotone in P(relevant | x). Its probabilities are not
    calibrated relevance probabilities;
  * models: M1 logistic regression on BASE_FEATURES; M2 HistGradientBoosting on BASE_FEATURES;
    M3 logistic regression on BASE_FEATURES + frozen MiniLM product features;
  * every model and the Hybrid RRF baseline rerank the SAME hybrid top-100 pool for the SAME eligible claims
    (claims with >= 1 labelled document in their corpus);
  * selection: highest claim-level Recall@10 on VALIDATION (ties -> simpler model);
  * test: scored ONCE; primary McNemar (exact) selected model vs hybrid on per-claim hit@10.
Feature extraction is cached per claim (resumable); the final report is never overwritten.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pickle
import platform
import random
import sys
import time

import numpy as np

from rb_common import (N_UNLABELLED_PER_CLAIM, OUT, POOL, SAMPLING_POLICY, SEED_UNLABELLED, SPLIT_MANIFEST,
                       TRAIN_JSON, TRAIN_KS_DIR, sample_unlabelled)
from features import BASE_FEATURES, assert_safe, build_corpus, minilm_features, pair_features, rankings

KS_EVAL = (1, 5, 10, 20)
PARTS = ("fit", "validation", "test")

LABEL_NOTE = (
    "PU labels. s=1: AVeriTeC evidence-URL match with non-empty text = WEAK POSITIVE relevance proxy (not a "
    "human-verified authority label). All other documents are UNLABELLED, never confirmed negatives. Recall, MRR "
    "and pool coverage count only labelled documents. 'labelled_P@10' counts unlabelled documents as non-hits, so "
    "it is a LOWER BOUND on true precision@10, and only if labelled documents are truly relevant. It also favours "
    "models that imitate fact-checker citation choices. No average precision is reported, because ranking-wide AP "
    "with unlabelled-as-negative has no valid bound interpretation.")
PU_ASSUMPTIONS = [
    "SCAR (selected completely at random): labelled documents are assumed to be a random sample of all relevant "
    "documents. This is very likely violated. Fact-checkers prefer some source types (official pages, news, "
    "fact-check sites) and pages they could find with their own searches, so the model learns 'what fact-checkers "
    "cite', not relevance in general.",
    "Incomplete positives: most relevant pages in a knowledge store are never cited, so the unlabelled sample "
    "contains relevant documents (label noise in the s=0 class). Recall against labelled documents "
    "underestimates the true recall of relevant documents.",
    "Knowledge-store construction: AVeriTeC stores were built partly from queries derived from the gold "
    "evidence, so retrieval features may be easier on this data than on open-web retrieval.",
    "Empty-text evidence documents (scrape failures) cannot be labelled and are excluded. Claims whose evidence "
    "has no text are not eligible for evaluation.",
    "class_weight='balanced' reweights s=1 vs s=0. It changes calibration, not the validity of ranking under SCAR.",
]


def load_real():
    from build_sample import normalise
    from common import read_jsonl
    if not SPLIT_MANIFEST.exists():
        sys.exit("No split manifest. Run make_train_split.py (R1).")
    man = json.load(open(SPLIT_MANIFEST, encoding="utf-8"))
    missing = [i for v in man["split"].values() for i in v if not (TRAIN_KS_DIR / f"{i}.jsonl.gz").exists()]
    if missing:
        sys.exit(f"DATA REQUIREMENT NOT MET: {len(missing)} train knowledge-store extracts missing in {TRAIN_KS_DIR}.")
    train = json.load(open(TRAIN_JSON, encoding="utf-8"))
    claims = {}
    for part, ids in man["split"].items():
        for i in ids:
            r = normalise(i, train[i])
            claims[i] = {"part": part,
                         "row": {"claim": r["claim"], "speaker_or_entity": r["speaker_or_entity"],
                                 "location_ISO_code": r["location_ISO_code"]},   # the only claim fields features see
                         "evidence": {g["source_url_norm"] for g in r["gold_evidence"] if g["is_web_source"]},
                         "ks": lambda i=i: read_jsonl(TRAIN_KS_DIR / f"{i}.jsonl.gz")}
    return claims, man["split_sha256"]


def load_synthetic():
    """Clearly FAKE fixture for code testing only: 18 invented claims with invented documents."""
    rng = random.Random(7)
    topics = ["vaccine trial results", "city budget allocation", "satellite launch date", "river pollution report",
              "school exam policy", "new tax rule", "solar plant output", "hospital bed capacity", "rail fare change"]
    claims = {}
    for i in range(18):
        tp = topics[i % len(topics)]
        claim = f"Synthetic claim {i}: officials announced the {tp} figure of {100 + i} units"
        rows = []
        for j in range(60):
            rel = j < 3
            body = (f"Report on the {tp}: officials announced {100 + i} units. " if rel else
                    f"Unrelated page {j} about {rng.choice(topics)} and other matters. ") * rng.randint(3, 12)
            rows.append({"url": f"http://site{j % 7}.example/{i}/{j}", "text": body})
        ev = {f"site{j % 7}.example/{i}/{j}" for j in range(2)}
        part = "fit" if i < 10 else "validation" if i < 14 else "test"
        claims[i] = {"part": part, "row": {"claim": claim, "speaker_or_entity": None, "location_ISO_code": None},
                     "evidence": ev, "ks": lambda rows=rows: rows}
    return claims, "SYNTHETIC"


def prepare_claim(cid, c):
    docs = build_corpus(c["ks"](), cid)                     # drops empty-text documents
    if not docs:
        return None
    b, d, h = rankings(c["row"]["claim"], docs)
    pool = [u for u, _ in h[:POOL]]
    doc_urls = [x["url_norm"] for x in docs]
    labelled = c["evidence"] & set(doc_urls)                # weak positives with non-empty text
    unl = sample_unlabelled(cid, doc_urls, labelled) if c["part"] == "fit" else []
    fit_urls = sorted(labelled) + unl if c["part"] == "fit" else []
    allu = list(dict.fromkeys(pool + fit_urls))
    X = pair_features(c["row"], docs, b, d, h, allu)
    tx = {x["url_norm"]: x["text"] for x in docs}
    X = np.hstack([X, minilm_features(c["row"]["claim"], [tx[u] for u in allu])])
    ix = {u: k for k, u in enumerate(allu)}
    fi = [ix[u] for u in fit_urls]
    return {"part": c["part"], "n_docs": len(docs), "pool": pool, "X": X[:len(pool)],
            "X_fit": X[fi] if fi else X[:0], "s_fit": np.array([u in labelled for u in fit_urls], dtype=int),
            "labelled": labelled, "unlabelled_sample": unl,
            "unlabelled_sample_sha256": hashlib.sha256("\n".join(unl).encode()).hexdigest()}


def prepare(claims, cache_dir):
    prep, t0 = {}, time.time()
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
    for n, (cid, c) in enumerate(sorted(claims.items()), 1):
        f = cache_dir / f"{cid}.pkl" if cache_dir else None
        if f and f.exists():
            p = pickle.load(open(f, "rb"))
            src = "cache"
        else:
            p = prepare_claim(cid, c)
            src = "computed"
            if f:
                pickle.dump(p, open(f.with_suffix(".tmp"), "wb"))
                f.with_suffix(".tmp").replace(f)
        if p is None:
            print(f"[{n}/{len(claims)}] claim {cid} ({c['part']}): no non-empty documents", flush=True)
            continue
        prep[cid] = p
        print(f"[{n}/{len(claims)}] claim {cid} ({c['part']}): {p['n_docs']} docs, {len(p['labelled'])} labelled, "
              f"{len(p['unlabelled_sample'])} unlabelled sampled [{src}] ({time.time() - t0:.0f}s)", flush=True)
    return prep


def frac(a, b):
    return f"{a}/{b} = {a / b:.3f}" if b else f"{a}/0 = n/a"


def coverage(claims, prep, part):
    """Empirical upper bound for reranking the hybrid top-100: share of eligible claims / labelled docs in pool."""
    in_split = [c for c, x in claims.items() if x["part"] == part]
    elig = [c for c in in_split if c in prep and prep[c]["labelled"]]
    hit = sum(bool(prep[c]["labelled"] & set(prep[c]["pool"])) for c in elig)
    dl = sum(len(prep[c]["labelled"]) for c in elig)
    dh = sum(len(prep[c]["labelled"] & set(prep[c]["pool"])) for c in elig)
    return {"claims_in_split": len(in_split),
            "claims_with_nonempty_docs": sum(c in prep for c in in_split),
            "eligible_claims_(>=1_labelled_doc)": len(elig),
            "pool_coverage_claim_level_(max_claim_R@100)": frac(hit, len(elig)),
            "pool_coverage_doc_level_(max_doc_R@100)": frac(dh, dl)}


def evaluate(prep, part, scorer):
    ev = sorted(c for c, p in prep.items() if p["part"] == part and p["labelled"])
    hits = {k: [] for k in KS_EVAL}
    rr, found, total, lab10, slots10, best = [], 0, 0, 0, 0, {}
    for c in ev:
        ranked = scorer(c)
        g = prep[c]["labelled"]
        for k in KS_EVAL:
            hits[k].append(bool(g & set(ranked[:k])))
        r = next((i for i, u in enumerate(ranked, 1) if u in g), None)
        best[c] = r
        rr.append(1 / r if r else 0.0)
        found += len(g & set(ranked[:10]))
        total += len(g)
        lab10 += len(g & set(ranked[:10]))
        slots10 += min(10, len(ranked))
    m = {f"claim_R@{k}": frac(sum(v), len(ev)) for k, v in hits.items()}
    m["doc_R@10_micro"] = frac(found, total)
    m["MRR@100"] = f"{sum(rr):.2f}/{len(ev)} = {sum(rr) / len(ev):.3f}" if ev else "0/0 = n/a"
    m["labelled_P@10_lower_bound"] = frac(lab10, slots10)
    m["n_eval_claims"] = len(ev)
    return m, hits[10], best


def main():
    import joblib
    import sklearn
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from validation_heldout import mcnemar

    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true", help="fake fixture; verifies code only, no real metrics")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    assert_safe(BASE_FEATURES)
    claims, split_hash = load_synthetic() if a.synthetic else load_real()
    tag = a.tag or ("SYNTHETIC_SMOKE_TEST" if a.synthetic else "run1_pu")
    out = OUT / tag
    if (out / "relevance_baseline_report.json").exists() and not a.synthetic:
        sys.exit(f"{out / 'relevance_baseline_report.json'} exists; refusing to overwrite.")
    t_start = time.time()
    prep = prepare(claims, None if a.synthetic else out / "feature_cache")
    nb = len(BASE_FEATURES)
    fit = sorted(c for c, p in prep.items() if p["part"] == "fit")
    Xf = np.vstack([prep[c]["X_fit"] for c in fit])
    sf = np.concatenate([prep[c]["s_fit"] for c in fit])
    models = {
        "M1_logreg": (make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")), nb),
        "M2_hist_gbdt": (HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, class_weight="balanced",
                                                         random_state=2051), nb),
        "M3_logreg_minilm": (make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=0.1,
                                                                                class_weight="balanced")), None),
    }
    for name, (mdl, ncol) in models.items():
        mdl.fit(Xf[:, :ncol] if ncol else Xf, sf)

    def scorer_for(mdl, ncol):
        def s(c):
            X = prep[c]["X"][:, :ncol] if ncol else prep[c]["X"]
            p = mdl.predict_proba(X)[:, 1]
            order = sorted(range(len(p)), key=lambda i: (-p[i], i))  # tie -> hybrid order
            return [prep[c]["pool"][i] for i in order]
        return s

    systems = {"hybrid_rrf_baseline": lambda c: prep[c]["pool"]}
    systems.update({n: scorer_for(m, k) for n, (m, k) in models.items()})
    res, hits10, best = {}, {}, {}
    for part in PARTS:
        res[part] = {"pool_coverage_upper_bound": coverage(claims, prep, part)}
        for name, fn in systems.items():
            m, h, b = evaluate(prep, part, fn)
            res[part][name] = m
            hits10[(part, name)], best[(part, name)] = h, b
    r10 = lambda m: float(m["claim_R@10"].split("= ")[1])
    selected = max(models, key=lambda n: (r10(res["validation"][n]), -list(models).index(n)))
    for name in models:
        w, l, p = mcnemar(hits10[("test", "hybrid_rrf_baseline")], hits10[("test", name)])
        res["test"][name]["vs_hybrid_hit@10_mcnemar"] = {
            "wins": w, "losses": l, "p_exact": round(p, 4),
            "role": "PRIMARY (selected on validation)" if name == selected else "secondary/exploratory, uncorrected"}

    n_unl = sum(len(prep[c]["unlabelled_sample"]) for c in fit)
    report = {
        "status": "SYNTHETIC SMOKE TEST - numbers are meaningless" if a.synthetic else
                  "PU relevance ranking baseline (NOT authority). AVeriTeC train split only; offline; no LLM/API.",
        "split_sha256": split_hash,
        "label_note": LABEL_NOTE, "pu_assumptions_and_limitations": PU_ASSUMPTIONS,
        "unlabelled_sampling": {"policy": SAMPLING_POLICY, "seed": SEED_UNLABELLED,
                                "n_per_claim": N_UNLABELLED_PER_CLAIM,
                                "all_fit_samples_sha256": hashlib.sha256("\n".join(
                                    f"{c} {prep[c]['unlabelled_sample_sha256']}" for c in fit).encode()).hexdigest()},
        "fit_data": {"fit_claims_with_docs": len(fit),
                     "fit_claims_with_>=1_labelled": sum(bool(prep[c]["labelled"]) for c in fit),
                     "n_fit_pairs": int(len(sf)), "n_labelled_s1": int(sf.sum()), "n_unlabelled_sampled_s0": n_unl},
        "features": BASE_FEATURES + ["minilm_product_384 (M3 only)"],
        "candidate_pool": f"hybrid RRF top-{POOL}; identical for all systems and claims",
        "training_fit_claims": res["fit"],
        "training_note": "IN-SAMPLE: these claims' labelled documents were used for fitting; scores are optimistic.",
        "validation": res["validation"], "selected_on_validation": selected,
        "selection_rule": "max validation claim_R@10; ties -> simpler model (M1 < M2 < M3)",
        "test": res["test"], "test_note": "single test pass after model selection on validation",
        "environment": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                        "numpy": np.__version__, "runtime_s": round(time.time() - t_start)},
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "models").mkdir(exist_ok=True)
    for name, (mdl, ncol) in models.items():
        joblib.dump({"model": mdl, "n_feature_columns": ncol or Xf.shape[1], "base_features": BASE_FEATURES,
                     "note": "PU labelled-vs-unlabelled ranker; NOT an authority model"}, out / "models" / f"{name}.joblib")
    with open(out / "per_claim.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["train_idx", "part", "n_docs", "n_labelled", "labelled_in_pool", "n_unlabelled_sampled",
                    "unlabelled_sample_sha256"] + [f"best_labelled_rank_{n}" for n in systems])
        for c in sorted(prep):
            p = prep[c]
            w.writerow([c, p["part"], p["n_docs"], len(p["labelled"]), len(p["labelled"] & set(p["pool"])),
                        len(p["unlabelled_sample"]), p["unlabelled_sample_sha256"]] +
                       [best[(p["part"], n)].get(c, "") for n in systems])
    json.dump({str(c): prep[c]["unlabelled_sample"] for c in fit},
              open(out / "unlabelled_samples.json", "w", encoding="utf-8"), indent=0)
    json.dump(report, open(out / "relevance_baseline_report.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(report, indent=1))
    print(f"-> {out / 'relevance_baseline_report.json'}")


if __name__ == "__main__":
    main()
