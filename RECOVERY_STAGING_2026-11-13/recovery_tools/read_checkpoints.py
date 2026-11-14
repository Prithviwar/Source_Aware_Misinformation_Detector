"""Compare reconstructed files against later transcript evidence of their on-disk content:
(1) Read tool results (line-numbered), (2) `cat`/`sed -n` shell outputs containing the text.
Usage: python -I read_checkpoints.py EVENTS_PKL PROJECT_ABS_ROOT LOCAL_DIR rel1 [rel2 ...]
"""
import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pickle, re, os
EV, ROOT, LOCAL = sys.argv[1:4]; rels = sys.argv[4:]
d = pickle.load(open(EV, "rb")); ev = d["events"]; res = d["results"]
norm = lambda p: p.replace("/", "\\").lower()
for r in rels:
    full = norm(os.path.join(ROOT, r))
    text = open(os.path.join(LOCAL, r), "rb").read().decode("utf-8").replace("\r\n", "\n")
    L = text.split("\n")
    seen, out = set(), []
    for i, (ts, s, k, p, inp, tid, ln) in enumerate(ev):
        if tid in seen: continue
        seen.add(tid)
        body = res.get(tid, (True, ""))
        if body[0]: continue
        if k == "Read" and p and norm(p) == full:
            got = [(int(m.group(1)), m.group(2)) for m in (re.match(r"^\s*(\d+)\t(.*)$", l) for l in body[1].split("\n")) if m]
            ok = sum(1 for n, t in got if n - 1 < len(L) and L[n - 1].rstrip("\r") == t.rstrip("\r"))
            out.append(f"  Read  {ts[:16] or '(no ts)'} [{i}] lines {ok}/{len(got)} identical" + ("" if ok == len(got) else "  <-- DIFF"))
        elif k == "Bash" and os.path.basename(r) in inp["command"] and re.search(r"\b(cat|sed -n|head|tail)\b", inp["command"]):
            blines = [l for l in body[1].replace("\r\n", "\n").split("\n") if len(l.strip()) > 25]
            if not blines: continue
            hit = sum(1 for l in blines if l in text)
            if hit >= 5:
                out.append(f"  shell {ts[:16] or '(no ts)'} [{i}] {hit}/{len(blines)} long output lines found in reconstruction")
    print(r); print("\n".join(out[-6:]) if out else "  (no later read evidence)")
