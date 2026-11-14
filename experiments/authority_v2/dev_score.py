"""Development scoring and X build for T version k (preregistration §7). Development gold is
read HERE only; the reserved set is never touched.

  python dev_score.py score --version 1            X build + scoring of a finished T version
  python dev_score.py dryrun                       pipeline check with a SYNTHETIC T (not a version)
"""
import argparse
import csv
import gzip
import json
from collections import Counter

from v2common import RES, ROOT, halt, load_config, log_event, rel, sha256_file, write_new_json

import validation_heldout as V
from dev_data import load_dev, pool_keys, rank_with
from x_control import build_x

EXPECTED = {"dev120": 99, "dev200": 167}  # (stored) eligible counts, §3.2
KS = (1, 3, 5, 10, 20)


def dev_truth(claims):
    """Per claim: reachable web-gold URL set R(c) and eligibility E (§3.2). Halts on U9."""
    gold = {}
    for split, fn in (("dev120", "averitec_sample.jsonl"), ("dev200", "averitec_heldout.jsonl")):
        for r in map(json.loads, open(ROOT / "data/processed" / fn, encoding="utf-8")):
            gold[int(r["claim_id"])] = {g["source_url_norm"] for g in r["gold_evidence"] if g["is_web_source"]}
    stored = {}
    with open(ROOT / "results/source_targeted/per_claim_dev.csv", encoding="utf-8") as fh:
        for x in csv.DictReader(fh):
            v = x.get("n_gold_reachable")
            stored[int(x["claim_id"])] = int(v) if v is not None and v.strip().lstrip("-").isdigit() else None
    full = {}
    with gzip.open(ROOT / "results/heldout/rankings_hybrid.jsonl.gz", "rt", encoding="utf-8") as fh:
        for r in map(json.loads, fh):
            full[int(r["claim_id"])] = {u for u, _ in r["ranked"]}
    R, E, missing, u9 = {}, set(), [], []
    for c in claims:
        cid = c["claim_id"]
        if c["split"] == "dev120":
            n = stored.get(cid)
            in_pool = gold[cid] & {u for u, _ in c["pool"]}
            if n is None:
                missing.append(cid)
                R[cid] = set()
                continue
            if n == 0 and in_pool:
                u9.append(cid)
            R[cid] = gold[cid] if n >= 1 else set()  # every ranked doc is non-empty: a hit needs a gold URL
        else:
            R[cid] = gold[cid] & full[cid]
        if R[cid] and c["d_keys"] is not None:
            E.add(cid)
    if u9:
        halt("U9: stored n_gold_reachable = 0 contradicted by a gold URL in the frozen top-100", claims=u9)
    counts = {s: sum(c["claim_id"] in E for c in claims if c["split"] == s) for s in EXPECTED}
    if counts != EXPECTED:
        halt("eligible counts differ from the stored counts", got=counts, expected=EXPECTED)
    return R, E, {"eligible": counts, "N": len(E), "missing_reachability_120": missing}


def score(claims, t, label, out_dir):
    """t: {claim_id: {'keys': [...], 'status': ...}} -> X build, rankings and the §7 statistics."""
    R, E, pop = dev_truth(claims)
    by = {c["claim_id"]: c for c in claims}
    x_rows, x_keys, budgets = [], {}, {}
    for cid, c in by.items():
        tk = t[cid]["keys"]
        xk, slots, b = build_x(cid, tk, c["d_keys"], [u for u, _ in c["pool"]])
        x_keys[cid], budgets[cid] = xk, b
        x_rows += [{"claim_id": cid, **s} for s in slots]
    rk = {cid: {"A": rank_with(c["pool"], ()), "D": rank_with(c["pool"], c["d_keys"]),
                "T": rank_with(c["pool"], t[cid]["keys"]), "X": rank_with(c["pool"], x_keys[cid])}
          for cid, c in by.items()}
    hit = lambda cid, m, k: int(bool(R[cid] & {u for u, _ in rk[cid][m][:k]}))
    Ec = sorted(E)
    W = sum(hit(c, "T", 10) - hit(c, "D", 10) for c in Ec)
    tb2 = sum(hit(c, "T", 10) - hit(c, "X", 10) for c in Ec)
    tb3 = sum(hit(c, "T", 20) - hit(c, "D", 20) for c in Ec)
    f = sum(t[c]["status"] == "parse_failure" for c in by) / len(by)
    cfg = load_config()["dev_selection"]
    table = {m: {f"R@{k}": round(sum(hit(c, m, k) for c in Ec) / len(Ec), 4) for k in KS} for m in "ADTX"}
    pair = {}
    for a, b in (("T", "D"), ("T", "X"), ("T", "A"), ("D", "A")):
        w = sum(hit(c, a, 10) > hit(c, b, 10) for c in Ec)
        l = sum(hit(c, a, 10) < hit(c, b, 10) for c in Ec)
        pair[f"{a}-{b}@10"] = {"wins": w, "losses": l, "ties": len(Ec) - w - l}
    bx = [budgets[c]["B_X"] - budgets[c]["B_T"] for c in by if budgets[c]["n_T"]]
    flags = Counter(r["flag"] for r in x_rows)
    res = {"label": label, "population": pop, "N": len(Ec), "n_claims": len(by),
           "f": round(f, 4), "admissible": f <= cfg["f_threshold"],
           "W": W, "S": round(W / len(Ec), 4), "tiebreak_sum_T_minus_X_at10": tb2, "tiebreak_sum_T_minus_D_at20": tb3,
           "table_on_E": table, "pairwise_hit10_on_E": pair,
           "t_status_all320": dict(Counter(t[c]["status"] for c in by)),
           "t_status_on_E": dict(Counter(t[c]["status"] for c in Ec)),
           "t_overlap_with_D_keys": sum(bool(set(t[c]["keys"]) & set(by[c]["d_keys"] or ())) for c in by),
           "x_flags": dict(flags), "x_claims_with_BX_ne_BT": sum(v != 0 for v in bx),
           "x_mean_BX_minus_BT": round(sum(bx) / len(bx), 3) if bx else None,
           "x_median_BX_minus_BT": sorted(bx)[len(bx) // 2] if bx else None,
           "boosted_docs_per_claim_T": round(sum(sum(n for k, n in pool_keys(by[c]["pool"]).items() if k in t[c]["keys"])
                                                 for c in by) / len(by), 3)}
    h1 = write_new_json(out_dir / "x_slots.json", x_rows)
    h2 = write_new_json(out_dir / "x_keys.json", {str(c): {"keys": x_keys[c], **budgets[c]} for c in by})
    h3 = write_new_json(out_dir / "per_claim.json",
                        [{"claim_id": c, "split": by[c]["split"], "eligible": c in E, "t_status": t[c]["status"],
                          **{f"h{k}_{m}": hit(c, m, k) for m in "ADTX" for k in (5, 10, 20)}} for c in sorted(by)])
    res["outputs_sha256"] = {"x_slots.json": h1, "x_keys.json": h2, "per_claim.json": h3}
    write_new_json(out_dir / "score.json", res)
    return res


def cmd_score(version):
    d = RES / "dev" / f"T_v{version}"
    if not (d / "keys.json").exists():
        halt(f"T v{version} not finalised")
    if (d / "score.json").exists():
        halt(f"T v{version} already scored; scoring runs once")
    t = {int(k): v for k, v in json.loads((d / "keys.json").read_text(encoding="utf-8")).items()}
    res = score(load_dev(), t, f"T_v{version}", d)
    log_event("dev_score_done", version=version, keys_sha256=sha256_file(d / "keys.json"),
              **{k: res[k] for k in ("N", "f", "admissible", "W", "S", "tiebreak_sum_T_minus_X_at10",
                                     "tiebreak_sum_T_minus_D_at20", "t_status_all320", "x_flags")})
    print(json.dumps(res, indent=1))


def cmd_dryrun():
    """SYNTHETIC T (not a version, never selectable): T := the pool keys of D's prediction in D's key
    order, as a stand-in to exercise postprocess-shaped input, X and scoring end to end."""
    from t_resolver import postprocess
    claims = load_dev()
    t = {}
    for c in claims:
        pk = list(pool_keys(c["pool"]))
        fake = {"abstain": False, "selections": [{"key": k.upper() + " "} for k in sorted(c["d_keys"] or ())] + [{"key": 7}]}
        keys, status, flags = postprocess(fake, pk)
        t[c["claim_id"]] = {"keys": keys, "status": status, "flags": flags}
    out = RES / "dryrun" / "synthetic_T_from_D"
    res = score(claims, t, "DRYRUN_synthetic_T_from_D (not a T version; exercises code only)", out)
    log_event("dev_dryrun_done", output=rel(out), N=res["N"], population=res["population"],
              x_flags=res["x_flags"], t_status=res["t_status_all320"])
    print(json.dumps({k: res[k] for k in ("population", "N", "f", "t_status_all320", "x_flags",
                                          "x_claims_with_BX_ne_BT")}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["score", "dryrun"])
    ap.add_argument("--version", type=int)
    a = ap.parse_args()
    cmd_score(a.version) if a.cmd == "score" else cmd_dryrun()
