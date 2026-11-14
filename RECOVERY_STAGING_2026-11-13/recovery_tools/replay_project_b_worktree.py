"""Replay Project B transcript Write/Edit events, starting each file from its committed
blob where one exists. Used (a) to check that the transcript and commit 0bf11fc agree and
(b) to reproduce the post-commit uncommitted working-tree edits.

Usage: python -I replay_project_b_worktree.py EVENTS_PKL REPO_DIR OUT_JSON
Writes nothing into REPO_DIR; reports to OUT_JSON only.
"""
import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pickle, subprocess, hashlib, json, collections
EV, REPO, OUT = sys.argv[1:4]
COMMIT_UTC = "2026-10-29T10:10:50"
ROOT = "c:\\users\\lenovo\\downloads\\capstone\\first_hand_authority_model\\"
d = pickle.load(open(EV, "rb")); ev = d["events"]; res = d["results"]
def rel(p):
    k = p.replace("/", "\\").lower()
    return p.replace("/", "\\")[len(ROOT):].replace("\\", "/") if k.startswith(ROOT) else None
def blob(path):
    r = subprocess.run(["git", "-C", REPO, "show", "0bf11fc:" + path], capture_output=True)
    return r.stdout.decode("utf-8") if r.returncode == 0 else None
ts_of = {}
for e in ev:
    if e[0]: ts_of.setdefault(e[5], e[0])
seen, last, pre, post = set(), {}, {}, {}
warn = []
for i, (ts, s, k, p, inp, tid, ln) in enumerate(ev):
    if tid in seen: continue
    seen.add(tid)
    t = ts_of.get(tid) or last.get(s, ""); last[s] = t
    if k not in ("Write", "Edit") or not p or not rel(p) or res.get(tid, (False, ""))[0]: continue
    r = rel(p); state = pre if t < COMMIT_UTC else post
    if state is post and r not in post:
        post[r] = blob(r)               # continue from the committed blob (authoritative)
        if post[r] is not None and post[r] != pre.get(r):
            warn.append(f"note: {r} committed blob differs from transcript pre-commit state (shell edits); post-commit edits applied to the blob")
    if k == "Write":
        state[r] = inp["content"]
    else:
        cur = state.get(r)
        if cur is None or inp["old_string"] not in cur:
            warn.append(f"edit not applicable {r} [{i}]"); continue
        state[r] = cur.replace(inp["old_string"], inp["new_string"], 1) if not inp.get("replace_all") else cur.replace(inp["old_string"], inp["new_string"])
out = {"pre_commit_vs_blob": {}, "post_commit_files": {}, "warnings": warn}
for r, c in sorted(pre.items()):
    b = blob(r)
    out["pre_commit_vs_blob"][r] = "identical" if b == c else ("no blob" if b is None else "DIFFERS")
for r, c in sorted(post.items()):
    out["post_commit_files"][r] = {"sha256": hashlib.sha256(c.encode("utf-8")).hexdigest(), "bytes": len(c.encode("utf-8")),
                                   "in_commit": blob(r) is not None, "differs_from_commit": blob(r) != c, "content": c}
json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
print(collections.Counter(out["pre_commit_vs_blob"].values()))
for r, v in out["pre_commit_vs_blob"].items():
    if v != "identical": print("  pre-commit", v, r)
for r, v in out["post_commit_files"].items():
    print("  post-commit", r, v["bytes"], v["sha256"][:12], "in_commit" if v["in_commit"] else "NEW", "changed" if v["differs_from_commit"] else "same")
for w in warn: print("WARN", w)
