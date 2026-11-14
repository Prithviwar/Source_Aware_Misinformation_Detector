"""Copy approved OneDrive data into the repo. Never overwrites; verifies each copy against the Step-4 inventory hash."""
import csv, os, sys, hashlib, shutil
OD = r"C:\Users\Lenovo\OneDrive\Desktop\sourceawaremisinformation"
R = r"C:\Users\Lenovo\Downloads\capstone\Source_Aware_Misinformation_Detector"
inv = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
plan = [x for x in inv if x["group"] in ("raw_outer", "ks_outer")] + [x for x in inv if x["group"] == "rank_outer" and x["path"].count("/") == 1]
assert all(x["path"].startswith("data/raw/averitec/") or (x["path"].startswith("results/rankings_") and x["path"].endswith(".jsonl.gz")) for x in plan)
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()
for x in plan:
    if os.path.exists(os.path.join(R, x["path"])): sys.exit("CONFLICT (stopping, nothing overwritten): " + x["path"])
done = 0
for x in plan:
    src = os.path.join(OD, x["path"]); dst = os.path.join(R, x["path"])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(src, "rb") as fi, open(dst, "xb") as fo: shutil.copyfileobj(fi, fo, 1 << 20)
    shutil.copystat(src, dst)
    h = sha(dst)
    if h != x["sha256"] or os.path.getsize(dst) != int(x["size"]): sys.exit(f"HASH/SIZE MISMATCH, stopping after {done} files: {x['path']}")
    done += 1
print("copied and hash-verified:", done)
