"""Reconstruct Project A files (non-authority-v2) from Claude transcript events.

Writes ONLY under OUT (staging). Replays, in chronological order:
  * deduplicated Write/Edit tool calls (tool errors skipped),
  * the recorded shell modifications (sed -i expressions and python heredoc bodies,
    re-executed verbatim with the same Windows Python / Git-Bash sed on the staged copy).
Every intermediate and final state is checked against every SHA-256 that a transcript
tool result printed next to the file name.

Usage: python -I replay_project_a.py EVENTS_PKL OUT_DIR SCRATCH_36c390a8 > log
"""
import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pickle, os, re, hashlib, subprocess, json, shutil, collections

EV, OUT, SCR = sys.argv[1], sys.argv[2], sys.argv[3]
if os.path.exists(OUT):
    sys.exit("OUT exists - refusing to overwrite: " + OUT)
os.makedirs(OUT)
d = pickle.load(open(EV, "rb")); ev = d["events"]; res = d["results"]
ROOT = "c:\\users\\lenovo\\downloads\\capstone\\source_aware_misinformation_detector\\"

def rel(p):
    k = p.replace("/", "\\").lower()
    if not k.startswith(ROOT): return None
    r = p.replace("/", "\\")[len(ROOT):].replace("\\", "/")
    if r.startswith("experiments/authority_v2/") or r.startswith("docs/authority_v2_"):
        return None  # handled by the verified 2026-11-06 authority-v2 replay
    return r

fp = lambda r: os.path.join(OUT, r.replace("/", os.sep))
sha = lambda b: hashlib.sha256(b).hexdigest()

# ---------- ordered, deduplicated step list ----------
seen, steps, last_ts = set(), [], {}
ts_of = collections.defaultdict(str)
for e in ev:                                   # best timestamp per tool id
    if e[0]: ts_of[e[5]] = ts_of[e[5]] or e[0]
SHELL = {79, 117, 121, 129, 144, 171, 175, 189, 878, 245, 262, 312}
for i, (ts, s, k, p, inp, tid, ln) in enumerate(ev):
    if tid in seen: continue
    seen.add(tid)
    t = ts_of[tid] or last_ts.get(s, "")
    last_ts[s] = t
    if k in ("Write", "Edit", "MultiEdit") and p and rel(p):
        if res.get(tid, (False, ""))[0]: continue
        steps.append((t, i, "tool", k, rel(p), inp))
    elif i in SHELL:
        steps.append((t, i, "shell", k, None, inp))
steps.sort(key=lambda x: (x[0], x[1]))

hist = collections.defaultdict(list)
def note(r, t, act):
    hist[r].append((t[:19], act, sha(open(fp(r), "rb").read())))

def heredoc(c):
    return c.split("<<'EOF'\n", 1)[1].split("\nEOF", 1)[0]

def run_py(body, cwd):
    r = subprocess.run([sys.executable, "-I", "-"], input=body.encode("utf-8"), cwd=cwd, capture_output=True)
    if r.returncode: print("!! python body failed", r.stderr.decode()[-500:])

def run_sed(c, files_dir, rels):
    n = 0
    for m in re.finditer(r"sed -i '((?:[^']|'\\'')*)' ((?:[\w.-]+\.(?:md|py) ?)+)", c):
        names = m.group(2).split()
        r = subprocess.run(["sed", "-i", m.group(1)] + names, cwd=files_dir, capture_output=True)
        if r.returncode: print("!! sed failed", r.stderr)
        n += 1
    return n

warn = []
for t, i, kind, k, r, inp in steps:
    if kind == "tool":
        os.makedirs(os.path.dirname(fp(r)), exist_ok=True)
        if k == "Write":
            open(fp(r), "wb").write(inp["content"].encode("utf-8")); note(r, t, f"Write[{i}]"); continue
        raw = open(fp(r), "rb").read().decode("utf-8")
        crlf = "\r\n" in raw
        s = raw.replace("\r\n", "\n") if crlf else raw
        for e in (inp.get("edits") or [inp]):
            o, n = e["old_string"], e["new_string"]
            c = s.count(o)
            if c == 0:
                warn.append(f"EDIT NOT APPLIED (old_string missing) {r} [{i}] {t}"); continue
            if c > 1 and not e.get("replace_all"):
                warn.append(f"EDIT ambiguous ({c} matches, first replaced) {r} [{i}]")
            s = s.replace(o, n) if e.get("replace_all") else s.replace(o, n, 1)
        if crlf: s = s.replace("\n", "\r\n")
        open(fp(r), "wb").write(s.encode("utf-8")); note(r, t, f"Edit[{i}]" + (" (CRLF file)" if crlf else ""))
        continue
    c = inp["command"]
    E = lambda x: os.path.join(OUT, "experiments", *x.split("/")) if x else os.path.join(OUT, "experiments")
    if i == 79:
        run_py(heredoc(c), E("esa_nov2026")); note("experiments/esa_nov2026/demo.py", t, f"shell py[{i}]")
    elif i == 117:
        run_sed(c, os.path.join(OUT, "docs"), None)
        for x in ("docs/ESA_IMPLEMENTATION_AND_EXPERIMENT_REPORT.md", "docs/ESA_DEMO_SCRIPT.md"): note(x, t, f"shell sed[{i}]")
    elif i == 121:
        run_py(heredoc(c), E("esa_nov2026/relevance_baseline")); note("experiments/esa_nov2026/relevance_baseline/extract_train_ks_sample.py", t, f"shell py[{i}]")
    elif i == 129:
        run_py(heredoc(c), E("esa_nov2026/relevance_baseline")); note("experiments/esa_nov2026/relevance_baseline/train_relevance.py", t, f"shell py[{i}]")
    elif i == 144:
        run_py(heredoc(c), E("esa_nov2026/relevance_baseline")); note("experiments/esa_nov2026/relevance_baseline/rb_common.py", t, f"shell py[{i}]")
    elif i == 171:
        rr = subprocess.run([sys.executable, "-I", os.path.join(SCR, "update_report.py"), "docs/ESA_IMPLEMENTATION_AND_EXPERIMENT_REPORT.md",
                             os.path.join(SCR, "sec6.md"), os.path.join(SCR, "sec71.md")], cwd=OUT, capture_output=True)
        if rr.returncode: print("!! update_report failed", rr.stderr.decode()[-800:])
        note("docs/ESA_IMPLEMENTATION_AND_EXPERIMENT_REPORT.md", t, f"shell update_report.py[{i}]")
    elif i == 175:
        body = c.split('python -c "', 1)[1].split('"; git status', 1)[0]
        run_py(body, OUT); note("docs/ESA_DEMO_SCRIPT.md", t, f"shell py-c[{i}]")
    elif i == 189:
        rr = subprocess.run([sys.executable, "-I", os.path.join(SCR, "fix_ad.py"), "docs/ESA_IMPLEMENTATION_AND_EXPERIMENT_REPORT.md"], cwd=OUT, capture_output=True)
        print("fix_ad:", rr.stdout.decode().strip(), rr.stderr.decode()[-300:])
        note("docs/ESA_IMPLEMENTATION_AND_EXPERIMENT_REPORT.md", t, f"shell fix_ad.py[{i}]")
    elif i == 878:
        run_sed(c, os.path.join(OUT, "docs"), None); note("docs/RESEARCH_PROPOSAL_INFORMATION_PACKAGE.md", t, f"shell sed[{i}]")
    elif i in (245, 262):
        run_sed(c, E(""), None); note("experiments/authority_bottleneck_diagnostics.py", t, f"shell sed[{i}]")
    elif i == 312:
        run_py(heredoc(c), E("")); note("experiments/authority_diagnostic_audit.py", t, f"shell py[{i}]")

# ---------- recorded hashes printed in any tool result ----------
rec = collections.defaultdict(set)
pat = re.compile(r"\b([0-9a-f]{64})\b\s+\*?([^\s]+)")
for tid, (err, txt) in res.items():
    for m in pat.finditer(txt or ""):
        rec[m.group(2).replace("\\", "/").split("/")[-1].lower()].add(m.group(1))
# script_sha256 recorded by authority_bottleneck_diagnostics provenance (event 276)
rec["authority_bottleneck_diagnostics.py"].add("66a962c0e95259af52b895bc950f7aa71671e4f95bbfd100886900de363cb23b")

report = []
for r in sorted(hist):
    h = hist[r]; final = h[-1][2]; known = rec.get(r.split("/")[-1].lower(), set())
    states = {x[2] for x in h}
    if final in known: v = "FINAL HASH MATCHES TRANSCRIPT RECORD"
    elif known & states: v = "intermediate state matches record; final state has no record"
    elif known: v = "NO MATCH with recorded hash(es)"
    else: v = "no recorded hash"
    report.append(dict(path=r, steps=len(h), final_sha256=final, bytes=os.path.getsize(fp(r)), verdict=v,
                       recorded=sorted(known), chronology=[dict(ts=a, action=b, sha256_after=c,
                       matches_record=c in known) for a, b, c in h]))
    print(f"{v:62s} steps={len(h):2d} {final[:12]} {r}")
for w in warn: print("WARN", w)
json.dump(dict(files=report, warnings=warn), open(OUT + "_replay_report.json", "w", encoding="utf-8"), indent=1)
