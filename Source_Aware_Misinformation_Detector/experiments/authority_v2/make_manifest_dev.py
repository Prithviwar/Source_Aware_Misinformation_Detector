"""MANIFEST_dev_v{k}.json (preregistration §7): hashes version k's prompts, config and resolver
before its first call. Requires freeze 1, a passing hash gate, a passing D-recompute gate, a
passing leak check, and (for k > 1) a finished, scored previous version plus the owner's
decision in the decision log (DL-011).

  python make_manifest_dev.py --version 1
"""
import argparse
import json

import hash_gate
import leak_check
from v2common import (CONFIG, DECISION_LOG, MANIFESTS, RES, V2, halt, lib_versions, log_event, now, read_log, rel,
                      sha256_file, write_new_json)


def main(k):
    out = MANIFESTS / f"MANIFEST_dev_v{k}.json"
    if out.exists():
        halt(f"{rel(out)} exists; manifests are written once")
    if not (MANIFESTS / "MANIFEST_freeze1.json").exists():
        halt("freeze 1 missing")
    if k > 3:
        halt("at most 3 development versions")
    if k > 1:
        if not (RES / "dev" / f"T_v{k - 1}" / "score.json").exists():
            halt(f"V{k} may follow only a completed and scored V{k - 1}")
        if not any(e["event"] == "owner_decision_dev_versions" and k in e.get("approved_versions", [])
                   for e in read_log()):
            halt(f"no logged owner decision approving V{k} (DL-011); append it to {rel(DECISION_LOG)} and the log")
    gate = hash_gate.check()
    if not gate["pass"]:
        halt("hash gate failed")
    if not any(e["event"] == "dev_d_recompute_gate" and e.get("pass") for e in read_log()):
        halt("development D-recompute gate has not passed")
    leak = leak_check.check()
    if not leak["pass"]:
        halt("leak check failed", hits=leak["hits"])
    files = [V2 / "prompts" / f"T_system_v{k}.md", V2 / "prompts" / f"T_user_v{k}.md", CONFIG,
             V2 / "t_resolver.py", V2 / "dev_data.py", V2 / "x_control.py", V2 / "dev_score.py", V2 / "v2common.py"]
    for p in files:
        if b"\r" in p.read_bytes():
            halt(f"{rel(p)} is not LF-only")
    man = {"manifest": f"dev_v{k}", "written_at": now(), "files": {rel(p): sha256_file(p) for p in files},
           "hash_gate_pass": True, "git_head": gate["git_head"], "leak_check": leak, "versions": lib_versions()}
    h = write_new_json(out, man)
    log_event("manifest_dev", version=k, manifest=rel(out), manifest_sha256=h, files=man["files"])
    print(json.dumps(man["files"], indent=1), "\nmanifest sha256", h)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True)
    main(ap.parse_args().version)
