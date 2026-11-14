"""Step R2b (offline): verify the train knowledge-store extraction and write the extraction manifest.

  python experiments/esa_nov2026/relevance_baseline/verify_extraction.py

Checks:
  * exactly the 300 frozen-split train claims were extracted (no extra, none missing);
  * each output file's SHA-256 / size matches the extraction log;
  * per-claim document counts and empty-text counts;
  * alignment: the claim's own AVeriTeC train evidence URLs are present in its extracted file.
    This confirms that zip member <i>.json belongs to train.json[i]. It uses the train split's
    evidence URLs, which this approved task may read. No dev, reserved or sealed data is read.
No model is trained. Writes results/esa_nov2026/relevance_baseline/EXTRACTION_MANIFEST.{json,md}.
"""
import hashlib
import json
from collections import Counter

from rb_common import OUT, SPLIT_MANIFEST, TRAIN_JSON, TRAIN_KS_DIR


def main():
    from build_sample import normalise
    from common import read_jsonl
    man = json.load(open(SPLIT_MANIFEST, encoding="utf-8"))
    part_of = {i: p for p, ids in man["split"].items() for i in ids}
    log = {}
    for line in open(OUT / "extraction_log.jsonl", encoding="utf-8"):
        x = json.loads(line)
        log[x["train_idx"]] = x  # last entry wins
    files = sorted(int(p.name.split(".")[0]) for p in TRAIN_KS_DIR.glob("*.jsonl.gz"))
    train = json.load(open(TRAIN_JSON, encoding="utf-8"))
    rows, problems = [], []
    tot = Counter()
    for i in files:
        p = TRAIN_KS_DIR / f"{i}.jsonl.gz"
        b = p.read_bytes()
        sha = hashlib.sha256(b).hexdigest()
        docs = read_jsonl(p)
        urls = {d["url_norm"] for d in docs}
        nonempty = {d["url_norm"] for d in docs if d["text"].strip()}
        gold = {g["source_url_norm"] for g in normalise(i, train[i])["gold_evidence"] if g["is_web_source"]}
        L = log.get(i)
        if i not in part_of:
            problems.append(f"{i}: not in frozen split")
        if not L:
            problems.append(f"{i}: no extraction-log entry")
        elif L["out_sha256"] != sha or L["out_bytes"] != len(b):
            problems.append(f"{i}: hash/size differs from extraction log")
        r = {"train_idx": i, "split_part": part_of.get(i), "file": p.name, "bytes": len(b), "sha256": sha,
             "n_docs": len(docs), "n_empty_text": len(docs) - sum(bool(d["text"].strip()) for d in docs),
             "n_web_evidence_urls": len(gold), "n_evidence_urls_in_file": len(gold & urls),
             "n_evidence_urls_nonempty": len(gold & nonempty),
             "source_member": (L or {}).get("member"), "source_zip": (L or {}).get("zip_url"),
             "member_crc32": (L or {}).get("member_crc32"), "member_bytes": (L or {}).get("member_bytes")}
        rows.append(r)
        for k in ("bytes", "n_docs", "n_empty_text", "n_web_evidence_urls", "n_evidence_urls_in_file",
                  "n_evidence_urls_nonempty"):
            tot[k] += r[k]
    missing = sorted(set(part_of) - set(files))
    by_part = {p: {"claims": sum(r["split_part"] == p for r in rows),
                   "claims_with_>=1_nonempty_evidence_doc": sum(r["split_part"] == p and r["n_evidence_urls_nonempty"] > 0
                                                                 for r in rows)}
               for p in ("fit", "validation", "test")}
    out = {
        "status": "OK" if not problems and not missing else "PROBLEMS",
        "source": {"repo": "huggingface.co/chenxwh/AVeriTeC", "revision": "2ca9dee23a2a6fa64c5bd918e0cd28ed0aa09031",
                   "licence": "CC BY-NC 4.0 (repository card: license cc-by-nc-4.0)",
                   "zips": "data_store/knowledge_store/train/train_{0_999,1000_1999,2000_3067}.zip (only selected members "
                           "streamed via HTTP range requests; zip CRC-32 checked on read by Python zipfile)",
                   "train_json_sha256": man["train_json_sha256"]},
        "split_sha256": man["split_sha256"], "output_dir": str(TRAIN_KS_DIR),
        "n_files": len(files), "n_expected": len(part_of), "missing": missing, "problems": problems,
        "totals": dict(tot), "by_split_part": by_part,
        "label_note": "AVeriTeC evidence-URL membership is a WEAK RELEVANCE PROXY, not a human-verified authority label. "
                      "Non-evidence documents are UNLABELLED (not confirmed irrelevant).",
        "files": rows,
    }
    out["manifest_sha256_of_file_list"] = hashlib.sha256(
        "\n".join(f"{r['file']} {r['sha256']}" for r in rows).encode()).hexdigest()
    json.dump(out, open(OUT / "EXTRACTION_MANIFEST.json", "w", encoding="utf-8"), indent=1)
    md = [f"# Train knowledge-store extraction manifest\n", f"Status: **{out['status']}**  ",
          f"Source: {out['source']['repo']} @ `{out['source']['revision']}` ({out['source']['licence']})  ",
          f"Files: {len(files)}/{len(part_of)}; total {tot['bytes'] / 2**20:.1f} MiB; documents {tot['n_docs']} "
          f"({tot['n_empty_text']} empty text)  ",
          f"Evidence URLs: {tot['n_web_evidence_urls']} total; {tot['n_evidence_urls_in_file']} found in files; "
          f"{tot['n_evidence_urls_nonempty']} non-empty  ",
          f"By split: {json.dumps(by_part)}  ", f"File-list SHA-256: `{out['manifest_sha256_of_file_list']}`  ",
          f"Problems: {problems or 'none'}; missing: {missing or 'none'}\n", f"> {out['label_note']}\n",
          "| train_idx | part | docs | empty | evid. URLs (in file / non-empty / total) | bytes | sha256 |", "|---|---|---|---|---|---|---|"]
    md += [f"| {r['train_idx']} | {r['split_part']} | {r['n_docs']} | {r['n_empty_text']} | {r['n_evidence_urls_in_file']} / "
           f"{r['n_evidence_urls_nonempty']} / {r['n_web_evidence_urls']} | {r['bytes']} | `{r['sha256']}` |" for r in rows]
    (OUT / "EXTRACTION_MANIFEST.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("status", "n_files", "n_expected", "missing", "problems", "totals",
                                          "by_split_part", "manifest_sha256_of_file_list")}, indent=1))


if __name__ == "__main__":
    main()
