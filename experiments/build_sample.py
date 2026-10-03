"""Step 2: build a small, label-stratified sample of AVeriTeC dev claims.

Reads data/raw/averitec/dev.json (never modified) and writes
data/processed/averitec_sample.jsonl. claim_id == index in dev.json, which is
also the key of the per-claim file in the dev knowledge store.
"""
import json
import random

from common import PROCESSED, RAW, is_placeholder_url, normalize_url, registered_domain, write_jsonl

SEED = 2026
PER_LABEL = {
    "Refuted": 70,
    "Supported": 30,
    "Conflicting Evidence/Cherrypicking": 10,
    "Not Enough Evidence": 10,
}


def normalise(idx: int, c: dict) -> dict:
    gold = []
    for qi, q in enumerate(c["questions"]):
        for a in q["answers"]:
            url = (a.get("source_url") or "").strip()
            placeholder = not url or is_placeholder_url(url)
            gold.append({
                "question_idx": qi,
                "question": q["question"],
                "answer": a.get("answer"),
                "answer_type": a.get("answer_type"),
                "boolean_explanation": a.get("boolean_explanation"),
                "source_url": url or None,
                "is_web_source": not placeholder,  # False for 'http://Metadata' / empty
                "source_url_norm": None if placeholder else normalize_url(url),
                "source_domain": None if placeholder else registered_domain(url),
                "source_medium": a.get("source_medium") or None,
            })
    urls = list(dict.fromkeys(g["source_url"] for g in gold if g["is_web_source"]))
    return {
        "claim_id": idx,
        "claim": c["claim"],
        "claim_date": c["claim_date"],  # DD-MM-YYYY in the raw data
        "gold_label": c["label"],
        "gold_evidence": gold,
        "evidence_urls": urls,
        "speaker_or_entity": (c.get("speaker") or "").strip() or None,
        "reporting_source": (c.get("reporting_source") or "").strip() or None,
        "location_ISO_code": c.get("location_ISO_code"),
        "claim_types": c.get("claim_types"),
        "fact_checking_strategies": c.get("fact_checking_strategies"),
        "original_claim_url": c.get("original_claim_url"),
        "fact_checking_article": c.get("fact_checking_article"),
        "justification": c.get("justification"),
        "required_reannotation": c.get("required_reannotation"),
    }


def main():
    dev = json.load(open(RAW / "dev.json", encoding="utf-8"))
    rng = random.Random(SEED)
    chosen = []
    for label, n in PER_LABEL.items():
        idxs = [i for i, c in enumerate(dev) if c["label"] == label]
        chosen += rng.sample(idxs, n)
    chosen.sort()
    rows = [normalise(i, dev[i]) for i in chosen]
    write_jsonl(PROCESSED / "averitec_sample.jsonl", rows)
    n_urls = sum(len(r["evidence_urls"]) for r in rows)
    print(f"{len(rows)} claims, {n_urls} unique gold evidence URLs -> {PROCESSED / 'averitec_sample.jsonl'}")


if __name__ == "__main__":
    main()
