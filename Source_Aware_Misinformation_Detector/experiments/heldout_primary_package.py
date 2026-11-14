"""Build the BLIND claim-level primary-source annotation package for the 192 frozen held-out claims.

  python heldout_primary_package.py

Order and claim IDs are copied from the existing data/annotations/heldout_annotator_claim_authority_template.csv
(seeded shuffle, 192 claims = held-out claims with >=1 web gold URL). The sheet shows ONLY the claim and the
inference-time metadata (speaker, date, country). It never reads rankings, predictions, results or gold evidence
(the only gold-derived fact is which 192 claims are in the sheet, fixed earlier and not visible to the annotator).

Writes data/annotations/heldout_primary_package/:
  heldout_primary_annotation.csv   (canonical; the annotator fills the empty columns)
  heldout_primary_annotation.xlsx  (same content, dropdowns for constrained columns)
  MANIFEST.json                    (claim order, SHA-256 of the blank sheet and of the scorer)
"""
import csv
import hashlib
import json
from pathlib import Path

from common import ANNOTATIONS, PROCESSED, read_jsonl
from second_annotator_package import write_xlsx

PKG = ANNOTATIONS / "heldout_primary_package"
SRC_ORDER = ANNOTATIONS / "heldout_annotator_claim_authority_template.csv"
SHEET = PKG / "heldout_primary_annotation.csv"

CONTEXT_COLS = ["row", "claim_id", "claim_text", "claim_speaker", "claim_date", "claim_country"]
AUTH_COLS = [f"authority_{i}_{f}" for i in (1, 2, 3) for f in ("name", "domain_or_account", "type")]
FILL_COLS = ["annotator_id", "authority_situation", *AUTH_COLS, "authority_rationale", "confidence",
             "research_used", "notes"]
COLS = CONTEXT_COLS + FILL_COLS

AUTHORITY_TYPES = ["government_executive", "legislature", "court_or_prosecutor", "regulator_or_election_body",
                   "statistics_or_data_agency", "intergovernmental_org", "health_or_science_agency",
                   "academic_or_research_producer", "organisation_about_itself", "person_own_statement_or_account",
                   "other"]
ALLOWED = {"authority_situation": ["single_primary", "multiple_legitimate_authorities",
                                   "no_identifiable_primary", "unclear"],
           "confidence": ["high", "medium", "low"],
           "research_used": ["none", "institution_lookup_only"],
           **{f"authority_{i}_type": AUTHORITY_TYPES for i in (1, 2, 3)}}
# columns that must never appear in the annotator's sheet
FORBIDDEN = {"gold_evidence", "evidence_urls", "evidence_url", "gold_label", "label", "justification",
             "fact_checking_article", "reporting_source", "original_claim_url", "pred", "rank", "authority_pred"}


def main():
    with open(SRC_ORDER, encoding="utf-8-sig") as fh:
        order = [int(r["claim_id"]) for r in csv.DictReader(fh)]
    assert len(order) == 192 and len(set(order)) == 192
    ho = {int(r["claim_id"]): r for r in read_jsonl(PROCESSED / "averitec_heldout.jsonl")}
    assert set(order) <= set(ho)
    assert not FORBIDDEN & set(COLS)

    rows = []
    for i, c in enumerate(order, 1):
        r = ho[c]
        rows.append({"row": i, "claim_id": c, "claim_text": r["claim"], "claim_speaker": r.get("speaker_or_entity") or "",
                     "claim_date": r.get("claim_date") or "", "claim_country": r.get("location_ISO_code") or "",
                     **{k: "" for k in FILL_COLS}})

    # leak check: no gold URL / fact-check URL / label text may appear anywhere in the sheet
    leaks = []
    for x in rows:
        r = ho[x["claim_id"]]
        cells = " ".join(str(v) for v in x.values()).lower()
        for g in r["gold_evidence"]:
            u = (g.get("source_url_norm") or "").lower()
            if len(u) > 12 and u in cells:
                leaks.append((x["claim_id"], u))
        fc = (r.get("fact_checking_article") or "").lower()
        if len(fc) > 12 and fc in cells:
            leaks.append((x["claim_id"], fc))
    assert not leaks, leaks

    PKG.mkdir(parents=True, exist_ok=True)
    with open(SHEET, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    write_xlsx(SHEET, COLS, ALLOWED)

    here = Path(__file__).parent
    manifest = {"n_claims": len(rows), "claim_order": order,
                "source_of_order": SRC_ORDER.name,
                "sheet_sha256_blank": hashlib.sha256(SHEET.read_bytes()).hexdigest(),
                "context_cols": CONTEXT_COLS, "fill_cols": FILL_COLS, "allowed_values": ALLOWED,
                "frozen_rankings": "results/source_targeted/rankings_heldout.jsonl.gz",
                "frozen_rankings_sha256": hashlib.sha256(
                    (here.parent / "results/source_targeted/rankings_heldout.jsonl.gz").read_bytes()).hexdigest(),
                "scorer": "experiments/score_heldout_primary.py",
                "scorer_sha256": hashlib.sha256((here / "score_heldout_primary.py").read_bytes()).hexdigest()}
    json.dump(manifest, open(PKG / "MANIFEST.json", "w", encoding="utf-8"), indent=1)
    print(f"{len(rows)} claims -> {SHEET} (+ .xlsx); leak check passed; manifest written")


if __name__ == "__main__":
    main()
