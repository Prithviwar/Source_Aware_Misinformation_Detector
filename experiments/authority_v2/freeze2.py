"""Freeze 2 (preregistration §7, §8): selected prompts and config, all v2 scripts, selection.json and
the leak-check result -> MANIFEST_freeze2.json, before dev.json is downloaded or the reserved
claims are identified.
"""
import json

import leak_check
import verify_manifests
from paths_reserved import DEV_JSON, INPUTS, SEALED
from v2common import CONFIG, MANIFESTS, RES, V2, halt, lib_versions, log_event, now, rel, sha256_file, write_new_json


def main():
    out = MANIFESTS / "MANIFEST_freeze2.json"
    if out.exists():
        halt("MANIFEST_freeze2.json exists; manifests are written once")
    for p in (DEV_JSON, INPUTS, SEALED):
        if p.exists():
            halt(f"{rel(p)} already exists; freeze 2 must precede the download and the reserved sample")
    sel_p = RES / "selection.json"
    if not sel_p.exists():
        halt("selection.json missing")
    sel = json.loads(sel_p.read_text(encoding="utf-8"))
    ver = verify_manifests.require((1,))
    leak = leak_check.check()
    if not leak["pass"]:
        halt("leak check failed", hits=leak["hits"])
    files = sorted(V2.glob("*.py")) + sorted(V2.glob("prompts/*.md")) + [CONFIG, sel_p]
    for p in files:
        if b"\r" in p.read_bytes():
            halt(f"{rel(p)} is not LF-only")
    man = {"freeze": 2, "written_at": now(), "selection": sel, "files": {rel(p): sha256_file(p) for p in files},
           "selected_prompts": ([rel(V2 / "prompts" / f"T_{s}_v{sel['selected_version']}.md") for s in ("system", "user")]
                                if sel.get("family_N_executed") else None),
           "leak_check": leak, "freeze1_verification": ver, "versions": lib_versions()}
    h = write_new_json(out, man)
    log_event("freeze2", manifest=rel(out), manifest_sha256=h, n_files=len(man["files"]),
              family_N_executed=sel.get("family_N_executed"), selected_version=sel.get("selected_version"))
    print(f"freeze 2 written: {rel(out)} sha256={h}")


if __name__ == "__main__":
    main()
