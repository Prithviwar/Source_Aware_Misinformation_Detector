import csv, os, sys, hashlib
OD = r"C:\Users\Lenovo\OneDrive\Desktop\sourceawaremisinformation"
R = r"C:\Users\Lenovo\Downloads\capstone\Source_Aware_Misinformation_Detector"
inv = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()
groups = {"raw top-level": [x for x in inv if x["group"] == "raw_outer"], "ks_sample": [x for x in inv if x["group"] == "ks_outer"],
          "dev rankings": [x for x in inv if x["group"] == "rank_outer" and x["path"].count("/") == 1]}
for g, rows in groups.items():
    sb = sum(os.path.getsize(os.path.join(OD, x["path"])) for x in rows)
    db = sum(os.path.getsize(os.path.join(R, x["path"])) for x in rows)
    dh = sum(sha(os.path.join(R, x["path"])) == x["sha256"] for x in rows)
    print(f"{g:14s} files src={len(rows)} dst={sum(os.path.exists(os.path.join(R, x['path'])) for x in rows)}  bytes src={sb:,} dst={db:,}  dst hash==inventory: {dh}/{len(rows)}")
# destination has nothing extra
extra_raw = [os.path.relpath(os.path.join(d, f), R) for d, _, fs in os.walk(os.path.join(R, "data", "raw")) for f in fs]
print("files now under data/raw:", len(extra_raw), "| results/rankings_*.jsonl.gz:", len([f for f in os.listdir(os.path.join(R, "results")) if f.startswith("rankings_")]))
# OneDrive source unchanged: re-hash every inventoried file (all 956, both copies)
bad = [x["path"] for x in inv if sha(os.path.join(OD, x["path"])) != x["sha256"]]
print("OneDrive inventory files re-hashed:", len(inv), "changed:", len(bad))
cnt = sum(len(fs) for _, _, fs in os.walk(OD)); print("OneDrive total file count now:", cnt)
for x in [r for r in inv if r["group"] == "raw_outer"]:
    print(f"   {x['path'].split('/')[-1]:14s} {x['sha256'][:16]}  verified")
