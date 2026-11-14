"""Freeze 3 (preregistration §8.3): before any reserved gold is read. Hashes the reserved inputs, KS
extracts, rankings, Wikidata cache/diff/mentions, D/T/X outputs, probe outputs (if any) and the raw
bytes of the sealed file (compared with the hash recorded at write time; contents are not parsed).
"""
import json

import verify_manifests
from paths_reserved import HO_RES, INPUTS, KS_RESERVED, SEALED, WD_COPY, WD_DIR
from v2common import MANIFESTS, ROOT, halt, log_event, now, read_log, rel, sha256_file, write_new_json


def main():
    out = MANIFESTS / "MANIFEST_freeze3.json"
    if out.exists():
        halt("MANIFEST_freeze3.json exists; manifests are written once")
    ver = verify_manifests.require((1, 2))
    sel = json.loads((ROOT / "results/authority_v2/selection.json").read_text(encoding="utf-8"))
    ks = sorted(KS_RESERVED.glob("*.jsonl.gz"))
    if len(ks) != 180:
        halt(f"{len(ks)} KS extracts, expected 180")
    req = [INPUTS, *ks, *(HO_RES / f"rankings_{m}.jsonl.gz" for m in ("bm25", "dense", "hybrid")),
           WD_COPY, WD_DIR / "diff_vs_frozen.json", HO_RES / "wikidata_claim_mentions.json", HO_RES / "authority_raw.jsonl"]
    if sel.get("family_N_executed"):
        req += [HO_RES / "T" / f for f in ("raw.jsonl", "keys.json", "summary.json")]
        req += [HO_RES / "X" / f for f in ("x_keys.json", "x_slots.json", "summary.json")]
    probe_ran = any(e["event"] == "probe_done" for e in read_log())
    if probe_ran:
        req.append(HO_RES / "memorisation_probe_raw.jsonl")
    missing = [rel(p) for p in req if not p.exists()]
    if missing:
        halt("freeze 3 incomplete", missing=missing)
    recorded = [e for e in read_log() if e["event"] == "reserved_sample_built"]
    sealed_now = sha256_file(SEALED)
    if not recorded or recorded[-1]["sealed_sha256_at_write"] != sealed_now:
        halt("sealed file hash differs from the hash recorded at write time")
    man = {"freeze": 3, "written_at": now(), "files": {rel(p): sha256_file(p) for p in req},
           "sealed_raw_sha256": sealed_now, "sealed_path": rel(SEALED), "probe_executed": probe_ran,
           "family_N_executed": sel.get("family_N_executed"), "freeze1_2_verification": ver}
    man["files"][rel(SEALED)] = sealed_now
    h = write_new_json(out, man)
    log_event("freeze3", manifest=rel(out), manifest_sha256=h, n_files=len(man["files"]), probe_executed=probe_ran)
    print(f"freeze 3 written: {rel(out)} sha256={h}")


if __name__ == "__main__":
    main()
