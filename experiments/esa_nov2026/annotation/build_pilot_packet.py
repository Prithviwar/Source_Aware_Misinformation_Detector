"""Build the PILOT annotation packet for claim-specific authority labelling (NO labels are created here).

  python experiments/esa_nov2026/annotation/build_pilot_packet.py

What it does
  * draws 20 claims from the 120 DEVELOPMENT-sample claims (seed 2060; never the 200 held-out, never the 180
    reserved, never AVeriTeC test). Pilot labels exist only to test the guidelines and measure agreement; they
    must not be used to train or to evaluate the final model.
  * takes each claim's frozen hybrid-RRF top-10 documents (the pool the authority module actually sees)
  * shuffles the 10 documents within each claim (seeded) so annotators cannot infer the retrieval rank
  * writes ONE blank sheet per annotator (A, B) with identical rows, plus a separate KEY file with the retrieval
    rank and the AVeriTeC evidence indicator, which must NOT be given to annotators (leakage control)

Annotators see: claim text, speaker, claim date, country, document URL, publisher key, text excerpt.
Annotators never see: AVeriTeC verdict, justification, questions/answers, fact-check article, evidence indicator,
retrieval rank or score, any model prediction.

Outputs: data/annotations/authority_pilot_2026-11/
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from esa_common import ROOT, claims  # noqa: E402

SEED = 2060
N_CLAIMS = 20
TOP = 10
EXCERPT = 1500
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
OUT = ROOT / "data" / "annotations" / "authority_pilot_2026-11"

LABEL_COLS = ["relevance", "authority", "authority_basis", "doc_type", "accessible", "confidence_1to3",
              "time_spent_min", "notes"]


def main():
    from baseline_retrieval import retrieval_corpus
    from demo_pipeline import frozen_rankings
    from source_targeted import cand_key
    if (OUT / "pilot_annotator_A.csv").exists():
        sys.exit(f"{OUT} already contains a packet; refusing to overwrite (annotators may already have it).")
    dev = sorted(cid for cid, r in claims().items() if r["split"] == "dev120")
    pick = sorted(random.Random(SEED).sample(dev, N_CLAIMS))
    rk = frozen_rankings("dev120")["hybrid"]
    rows, key = [], []
    for cid in pick:
        r = claims()[cid]
        texts = {d["url_norm"]: d["text"] for d in retrieval_corpus(cid)}
        gold = {g["source_url_norm"] for g in r["gold_evidence"] if g["is_web_source"]}
        top = [u for u, _ in rk[cid][:TOP]]
        order = top[:]
        random.Random(SEED * 1000 + cid).shuffle(order)
        for j, u in enumerate(order, 1):
            pid = f"P{cid:03d}-{j:02d}"
            ex = re.sub(r"\s+", " ", texts.get(u, ""))[:EXCERPT]
            ex = EMAIL.sub("[REDACTED_EMAIL]", ex)  # privacy: no third-party email addresses in public sheets
            rows.append({"pair_id": pid, "claim_id": cid, "claim": r["claim"], "speaker": r.get("speaker_or_entity") or "",
                         "claim_date": r.get("claim_date") or "", "country": r.get("location_ISO_code") or "",
                         "doc_url": "https://" + u, "publisher_key": cand_key(u) or "", "doc_excerpt": ex,
                         **{c: "" for c in LABEL_COLS}})
            key.append({"pair_id": pid, "claim_id": cid, "hybrid_rank": top.index(u) + 1,
                        "is_averitec_evidence_url": int(u in gold)})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_KEY_DO_NOT_GIVE_TO_ANNOTATORS").mkdir(exist_ok=True)
    fields = list(rows[0].keys())
    for ann in ("A", "B"):
        with open(OUT / f"pilot_annotator_{ann}.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    with open(OUT / "_KEY_DO_NOT_GIVE_TO_ANNOTATORS" / "pilot_key.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(key[0].keys()))
        w.writeheader()
        w.writerows(key)
    adj = ["pair_id", "claim_id", "relevance_A", "relevance_B", "authority_A", "authority_B", "relevance_final",
           "authority_final", "adjudicator", "disagreement_type", "guideline_section", "adjudication_note"]
    with open(OUT / "pilot_adjudication_template.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(adj)
        for x in rows:
            w.writerow([x["pair_id"], x["claim_id"]] + [""] * (len(adj) - 2))
    man = {"built_at": datetime.now().isoformat(timespec="seconds"), "seed": SEED, "claims": pick,
           "n_pairs": len(rows), "source_pool": "frozen hybrid RRF top-10 (results/rankings_hybrid.jsonl.gz, dev sample)",
           "split_policy": "PILOT ONLY: dev-sample claims; never train/evaluate the final model on these labels",
           "hidden_from_annotators": ["AVeriTeC verdict/label", "justification", "questions/answers", "fact-check article",
                                      "evidence indicator", "retrieval rank/score", "model predictions"],
           "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob("*.csv"))},
           "labels_present": False,
           "note": "Sheets are BLANK. No human or model labels have been created."}
    json.dump(man, open(OUT / "PILOT_MANIFEST.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: man[k] for k in ("claims", "n_pairs")}, indent=1))
    print(f"evidence-URL pairs in pilot (hidden from annotators): {sum(k['is_averitec_evidence_url'] for k in key)}/{len(key)}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
