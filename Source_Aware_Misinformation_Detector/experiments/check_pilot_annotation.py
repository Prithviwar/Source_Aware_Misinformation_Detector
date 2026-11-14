"""Validate a returned 15-claim PILOT sheet and summarise it for the guide review. Reads NO gold, rankings or results.

  python check_pilot_annotation.py <pilot_A.csv|xlsx> [<pilot_B.csv|xlsx>]

Same validation rules as `score_heldout_primary.py check` (shared parser `entry_keys`, allowed values from the
package MANIFEST), restricted to the pilot claim IDs/order in PILOT_MANIFEST.json. With two files it also reports
between-annotator agreement. Output: printed report + <file>.pilot_check.json next to the returned file.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from common import ANNOTATIONS
from score_heldout_primary import entry_keys

PKG = ANNOTATIONS / "heldout_primary_package"
PILOT = PKG / "pilot"


def load_rows(path: Path) -> list[dict]:
    if path.suffix == ".xlsx":
        from openpyxl import load_workbook
        vals = list(load_workbook(path, read_only=True).active.iter_rows(values_only=True))
        head = [str(h) for h in vals[0]]
        return [{h: ("" if v is None else str(v)) for h, v in zip(head, row)} for row in vals[1:] if any(row)]
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def validate(path: Path):
    man = json.load(open(PKG / "MANIFEST.json", encoding="utf-8"))
    pm = json.load(open(PILOT / "PILOT_MANIFEST.json", encoding="utf-8"))
    blank = {int(r["claim_id"]): r for r in load_rows(PILOT / "handout" / "heldout_primary_pilot15.csv")}
    rows = load_rows(path)
    errors, ann = [], {}
    if [int(float(r["claim_id"])) for r in rows] != pm["pilot_claim_ids"]:
        errors.append("claim IDs / order differ from the pilot (rows must not be added, removed or re-sorted)")
    for r in rows:
        c = int(float(r["claim_id"]))
        where = f"row {r.get('row')} claim {c}"
        for col in man["context_cols"]:
            a, b = (r.get(col) or "").strip(), (blank.get(c, {}).get(col) or "").strip()
            if col in ("row", "claim_id"):
                a, b = a.split(".")[0], b.split(".")[0]     # Excel may turn 1 into 1.0
            if a != b:
                errors.append(f"{where}: context column '{col}' was edited")
        for col, allowed in man["allowed_values"].items():
            v = (r.get(col) or "").strip()
            if v and v not in allowed:
                errors.append(f"{where}: {col}='{v}' not in allowed values")
        for col in ("annotator_id", "authority_situation", "confidence", "research_used"):
            if not (r.get(col) or "").strip():
                errors.append(f"{where}: {col} is empty")
        sit = (r.get("authority_situation") or "").strip()
        auths = []
        for i in (1, 2, 3):
            name, dk = (r.get(f"authority_{i}_name") or "").strip(), (r.get(f"authority_{i}_domain_or_account") or "").strip()
            if not (name or dk):
                continue
            keys, bad = entry_keys(dk)
            errors += [f"{where}: authority_{i}: {b}" for b in bad]
            if not keys:
                errors.append(f"{where}: authority_{i} has no usable domain_or_account")
            if not name:
                errors.append(f"{where}: authority_{i}_name is empty")
            if not (r.get(f"authority_{i}_type") or "").strip():
                errors.append(f"{where}: authority_{i}_type is empty")
            auths.append({"name": name, "keys": sorted(keys), "type": (r.get(f"authority_{i}_type") or "").strip()})
        if sit in ("single_primary", "multiple_legitimate_authorities") and not auths:
            errors.append(f"{where}: situation '{sit}' but no authority listed")
        if sit == "multiple_legitimate_authorities" and len(auths) < 2:
            errors.append(f"{where}: 'multiple_legitimate_authorities' needs >=2 authorities")
        if sit == "no_identifiable_primary" and auths:
            errors.append(f"{where}: 'no_identifiable_primary' but authorities are listed")
        if sit and not (r.get("authority_rationale") or "").strip():
            errors.append(f"{where}: authority_rationale is empty")
        ann[c] = {"row": r.get("row"), "situation": sit, "confidence": (r.get("confidence") or "").strip(),
                  "research": (r.get("research_used") or "").strip(), "authorities": auths,
                  "notes": bool((r.get("notes") or "").strip())}
    return ann, errors


def summary(ann):
    types = Counter(a["type"] for x in ann.values() for a in x["authorities"])
    return {"n_rows": len(ann),
            "situation": dict(Counter(x["situation"] for x in ann.values())),
            "confidence": dict(Counter(x["confidence"] for x in ann.values())),
            "research_used": dict(Counter(x["research"] for x in ann.values())),
            "n_authorities_per_row": dict(Counter(len(x["authorities"]) for x in ann.values())),
            "authority_types": dict(types),
            "rows_type_other": [x["row"] for x in ann.values() if any(a["type"] == "other" for a in x["authorities"])],
            "rows_unclear_or_low_conf": [x["row"] for x in ann.values() if x["situation"] == "unclear" or x["confidence"] == "low"],
            "rows_with_notes": sum(x["notes"] for x in ann.values())}


def agreement(a, b):
    ids = [c for c in a if c in b]
    k1 = lambda x: set(x["authorities"][0]["keys"]) if x["authorities"] else set()
    ka = lambda x: set().union(*[set(y["keys"]) for y in x["authorities"]]) if x["authorities"] else set()
    both_named = [c for c in ids if ka(a[c]) and ka(b[c])]
    return {"n": len(ids),
            "situation_same": sum(a[c]["situation"] == b[c]["situation"] for c in ids),
            "both_list_an_authority": len(both_named),
            "top1_key_overlap": sum(bool(k1(a[c]) & k1(b[c])) for c in both_named),
            "any_key_overlap": sum(bool(ka(a[c]) & ka(b[c])) for c in both_named),
            "rows_no_key_overlap": [a[c]["row"] for c in both_named if not ka(a[c]) & ka(b[c])],
            "rows_situation_differs": [a[c]["row"] for c in ids if a[c]["situation"] != b[c]["situation"]]}


def main(paths):
    out, anns = {}, []
    for p in map(Path, paths):
        ann, errors = validate(p)
        anns.append(ann)
        out[p.name] = {"n_problems": len(errors), "problems": errors, "summary": summary(ann)}
    if len(anns) == 2:
        out["agreement"] = agreement(*anns)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    for p in map(Path, paths):
        json.dump(out, open(p.with_suffix(p.suffix + ".pilot_check.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    sys.exit(1 if any(v.get("n_problems") for v in out.values() if isinstance(v, dict) and "n_problems" in v) else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
