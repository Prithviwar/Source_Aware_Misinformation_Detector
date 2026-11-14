"""Step R2 (NETWORK - REQUIRES OWNER APPROVAL; NOT RUN): stream the sampled train claims'
knowledge-store members from the AVeriTeC train zips with HTTP range requests.

  python experiments/esa_nov2026/relevance_baseline/extract_train_ks_sample.py --preflight
  python experiments/esa_nov2026/relevance_baseline/extract_train_ks_sample.py --approved \
         --zip-url <URL of train knowledge-store zip 1> [--zip-url <zip 2> ...]

Same method as the frozen experiments/extract_knowledge_store.py (dev): read each zip's central
directory remotely and stream only the members for the sampled claims. The full ~62 GB archives
are NOT downloaded. Exact zip URLs must be copied from the Hugging Face tree of chenxwh/AVeriTeC
(data_store/knowledge_store/...) by the owner; they are not guessed here.

Estimated volume (EST, extrapolated from dev: 320 claims ~ 1.4 GB gzip): ~4.4 MB per claim,
so N_SAMPLE = 300 claims ~ 1.3 GB on disk plus range-request traffic. Preflight checks free space.

Output: storage/datasets/averitec_train_ks_sample/<train_idx>.jsonl.gz with the same fields as the
dev extracts. ks_type / ks_query are kept ONLY for audit; feature code never reads them.
"""
import argparse
import json
import shutil
import sys
import time
import zipfile

from rb_common import SPLIT_MANIFEST, STORAGE, TRAIN_KS_DIR

EST_MB_PER_CLAIM = 4.4
SAFETY_GB = 5.0
HF_REVISION = "2ca9dee23a2a6fa64c5bd918e0cd28ed0aa09031"   # chenxwh/AVeriTeC, verified 2026-11-08, licence cc-by-nc-4.0
OFFICIAL_ZIPS = {  # path -> (bytes, LFS sha256) as reported by the Hugging Face API at HF_REVISION
    "train_0_999.zip": (20730339734, "389d2284c5f25410205ec530c2101c3e6d575eae460731e1909ad19192dcb810"),
    "train_1000_1999.zip": (21273604733, "e2bf5c1dccc855cf3474ccd3f14678fe60f21e6c69685a34d7bc884996fec446"),
    "train_2000_3067.zip": (21520772573, "d3e27cc4072cd085dbac44272f1ea918dd3ff970b39d94f143e40c51bbde43d0"),
}


def official_url(name):
    return f"https://huggingface.co/chenxwh/AVeriTeC/resolve/{HF_REVISION}/data_store/knowledge_store/train/{name}"


def preflight(n):
    free = shutil.disk_usage(STORAGE).free / 2**30
    need = n * EST_MB_PER_CLAIM / 1024
    print(f"free on C: {free:.1f} GB | estimated extract size {need:.2f} GB (EST) | safety margin {SAFETY_GB} GB")
    print(f"output dir: {TRAIN_KS_DIR}")
    ok = free - need > SAFETY_GB
    print("preflight:", "OK" if ok else "INSUFFICIENT SPACE")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--approved", action="store_true", help="owner approval recorded for this network step")
    ap.add_argument("--zip-url", action="append", default=[], help="default: the 3 official pinned train zips")
    a = ap.parse_args()
    if not SPLIT_MANIFEST.exists():
        sys.exit("run make_train_split.py first")
    man = json.load(open(SPLIT_MANIFEST, encoding="utf-8"))
    ids = sorted(i for v in man["split"].values() for i in v)
    if not preflight(len(ids)) or a.preflight:
        return
    if not a.approved:
        sys.exit("Network extraction needs explicit owner approval (--approved).")
    a.zip_url = a.zip_url or [official_url(n) for n in OFFICIAL_ZIPS]
    import hashlib
    import fsspec
    from common import normalize_url, write_jsonl
    from rb_common import OUT
    log = open(OUT / "extraction_log.jsonl", "a", encoding="utf-8")
    from extract_knowledge_store import MAX_CHARS
    TRAIN_KS_DIR.mkdir(parents=True, exist_ok=True)
    todo = {str(i) for i in ids if not (TRAIN_KS_DIR / f"{i}.jsonl.gz").exists()}
    t0 = time.time()
    for url in a.zip_url:
        z = zipfile.ZipFile(fsspec.open(url, block_size=8 * 2**20).open())
        members = {m.filename.split("/")[-1][:-5]: m for m in z.infolist() if m.filename.endswith(".json")}
        for cid in sorted(todo & set(members), key=int):
            rows = []
            with z.open(members[cid]) as fh:
                for doc_idx, line in enumerate(fh):
                    d = json.loads(line)
                    text = "\n".join(d.get("url2text") or [])
                    rows.append({"doc_idx": doc_idx, "url": d["url"], "url_norm": normalize_url(d["url"]),
                                 "text": text[:MAX_CHARS], "n_chars": len(text),
                                 "ks_type": d.get("type"), "ks_query": d.get("query")})
            out = TRAIN_KS_DIR / f"{cid}.jsonl.gz"
            tmp = out.with_suffix(".tmp.gz")
            write_jsonl(tmp, rows)
            tmp.replace(out)
            m = members[cid]
            log.write(json.dumps({"train_idx": int(cid), "zip_url": url, "member": m.filename, "member_crc32": m.CRC,
                                  "member_bytes": m.file_size, "member_compressed_bytes": m.compress_size,
                                  "n_docs": len(rows), "n_empty_text": sum(not r["text"].strip() for r in rows),
                                  "out_file": out.name, "out_bytes": out.stat().st_size,
                                  "out_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                                  "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")
            log.flush()
            todo.discard(cid)
            print(f"train claim {cid}: {len(rows)} docs ({time.time() - t0:.0f}s, {len(todo)} left)", flush=True)
    print("missing after all zips:", sorted(todo, key=int)[:20], "..." if len(todo) > 20 else "")


if __name__ == "__main__":
    main()
