"""AI-labelled primary-evidence recall (held-out). Labels are MODEL_GENERATED (AI), never human.

Converts evidence-level AI role labels into the frozen scorer's claim-level sheet and scores the FROZEN rankings with
the UNCHANGED frozen scorer (score_heldout_primary.py). Nothing is retrieved, re-ranked or re-predicted.

  python score_ai_primary.py selftest                  no labels: input mapping, key round trip, frozen scorer selftest
  python score_ai_primary.py convert <roles.csv>       -> ai/MODEL_GENERATED_heldout_primary_sheet_from_evidence_roles.csv
  python score_ai_primary.py score   <roles.csv>       convert + frozen check + frozen score -> results/heldout_ai_primary/
  python score_ai_primary.py agreement <a.csv> <b.csv> AI-AI agreement on shared items (run A vs B, or cross-family)
  python score_ai_primary.py overlap <roles.csv> [<claim_labels.csv>]
                                                       descriptive circularity diagnostics vs the authority predictor

Definition (source_targeted_preregistration.md Addendum 3): AI-primary docs of claim c = reachable human-gold docs of c
whose publisher key (cand_key) equals the key of >=1 gold URL of c that the AI labelled 'primary'.
Claims with none -> 'no_identifiable_primary' (excluded, counted). Row confidence = lowest confidence among the claim's
'primary' labels. Keys that the frozen sheet format cannot express (bare platform, malformed URL) are excluded and counted.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import score_heldout_primary as sph
from common import RESULTS
from source_targeted import cand_key

PKG = sph.PKG
AI = PKG / "ai"
EVIDENCE_SHEET = PKG.parent / "heldout_annotator_template.csv"
SHEET_OUT = AI / "MODEL_GENERATED_heldout_primary_sheet_from_evidence_roles.csv"
OUT = RESULTS / "heldout_ai_primary"
RANK = {"low": 0, "medium": 1, "high": 2}
ENDPOINT = "AI-labelled primary-evidence recall"


def gold_url_norm() -> dict:
    """item_id -> (claim_id, source_url_norm) via exact source_url match (asserted for all 422 rows)."""
    ho = {}
    for x in map(json.loads, open(PKG.parent.parent / "processed" / "averitec_heldout.jsonl", encoding="utf-8")):
        ho[int(x["claim_id"])] = {e["source_url"]: e["source_url_norm"] for e in x["gold_evidence"] if e.get("is_web_source")}
    out = {}
    for r in csv.DictReader(open(EVIDENCE_SHEET, encoding="utf-8-sig")):
        c = int(r["claim_id"])
        assert r["evidence_url"] in ho[c], f"item {r['item_id']} does not map to a gold URL"
        out[r["item_id"]] = (c, ho[c][r["evidence_url"]])
    return out


def expressible(k: str) -> bool:
    keys, bad = sph.entry_keys(k)
    return keys == {k} and not bad


def read_roles(path) -> dict:
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    assert all(r["annotator_id"].startswith("MODEL_GENERATED_") for r in rows), "labels must be MODEL_GENERATED"
    return {r["item"]: r for r in rows}


def convert(path) -> Path:
    roles, gmap = read_roles(path), gold_url_norm()
    missing = sorted(set(gmap) - set(roles), key=int)
    assert not missing, f"{len(missing)} gold URLs have no AI label: {missing[:10]}"
    per_claim, unexpressible = {}, Counter()
    for item, (c, u) in gmap.items():
        r = roles[item]
        if r["label"] != "primary":
            continue
        k = cand_key(u)
        if not expressible(k):
            unexpressible[k] += 1
            continue
        d = per_claim.setdefault(c, {"keys": {}, "conf": "high"})
        d["keys"].setdefault(k, r["publisher_name"].strip() or k)
        d["conf"] = min(d["conf"], r["confidence"], key=RANK.get)
    blank = list(csv.DictReader(open(PKG / "heldout_primary_annotation.csv", encoding="utf-8-sig")))
    cols = list(blank[0].keys())
    for row in blank:
        c = int(row["claim_id"])
        d = per_claim.get(c)
        row.update({"annotator_id": "MODEL_GENERATED_CLAUDE_OPUS_5_5_EVIDENCE_ROLES", "research_used": "none",
                    "authority_rationale": "converted from AI evidence-level role labels (MODEL_GENERATED)"})
        if not d:
            row.update({"authority_situation": "no_identifiable_primary", "confidence": "high",
                        "notes": "no gold URL of this claim was AI-labelled primary"})
            continue
        keys = sorted(d["keys"])
        groups = [[k] for k in keys[:2]] + ([keys[2:]] if len(keys) > 2 else [])
        row["authority_situation"] = "single_primary" if len(keys) == 1 else "multiple_legitimate_authorities"
        for i, g in enumerate(groups, 1):
            row[f"authority_{i}_name"] = "; ".join(d["keys"][k] for k in g)
            row[f"authority_{i}_domain_or_account"] = "; ".join(g)
            row[f"authority_{i}_type"] = "other"
        row["confidence"] = d["conf"]
        row["notes"] = "type not annotated at evidence level (set to 'other')"
    AI.mkdir(parents=True, exist_ok=True)
    with open(SHEET_OUT, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(blank)
    json.dump({"unexpressible_primary_keys": dict(unexpressible)},
              open(SHEET_OUT.with_suffix(".conversion.json"), "w", encoding="utf-8"), indent=1)
    print(f"wrote {SHEET_OUT.name}: {len(per_claim)} claims with an AI-primary publisher; "
          f"unexpressible primary keys excluded: {dict(unexpressible)}")
    return SHEET_OUT


def score(path):
    sheet = convert(path)
    ann, errors = sph.read_sheet(sheet)
    assert not errors, errors[:20]
    sph.OUT = OUT                       # redirect output only; frozen scorer code is unchanged
    sph.score(str(sheet))
    res = json.load(open(OUT / "primary_results_heldout.json", encoding="utf-8"))
    res = {"endpoint": ENDPOINT, "label_source": "MODEL_GENERATED (AI, Claude Opus 5.5); NOT human-annotated",
           "same_model_as_authority_predictor": True, "roles_file": str(path),
           "metric_names_note": "'Prim*' keys below mean AI-labelled primary-evidence metrics (AI-PrimR@K etc.)", **res}
    json.dump(res, open(OUT / "MODEL_GENERATED_ai_primary_evidence_recall_heldout.json", "w", encoding="utf-8"), indent=1)
    (OUT / "primary_results_heldout.json").unlink()   # keep only the explicitly AI-named file
    print(f"wrote {OUT / 'MODEL_GENERATED_ai_primary_evidence_recall_heldout.json'}")


def kappa(a: list, b: list) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / n / n
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def agreement(pa, pb):
    a, b = read_roles(pa), read_roles(pb)
    common = sorted(set(a) & set(b), key=int)
    la, lb = [a[i]["label"] for i in common], [b[i]["label"] for i in common]
    ba, bb = [x == "primary" for x in la], [x == "primary" for x in lb]
    out = {"comparison": "AI-AI agreement (not human validation)", "a": pa, "b": pb, "n_items": len(common),
           "pct_agree_4way": round(sum(x == y for x, y in zip(la, lb)) / len(common), 3), "kappa_4way": kappa(la, lb),
           "pct_agree_primary_vs_not": round(sum(x == y for x, y in zip(ba, bb)) / len(common), 3),
           "kappa_primary_vs_not": kappa(ba, bb),
           "discordant_items": [i for i, x, y in zip(common, la, lb) if x != y]}
    print(json.dumps(out, indent=1))
    return out


def overlap(roles_path, claim_path=None):
    """Descriptive only. Reads the frozen predictor output read-only."""
    from source_targeted import primary_authority_candidates
    pred = {}
    for x in map(json.loads, open(RESULTS / "heldout" / "authority_raw.jsonl", encoding="utf-8")):
        if x.get("cond") == "L+Wctx" and x.get("pred"):
            pred[int(x["claim_id"])] = set().union(*[set(a["keys"]) for a in primary_authority_candidates(x["pred"])] or [set()])
    roles, gmap = read_roles(roles_path), gold_url_norm()
    inpred = Counter()
    for item, (c, u) in gmap.items():
        inpred[(roles[item]["label"] == "primary", cand_key(u) in pred.get(c, set()))] += 1
    out = {"note": "descriptive circularity diagnostic; not a test",
           "share_of_AI_primary_gold_urls_whose_publisher_is_in_predictor_top3":
               round(inpred[(True, True)] / max(1, inpred[(True, True)] + inpred[(True, False)]), 3),
           "share_of_other_gold_urls_whose_publisher_is_in_predictor_top3":
               round(inpred[(False, True)] / max(1, inpred[(False, True)] + inpred[(False, False)]), 3),
           "counts": {f"primary={p},in_pred={q}": n for (p, q), n in inpred.items()}}
    if claim_path:
        rows = list(csv.DictReader(open(claim_path, encoding="utf-8-sig")))
        anyk = top1 = n = 0
        for r in rows:
            ks = [sph.entry_keys(r.get(f"authority_{i}_domain_or_account") or "")[0] for i in (1, 2, 3)]
            allk = set().union(*ks)
            if not allk:
                continue
            n += 1
            anyk += bool(allk & pred.get(int(r["claim_id"]), set()))
            top1 += bool(ks[0] & pred.get(int(r["claim_id"]), set()))
        out["claim_level_AI_named_authority_vs_predictor_top3"] = {
            "claims_with_keys": n, "any_key_overlap": anyk, "authority1_in_predictor_top3": top1}
    print(json.dumps(out, indent=1))
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / "MODEL_GENERATED_circularity_overlap.json", "w", encoding="utf-8"), indent=1)


def selftest():
    gmap = gold_url_norm()
    print(f"input mapping OK: {len(gmap)}/422 evidence rows map to held-out gold URLs")
    keys = Counter(cand_key(u) for _, u in gmap.values())
    bad = {k: n for k, n in keys.items() if not expressible(k)}
    print(f"{len(keys)} distinct gold publisher keys; not expressible in the frozen sheet (excluded if AI-primary): {bad}")
    sph.selftest()


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    {"selftest": selftest, "convert": lambda: convert(args[0]), "score": lambda: score(args[0]),
     "agreement": lambda: agreement(*args[:2]), "overlap": lambda: overlap(*args[:2])}[cmd]()
