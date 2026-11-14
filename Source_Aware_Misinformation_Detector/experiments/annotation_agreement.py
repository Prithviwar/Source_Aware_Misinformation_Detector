"""Step 11b: agreement between the pilot annotation and a genuine second annotator.

Reads data/annotations/second_annotator_template.csv or its .xlsx copy (filled by a HUMAN) and the
pilot labels in source_roles.csv. Reports raw agreement, Cohen's kappa (4 classes
and primary-vs-rest) and the confusion matrix. If no labels are filled in, it
reports PENDING and computes nothing. Never fills labels itself.

Writes results/annotation_agreement.json.
"""
import csv
import json
from collections import Counter

from common import ANNOTATIONS, RESULTS, normalize_url

MAP = {"A_primary": "primary", "B_secondary": "secondary", "C_derived": "derived", "D_unclear": "unclear"}
LABELS = ["primary", "secondary", "derived", "unclear"]


def kappa(pairs, labels):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[l] * cb[l] for l in labels) / n ** 2
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan")


def read_filled(stem):
    """Rows of the CSV template, or of its .xlsx copy if the annotator filled that one instead."""
    with open(ANNOTATIONS / f"{stem}.csv", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    xl = ANNOTATIONS / f"{stem}.xlsx"
    if not any((r.get("annotator_label") or "").strip() for r in rows) and xl.exists():
        from openpyxl import load_workbook
        vals = list(load_workbook(xl, read_only=True).active.values)
        head = [str(h) for h in vals[0]]
        xrows = [{h: ("" if v is None else str(v)) for h, v in zip(head, r)} for r in vals[1:]]
        if any(r.get("annotator_label", "").strip() for r in xrows):
            rows = xrows
    return rows


def main():
    pilot = {}
    with open(ANNOTATIONS / "source_roles.csv", encoding="utf-8") as fh:
        for x in csv.DictReader(fh):
            pilot[(int(x["claim_id"]), normalize_url(x["evidence_url"]))] = MAP[x["source_role"]]
    rows = read_filled("second_annotator_template")
    filled = [r for r in rows if r["annotator_label"].strip()]
    out = {"items": len(rows), "labelled": len(filled)}
    if not filled:
        out["status"] = "PENDING: no second-annotator labels yet"
        print(json.dumps(out, indent=1))
        json.dump(out, open(RESULTS / "annotation_agreement.json", "w"), indent=1)
        return
    bad = [r["item_id"] for r in filled if r["annotator_label"].strip().lower() not in LABELS]
    if bad:
        raise SystemExit(f"invalid labels in items {bad[:20]} (allowed: {LABELS})")
    pairs = [(pilot[(int(r["claim_id"]), normalize_url(r["evidence_url"]))], r["annotator_label"].strip().lower())
             for r in filled]
    po, k = kappa(pairs, LABELS)
    pb = [("primary" if a == "primary" else "other", "primary" if b == "primary" else "other") for a, b in pairs]
    po2, k2 = kappa(pb, ["primary", "other"])
    out.update(status="complete" if len(filled) == len(rows) else "PARTIAL",
               raw_agreement=round(po, 3), cohen_kappa_4class=round(k, 3),
               raw_agreement_primary_vs_rest=round(po2, 3), cohen_kappa_primary_vs_rest=round(k2, 3),
               second_annotator_multiple_primary_flag=dict(Counter((r.get("multiple_primary_sources") or "").strip().lower() or "blank"
                                                                    for r in filled)),
               confusion_rows_pilot_cols_second={a: {b: sum(1 for x, y in pairs if x == a and y == b) for b in LABELS}
                                                 for a in LABELS})
    print(json.dumps(out, indent=1))
    json.dump(out, open(RESULTS / "annotation_agreement.json", "w"), indent=1)


if __name__ == "__main__":
    main()
