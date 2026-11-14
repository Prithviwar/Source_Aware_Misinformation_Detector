"""Re-verification of freezes 1-3 and the frozen-file table (preregistration §8.4).

The decision log is append-only, so freeze 1's decision-log hash must match a line-boundary
prefix of the current file; every other recorded file must match exactly.
"""
import json

import hash_gate
from v2common import DECISION_LOG, MANIFESTS, ROOT, halt, sha256_bytes, sha256_file


def _prefix_match(path, digest):
    b = path.read_bytes()
    cut = [i + 1 for i, ch in enumerate(b) if ch == 0x0A]
    return any(sha256_bytes(b[:i]) == digest for i in cut)


def verify(stages=(1, 2, 3)):
    res, ok = {}, True
    g = hash_gate.check()
    res["frozen_file_gate"] = g["pass"]
    ok &= g["pass"]
    for k in stages:
        p = MANIFESTS / f"MANIFEST_freeze{k}.json"
        if not p.exists():
            res[f"freeze{k}"] = "missing"
            ok = False
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        if k == 1:
            files = {**m["documents"], **m["development_inputs_raw_sha256"],
                     **m["wrapped_modules_without_recorded_hash_raw_sha256"]}
        else:
            files = m["files"]
        bad = []
        for f, h in files.items():
            fp = ROOT / f
            if not fp.exists():
                bad.append(f + " (missing)")
            elif fp == DECISION_LOG:
                if not _prefix_match(fp, h):
                    bad.append(f + " (freeze-time content is no longer a prefix)")
            elif sha256_file(fp) != h:
                bad.append(f)
        res[f"freeze{k}"] = {"n_files": len(files), "differing": bad, "manifest_sha256": sha256_file(p)}
        ok &= not bad
    res["pass"] = ok
    return res


def require(stages=(1, 2, 3)):
    r = verify(stages)
    if not r["pass"]:
        halt("manifest verification failed", result=r)
    return r


if __name__ == "__main__":
    import sys
    st = tuple(int(x) for x in sys.argv[1:]) or (1, 2, 3)
    print(json.dumps(verify(st), indent=1))
