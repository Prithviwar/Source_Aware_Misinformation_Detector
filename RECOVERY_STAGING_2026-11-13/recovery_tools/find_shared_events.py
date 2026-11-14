import sys; sys.stdout.reconfigure(encoding="utf-8")
import pickle
d = pickle.load(open(sys.argv[1], "rb")); ev = d["events"]; res = d["results"]
SEP = chr(92)
seen = set()
for i, e in enumerate(ev):
    if e[5] in seen: continue
    seen.add(e[5])
    p = (e[3] or "").lower().replace("/", SEP)
    c = e[4].get("command", "") if e[2] == "Bash" else ""
    if ("research_roadmap" in p or SEP + "storage" + SEP in p) and e[2] in ("Write", "Edit", "Read"):
        print(i, e[0][:19], e[2], e[3][-75:], "ERR" if res.get(e[5], (0,))[0] else "")
    elif ("RESEARCH_ROADMAP" in c or "RECOVERY_MANIFEST.md" in c or ("README.md" in c and "recovery_staging" in c)) and any(x in c for x in ("sed -i", ">>", "python -", "mv ", "rm ")):
        print(i, e[0][:19], "BASH", c[:250].replace("\n", " "))
