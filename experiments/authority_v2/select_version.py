"""Step 4 end: development selection (preregistration §7) -> results/authority_v2/selection.json.

Runs only after the owner's logged final decision on the number of versions (DL-011).
Admissible: f(v) <= 0.05. Lexicographic: max W, max sum(h10_T - h10_X), max sum(h20_T - h20_D),
min f, earliest version. U1a: none admissible -> Family N not executed. U1b: W <= 0 -> proceed.
"""
import json

from v2common import RES, halt, load_config, log_event, read_log, rel, sha256_file, write_new_json


def main():
    out = RES / "selection.json"
    if out.exists():
        halt("selection.json exists; selection runs once")
    if not any(e["event"] == "owner_decision_dev_versions" and e.get("final") for e in read_log()):
        halt("no final owner decision on the number of development versions is logged (DL-011)")
    thr = load_config()["dev_selection"]["f_threshold"]
    runs = []
    for v in (1, 2, 3):
        p = RES / "dev" / f"T_v{v}" / "score.json"
        if p.exists():
            s = json.loads(p.read_text(encoding="utf-8"))
            runs.append({"version": v, "W": s["W"], "S": s["S"], "tb_TX10": s["tiebreak_sum_T_minus_X_at10"],
                         "tb_TD20": s["tiebreak_sum_T_minus_D_at20"], "f": s["f"], "admissible": s["f"] <= thr,
                         "score_sha256": sha256_file(p)})
    if not runs:
        halt("no scored development version")
    adm = [r for r in runs if r["admissible"]]
    if not adm:
        sel = {"family_N_executed": False, "reason": "not executed: admissibility failed (U1a)", "versions": runs}
    else:
        best = sorted(adm, key=lambda r: (-r["W"], -r["tb_TX10"], -r["tb_TD20"], r["f"], r["version"]))[0]
        sel = {"family_N_executed": True, "selected_version": best["version"], "versions": runs,
               "rule": "admissible f<=%.2f; max W, max sum(h10_T-h10_X), max sum(h20_T-h20_D), min f, earliest" % thr,
               "U1b_W_le_0": best["W"] <= 0,
               "note": "proceed and report the development result alongside (U1b)" if best["W"] <= 0 else None}
    h = write_new_json(out, sel)
    log_event("selection", output=rel(out), sha256=h, **{k: v for k, v in sel.items() if k != "versions"})
    print(json.dumps(sel, indent=1))


if __name__ == "__main__":
    main()
