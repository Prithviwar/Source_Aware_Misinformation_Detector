"""Step 14a: X on the reserved set from the finished reserved T (gold-blind, §2.2)."""
import json
from collections import Counter

import verify_manifests
from paths_reserved import HO_RES, redirect
from v2common import halt, log_event, rel, write_new_json
from reserved_inputs import load_reserved
from x_control import build_x


def main():
    verify_manifests.require((1, 2))
    redirect()
    t_path, out = HO_RES / "T" / "keys.json", HO_RES / "X"
    if not t_path.exists():
        halt("reserved T not finalised")
    if (out / "x_keys.json").exists():
        halt("reserved X exists")
    t = json.loads(t_path.read_text(encoding="utf-8"))
    rows, keys = [], {}
    for c in load_reserved():
        x, slots, b = build_x(c["claim_id"], t[str(c["claim_id"])]["keys"], c["d_keys"], [u for u, _ in c["pool"]])
        keys[str(c["claim_id"])] = {"keys": x, **b}
        rows += [{"claim_id": c["claim_id"], **s} for s in slots]
    bx = [v["B_X"] - v["B_T"] for v in keys.values() if v["n_T"]]
    summ = {"n_claims": len(keys), "n_claims_with_T_keys": len(bx), "slot_flags": dict(Counter(r["flag"] for r in rows)),
            "claims_BX_ne_BT": sum(v != 0 for v in bx), "mean_BX_minus_BT": round(sum(bx) / len(bx), 3) if bx else None,
            "median_BX_minus_BT": sorted(bx)[len(bx) // 2] if bx else None,
            "distribution_BX_minus_BT": dict(sorted(Counter(bx).items()))}
    h1 = write_new_json(out / "x_keys.json", keys)
    h2 = write_new_json(out / "x_slots.json", rows)
    write_new_json(out / "summary.json", {**summ, "x_keys_sha256": h1, "x_slots_sha256": h2})
    log_event("reserved_x_done", output=rel(out), **summ)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
