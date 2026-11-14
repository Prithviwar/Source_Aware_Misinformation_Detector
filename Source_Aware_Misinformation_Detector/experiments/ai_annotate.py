"""MODEL_GENERATED annotation runner. Every label written by this script is AI-generated, never human.

  python ai_annotate.py evidence pilot   --run A|B      evidence-level roles, 34 gold URLs of the 15 pilot claims
  python ai_annotate.py evidence heldout --run A        evidence-level roles, all 422 held-out gold URLs (needs freeze)
  python ai_annotate.py claim    pilot   --run A        claim-level authorities, 15 pilot claims (descriptive only)
  python ai_annotate.py claim    heldout --run A        claim-level authorities, 192 claims (needs freeze; descriptive only)
  python ai_annotate.py evidence xfam    --run X --backend ollama --ollama-model <name>
                                                        cross-family subset (AI-AI agreement only)
  python ai_annotate.py export-xfam                     subset prompts as CSV, for a cross-family model run outside
  python ai_annotate.py hashes                          SHA-256 of prompts, guide, runner and converter
  python ai_annotate.py freeze                          write ai/FROZEN_HASHES.json (only after the pilot review)

Protocol: data/annotations/heldout_primary_package/AI_ANNOTATION_PROTOCOL.md.
Annotator: claude -p, model claude-opus-5-5 (THE SAME MODEL as the L+Wctx authority predictor), no tools, no web,
no MCP, no session persistence, fresh empty temporary working directory, one call per item.
Inputs: evidence = one row of heldout_annotator_template.csv (claim context + that one gold page + the gold Q/A it was
cited for); claim = one row of the blank canonical sheet + ANNOTATION_GUIDE.md.
This script NEVER reads results/, rankings, authority predictions, source_roles.csv, or any other annotation.
"""
import argparse
import csv
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANN = HERE.parent / "data" / "annotations"
PKG = ANN / "heldout_primary_package"
AI = PKG / "ai"
EVIDENCE_SHEET = ANN / "heldout_annotator_template.csv"
CLAIM_SHEET = PKG / "heldout_primary_annotation.csv"
GUIDE = PKG / "ANNOTATION_GUIDE.md"
PROMPTS = {"evidence": AI / "AI_EVIDENCE_PROMPT.md", "claim": AI / "AI_CLAIM_PROMPT.md"}
FROZEN = AI / "FROZEN_HASHES.json"
CANONICAL_SHA = "cf063d5ebbb25c3c853f7bc1b26a3d19b621482b797e3592ce865d7b8637259c"

MODEL = "claude-opus-5-5"
CLAUDE = os.environ.get("CLAUDE_CODE_EXECPATH") or shutil.which("claude.exe") or shutil.which("claude")
XFAM_SEED, XFAM_N = 2028, 40

LABELS = {"primary", "secondary", "derived", "unclear"}
CONF = {"high", "medium", "low"}
SITUATIONS = {"single_primary", "multiple_legitimate_authorities", "no_identifiable_primary", "unclear"}
TYPES = {"government_executive", "legislature", "court_or_prosecutor", "regulator_or_election_body",
         "statistics_or_data_agency", "intergovernmental_org", "health_or_science_agency",
         "academic_or_research_producer", "organisation_about_itself", "person_own_statement_or_account", "other"}
EV_FIELDS = ["claim_text", "claim_speaker", "claim_date", "claim_country", "evidence_url", "source_domain",
             "evidence_title", "evidence_snippet", "question_it_answered", "answer_given"]
CL_FIELDS = ["claim_text", "claim_speaker", "claim_date", "claim_country"]
EV_OUT = ["label", "publisher_name", "authority_rationale", "confidence", "notes"]
CL_OUT = ["authority_situation"] + [f"authority_{i}_{f}" for i in (1, 2, 3) for f in ("name", "domain_or_account", "type")] \
    + ["authority_rationale", "confidence", "research_used", "notes"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def current_hashes() -> dict:
    return {"AI_EVIDENCE_PROMPT.md": sha(PROMPTS["evidence"]), "AI_CLAIM_PROMPT.md": sha(PROMPTS["claim"]),
            "ANNOTATION_GUIDE.md": sha(GUIDE), "ai_annotate.py": sha(Path(__file__)),
            "score_ai_primary.py": sha(HERE / "score_ai_primary.py")}


def split_prompt(task: str) -> tuple[str, str]:
    t = PROMPTS[task].read_text(encoding="utf-8")
    system, user = t.split("<!-- USER -->")
    system = system.replace("<!-- SYSTEM -->", "").strip()
    if task == "claim":
        system = system.replace("{guide}", GUIDE.read_text(encoding="utf-8").strip())
    return system, user.strip()


def fill(template: str, row: dict, fields: list[str]) -> str:
    for f in fields:  # plain replacement: the template also contains literal JSON braces
        template = template.replace("{" + f + "}", (row.get(f) or "").strip())
    return template


def pilot_ids() -> list[int]:
    return json.load(open(PKG / "pilot" / "PILOT_MANIFEST.json", encoding="utf-8"))["pilot_claim_ids"]


def xfam_ids() -> list[int]:
    order = json.load(open(PKG / "MANIFEST.json", encoding="utf-8"))["claim_order"]
    pool = [c for c in order if c not in set(pilot_ids())]
    return sorted(random.Random(XFAM_SEED).sample(pool, XFAM_N))


def items(task: str, which: str) -> list[dict]:
    assert sha(CLAIM_SHEET) == CANONICAL_SHA, "canonical 192-row sheet changed"
    keep = None if which == "heldout" else set(pilot_ids() if which == "pilot" else xfam_ids())
    sheet, fields, key = (EVIDENCE_SHEET, EV_FIELDS, "item_id") if task == "evidence" else (CLAIM_SHEET, CL_FIELDS, "claim_id")
    system, user = split_prompt(task)
    out = []
    for r in csv.DictReader(open(sheet, encoding="utf-8-sig")):
        if keep is None or int(r["claim_id"]) in keep:
            out.append({"item": r[key], "claim_id": int(r["claim_id"]), "system": system, "prompt": fill(user, r, fields)})
    return out


def validate(task: str, obj) -> str | None:
    if not isinstance(obj, dict):
        return "not a JSON object"
    need = EV_OUT if task == "evidence" else CL_OUT
    if set(need) - set(obj):
        return f"missing keys {sorted(set(need) - set(obj))}"
    if obj.get("confidence") not in CONF:
        return "bad confidence"
    if task == "evidence":
        return None if obj.get("label") in LABELS else "bad label"
    if obj.get("authority_situation") not in SITUATIONS:
        return "bad authority_situation"
    for i in (1, 2, 3):
        t = (obj.get(f"authority_{i}_type") or "").strip()
        if t and t not in TYPES:
            return f"bad authority_{i}_type"
    return None


def call_claude(it: dict) -> dict:
    with tempfile.TemporaryDirectory() as empty:
        p = subprocess.run([CLAUDE, "-p", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
                            "--model", MODEL, "--system-prompt", it["system"], "--output-format", "json"],
                           input=it["prompt"], capture_output=True, text=True, encoding="utf-8", cwd=empty, timeout=300)
    env = json.loads(p.stdout)
    return {"text": env.get("result", ""), "cost": env.get("total_cost_usd"), "num_turns": env.get("num_turns"),
            "model_usage": list((env.get("modelUsage") or {}).keys())}


def call_ollama(it: dict, model: str) -> dict:
    body = json.dumps({"model": model, "stream": False, "format": "json", "options": {"temperature": 0},
                       "messages": [{"role": "system", "content": it["system"]},
                                    {"role": "user", "content": it["prompt"]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", body, {"Content-Type": "application/json"})
    env = json.loads(urllib.request.urlopen(req, timeout=900).read())
    return {"text": env["message"]["content"], "cost": 0.0, "num_turns": 1, "model_usage": [model]}


def annotate(task: str, it: dict, backend: str, omodel: str | None) -> dict:
    last = None
    for attempt in (1, 2):  # one retry if the answer is unparseable or invalid
        try:
            r = call_claude(it) if backend == "claude" else call_ollama(it, omodel)
            m = re.search(r"\{.*\}", r["text"], re.S)
            obj = json.loads(m.group(0)) if m else None
            err = validate(task, obj)
            last = {**r, "parsed": obj if not err else None, "error": err, "attempt": attempt}
            if not err:
                return last
        except Exception as e:  # noqa: BLE001
            last = {"text": "", "parsed": None, "error": repr(e), "attempt": attempt}
    return last


def run(task: str, which: str, run_id: str, backend: str, omodel: str | None):
    if which == "heldout":
        if not FROZEN.exists():
            sys.exit("REFUSED: no ai/FROZEN_HASHES.json. Freeze the protocol after the pilot review first.")
        frozen = json.load(open(FROZEN, encoding="utf-8"))["hashes"]
        if frozen != current_hashes():
            sys.exit(f"REFUSED: protocol files differ from the freeze.\nfrozen={frozen}\nnow={current_hashes()}")
    who = "CLAUDE_OPUS_5_5" if backend == "claude" else re.sub(r"[^A-Za-z0-9]+", "_", omodel).upper()
    stem = f"MODEL_GENERATED_{task}_{which}_run{run_id}_{who}"
    raw, clean = AI / f"{stem}.jsonl", AI / f"{stem}.csv"
    todo = items(task, which)
    done = {}
    if raw.exists():
        for x in map(json.loads, open(raw, encoding="utf-8")):
            if x.get("parsed"):
                done[x["item"]] = x
    todo = [i for i in todo if i["item"] not in done]
    meta = {"label_source": "MODEL_GENERATED (AI); not human", "task": task, "items": which, "run": run_id,
            "backend": backend, "model": MODEL if backend == "claude" else omodel, "hashes": current_hashes()}
    print(json.dumps(meta, indent=1), f"\n{len(done)} cached, {len(todo)} to run", flush=True)
    with ThreadPoolExecutor(4 if backend == "claude" else 1) as ex, open(raw, "a", encoding="utf-8") as fh:
        for n, (it, res) in enumerate(zip(todo, ex.map(lambda i: annotate(task, i, backend, omodel), todo)), 1):
            rec = {"item": it["item"], "claim_id": it["claim_id"], **res, **meta,
                   "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if res.get("parsed"):
                done[it["item"]] = rec
            print(f"[{n}/{len(todo)}] {it['item']} {'ok' if res.get('parsed') else res.get('error')}", flush=True)
    cols = ["item", "claim_id"] + (EV_OUT if task == "evidence" else CL_OUT) + ["annotator_id"]
    with open(clean, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for k in sorted(done, key=lambda s: int(s)):
            p = done[k]["parsed"]
            w.writerow({"item": k, "claim_id": done[k]["claim_id"], **{c: p.get(c, "") for c in cols[2:-1]},
                        "annotator_id": f"MODEL_GENERATED_{who}"})
    print(f"wrote {clean.name}: {len(done)}/{len(items(task, which))} items parsed")


def export_xfam():
    out = AI / "xfam_subset_prompts_NO_LABELS.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "claim_id", "system_prompt", "user_prompt"] + EV_OUT)
        for it in items("evidence", "xfam"):
            w.writerow([it["item"], it["claim_id"], it["system"], it["prompt"]] + [""] * len(EV_OUT))
    print(f"wrote {out} (claims {xfam_ids()})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["evidence", "claim", "export-xfam", "hashes", "freeze"])
    ap.add_argument("which", nargs="?", choices=["pilot", "heldout", "xfam"])
    ap.add_argument("--run", default="A")
    ap.add_argument("--backend", choices=["claude", "ollama"], default="claude")
    ap.add_argument("--ollama-model")
    a = ap.parse_args()
    AI.mkdir(parents=True, exist_ok=True)
    if a.cmd == "hashes":
        print(json.dumps(current_hashes(), indent=1))
    elif a.cmd == "freeze":
        json.dump({"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "hashes": current_hashes()},
                  open(FROZEN, "w", encoding="utf-8"), indent=1)
        print(f"wrote {FROZEN}")
    elif a.cmd == "export-xfam":
        export_xfam()
    else:
        if a.which == "xfam" and a.cmd != "evidence":
            sys.exit("xfam is evidence-level only")
        run(a.cmd, a.which, a.run, a.backend, a.ollama_model)


if __name__ == "__main__":
    main()
