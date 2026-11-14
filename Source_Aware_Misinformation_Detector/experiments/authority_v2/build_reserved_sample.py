"""Steps 6-7 (preregistration §3.3): download dev.json, then build the 180-claim reserved sample.

  python build_reserved_sample.py download   step 6 (network): records status, size, ETag, SHA-256
  python build_reserved_sample.py build      step 7: inputs file + sealed full records; prints counts only

dev.json holds gold for every claim; it is read only here. The sealed file's raw hash is
computed from the bytes at write time; the file is not opened again before freeze 3.
"""
import json
import sys
import urllib.request

import verify_manifests
from paths_reserved import DEV_JSON, INPUTS, SEALED
from v2common import ROOT, halt, load_config, log_event, now, rel, sha256_file, write_new_bytes, write_new_text

INPUT_FIELDS = ("claim_id", "claim", "speaker_or_entity", "claim_date", "location_ISO_code")


def download():
    verify_manifests.require((1, 2))
    if DEV_JSON.exists():
        halt(f"{rel(DEV_JSON)} exists; refusing to overwrite")
    url = load_config()["reserved"]["dev_json_url"]
    req = urllib.request.Request(url, headers={"User-Agent": "authority-v2-study"})
    t0 = now()
    with urllib.request.urlopen(req, timeout=300) as r:
        data, status, headers, final = r.read(), r.status, dict(r.headers), r.geturl()
    if status != 200:
        halt(f"dev.json download status {status}")
    h = write_new_bytes(DEV_JSON, data)
    log_event("dev_json_download", url=url, final_url=final.split("?")[0], status=status, size=len(data), sha256=h,
              etag=headers.get("ETag") or headers.get("Etag"), content_length=headers.get("Content-Length"),
              started=t0)
    print(f"dev.json: status {status}, {len(data)} bytes, sha256 {h}")


def build():
    verify_manifests.require((1, 2))
    from build_sample import normalise
    for p in (INPUTS, SEALED):
        if p.exists():
            halt(f"{rel(p)} exists; refusing to overwrite")
    dev = json.load(open(DEV_JSON, encoding="utf-8"))
    used, mism = set(), 0
    for fn in ("averitec_sample.jsonl", "averitec_heldout.jsonl"):
        for r in map(json.loads, open(ROOT / "data/processed" / fn, encoding="utf-8")):
            i = int(r["claim_id"])
            used.add(i)
            mism += json.loads(json.dumps(normalise(i, dev[i]), ensure_ascii=False)) != r
    if len(used) != 320 or mism:
        halt("dev.json does not reproduce the stored development records", n_used=len(used), n_mismatch=mism)
    reserved = [i for i in range(len(dev)) if i not in used]
    if len(reserved) != load_config()["reserved"]["expected_n"]:
        halt(f"reserved count is {len(reserved)}, not 180")
    rows = [normalise(i, dev[i]) for i in reserved]
    jl = lambda rs: "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rs)
    h_in = write_new_text(INPUTS, jl([{k: r[k] for k in INPUT_FIELDS} for r in rows]))
    h_gold = write_new_text(SEALED, jl(rows))
    log_event("reserved_sample_built", n_dev=len(dev), n_used=len(used), n_reserved=len(reserved),
              first_id=reserved[0], last_id=reserved[-1], inputs=rel(INPUTS), inputs_sha256=h_in,
              sealed=rel(SEALED), sealed_sha256_at_write=h_gold, dev_json_sha256=sha256_file(DEV_JSON),
              dev_records_reproduced=320)
    print(f"dev {len(dev)} claims; used {len(used)} (all 320 reproduced); reserved {len(reserved)}")
    print(f"inputs sha256 {h_in}; sealed sha256 {h_gold}")


if __name__ == "__main__":
    {"download": download, "build": build}[sys.argv[1]]()
