"""Build the 15-claim annotation PILOT from the canonical blank held-out sheet, and run the leak scan.

  python heldout_primary_pilot.py

Pilot = rows 1-15 of data/annotations/heldout_primary_package/heldout_primary_annotation.csv (frozen order),
same columns and allowed values. The canonical sheet is only read, never written (its hash is asserted).
Writes data/annotations/heldout_primary_package/pilot/:
  handout/heldout_primary_pilot15.csv (+ .xlsx)   the annotator's sheet
  handout/ANNOTATION_GUIDE.md                     byte-identical copy of the package guide
  (handout/PILOT_INSTRUCTIONS.md and PILOT_FEEDBACK.md are hand-written, not generated)
  PILOT_MANIFEST.json                             IDs, hashes, leak-scan result
Reads NO rankings, predictions or results; gold/prediction files are read only to prove they do not leak.
"""
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

from common import ANNOTATIONS, PROCESSED, RESULTS, read_jsonl
from heldout_primary_package import ALLOWED, COLS, PKG, SHEET
from second_annotator_package import write_xlsx

N_PILOT = 15
PILOT = PKG / "pilot"
HANDOUT = PILOT / "handout"
PILOT_SHEET = HANDOUT / "heldout_primary_pilot15.csv"
CANONICAL_SHA = "cf063d5ebbb25c3c853f7bc1b26a3d19b621482b797e3592ce865d7b8637259c"  # Addendum 2
# evaluation vocabulary that must not appear in annotator-facing files
RESULT_TERMS = re.compile(r"GoldR@|PrimR@|R@\d|MRR|hybrid|bm25|dense|rerank|ORACLE|oracle|llm_authority|"
                          r"targeted|L\+Wctx|McNemar|validation_heldout|rankings_|authority_raw|0\.293|0\.246", re.I)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def file_text(p: Path) -> str:
    if p.suffix == ".xlsx":
        from openpyxl import load_workbook
        ws = load_workbook(p, read_only=True).active
        return "\n".join(" ".join("" if v is None else str(v) for v in row) for row in ws.iter_rows(values_only=True))
    return p.read_text(encoding="utf-8-sig")


def leak_scan(files, pilot_ids):
    """Needles: every gold URL / fact-check URL / justification of all 200 held-out claims; for the pilot claims also
    the gold publisher domains and the model's predicted publisher keys; evaluation vocabulary."""
    from authority_resolution import SOCIAL, org_domain
    from source_targeted import primary_authority_candidates
    ho = read_jsonl(PROCESSED / "averitec_heldout.jsonl")
    claims_lower = [r["claim"].lower() for r in ho]
    claim_text = {int(r["claim_id"]): r["claim"].lower() for r in ho}
    url_needles, dom_needles, just_needles = set(), set(), set()
    for r in ho:
        for g in r["gold_evidence"]:
            if g.get("source_url_norm") and len(g["source_url_norm"]) > 12:
                url_needles.add(g["source_url_norm"].lower())
        if r.get("fact_checking_article") and len(r["fact_checking_article"]) > 12:
            url_needles.add(r["fact_checking_article"].lower().split("://")[-1].removeprefix("www."))
        if r.get("justification") and len(r["justification"]) > 40:
            just_needles.add(r["justification"][:60].lower())
        if int(r["claim_id"]) in pilot_ids:
            for g in r["gold_evidence"]:
                if g.get("is_web_source"):
                    d = org_domain(g["source_url"])
                    # bare platforms (twitter.com, ...) are not publisher keys: handles are checked via predictions
                    if d and d not in ("archive.org", "archive.ph") and d not in SOCIAL and d not in claim_text[int(r["claim_id"])]:
                        dom_needles.add(d)
    pred_needles = set()
    for line in open(RESULTS / "heldout" / "authority_raw.jsonl", encoding="utf-8"):
        x = json.loads(line)
        if x.get("cond") == "L+Wctx" and x.get("pred") and int(x["claim_id"]) in pilot_ids:
            for a in primary_authority_candidates(x["pred"]):
                pred_needles |= {k for k in a["keys"] if k.split("/")[0] not in claim_text[int(x["claim_id"])]}
    report = {}
    for f in files:
        t = file_text(f).lower()
        for ct in claims_lower:           # the claims themselves are allowed to contain any word
            t = t.replace(ct, " ")
        hits = {"gold_or_factcheck_url": sorted(u for u in url_needles if u in t),
                "justification_text": sorted(j for j in just_needles if j in t),
                "pilot_gold_publisher_domain": sorted(d for d in dom_needles if re.search(r"(?<![\w.])" + re.escape(d) + r"(?![\w])", t)),
                "pilot_predicted_publisher_key": sorted(k for k in pred_needles if re.search(r"(?<![\w.])" + re.escape(k) + r"(?![\w])", t)),
                "evaluation_terms": sorted(set(m.group(0) for m in RESULT_TERMS.finditer(t)))}
        report[str(f.relative_to(PKG))] = {k: v for k, v in hits.items() if v}
    return report, {"gold_urls": len(url_needles), "justifications": len(just_needles),
                    "pilot_gold_domains": len(dom_needles), "pilot_predicted_keys": len(pred_needles)}


def main():
    assert sha(SHEET) == CANONICAL_SHA, "canonical blank sheet changed"
    with open(SHEET, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    pilot = rows[:N_PILOT]
    assert [int(r["row"]) for r in pilot] == list(range(1, N_PILOT + 1))
    HANDOUT.mkdir(parents=True, exist_ok=True)
    with open(PILOT_SHEET, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(pilot)
    write_xlsx(PILOT_SHEET, COLS, ALLOWED)
    shutil.copyfile(PKG / "ANNOTATION_GUIDE.md", HANDOUT / "ANNOTATION_GUIDE.md")

    ids = {int(r["claim_id"]) for r in pilot}
    facing = [SHEET, SHEET.with_suffix(".xlsx"), PKG / "ANNOTATION_GUIDE.md"] + sorted(HANDOUT.iterdir())
    report, needles = leak_scan(facing, ids)
    here = Path(__file__).parent
    manifest = {"n_pilot": len(pilot), "pilot_rows": [int(r["row"]) for r in pilot],
                "pilot_claim_ids": [int(r["claim_id"]) for r in pilot],
                "canonical_sheet_sha256_unchanged": sha(SHEET),
                "pilot_sheet_sha256_blank": sha(PILOT_SHEET),
                "guide_copy_identical": sha(HANDOUT / "ANNOTATION_GUIDE.md") == sha(PKG / "ANNOTATION_GUIDE.md"),
                "guide_sha256": sha(PKG / "ANNOTATION_GUIDE.md"),
                "frozen_hashes_now": {"score_heldout_primary.py": sha(here / "score_heldout_primary.py"),
                                      "rankings_heldout.jsonl.gz": sha(RESULTS / "source_targeted" / "rankings_heldout.jsonl.gz"),
                                      "heldout/rankings_hybrid.jsonl.gz": sha(RESULTS / "heldout" / "rankings_hybrid.jsonl.gz")},
                "leak_scan_needles": needles, "leak_scan_hits": report}
    json.dump(manifest, open(PILOT / "PILOT_MANIFEST.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
