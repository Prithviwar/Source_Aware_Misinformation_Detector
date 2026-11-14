"""Restore capstone-root and storage files. Never overwrites. Writes manifest_shared.json."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
import pickle, os, json, hashlib, re, shutil
ST = r"C:\Users\Lenovo\Downloads\capstone\RECOVERY_STAGING_2026-11-13"
CAP = r"C:\Users\Lenovo\Downloads\capstone"
d = pickle.load(open(os.path.join(ST, "recovery_tools", "events.pkl"), "rb")); ev = d["events"]; res = d["results"]
sha = lambda b: hashlib.sha256(b).hexdigest()
rows, plan = [], []
LP = chr(92) * 2 + "?" + chr(92)
WRITES = {579: "RESEARCH_ROADMAP_2026-11-02.md",
          471: "storage/recovery_staging/authority_v2/RECOVERY_MANIFEST.md",
          512: "storage/recovery_staging/bottleneck_analysis/README.md",
          513: "storage/recovery_staging/evidence_package/README.md"}
for i, rel in WRITES.items():
    e = ev[i]; assert e[2] == "Write" and e[3].replace("\\", "/").endswith(rel.split("/")[-1])
    data = e[4]["content"].encode("utf-8")
    ver = "NOT VERIFIED independently (single Write, no later edit seen)"
    if i == 579:  # full Read 2026-11-03 [886]
        txt = res[ev[886][5]][1]
        got = [(int(m.group(1)), m.group(2)) for m in (re.match(r"^\s*(\d+)\t(.*)$", l) for l in txt.split("\n")) if m]
        L = data.decode("utf-8").split("\n"); ok = sum(1 for n, t in got if L[n - 1] == t)
        ver = f"content-verified: {ok}/{len(got)} lines identical to Read 2026-11-03T04:53"
    plan.append((rel, data)); rows.append(dict(relative_path=rel, project="capstone root" if "/" not in rel else "storage",
        original_location=rel, recovery_source=f"Claude transcript Write [{i}] {e[0][:19]}", bytes=len(data), sha256=sha(data),
        status="RECONSTRUCTED FROM TRANSCRIPT", verification=ver,
        note="Describes the 2026-11-06 staging; its files/ subfolders are not recreated (their contents are restored in Project A)." if "recovery_staging" in rel else ""))
SRC = LP + os.path.join(ST, "_preserved_sources", "recyclebin_storage_R4I77XK", "backups")
for dp, _, fs in os.walk(SRC):
    for f in fs:
        full = os.path.join(dp, f); rel = "storage/backups/" + os.path.relpath(full, SRC).replace(os.sep, "/")
        data = open(full, "rb").read(); plan.append((rel, data))
        rows.append(dict(relative_path=rel, project="storage", original_location=rel,
            recovery_source="Recycle Bin $R4I77XK (deleted 2026-11-13 18:02)", bytes=len(data), sha256=sha(data),
            status="RECOVERED EXACT COPY", verification="byte-identical to Recycle Bin original; git object SHA-1 verified (Project B commit 0bf11fc)", note=""))
conf = [r for r, _ in plan if os.path.exists(LP + os.path.join(CAP, r.replace("/", os.sep)))]
if conf: sys.exit("CONFLICT: " + ", ".join(conf))
for rel, data in plan:
    p = LP + os.path.join(CAP, rel.replace("/", os.sep)); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "xb") as fh: fh.write(data)
    assert open(p, "rb").read() == data
json.dump(rows, open(os.path.join(ST, "manifest_shared.json"), "w", encoding="utf-8"), indent=1)
print("restored", len(plan)); [print(" ", r["status"], "|", r["verification"][:60], "|", r["relative_path"]) for r in rows if "objects" not in r["relative_path"]]
