"""T: pool-grounded claim-specific resolver (preregistration §2.2, U12).

Calls go through the frozen authority_resolution.call() (claude -p, --tools "", strict MCP
config, no session persistence, empty temp dir, 300 s) with T's own system prompt, and the
frozen validation_heldout._run_calls (3 passes, 6 workers, re-trying only unparsed claims).
A response is "parsed" only if it is a JSON object with a list `selections` and a JSON
boolean `abstain`; anything else is turned into pred=None so _run_calls retries it.

Model inputs: claim, speaker, date, ISO, the Wikidata block, and the pool's publisher keys
with document counts. Never: titles, URL paths, page text, ranks, scores, gold or any
gold-informed list.

  python t_resolver.py run --version 1 --split dev [--resume]
"""
import argparse
import json

from v2common import MANIFESTS, RES, V2, halt, log_event, rel, sha256_file, write_new_json

import authority_resolution as AR
import validation_heldout as V

PROMPTS = V2 / "prompts"
BUDGET = 3


def prompts(version):
    sys_p, usr_p = PROMPTS / f"T_system_v{version}.md", PROMPTS / f"T_user_v{version}.md"
    return sys_p, usr_p, sys_p.read_text(encoding="utf-8"), usr_p.read_text(encoding="utf-8")


def pool_list(keys_counts):
    return "\n".join(f"- {k} ({n})" for k, n in keys_counts.items())


def make_item(cid, cond, base, wd, keys_counts, user_tpl):
    return {"claim_id": cid, "cond": cond, "pool_keys": list(keys_counts),
            "prompt": user_tpl.format(**base, wd=wd, pool=pool_list(keys_counts))}


def schema_error(pred):
    if not isinstance(pred, dict):
        return "no JSON object"
    if not isinstance(pred.get("selections"), list):
        return "selections missing or not a list"
    if not isinstance(pred.get("abstain"), bool):
        return "abstain missing or not a JSON boolean"
    return None


def t_call(item):
    res = AR.call(item)  # frozen extraction: first '{' .. last '}', json.loads
    err = None if res["pred"] is None else schema_error(res["pred"])
    if err:
        res = {**res, "pred": None, "rejected_pred": res["pred"], "error": f"schema: {err}"}
    return res


def postprocess(pred, pool_keys):
    """U12 rules 3-9. Returns (retained keys in model order, status, flag counts)."""
    flags = {"invalid_key": 0, "duplicate_key": 0, "truncated": 0, "abstain_conflict": 0}
    if pred is None:
        return [], "parse_failure", flags
    if pred["abstain"]:
        flags["abstain_conflict"] = int(bool(pred["selections"]))
        return [], "abstain", flags
    pool, kept = set(pool_keys), []
    for s in pred["selections"]:
        if not isinstance(s, dict) or not isinstance(s.get("key"), str):
            flags["invalid_key"] += 1
            continue
        k = s["key"].strip().lower()
        if k not in pool:
            flags["invalid_key"] += 1
        elif k in kept:
            flags["duplicate_key"] += 1
        else:
            kept.append(k)
    if len(kept) > BUDGET:
        flags["truncated"] = len(kept) - BUDGET
        kept = kept[:BUDGET]
    return kept, ("selected" if kept else "empty_selection"), flags


def check_manifest(version, split, files):
    man = MANIFESTS / (f"MANIFEST_dev_v{version}.json" if split == "dev" else "MANIFEST_freeze2.json")
    if not man.exists():
        halt(f"{rel(man)} missing; T refuses to run without its manifest")
    rec = json.loads(man.read_text(encoding="utf-8"))["files"]
    bad = [rel(p) for p in files if rec.get(rel(p)) != sha256_file(p)]
    if bad:
        halt("T inputs differ from manifest", manifest=rel(man), differing=bad)
    return man


def keys_from_raw(raw_path, items):
    """Final per-claim T result: last parsed record per claim (as _run_calls caches it)."""
    done = {}
    for line in open(raw_path, encoding="utf-8"):
        x = json.loads(line)
        if x.get("pred"):
            done[x["claim_id"]] = x
    out = {}
    for it in items:
        x = done.get(it["claim_id"])
        keys, status, flags = postprocess(x["pred"] if x else None, it["pool_keys"])
        out[str(it["claim_id"])] = {"keys": keys, "status": status, "flags": flags,
                                    "confidence": (x or {}).get("pred", {}).get("confidence") if x else None,
                                    "selections": (x or {}).get("pred", {}).get("selections") if x else None}
    return out


def run_dev(version, resume):
    from dev_data import base_fields, load_dev, pool_keys, wd_block
    sys_p, usr_p, system, user = prompts(version)
    man = check_manifest(version, "dev", [sys_p, usr_p, V2 / "t_resolver.py", V2 / "dev_data.py", V2 / "config.json"])
    out_dir = RES / "dev" / f"T_v{version}"
    raw = out_dir / "raw.jsonl"
    if raw.exists() and not resume:
        halt(f"{rel(raw)} exists: a started version cannot be re-run (use --resume only after a crash)")
    if (out_dir / "keys.json").exists():
        halt(f"T v{version} already finalised")
    items = []
    for c in load_dev():
        wd = wd_block(c)
        if wd is None:
            halt(f"claim {c['claim_id']}: Wikidata block not reconstructable")
        items.append(make_item(c["claim_id"], f"T_v{version}", base_fields(c["inputs"]), wd, pool_keys(c["pool"]), user))
    out_dir.mkdir(parents=True, exist_ok=True)
    AR.SYSTEM = system  # T's frozen system prompt; the frozen call() body is unchanged
    log_event("t_dev_run_start" if not resume else "t_dev_run_resume", version=version, n_items=len(items),
              manifest=rel(man), raw=rel(raw))
    V._run_calls(items, raw, t_call)
    finalise(items, raw, out_dir, version, "dev")


def run_reserved(resume):
    """Step 13: the selected version, frozen at freeze 2, once over the 180 reserved claims."""
    from paths_reserved import RES as _R, redirect
    from reserved_inputs import load_reserved
    sel = json.loads((_R / "selection.json").read_text(encoding="utf-8"))
    if not sel.get("family_N_executed"):
        halt("Family N not executed (selection.json); reserved T is not run")
    version = sel["selected_version"]
    sys_p, usr_p, system, user = prompts(version)
    man = check_manifest(version, "reserved", [sys_p, usr_p, V2 / "t_resolver.py", V2 / "reserved_inputs.py",
                                               V2 / "dev_data.py", V2 / "paths_reserved.py", V2 / "config.json"])
    redirect()
    out_dir = _R / "reserved" / "T"
    raw = out_dir / "raw.jsonl"
    if raw.exists() and not resume:
        halt(f"{rel(raw)} exists: reserved T runs once (use --resume only after a crash)")
    if (out_dir / "keys.json").exists():
        halt("reserved T already finalised")
    claims = load_reserved()
    bad = [c["claim_id"] for c in claims if not c["wd_matches_D"]]
    if bad:
        halt("T's Wikidata string differs from D's stored prompt", claims=bad)
    from dev_data import base_fields, pool_keys
    items = [make_item(c["claim_id"], f"T_v{version}", base_fields(c["inputs"]), c["wd"], pool_keys(c["pool"]), user)
             for c in claims]
    out_dir.mkdir(parents=True, exist_ok=True)
    AR.SYSTEM = system
    log_event("t_reserved_run_start" if not resume else "t_reserved_run_resume", version=version,
              n_items=len(items), manifest=rel(man), raw=rel(raw))
    V._run_calls(items, raw, t_call)
    finalise(items, raw, out_dir, version, "reserved")


def finalise(items, raw, out_dir, version, split):
    keys = keys_from_raw(raw, items)
    recs = [json.loads(l) for l in open(raw, encoding="utf-8")]
    st = {s: sum(v["status"] == s for v in keys.values())
          for s in ("selected", "abstain", "empty_selection", "parse_failure")}
    fl = {f: sum(v["flags"][f] for v in keys.values()) for f in ("invalid_key", "duplicate_key", "truncated", "abstain_conflict")}
    summ = {"version": version, "split": split, "n": len(items), "status": st, "flags": fl,
            "f": round(st["parse_failure"] / len(items), 4),
            "n_calls": len(recs), "n_call_errors": sum(r.get("pred") is None for r in recs),
            "cost_usd": round(sum(r.get("cost") or 0 for r in recs), 4),
            "models": sorted({m for r in recs for m in (r.get("model") or [])}),
            "raw_sha256": sha256_file(raw)}
    h = write_new_json(out_dir / "keys.json", keys)
    write_new_json(out_dir / "summary.json", {**summ, "keys_sha256": h})
    log_event(f"t_{split}_run_done", **summ, keys_sha256=h)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--version", type=int)
    ap.add_argument("--split", choices=["dev", "reserved"], required=True)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    run_dev(a.version, a.resume) if a.split == "dev" else run_reserved(a.resume)
