"""Development inputs for T/X (preregistration §2.2, §7): the 120 + 200 already-used claims.

Reads ONLY input fields (claim, speaker, date, ISO), the frozen hybrid top-100 pools and the
frozen D predictions. Development gold is read only in dev_score.py.

  python dev_data.py gate    D-recompute gate (§7) + Wikidata-block reconstruction check
"""
import gzip
import json
import re
import sys

from v2common import RES, ROOT, halt, log_event, rel, sha256_file, write_new_json

import authority_resolution as AR
import validation_heldout as V

SPLITS = {  # name: (inputs file, frozen D raw, frozen source_targeted rankings)
    "dev120": (ROOT / "data/processed/averitec_sample.jsonl", ROOT / "results/authority_resolution_raw.jsonl",
               ROOT / "results/source_targeted/rankings_dev.jsonl.gz"),
    "dev200": (ROOT / "data/processed/averitec_heldout.jsonl", ROOT / "results/heldout/authority_raw.jsonl",
               ROOT / "results/source_targeted/rankings_heldout.jsonl.gz"),
}
INPUT_FIELDS = ("claim_id", "claim", "speaker_or_entity", "claim_date", "location_ISO_code")
_WD = re.compile(r"\nCountry \(ISO\): [^\n]*\n(.*)\nReturn JSON", re.S)


def base_fields(r):
    """Prompt fields formatted exactly as frozen cmd_predict / authority_resolution.inputs do."""
    return dict(claim=r["claim"], speaker=r.get("speaker_or_entity") or "None",
                date=r.get("claim_date") or "unknown", iso=r.get("location_ISO_code") or "unknown")


def pool_keys(pool):
    """Distinct non-empty cand_key of the pool -> doc count, in ascending code-point order (U2)."""
    cnt = {}
    for u, _ in pool:
        k = V.cand_key(u)
        if k:
            cnt[k] = cnt.get(k, 0) + 1
    return dict(sorted(cnt.items()))


def _rankings(path, methods):
    out = {m: {} for m in methods}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for r in map(json.loads, fh):
            if r["method"] in methods:
                out[r["method"]][int(r["claim_id"])] = [tuple(x) for x in r["ranked"]]
    return out


def load_dev():
    """List of per-claim dicts in (split, file) order. Input fields only."""
    claims = []
    for split, (inp, raw, rk_path) in SPLITS.items():
        rows = [{k: r.get(k) for k in INPUT_FIELDS} for r in map(json.loads, open(inp, encoding="utf-8"))]
        preds = V.load_preds(raw)
        prompts = {}
        for x in map(json.loads, open(raw, encoding="utf-8")):
            if x.get("cond") == "L+Wctx":
                prompts.setdefault(int(x["claim_id"]), x["prompt"])
        rk = _rankings(rk_path, ("hybrid", "hybrid+llm_authority"))
        for r in rows:
            cid = int(r["claim_id"])
            claims.append({"claim_id": cid, "split": split, "inputs": r, "d_prompt": prompts.get(cid),
                           "d_keys": preds[cid]["keys"] if cid in preds else None,
                           "pool": rk["hybrid"][cid][:V.POOL],
                           "stored_D": [u for u, _ in rk["hybrid+llm_authority"][cid]]})
    ids = [c["claim_id"] for c in claims]
    if len(ids) != 320 or len(set(ids)) != 320:
        halt(f"development set is not 320 distinct claims ({len(ids)}, {len(set(ids))} distinct)")
    return claims


def wd_block(c):
    """D's Wikidata block, copied verbatim from D's stored prompt (§2.2), checked by reconstruction."""
    m = _WD.search(c["d_prompt"] or "")
    if not m:
        return None
    wd = m.group(1)
    return wd if AR.USER.format(**base_fields(c["inputs"]), wd=wd) == c["d_prompt"] else None


def rank_with(pool, keys):
    """Frozen rerank: minmax(hybrid score in pool) + 1.0 * 1[cand_key in keys], stable."""
    keys = set(keys or ())
    return V.rerank(pool, lambda u: float(V.cand_key(u) in keys))


def gate():
    out = RES / "dev" / "d_recompute_gate.json"
    claims = load_dev()
    # dev200 pools must equal the frozen full hybrid ranking's top-100 (urls and scores)
    full = V.load_rk("hybrid", True)
    pool_mismatch = [c["claim_id"] for c in claims if c["split"] == "dev200"
                     and [tuple(x) for x in full[c["claim_id"]][:V.POOL]] != c["pool"]]
    d_mismatch, a_mismatch, no_pred, wd_fail, short_pool = [], [], [], [], []
    for c in claims:
        if c["d_keys"] is None:
            no_pred.append(c["claim_id"])
        if [u for u, _ in rank_with(c["pool"], c["d_keys"])] != c["stored_D"]:
            d_mismatch.append(c["claim_id"])
        if [u for u, _ in rank_with(c["pool"], ())] != [u for u, _ in c["pool"]]:
            a_mismatch.append(c["claim_id"])
        if wd_block(c) is None:
            wd_fail.append(c["claim_id"])
        if len(c["pool"]) < V.POOL:
            short_pool.append(c["claim_id"])
    res = {"n": len(claims), "by_split": {s: sum(c["split"] == s for c in claims) for s in SPLITS},
           "D_recomputed_equals_stored_hybrid+llm_authority": not d_mismatch, "D_mismatch": d_mismatch,
           "A_equals_hybrid_top100_order": not a_mismatch, "A_mismatch": a_mismatch,
           "dev200_pool_equals_frozen_full_hybrid_top100": not pool_mismatch, "pool_mismatch": pool_mismatch,
           "wikidata_block_reconstructs_D_prompt": not wd_fail, "wd_fail": wd_fail,
           "claims_without_parsed_D": no_pred, "claims_with_pool_lt_100": short_pool,
           "inputs_sha256": {rel(p): sha256_file(p) for s in SPLITS.values() for p in s}}
    res["pass"] = not (d_mismatch or a_mismatch or pool_mismatch or wd_fail)
    write_new_json(out, res)
    log_event("dev_d_recompute_gate", output=rel(out), **{k: v for k, v in res.items() if k != "inputs_sha256"})
    print(json.dumps({k: v for k, v in res.items() if k != "inputs_sha256"}, indent=1))
    if not res["pass"]:
        halt("development D-recompute gate failed")


if __name__ == "__main__":
    {"gate": gate}[sys.argv[1]]()
