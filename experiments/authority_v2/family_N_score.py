"""Family N scoring on the reserved set (preregistration §4.2, §5, §6). Runs once, after Family R.

Eligible set = Family R's gold_c (halts if they differ). A/D rankings must equal Family R's
(consistency gate). Tests use the frozen mcnemar / boot_ci / holm.
"""
import csv
import json
import math
from collections import Counter

import verify_manifests
from paths_reserved import HO_RES, redirect
from v2common import halt, load_config, log_event, read_log, rel, sha256_file, write_new_json

import authority_resolution as AR
import validation_heldout as V
from authority_retrieval import MAJOR_NEWS, PLATFORMS, REFERENCE
from common import registered_domain
from family_R_replication import merged_sample, probe_dict

KS = (1, 3, 5, 10, 20)
COND = ("A", "D", "T", "X")


def wilson(k, n, z=1.959964):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def test(a, b):
    """b vs a: wins = b hit & a miss."""
    w, l, p = V.mcnemar(a, b)
    d, lo, hi = V.boot_ci(a, b)
    return {"wins": w, "losses": l, "ties": len(a) - w - l, "p": round(p, 5), "diff": d, "CI95": [lo, hi]}


def classify(prim, tx):
    sig_pos = prim["p"] < 0.05 and prim["diff"] > 0 and prim["CI95"][0] > 0
    if sig_pos:
        return "N-Supported" if (tx["p_holm"] < 0.05 and tx["diff"] > 0) else "N-Partial"
    if prim["p"] < 0.05 and prim["diff"] < 0 and prim["CI95"][1] < 0:
        return "N-Harm"
    return "N-Inconclusive"


def main():
    ver = verify_manifests.require((1, 2, 3))
    if not any(e["event"] == "reserved_gold_gate_approved" for e in read_log()):
        halt("reserved-gold gate: no approval entry")
    if not any(e["event"] == "family_R_score_done" for e in read_log()):
        halt("Family R is scored first")
    sel = json.loads((HO_RES.parent / "selection.json").read_text(encoding="utf-8"))
    if not sel.get("family_N_executed"):
        halt("Family N not executed (U1a); nothing to score")
    redirect()
    out_p = HO_RES / "family_N.json"
    if out_p.exists():
        halt("family_N.json exists; one scoring pass per family")
    log_event("family_N_score_start", verification=ver)

    sample = merged_sample()
    G = V.gold_info(sample)
    preds = V.load_preds(V.PRED_RAW)
    cids = [int(r["claim_id"]) for r in sample]
    gold_c = [c for c in cids if G[c]["gold"] and c in preds]
    # ---- eligible set must equal Family R's gold_c
    with open(HO_RES / "family_R.csv", encoding="utf-8") as fh:
        famR = {int(x["claim_id"]): x for x in csv.DictReader(fh)}
    if set(famR) != set(gold_c):
        halt("Family N eligible set differs from Family R's gold_c")
    hyb = V.load_rk("hybrid", True)
    tk = {int(k): v for k, v in json.loads((HO_RES / "T" / "keys.json").read_text(encoding="utf-8")).items()}
    xk = {int(k): v for k, v in json.loads((HO_RES / "X" / "x_keys.json").read_text(encoding="utf-8")).items()}
    xslots = json.loads((HO_RES / "X" / "x_slots.json").read_text(encoding="utf-8"))
    keys = {c: {"A": set(), "D": preds[c]["keys"] if c in preds else set(), "T": set(tk[c]["keys"]),
                "X": set(xk[c]["keys"])} for c in cids}
    R = {c: {m: V.rerank(hyb[c], lambda u, k=keys[c][m]: float(V.cand_key(u) in k)) for m in COND} for c in cids}
    hit = lambda c, m, k: bool(G[c]["gold"] & {u for u, _ in R[c][m][:k]})
    brank = lambda c, m: V.best_rank(R[c][m], G[c]["gold"])
    # ---- consistency gate: recomputed A and D equal Family R's hybrid / hybrid+authority
    incons = [c for c in gold_c if int(famR[c]["rank_hybrid"]) != brank(c, "A")
              or int(famR[c]["rank_authority"]) != brank(c, "D")
              or (famR[c]["hit10_hybrid"] == "True") != hit(c, "A", 10)
              or (famR[c]["hit10_hybrid+authority"] == "True") != hit(c, "D", 10)]
    if incons:
        halt("A/D consistency gate failed", claims=incons)

    H = {m: {k: [hit(c, m, k) for c in gold_c] for k in KS} for m in COND}
    prim = {"comparison": "T vs D", "metric": "R@10", "n": len(gold_c), **test(H["D"][10], H["T"][10])}
    fam = [("T vs X @10", "X", 10), ("T vs A @10", "A", 10), ("T vs D @5", "D", 5), ("T vs D @20", "D", 20)]
    sec = [{"test": n, **test(H[ref][k], H["T"][k])} for n, ref, k in fam]
    for s, a in zip(sec, V.holm([s["p"] for s in sec])):
        s["p_holm"] = round(a, 5)
    decision = classify(prim, sec[0])

    # ---- descriptives
    n = len(gold_c)
    table = {}
    for m in COND:
        row = {f"R@{k}": round(sum(H[m][k]) / n, 4) for k in KS}
        row["MRR@100"] = round(sum((1 / brank(c, m)) if brank(c, m) <= V.POOL else 0.0 for c in gold_c) / n, 4)
        row["hit10_wilson95"] = wilson(sum(H[m][10]), n)
        table[m] = row
    coverage = sum(bool(G[c]["gold"] & {u for u, _ in hyb[c][:V.POOL]}) for c in gold_c)
    pairwise = {}
    for a, b in (("T", "D"), ("T", "X"), ("T", "A"), ("D", "A")):
        hw = sum(hit(c, a, 10) and not hit(c, b, 10) for c in gold_c)
        hl = sum(hit(c, b, 10) and not hit(c, a, 10) for c in gold_c)
        rw = sum(brank(c, a) < brank(c, b) for c in gold_c)
        rl = sum(brank(c, a) > brank(c, b) for c in gold_c)
        pairwise[f"{a}-{b}"] = {"hit10": {"wins": hw, "losses": hl, "ties": n - hw - hl},
                                "best_rank": {"wins": rw, "losses": rl, "ties": n - rw - rl}}
    boosted = {m: round(sum(sum(V.cand_key(u) in keys[c][m] for u, _ in hyb[c][:V.POOL]) for c in cids) / len(cids), 3)
               for m in ("D", "T", "X")}
    displaced = {m: round(sum(len({u for u, _ in R[c]["A"][:10]} - {u for u, _ in R[c][m][:10]}) for c in gold_c) / n, 3)
                 for m in ("D", "T", "X")}
    t_status = {"all_180": dict(Counter(v["status"] for v in tk.values())),
                "eligible": dict(Counter(tk[c]["status"] for c in gold_c)),
                "flags_all_180": {f: sum(v["flags"][f] for v in tk.values())
                                  for f in ("invalid_key", "duplicate_key", "truncated", "abstain_conflict")},
                "claims_T_overlaps_D": sum(bool(keys[c]["T"] & keys[c]["D"]) for c in cids)}
    xs = Counter(s["flag"] for s in xslots)
    bx = [xk[c]["B_X"] - xk[c]["B_T"] for c in cids if xk[c]["n_T"]]
    x_mech = {"slot_flags": dict(xs), "claims_BX_ne_BT": sum(v != 0 for v in bx),
              "mean_BX_minus_BT": round(sum(bx) / len(bx), 3) if bx else None,
              "median_BX_minus_BT": sorted(bx)[len(bx) // 2] if bx else None,
              "share_X_keys_that_are_gold_publishers": (lambda xs_: round(sum(k in G[c]["gold_keys"] for c, k in xs_) / len(xs_), 4)
                                                        if xs_ else None)([(c, k) for c in gold_c for k in xk[c]["keys"]])}
    # U8: T vs X on claims whose X slots are all same_type
    st = {}
    for s in xslots:
        st.setdefault(s["claim_id"], []).append(s["flag"])
    same = [c for c in gold_c if st.get(c) and all(f == "same_type" for f in st[c])]
    u8 = {"n": len(same), **(test([hit(c, "X", 10) for c in same], [hit(c, "T", 10) for c in same]) if same else {}),
          "note": "descriptive sensitivity (U8)"}
    # U6: T authority accuracy vs all human-gold publishers (evald definition)
    evald = [c for c in cids if c in preds and G[c]["gold_keys"]]
    u6 = {"n": len(evald),
          "top1": sum(bool(tk[c]["keys"][:1] and tk[c]["keys"][0] in G[c]["gold_keys"]) for c in evald),
          "top3": sum(bool(keys[c]["T"] & G[c]["gold_keys"]) for c in evald),
          "D_top1": sum(bool(preds[c]["top1"] & G[c]["gold_keys"]) for c in evald),
          "D_top3": sum(bool(preds[c]["keys"] & G[c]["gold_keys"]) for c in evald)}
    # breakdowns
    dkind = {}
    for x in map(json.loads, open(V.PRED_RAW, encoding="utf-8")):
        if x.get("cond") == "L+Wctx" and x.get("pred"):
            dkind[int(x["claim_id"])] = x["pred"].get("claim_kind")
    npub = lambda c: min(len({V.cand_key(u) for u in G[c]["gold"]} - {""}), 3)
    bd = {}
    for name, f in (("gold_verdict", lambda c: G[c]["label"]), ("D_claim_kind", lambda c: dkind.get(c)),
                    ("n_reachable_gold_publishers(3=3+)", npub)):
        groups = {}
        for c in gold_c:
            groups.setdefault(str(f(c)), []).append(c)
        bd[name] = {g: {"n": len(cs), **{f"R@10_{m}": round(sum(hit(c, m, 10) for c in cs) / len(cs), 3) for m in COND}}
                    for g, cs in sorted(groups.items())}
    # oracle ceilings (diagnostic only, not performance)
    def pub_oracle_hit(c):
        k = {V.cand_key(g) for g in G[c]["gold"] & {u for u, _ in hyb[c][:V.POOL]}} - {""}
        return bool(G[c]["gold"] & {u for u, _ in V.rerank(hyb[c], lambda u: float(V.cand_key(u) in k))[:10]})

    pub_or = [pub_oracle_hit(c) for c in gold_c]
    ceilings = {"url_oracle_in_pool(=pool coverage)": round(coverage / n, 4),
                "publisher_oracle_in_pool_R@10": round(sum(pub_or) / n, 4)}
    # memorisation-related metrics
    sel_types = {}
    for c in cids:
        for s in (tk[c].get("selections") or []):
            if isinstance(s, dict) and isinstance(s.get("key"), str):
                sel_types.setdefault((c, s["key"].strip().lower()), s.get("publisher_type"))
    t_sel = [(c, k) for c in gold_c for k in tk[c]["keys"]]
    fc_dom = {c: registered_domain(G[c]["fc_article"]) if G[c]["fc_article"] else "" for c in cids}
    mem = {"b_T_selects_fc_article_domain": sum(bool(fc_dom[c] and fc_dom[c] in keys[c]["T"]) for c in gold_c),
           "b_D_selects_fc_article_domain": sum(bool(fc_dom[c] and fc_dom[c] in keys[c]["D"]) for c in gold_c),
           "c_T_selections": len(t_sel),
           "c_T_selections_self_declared_news": sum(sel_types.get(x) == "news" for x in t_sel),
           "c_T_selections_in_frozen_lists_or_hint": sum(
               registered_domain(k) in (MAJOR_NEWS | REFERENCE | PLATFORMS) or bool(AR.NEWS_FC_HINT.search(k))
               for _, k in t_sel),
           "note": "(b), (c) are heuristics; gold metadata read at scoring only"}
    probe = probe_dict()
    if probe is not None:
        rec = {}
        mem["a_T_selects_probe_named_fc_domain"] = mem["a_D_selects_probe_named_fc_domain"] = 0
        for c in cids:
            p = probe.get(c)
            d = registered_domain(str((p or {}).get("fact_checker_domain") or "")) if p else ""
            rec[c] = bool(p and fc_dom[c] and d and d == fc_dom[c])  # as analyse(): "likely recognised"
            if c in gold_c and d:
                mem["a_T_selects_probe_named_fc_domain"] += d in keys[c]["T"]
                mem["a_D_selects_probe_named_fc_domain"] += d in keys[c]["D"]
        for name, sub in (("not_recognised", [c for c in gold_c if not rec[c]]), ("recognised", [c for c in gold_c if rec[c]])):
            mem[f"d_{name}"] = {"n": len(sub), **({f"R@10_{m}": round(sum(hit(c, m, 10) for c in sub) / len(sub), 3) for m in COND}
                                                  if sub else {}),
                                **({"T_vs_D_exploratory": test([hit(c, "D", 10) for c in sub], [hit(c, "T", 10) for c in sub])}
                                   if sub else {})}
    else:
        mem["probe"] = "not executed: probe-dependent metrics (a), (d) not computed"

    res = {"family": "N", "eligible_set": "Family R gold_c", "n_eligible": n, "n_claims": len(cids),
           "denominators": {"eligible": n, "web_gold_any": sum(bool(G[c]["gold_all"]) for c in cids), "all": len(cids)},
           "exclusions": {"D_unparsed": sum(c not in preds for c in cids),
                          "no_web_gold": sum(not G[c]["gold_all"] for c in cids),
                          "web_gold_unreachable": sum(bool(G[c]["gold_all"]) and not G[c]["gold"] for c in cids)},
           "selected_version": sel["selected_version"], "primary": prim, "secondary_holm": sec, "decision": decision,
           "decision_rule": "significant positive = p<0.05, diff>0, CI lower>0; Supported needs T vs X p_holm<0.05, diff>0",
           "table": table, "pool_coverage": f"{coverage}/{n}", "pairwise": pairwise,
           "mechanism": {"boosted_docs_per_claim_all180": boosted, "A_top10_displaced_mean": displaced,
                         "T": t_status, "X": x_mech},
           "U6_T_authority_accuracy_vs_human_gold_publishers": u6, "U8_T_vs_X_same_type_only": u8,
           "breakdowns": bd, "oracle_ceilings_diagnostic_only": ceilings, "memorisation": mem,
           "bootstrap": load_config()["bootstrap"]}
    h = write_new_json(out_p, res)
    per = [{"claim_id": c, "t_status": tk[c]["status"], "T_keys": " ".join(tk[c]["keys"]), "X_keys": " ".join(xk[c]["keys"]),
            **{f"rank_{m}": brank(c, m) for m in COND}, **{f"hit10_{m}": int(hit(c, m, 10)) for m in COND}} for c in gold_c]
    hc = write_new_json(HO_RES / "family_N_per_claim.json", per)
    log_event("family_N_score_done", decision=decision, primary=prim, secondary=sec, json_sha256=h, per_claim_sha256=hc)
    print(json.dumps({"decision": decision, "primary": prim, "secondary": sec}, indent=1))


if __name__ == "__main__":
    main()
