"""Restore reconstructed Project A files into the live clone. Never overwrites (open 'xb').
Copies sources into STAGING/reconstructed/project_A_final first, then into the live repo,
and writes manifest rows to STAGING/manifest_project_A.json."""
import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os, json, hashlib, gzip, shutil, pickle
ST = r"C:\Users\Lenovo\Downloads\capstone\RECOVERY_STAGING_2026-11-13"
LIVE = r"C:\Users\Lenovo\Downloads\capstone\Source_Aware_Misinformation_Detector"
REC = os.path.join(ST, "reconstructed", "project_A")
V2 = os.path.join(ST, "_preserved_sources", "temp_scratchpads", "398127e0-e3ff-406d-9f09-edf34e128c02", "scratchpad", "replay_work")
BB = os.path.join(ST, "_preserved_sources", "vscode_blackbox_snapshots")
FINAL = os.path.join(ST, "reconstructed", "project_A_final")
sha = lambda b: hashlib.sha256(b).hexdigest()
rep = json.load(open(os.path.join(ST, "reconstructed", "project_A_replay_report.json"), encoding="utf-8"))
rep = {f["path"]: f for f in rep["files"]}
v2rec = pickle.load(open(os.path.join(os.path.dirname(V2), "hashes.pkl"), "rb"))

BLACKBOX = {
  "docs/authority_resolution_bottleneck_analysis.md": "1793206234176/Source_Aware_Misinformation_DetectorBBFLDRDELdocsBBFLDRDELauthority_resolution_bottleneck_analysis.md.gz",
  "docs/authority_v2_progress_report_steps1-9.md": "1793621858383/Source_Aware_Misinformation_DetectorBBFLDRDELdocsBBFLDRDELauthority_v2_progress_report_steps1-9.md.gz",
}
READ_VERIFIED = {  # final text identical to a full Read made after the last modification
  "docs/RESEARCH_PROPOSAL_INFORMATION_PACKAGE.md": "456/456 lines identical to Read 2026-11-08T06:45",
  "experiments/esa_nov2026/relevance_baseline/features.py": "103/103 lines identical to Read 2026-11-08T12:10",
  "docs/authority_v2_decision_log.md": "105/105 lines identical to full Reads 2026-11-01/02/03 (2026-11-06 audit); bytes verified only at Freeze-1 state (581ecc44...)",
  "docs/authority_resolution_diagnostic_audit.md": "22/22 long lines found in a later cat output (2026-10-28T16:51); partial check",
}
NOTES = {
  "experiments/esa_nov2026/relevance_baseline/extract_train_ks_sample.py":
    "Edit [122] (fixing a literal newline introduced by shell edit [121]) found nothing to change: the replayed shell edit already produced the escaped \"\\n\" form, i.e. the same end state. Syntax check passes.",
}
rows, plan = [], []
def add(rel, data, source, status, verification):
    plan.append((rel, data)); rows.append(dict(relative_path=rel, project="A", original_location="Source_Aware_Misinformation_Detector/" + rel,
        recovery_source=source, bytes=len(data), sha256=sha(data), status=status, verification=verification, note=NOTES.get(rel, "")))

for rel, gz in BLACKBOX.items():
    data = gzip.open(os.path.join(BB, gz.replace("/", os.sep)), "rb").read()
    rp = os.path.join(REC, rel) if os.path.exists(os.path.join(REC, rel)) else os.path.join(V2, rel)
    same = open(rp, "rb").read() == data
    add(rel, data, "VS Code Blackbox snapshot " + gz.split("/")[0], "RECOVERED EXACT COPY",
        "original on-disk snapshot; transcript replay byte-identical" if same else "snapshot only; transcript replay DIFFERS")
for dp, _, fs in os.walk(REC):
    for f in fs:
        rel = os.path.relpath(os.path.join(dp, f), REC).replace(os.sep, "/")
        if rel in BLACKBOX: continue
        data = open(os.path.join(dp, f), "rb").read(); r = rep[rel]
        assert sha(data) == r["final_sha256"]
        if r["verdict"].startswith("FINAL HASH MATCHES"):
            add(rel, data, "Claude transcript replay (Write/Edit + recorded shell edits)", "RECOVERED EXACT COPY",
                "byte-identical: SHA-256 equals the hash printed in the original session")
        elif rel in READ_VERIFIED:
            add(rel, data, "Claude transcript replay", "RECONSTRUCTED FROM TRANSCRIPT", "content-verified: " + READ_VERIFIED[rel])
        else:
            add(rel, data, "Claude transcript replay", "RECONSTRUCTED FROM TRANSCRIPT", "NOT VERIFIED independently (no recorded hash or later read); replay of original Write/Edit calls")
for dp, _, fs in os.walk(V2):
    for f in fs:
        rel = os.path.relpath(os.path.join(dp, f), V2).replace(os.sep, "/")
        if rel in BLACKBOX: continue
        data = open(os.path.join(dp, f), "rb").read()
        key = rel.split("authority_v2/")[-1] if rel.startswith("experiments/") else rel.split("docs/")[-1]
        recd = {x[0] for x in v2rec.get(key, set())}
        if sha(data) in recd:
            add(rel, data, "2026-11-06 authority-v2 transcript replay", "RECOVERED EXACT COPY",
                "byte-identical: SHA-256 equals hash recorded in the authority-v2 execution log / transcripts")
        else:
            add(rel, data, "2026-11-06 authority-v2 transcript replay", "RECONSTRUCTED FROM TRANSCRIPT",
                "content-verified: " + READ_VERIFIED[rel] if rel in READ_VERIFIED else "NOT VERIFIED")

conflicts = [rel for rel, _ in plan if os.path.exists(os.path.join(LIVE, rel))]
if conflicts: sys.exit("CONFLICTS - nothing written: " + ", ".join(conflicts))
if os.path.exists(FINAL): sys.exit("final staging dir exists - abort")
for rel, data in plan:
    for base in (FINAL, LIVE):
        p = os.path.join(base, rel.replace("/", os.sep)); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "xb") as fh: fh.write(data)
for rel, data in plan:
    assert open(os.path.join(LIVE, rel), "rb").read() == data
json.dump(rows, open(os.path.join(ST, "manifest_project_A.json"), "w", encoding="utf-8"), indent=1)
import collections
print("restored", len(plan), collections.Counter(r["status"] for r in rows))
