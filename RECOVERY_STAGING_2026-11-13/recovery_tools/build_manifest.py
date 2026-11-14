"""Build RECOVERY_MANIFEST.csv for every restored file; re-hash each at its live location."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
import os, json, csv, hashlib, subprocess, collections
ST = r"C:\Users\Lenovo\Downloads\capstone\RECOVERY_STAGING_2026-11-13"
CAP = r"C:\Users\Lenovo\Downloads\capstone"
A = os.path.join(CAP, "Source_Aware_Misinformation_Detector"); B = os.path.join(CAP, "first_hand_authority_model")
LP = chr(92) * 2 + "?" + chr(92)
def sha(p):
    h = hashlib.sha256()
    with open(LP + p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()
rows = []
for r in json.load(open(os.path.join(ST, "manifest_project_A.json"), encoding="utf-8")):
    r["live_path"] = os.path.join(A, r["relative_path"]); rows.append(r)
for r in json.load(open(os.path.join(ST, "manifest_shared.json"), encoding="utf-8")):
    r["live_path"] = os.path.join(CAP, r["relative_path"]); rows.append(r)
# Project B
pc = json.load(open(os.path.join(ST, "reconstructed", "project_B_postcommit_replay.json"), encoding="utf-8"))["post_commit_files"]
BVER = {"STATUS.md": "content-verified: verbatim in later `cat STATUS.md` outputs 2026-11-02 and 2026-11-03",
        "docs/DECISIONS.md": "content-verified: 110/110 lines identical to Read 2026-11-03T04:55",
        "docs/REAL_DATA_AND_TRAINING_PLAN_DRAFT.md": "content-verified: 203/203 lines identical to Read 2026-11-03T04:55"}
files = subprocess.run(["git", "-C", B, "ls-files"], capture_output=True, text=True).stdout.split()
for f in sorted(set(files) | set(pc)):
    if f in pc:
        rows.append(dict(relative_path=f, project="B", original_location="first_hand_authority_model/" + f,
            recovery_source=("commit 0bf11fc blob + " if f in files else "") + "post-commit Claude transcript edits (uncommitted in original)",
            status="RECONSTRUCTED FROM TRANSCRIPT", verification=BVER[f],
            note="Uncommitted working-tree change in the original repo (git status ' M'/'??' on 2026-11-02); reproduced as such.",
            live_path=os.path.join(B, f)))
    else:
        rows.append(dict(relative_path=f, project="B", original_location="first_hand_authority_model/" + f,
            recovery_source="git commit 0bf11fc loose objects (Recycle Bin backup $R4I77XK)", status="RECOVERED EXACT COPY",
            verification="git fsck --full --strict OK; working file byte-identical to committed blob (SHA-1 verified)", note="",
            live_path=os.path.join(B, f)))
# OneDrive data
for x in csv.DictReader(open(os.path.join(ST, "recovery_tools", "onedrive_data_inventory.csv"), encoding="utf-8")):
    if x["group"] in ("raw_outer", "ks_outer") or (x["group"] == "rank_outer" and x["path"].count("/") == 1):
        rows.append(dict(relative_path=x["path"], project="A (data)", original_location="Source_Aware_Misinformation_Detector/" + x["path"],
            recovery_source="OneDrive Desktop/sourceawaremisinformation (read-only copy, dated 2026-09-29/10-03)", status="RECOVERED EXACT COPY",
            verification="SHA-256 equals 2026-11-06 inventory hash", note="same data the 2026-11-06 recovery restored; git-ignored",
            live_path=os.path.join(A, x["path"]), expected=x["sha256"]))
rows.append(dict(relative_path="storage/datasets/README_RECOVERY_NOTE.md", project="storage", original_location="(new)",
    recovery_source="written 2026-11-13 by recovery", status="NEW RECOVERY NOTE (not original)", verification="n/a", note="documents missing dataset",
    live_path=os.path.join(CAP, "storage", "datasets", "README_RECOVERY_NOTE.md")))
bad = 0
for r in rows:
    r["live_path"] = os.path.normpath(r["live_path"])
    h = sha(r["live_path"]); r["bytes"] = os.path.getsize(LP + r["live_path"])
    exp = r.get("expected") or r.get("sha256")
    r["live_sha256_matches_record"] = "yes" if (exp is None or exp == h) else "NO"
    bad += r["live_sha256_matches_record"] == "NO"
    r["sha256"] = h
cols = ["project", "relative_path", "original_location", "recovery_source", "bytes", "sha256", "status", "verification", "live_sha256_matches_record", "note"]
with open(os.path.join(ST, "RECOVERY_MANIFEST.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
print("rows", len(rows), "| live hash mismatches:", bad)
c = collections.Counter((r["project"], r["status"], r["verification"].split(":")[0][:40]) for r in rows)
for k, v in sorted(c.items()): print(f"{v:4d}  {k}")
