"""Fetch the dev knowledge-store documents for the sampled claims only.

The full dev knowledge store is an 11.5 GB zip on Hugging Face. We read the
zip's central directory over HTTP range requests and stream just the members
for our sampled claim IDs, so nothing close to the full archive is downloaded.

Output: data/raw/averitec/ks_sample/<claim_id>.jsonl.gz, one line per document:
  doc_idx, url, url_norm, text (lines joined, truncated to MAX_CHARS),
  n_chars (original length), ks_type, ks_query.

ks_type/ks_query are kept ONLY for auditing (they reveal which documents are
gold); retrieval code must never read them.
"""
import json
import sys
import time
import zipfile

import fsspec

from common import KS_DIR, KS_ZIP_URL, load_sample, normalize_url, write_jsonl

MAX_CHARS = 50_000


def main():
    KS_DIR.mkdir(parents=True, exist_ok=True)
    ids = [r["claim_id"] for r in load_sample()]
    z = zipfile.ZipFile(fsspec.open(KS_ZIP_URL, block_size=8 * 2**20).open())
    members = {i.filename.split("/")[-1][:-5]: i for i in z.infolist() if i.filename.endswith(".json")}
    t0 = time.time()
    for n, cid in enumerate(ids, 1):
        out = KS_DIR / f"{cid}.jsonl.gz"
        if out.exists():
            continue
        rows = []
        with z.open(members[str(cid)]) as fh:
            for doc_idx, line in enumerate(fh):
                d = json.loads(line)
                text = "\n".join(d.get("url2text") or [])
                rows.append({
                    "doc_idx": doc_idx,
                    "url": d["url"],
                    "url_norm": normalize_url(d["url"]),
                    "text": text[:MAX_CHARS],
                    "n_chars": len(text),
                    "ks_type": d.get("type"),
                    "ks_query": d.get("query"),
                })
        tmp = out.with_suffix(".tmp.gz")
        write_jsonl(tmp, rows)
        tmp.replace(out)
        print(f"[{n}/{len(ids)}] claim {cid}: {len(rows)} docs ({time.time() - t0:.0f}s)", flush=True)
    print("done")


if __name__ == "__main__":
    sys.exit(main())
