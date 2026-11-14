"""Freeze 1 (preregistration §8.3): write MANIFEST_freeze1.json once, after the hash gate passes.

Records raw SHA-256 of the preregistration, config and decision log, of every development
input without a recorded freeze hash, and of the wrapped frozen modules without one.
"""
import hash_gate
from v2common import (CONFIG, DECISION_LOG, MANIFESTS, PREREG, ROOT, V2, git, halt, lib_versions, log_event,
                      now, rel, sha256_file, write_new_json)

DEV_INPUTS = [
    "results/wikidata_resolution.json", "results/wikidata_claim_authorities.json",
    "results/heldout/wikidata_claim_mentions.json", "results/source_targeted/rankings_dev.jsonl.gz",
    "results/source_targeted/per_claim_dev.csv", "results/authority_resolution_raw.jsonl",
    "results/heldout/authority_raw.jsonl", "results/heldout/rankings_bm25.jsonl.gz",
    "results/heldout/rankings_dense.jsonl.gz", "results/heldout/rankings_hybrid.jsonl.gz",
    "data/processed/averitec_sample.jsonl", "data/processed/averitec_heldout.jsonl",
]
WRAPPED = ["experiments/common.py", "experiments/wikidata_authority.py", "experiments/build_sample.py",
           "experiments/extract_knowledge_store.py"]


def main():
    out = MANIFESTS / "MANIFEST_freeze1.json"
    if out.exists():
        halt("MANIFEST_freeze1.json already exists; manifests are written once")
    gate = hash_gate.check()
    if not gate["pass"]:
        halt("hash gate failed; freeze 1 not taken", gate={k: v for k, v in gate.items() if k != "files"})
    for p in (PREREG, DECISION_LOG, CONFIG):
        if b"\r" in p.read_bytes():
            halt(f"{rel(p)} is not LF-only")
    h = lambda paths: {p: sha256_file(ROOT / p) for p in paths}
    man = {
        "freeze": 1, "written_at": now(), "git_head": gate["git_head"],
        "convention": "raw-byte SHA-256; frozen files verified against original records (form reported)",
        "documents": {rel(p): sha256_file(p) for p in (PREREG, CONFIG, DECISION_LOG)},
        "development_inputs_raw_sha256": h(DEV_INPUTS),
        "wrapped_modules_without_recorded_hash_raw_sha256": h(WRAPPED),
        "v2_code_at_freeze1": {rel(p): sha256_file(p) for p in sorted(V2.glob("*.py"))},
        "frozen_file_gate": gate,
        "versions": lib_versions(),
        "untracked_status": git("status", "--porcelain").splitlines(),
    }
    digest = write_new_json(out, man)
    log_event("freeze1", manifest=rel(out), manifest_sha256=digest, documents=man["documents"])
    print(f"freeze 1 written: {rel(out)} sha256={digest}")


if __name__ == "__main__":
    main()
