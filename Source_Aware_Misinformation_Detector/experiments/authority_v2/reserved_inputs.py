"""Reserved-set inputs for T/X (gold-blind): input fields, the reserved hybrid top-100 pools, the
reserved D predictions, and the Wikidata block D received (frozen wd_context over the experiment
cache). Never opens the sealed file.
"""
import json

from paths_reserved import HO_RES, INPUTS, WD_COPY

import authority_resolution as AR
import validation_heldout as V
from dev_data import base_fields

N_RESERVED = 180


def load_reserved():
    rows = [json.loads(l) for l in open(INPUTS, encoding="utf-8")]
    preds = V.load_preds(HO_RES / "authority_raw.jsonl")
    prompts = {}
    for x in map(json.loads, open(HO_RES / "authority_raw.jsonl", encoding="utf-8")):
        if x.get("cond") == "L+Wctx":
            prompts.setdefault(int(x["claim_id"]), x["prompt"])
    hyb = V.load_rk("hybrid", True) if V.HO == HO_RES else None
    if hyb is None:
        raise RuntimeError("paths_reserved.redirect() must be called first")
    cache = json.load(open(WD_COPY, encoding="utf-8"))
    ment = json.load(open(HO_RES / "wikidata_claim_mentions.json", encoding="utf-8"))
    claims = []
    for r in rows:
        cid = int(r["claim_id"])
        wd = AR.wd_context(ment[str(cid)]["mentions"], cache)
        claims.append({"claim_id": cid, "split": "reserved", "inputs": r, "wd": wd,
                       "d_prompt": prompts.get(cid), "d_keys": preds[cid]["keys"] if cid in preds else None,
                       "pool": hyb[cid][:V.POOL],
                       # D and T must receive the same Wikidata string
                       "wd_matches_D": prompts.get(cid) == AR.USER.format(**base_fields(r), wd=wd)})
    if len(claims) != N_RESERVED:
        raise RuntimeError(f"reserved inputs: {len(claims)} claims, expected {N_RESERVED}")
    return claims
