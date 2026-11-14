"""Step R1 (offline, no download): choose the train-claim sample and its claim-disjoint split.

  python experiments/esa_nov2026/relevance_baseline/make_train_split.py

Reads only data/raw/averitec/train.json. Selects N_SAMPLE train claims that have >= 1 web evidence
URL, stratified by verdict label (the label is used ONLY to balance the sample; it is never a
feature), seed 2051. Assigns each claim to exactly one of fit / validation / test (60/20/20, also
label-stratified). Writes results/esa_nov2026/relevance_baseline/train_sample_split.json with a
SHA-256 so the split can be frozen before any document is extracted or any model is fitted.
Refuses to overwrite an existing manifest.
"""
import hashlib
import json
import random
import sys

from rb_common import N_SAMPLE, OUT, SEED_SAMPLE, SPLIT_FRACTIONS, SPLIT_MANIFEST, TRAIN_JSON

LABELS = ["Refuted", "Supported", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"]


def main():
    if SPLIT_MANIFEST.exists():
        sys.exit(f"{SPLIT_MANIFEST} exists; refusing to overwrite a frozen split.")
    from build_sample import normalise  # frozen normaliser (same gold-URL handling as dev)
    train = json.load(open(TRAIN_JSON, encoding="utf-8"))
    eligible = {}
    for i, c in enumerate(train):
        r = normalise(i, c)
        if any(g["is_web_source"] for g in r["gold_evidence"]):
            eligible.setdefault(c["label"], []).append(i)
    tot = sum(len(v) for v in eligible.values())
    raw = {l: N_SAMPLE * len(eligible[l]) / tot for l in LABELS}
    alloc = {l: int(raw[l]) for l in LABELS}
    for l in sorted(LABELS, key=lambda l: -(raw[l] - alloc[l]))[:N_SAMPLE - sum(alloc.values())]:
        alloc[l] += 1
    rng = random.Random(SEED_SAMPLE)
    split = {"fit": [], "validation": [], "test": []}
    for l in LABELS:
        ids = sorted(rng.sample(sorted(eligible[l]), alloc[l]))
        rng.shuffle(ids)
        n_fit = round(len(ids) * SPLIT_FRACTIONS[0])
        n_val = round(len(ids) * SPLIT_FRACTIONS[1])
        split["fit"] += ids[:n_fit]
        split["validation"] += ids[n_fit:n_fit + n_val]
        split["test"] += ids[n_fit + n_val:]
    split = {k: sorted(v) for k, v in split.items()}
    allids = split["fit"] + split["validation"] + split["test"]
    assert len(allids) == len(set(allids)) == N_SAMPLE, "split must be claim-disjoint"
    body = {"dataset": "AVeriTeC train.json", "train_json_sha256": hashlib.sha256(TRAIN_JSON.read_bytes()).hexdigest(),
            "n_train_claims_total": len(train), "n_eligible_with_web_evidence": tot,
            "seed": SEED_SAMPLE, "n_sample": N_SAMPLE, "allocation_by_label": alloc,
            "fractions": SPLIT_FRACTIONS, "ids_are": "0-based indices into train.json (namespace 'train:')",
            "split": split, "sizes": {k: len(v) for k, v in split.items()},
            "never_used": "dev split (120 dev sample, 200 held-out, 180 reserved), test split, sealed gold"}
    body["split_sha256"] = hashlib.sha256(json.dumps(split, sort_keys=True).encode()).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(body, open(SPLIT_MANIFEST, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: body[k] for k in ("n_eligible_with_web_evidence", "allocation_by_label", "sizes",
                                           "split_sha256")}, indent=1))
    print(f"-> {SPLIT_MANIFEST}")


if __name__ == "__main__":
    main()
