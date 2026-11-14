"""Family R: reserved-set replication of the preregistered procedure (preregistration §4.1).

Only path constants of the frozen modules are reassigned (paths_reserved.redirect); the frozen
function bodies cmd_extract, cmd_rank, cmd_wikidata, cmd_predict, cmd_probe and analyse/_write
run unmodified. Sealed reserved records are opened only by `score`, after freezes 1-3 verify and
an approval entry is logged.

  python family_R_replication.py copy-wikidata | extract | rank | wikidata | predict [--resume]
  python family_R_replication.py probe [--resume]     (needs a logged probe_gate_approved entry)
  python family_R_replication.py score                (needs freeze 3 + reserved_gold_gate_approved)
"""
import json
import os
import shutil
import sys
import urllib.request

import verify_manifests
from paths_reserved import HO_RES, INPUTS, KS_RESERVED, SEALED, WD_COPY, WD_DIR, WD_FROZEN, redirect
from v2common import halt, log_event, read_log, rel, sha256_file, write_new_json

import common
import validation_heldout as V

RESUME = "--resume" in sys.argv


def _pre():
    verify_manifests.require((1, 2))
    red = redirect()
    return {k: str(v) for k, v in red.items()}


def _summ_calls(path):
    recs = [json.loads(l) for l in open(path, encoding="utf-8")]
    ok = {r["claim_id"] for r in recs if r.get("pred")}
    return {"n_records": len(recs), "n_parsed_claims": len(ok), "cost_usd": round(sum(r.get("cost") or 0 for r in recs), 4),
            "models": sorted({m for r in recs for m in (r.get("model") or [])}), "raw_sha256": sha256_file(path)}


def copy_wikidata():
    _pre()
    if WD_COPY.exists():
        halt(f"{rel(WD_COPY)} exists")
    h0 = sha256_file(WD_FROZEN)
    WD_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(WD_FROZEN, WD_COPY)
    log_event("wikidata_copy", frozen=rel(WD_FROZEN), frozen_sha256=h0, copy=rel(WD_COPY), copy_sha256=sha256_file(WD_COPY))


def extract():
    red = _pre()
    head = {}
    try:  # U7: record the remote KS file's ETag/size; proceed if changed; a missing member stops cmd_extract
        req = urllib.request.Request(common.KS_ZIP_URL, method="HEAD", headers={"User-Agent": "authority-v2-study"})
        with urllib.request.urlopen(req, timeout=120) as r:
            head = {k: r.headers.get(k) for k in ("ETag", "Content-Length", "X-Linked-Etag", "X-Linked-Size", "Last-Modified")}
            head["status"] = r.status
    except Exception as e:
        head = {"error": repr(e)}
    log_event("ks_extract_start", remote=head, redirect=red)
    V.cmd_extract()
    files = sorted(KS_RESERVED.glob("*.jsonl.gz"))
    log_event("ks_extract_done", n_files=len(files))


def rank():
    red = _pre()
    if any((HO_RES / f"rankings_{m}.jsonl.gz").exists() for m in ("bm25", "dense", "hybrid")) and not RESUME:
        halt("reserved rankings exist")
    os.environ["HF_HUB_OFFLINE"] = "1"  # MiniLM is cached locally (§9 step 10)
    log_event("rank_start", redirect=red, hf_hub_offline=True)
    V.cmd_rank()
    log_event("rank_done", **{f"rankings_{m}": sha256_file(HO_RES / f"rankings_{m}.jsonl.gz") for m in ("bm25", "dense", "hybrid")})


def wikidata():
    red = _pre()
    if not WD_COPY.exists():
        halt("run copy-wikidata first")
    h_frozen = sha256_file(WD_FROZEN)
    before = json.load(open(WD_COPY, encoding="utf-8"))
    log_event("wikidata_start", redirect=red, n_cache_before=len(before))
    V.cmd_wikidata()
    after = json.load(open(WD_COPY, encoding="utf-8"))
    orig = json.load(open(WD_FROZEN, encoding="utf-8"))
    diff = {"added_keys": sorted(set(after) - set(orig)), "removed_keys": sorted(set(orig) - set(after)),
            "changed_keys": sorted(k for k in set(orig) & set(after) if orig[k] != after[k])}
    if sha256_file(WD_FROZEN) != h_frozen:
        halt("the frozen Wikidata cache changed")
    h = write_new_json(WD_DIR / "diff_vs_frozen.json", diff)
    log_event("wikidata_done", n_new_mentions=len(diff["added_keys"]), n_changed=len(diff["changed_keys"]),
              n_removed=len(diff["removed_keys"]), diff_sha256=h, copy_sha256=sha256_file(WD_COPY),
              frozen_sha256_unchanged=h_frozen, mentions_sha256=sha256_file(HO_RES / "wikidata_claim_mentions.json"))


def predict():
    red = _pre()
    if V.PRED_RAW.exists() and not RESUME:
        halt("reserved D predictions exist; the frozen predictor runs once (--resume only after a crash)")
    log_event("reserved_D_start" if not RESUME else "reserved_D_resume", redirect=red)
    V.cmd_predict()
    log_event("reserved_D_done", **_summ_calls(V.PRED_RAW))


def probe():
    red = _pre()
    if not any(e["event"] == "probe_gate_approved" for e in read_log()):
        halt("probe gate: no probe_gate_approved entry in the execution log")
    if V.PROBE_RAW.exists() and not RESUME:
        halt("probe output exists; the probe runs once (--resume only after a crash)")
    log_event("probe_start" if not RESUME else "probe_resume", redirect=red)
    V.cmd_probe()
    log_event("probe_done", **_summ_calls(V.PROBE_RAW))


# ------------------------------------------------------------------ scoring (only place the sealed file is opened)
def merged_sample():
    """Inputs + sealed full records merged in memory (input fields must agree)."""
    inputs = [json.loads(l) for l in open(INPUTS, encoding="utf-8")]
    full = {int(r["claim_id"]): r for r in map(json.loads, open(SEALED, encoding="utf-8"))}
    if [int(r["claim_id"]) for r in inputs] != list(full):
        halt("inputs and sealed records differ in claims or order")
    bad = [r["claim_id"] for r in inputs if any(full[int(r["claim_id"])][k] != v for k, v in r.items())]
    if bad:
        halt("inputs and sealed records disagree on input fields", claims=bad)
    return [full[int(r["claim_id"])] for r in inputs]


def probe_dict():
    """Exactly cmd_evaluate's construction, or None if the probe was not executed (R-D10)."""
    ran = any(e["event"] == "probe_done" for e in read_log())
    if not ran or not V.PROBE_RAW.exists():
        return None
    probe = {}
    for line in open(V.PROBE_RAW, encoding="utf-8"):
        x = json.loads(line)
        if x.get("pred"):
            probe[int(x["claim_id"])] = x["pred"]
    return probe


NOT_RUN = "Probe not executed; the 'only holds on the recognised subset' example in rule B could not be evaluated"


def decide(out, probe_executed):
    """Approved operational reading (U10, rule C, U11)."""
    pe = out["primary_endpoint"]
    t4 = next(s for s in out["secondary_family_holm"] if s["test"] == "R@10 vs generic")
    if pe["diff_R@10"] <= 0:
        cls = "C"
    elif pe["p"] < 0.05 and pe["bootstrap95CI"][0] > 0 and t4["diff"] > 0 and t4["p_holm"] < 0.05:
        cls = "A"
    else:
        cls = "B"
    notes = []
    if not probe_executed:
        notes.append(NOT_RUN)
        if cls == "A":
            notes.append("The recognised-subset check could not be performed.")
    return {"outcome": cls,
            "criteria": {"primary_p": pe["p"], "primary_diff_R@10": pe["diff_R@10"], "primary_CI": pe["bootstrap95CI"],
                         "test4_R@10_vs_generic_diff": t4["diff"], "test4_p_holm": t4["p_holm"]},
            "rule": "A: p<0.05, CI lower>0, test4 diff>0 and p_holm<0.05; C: diff_R@10<=0; B: diff>0 and not A",
            "probe_executed": probe_executed, "notes": notes}


def score():
    ver = verify_manifests.require((1, 2, 3))
    if not any(e["event"] == "reserved_gold_gate_approved" for e in read_log()):
        halt("reserved-gold gate: no reserved_gold_gate_approved entry in the execution log")
    redirect()
    stem = HO_RES / "family_R"
    for p in (stem.with_suffix(".json"), stem.with_suffix(".csv"), HO_RES / "family_R_decision.json",
              HO_RES / "probe_status.json"):
        if p.exists():
            halt(f"{rel(p)} exists; one scoring pass per family")
    probe = probe_dict()
    write_new_json(HO_RES / "probe_status.json",
                   {"probe_executed": probe is not None,
                    "n_probed": len(probe) if probe is not None else 0,
                    "analyse_probe_argument": "dict built as cmd_evaluate" if probe is not None else "None (R-D10)"})
    log_event("family_R_score_start", verification=ver, sealed_sha256=sha256_file(SEALED),
              probe_executed=probe is not None)
    sample = merged_sample()
    out = V.analyse(sample, True, V.load_preds(V.PRED_RAW), probe=probe)
    dec = decide(out, probe is not None)
    V._write(out, stem)  # frozen writer -> family_R.json / family_R.csv
    h = write_new_json(HO_RES / "family_R_decision.json", dec)
    log_event("family_R_score_done", outcome=dec["outcome"], criteria=dec["criteria"], decision_sha256=h,
              json_sha256=sha256_file(stem.with_suffix(".json")), csv_sha256=sha256_file(stem.with_suffix(".csv")),
              n_claims=out["n_claims"], n_gold_reachable=out["n_gold_reachable"],
              n_missing_predictions=out["n_missing_predictions"])
    print(json.dumps(dec, indent=1))


if __name__ == "__main__":
    {"copy-wikidata": copy_wikidata, "extract": extract, "rank": rank, "wikidata": wikidata, "predict": predict,
     "probe": probe, "score": score}[sys.argv[1]]()
