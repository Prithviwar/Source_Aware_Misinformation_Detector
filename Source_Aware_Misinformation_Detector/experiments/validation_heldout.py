"""Validation of claim-specific authority prediction -> retrieval on a FRESH held-out
sample (pre-registration: docs/validation_preregistration.md; frozen settings below
must not be changed after the freeze).

Subcommands (run in order):
  sample    200 unused dev claims, label-proportional, seed 2027 -> data/processed/averitec_heldout.jsonl
  extract   knowledge-store extracts for those claims (same format/dir as extract_knowledge_store.py)
  rank      bm25, dense, hybrid full rankings -> results/heldout/rankings_<m>.jsonl.gz
  wikidata  Wikidata context for claim/speaker entities (predictor input)
  predict   frozen L+Wctx authority predictor, one call per claim -> results/heldout/authority_raw.jsonl
  probe     memorisation probe, one call per claim -> results/heldout/memorisation_probe_raw.jsonl
  evaluate  all metrics/tests for held-out AND the same analysis on the 120 development claims

Gold data (gold URLs, roles, labels, fact_checking_article) is read ONLY in evaluate().
"""
import csv
import gzip
import json
import random
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from math import comb

from common import (ANNOTATIONS, KS_DIR, KS_ZIP_URL, PROCESSED, RAW, RESULTS, is_placeholder_url, load_ks,
                    load_sample, normalize_url, read_jsonl, registered_domain, write_jsonl)

HO = RESULTS / "heldout"
HO_SAMPLE = PROCESSED / "averitec_heldout.jsonl"
PRED_RAW = HO / "authority_raw.jsonl"
PROBE_RAW = HO / "memorisation_probe_raw.jsonl"

# ------------------------------------------------------------------ FROZEN SETTINGS
SEED_SAMPLE = 2027
N_HELDOUT = 200
LAMBDA = 1.0          # authority weight, fixed before evaluation
POOL = 100            # rerank pool (hybrid top-100)
KS = (5, 10, 20)
BOOT = 10_000
SEED_BOOT = 2026
# -----------------------------------------------------------------------------------


def load_heldout():
    return read_jsonl(HO_SAMPLE)


# ================================================================== sample
def cmd_sample():
    from build_sample import normalise
    dev = json.load(open(RAW / "dev.json", encoding="utf-8"))
    used = {int(r["claim_id"]) for r in load_sample()}
    pool = [i for i in range(len(dev)) if i not in used]
    by = {}
    for i in pool:
        by.setdefault(dev[i]["label"], []).append(i)
    # proportional allocation (largest remainder), fixed order of labels
    labels = ["Refuted", "Supported", "Conflicting Evidence/Cherrypicking", "Not Enough Evidence"]
    raw = {l: N_HELDOUT * len(by[l]) / len(pool) for l in labels}
    alloc = {l: int(raw[l]) for l in labels}
    for l in sorted(labels, key=lambda l: -(raw[l] - alloc[l]))[:N_HELDOUT - sum(alloc.values())]:
        alloc[l] += 1
    rng = random.Random(SEED_SAMPLE)
    chosen = sorted(i for l in labels for i in rng.sample(by[l], alloc[l]))
    assert not set(chosen) & used
    write_jsonl(HO_SAMPLE, [normalise(i, dev[i]) for i in chosen])
    print(f"held-out: {len(chosen)} claims {alloc} (pool {len(pool)}) -> {HO_SAMPLE}")


# ================================================================== extract
def cmd_extract():
    import fsspec
    from extract_knowledge_store import MAX_CHARS
    ids = [r["claim_id"] for r in load_heldout()]
    z = zipfile.ZipFile(fsspec.open(KS_ZIP_URL, block_size=8 * 2**20).open())
    members = {i.filename.split("/")[-1][:-5]: i for i in z.infolist() if i.filename.endswith(".json")}
    t0 = time.time()
    for n, cid in enumerate(ids, 1):
        out = KS_DIR / f"{cid}.jsonl.gz"
        if out.exists():
            continue
        rows = []
        with z.open(members[str(cid)]) as fh:
            for doc_idx, line in enumerate(fh):
                d = json.loads(line)
                text = "\n".join(d.get("url2text") or [])
                rows.append({"doc_idx": doc_idx, "url": d["url"], "url_norm": normalize_url(d["url"]),
                             "text": text[:MAX_CHARS], "n_chars": len(text),
                             "ks_type": d.get("type"), "ks_query": d.get("query")})
        tmp = out.with_suffix(".tmp.gz")
        write_jsonl(tmp, rows)
        tmp.replace(out)
        print(f"[{n}/{len(ids)}] claim {cid}: {len(rows)} docs ({time.time() - t0:.0f}s)", flush=True)
    print("extract done")


# ================================================================== rank
def _save(method, rankings):
    HO.mkdir(parents=True, exist_ok=True)
    with gzip.open(HO / f"rankings_{method}.jsonl.gz", "wt", encoding="utf-8") as fh:
        for cid, ranked in rankings.items():
            fh.write(json.dumps({"claim_id": cid, "ranked": ranked}) + "\n")


def load_rk(method, heldout=True):
    path = (HO if heldout else RESULTS) / f"rankings_{method}.jsonl.gz"
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return {int(r["claim_id"]): [tuple(x) for x in r["ranked"]] for r in map(json.loads, fh)}


def cmd_rank(methods=("bm25", "dense")):
    from baseline_retrieval import rank_bm25, rank_dense, retrieval_corpus
    sample = load_heldout()
    for m in methods:
        if (HO / f"rankings_{m}.jsonl.gz").exists():
            print(f"{m}: exists, skipped")
            continue
        fn = rank_bm25 if m == "bm25" else rank_dense
        out, t0 = {}, time.time()
        for i, r in enumerate(sample, 1):
            docs = retrieval_corpus(r["claim_id"])
            out[r["claim_id"]] = fn(r["claim"], docs)
            print(f"[{m} {i}/{len(sample)}] claim {r['claim_id']} ({len(docs)} docs, {time.time() - t0:.0f}s)", flush=True)
        _save(m, out)
    bm, de = load_rk("bm25"), load_rk("dense")
    hyb = {}
    for cid in bm:
        fused = {}
        for rk in (bm[cid], de[cid]):
            for rank, (u, _) in enumerate(rk, 1):
                fused[u] = fused.get(u, 0.0) + 1.0 / (60 + rank)
        hyb[cid] = sorted(fused.items(), key=lambda x: -x[1])
    _save("hybrid", hyb)
    print("rank done")


# ================================================================== wikidata (predictor input)
def cmd_wikidata():
    from authority_retrieval import claim_entities
    from wikidata_authority import CACHE, fetch_presence, search
    sample = load_heldout()
    cache = json.load(open(CACHE, encoding="utf-8")) if CACHE.exists() else {}
    mentions = {r["claim_id"]: sorted({t for t, _ in claim_entities(r)}) for r in sample}
    todo = sorted({m for ms in mentions.values() for m in ms} - set(cache))
    print(f"wikidata: {len(todo)} new mentions", flush=True)
    for i, m in enumerate(todo, 1):
        cache[m] = search(m)
        if i % 25 == 0:
            print(f"searched {i}/{len(todo)}", flush=True)
            json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    need = sorted({v["qid"] for v in cache.values() if v.get("qid") and "websites" not in v})
    pres = fetch_presence(need)
    for v in cache.values():
        if v.get("qid") in pres:
            v.update(pres[v["qid"]])
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump({str(c): {"mentions": ms} for c, ms in mentions.items()},
              open(HO / "wikidata_claim_mentions.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("wikidata done")


# ================================================================== LLM helpers
def _run_calls(items, raw_path, call_fn, key=("claim_id", "cond"), workers=6):
    done = {}
    if raw_path.exists():
        for line in open(raw_path, encoding="utf-8"):
            x = json.loads(line)
            if x.get("pred"):
                done[tuple(x[k] for k in key)] = x
    for attempt in range(3):  # retry transient CLI failures
        todo = [i for i in items if tuple(i[k] for k in key) not in done]
        print(f"calls: {len(done)} cached, {len(todo)} to run (pass {attempt + 1})", flush=True)
        if not todo:
            break
        with ThreadPoolExecutor(workers) as ex, open(raw_path, "a", encoding="utf-8") as fh:
            for n, res in enumerate(ex.map(call_fn, todo), 1):
                fh.write(json.dumps(res, ensure_ascii=False) + "\n")
                fh.flush()
                if res["pred"]:
                    done[tuple(res[k] for k in key)] = res
                if n % 25 == 0 or not res["pred"]:
                    print(f"[{n}/{len(todo)}] {res['claim_id']} {'ok' if res['pred'] else res['error'][:80]}", flush=True)
    return done


def cmd_predict():
    from authority_resolution import USER, call, wd_context
    from wikidata_authority import CACHE
    cache = json.load(open(CACHE, encoding="utf-8"))
    ment = json.load(open(HO / "wikidata_claim_mentions.json", encoding="utf-8"))
    items = []
    for r in load_heldout():
        cid = int(r["claim_id"])
        base = dict(claim=r["claim"], speaker=r.get("speaker_or_entity") or "None",
                    date=r.get("claim_date") or "unknown", iso=r.get("location_ISO_code") or "unknown")
        items.append({"claim_id": cid, "cond": "L+Wctx",
                      "prompt": USER.format(**base, wd=wd_context(ment[str(cid)]["mentions"], cache))})
    _run_calls(items, PRED_RAW, call)
    print("predict done")


PROBE_SYSTEM = "You have no tools and no web access. Answer from memory only. Output ONLY one JSON object, no prose."
PROBE_USER = """Claim: {claim}
Speaker/claimant field: {speaker}
Claim date: {date}

Do you specifically remember this claim being examined in a published fact-check article?
Return JSON:
{{"recognised": <true only if you specifically remember a fact-check of THIS claim, else false>,
  "fact_checker_name": "<organisation that published the fact-check, or null>",
  "fact_checker_domain": "<its web domain, or null>",
  "verdict": "<true | false | misleading | unverifiable | unknown>"}}"""


def _probe_call(item):
    from authority_resolution import CLAUDE, MODEL
    with tempfile.TemporaryDirectory() as empty:
        p = subprocess.run([CLAUDE, "-p", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
                            "--model", MODEL, "--system-prompt", PROBE_SYSTEM, "--output-format", "json"],
                           input=item["prompt"], capture_output=True, text=True, encoding="utf-8", cwd=empty,
                           timeout=300)
    try:
        env = json.loads(p.stdout)
        m = re.search(r"\{.*\}", env.get("result", ""), re.S)
        pred = json.loads(m.group(0)) if m else None
        return {**{k: v for k, v in item.items() if k != "prompt"}, "pred": pred,
                "cost": env.get("total_cost_usd"), "error": None if pred else "unparseable"}
    except Exception as e:
        return {**{k: v for k, v in item.items() if k != "prompt"}, "pred": None, "error": repr(e) + p.stderr[-300:]}


def cmd_probe():
    items = [{"claim_id": int(r["claim_id"]), "cond": "probe",
              "prompt": PROBE_USER.format(claim=r["claim"], speaker=r.get("speaker_or_entity") or "None",
                                          date=r.get("claim_date") or "unknown")} for r in load_heldout()]
    _run_calls(items, PROBE_RAW, _probe_call)
    print("probe done")


# ================================================================== evaluate (only place gold is read)
def load_preds(path):
    from authority_resolution import pred_keys
    out = {}
    for line in open(path, encoding="utf-8"):
        x = json.loads(line)
        if x.get("cond") == "L+Wctx" and x.get("pred"):
            top = (x["pred"].get("top3") or [])[:3]
            out[int(x["claim_id"])] = {"keys": set().union(*[pred_keys(t) for t in top]) if top else set(),
                                       "top1": pred_keys(top[0]) if top else set(),
                                       "names": [t.get("publisher") or "" for t in top],
                                       "top3": top}
    return out


def cand_key(url):
    from authority_resolution import org_domain, social_key
    return social_key(url) or org_domain(url)


def gold_info(sample, roles=None):
    from authority_resolution import target_keys
    T = {}
    for r in sample:
        cid = int(r["claim_id"])
        docs = {}
        for d in load_ks(cid):  # duplicate URLs: keep the longest text (as claim_docs does)
            u = normalize_url(d["url"])
            if len(d["text"]) >= len(docs.get(u, "")):
                docs[u] = d["text"]
        nonempty = {u for u, t in docs.items() if t.strip()}
        web = [g for g in r["gold_evidence"] if g["is_web_source"]]
        gold_all = {g["source_url_norm"] for g in web}
        gkeys = set().union(*[target_keys(g["source_url"]) for g in web]) if web else set()
        prim = {u for u in gold_all if roles and roles.get((cid, u)) == "A_primary"}
        T[cid] = {"gold": gold_all & nonempty, "gold_all": gold_all, "gold_keys": gkeys,
                  "prim": prim & nonempty, "gold_texts": [docs[u] for u in gold_all & nonempty],
                  "fc_article": r.get("fact_checking_article"), "label": r["gold_label"]}
    return T


def rerank(base, prior, lam=LAMBDA, pool=POOL):
    from authority_retrieval import rerank as _r
    return _r(base, prior, lam, pool)


def best_rank(ranked, target, cap=POOL):
    for i, (u, _) in enumerate(ranked[:cap], 1):
        if u in target:
            return i
    return cap + 1  # absent from top-100


def mcnemar(a, b):
    w = sum(y and not x for x, y in zip(a, b))
    l = sum(x and not y for x, y in zip(a, b))
    n = w + l
    p = 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n)
    return w, l, p


def boot_ci(a, b, seed=SEED_BOOT, n=BOOT):
    rng = random.Random(seed)
    m = len(a)
    d = [int(y) - int(x) for x, y in zip(a, b)]
    stats = sorted(sum(d[rng.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return round(sum(d) / m, 4), round(stats[int(0.025 * n)], 4), round(stats[int(0.975 * n) - 1], 4)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def analyse(sample, heldout, preds, roles=None, probe=None):
    from authority_retrieval import generic_prior
    T = gold_info(sample, roles)
    rk = {m: load_rk(m, heldout) for m in ("bm25", "dense", "hybrid")}
    cids = [int(r["claim_id"]) for r in sample]
    missing_pred = [c for c in cids if c not in preds]
    R = {"bm25": rk["bm25"], "dense": rk["dense"], "hybrid": rk["hybrid"],
         "hybrid+generic": {c: rerank(rk["hybrid"][c], generic_prior) for c in cids},
         "hybrid+authority": {c: rerank(rk["hybrid"][c], lambda u, c=c: float(cand_key(u) in preds[c]["keys"]))
                              for c in cids if c in preds}}
    gold_c = [c for c in cids if T[c]["gold"] and c in preds]
    prim_c = [c for c in cids if T[c]["prim"] and c in preds]
    hit = lambda m, c, k, key="gold": bool(T[c][key] & {u for u, _ in R[m][c][:k]})
    out = {"n_claims": len(cids), "n_missing_predictions": len(missing_pred),
           "n_gold_reachable": len(gold_c), "n_gold_web_any": sum(bool(T[c]["gold_all"]) for c in cids),
           "n_primary_reachable": len(prim_c), "lambda": LAMBDA, "pool": POOL, "table": {}}
    for m in R:
        row = {f"R@{k}": round(sum(hit(m, c, k) for c in gold_c) / len(gold_c), 3) for k in KS}
        row["n_gold"] = len(gold_c)
        if prim_c:
            row.update({f"PrimR@{k}": round(sum(hit(m, c, k, "prim") for c in prim_c) / len(prim_c), 3) for k in KS})
            row["n_primary"] = len(prim_c)
        out["table"][m] = row

    # ---- tests (pre-registered)
    H = {m: {k: [hit(m, c, k) for c in gold_c] for k in KS} for m in ("hybrid", "hybrid+generic", "hybrid+authority")}
    w, l, p = mcnemar(H["hybrid"][10], H["hybrid+authority"][10])
    diff, lo, hi = boot_ci(H["hybrid"][10], H["hybrid+authority"][10])
    out["primary_endpoint"] = {"metric": "R@10", "comparison": "hybrid+authority vs hybrid", "n": len(gold_c),
                               "test": "exact McNemar, two-sided", "H0": "equal per-claim hit@10 probability",
                               "wins": w, "losses": l, "ties": len(gold_c) - w - l, "p": round(p, 5),
                               "diff_R@10": diff, "bootstrap95CI": [lo, hi]}
    fam = [("R@5 vs hybrid", "hybrid", 5), ("R@20 vs hybrid", "hybrid", 20),
           ("R@5 vs generic", "hybrid+generic", 5), ("R@10 vs generic", "hybrid+generic", 10),
           ("R@20 vs generic", "hybrid+generic", 20)]
    sec = []
    for name, ref, k in fam:
        w, l, p = mcnemar(H[ref][k], H["hybrid+authority"][k])
        d, lo, hi = boot_ci(H[ref][k], H["hybrid+authority"][k])
        sec.append({"test": name, "wins": w, "losses": l, "ties": len(gold_c) - w - l, "p": round(p, 5),
                    "diff": d, "bootstrap95CI": [lo, hi]})
    for s, a in zip(sec, holm([s["p"] for s in sec])):
        s["p_holm"] = round(a, 5)
    out["secondary_family_holm"] = sec
    # descriptive: generic vs hybrid
    out["descriptive_generic_vs_hybrid"] = {f"R@{k}": dict(zip(("wins", "losses", "p_uncorrected"),
                                                              mcnemar(H["hybrid"][k], H["hybrid+generic"][k])))
                                            for k in KS}

    # ---- per-claim rank analysis (best gold rank in top-100; absent = 101)
    per = []
    for c in gold_c:
        rb, ra, rg = (best_rank(R[m][c], T[c]["gold"]) for m in ("hybrid", "hybrid+authority", "hybrid+generic"))
        per.append({"claim_id": c, "label": T[c]["label"],
                    "rank_bm25": best_rank(R["bm25"][c], T[c]["gold"]), "rank_dense": best_rank(R["dense"][c], T[c]["gold"]),
                    "rank_hybrid": rb, "rank_generic": rg, "rank_authority": ra,
                    **{f"hit10_{m}": hit(m, c, 10) for m in ("bm25", "dense", "hybrid", "hybrid+generic", "hybrid+authority")},
                    "authority_vs_hybrid": "win" if ra < rb else "loss" if ra > rb else "tie",
                    "authority_vs_generic": "win" if ra < rg else "loss" if ra > rg else "tie",
                    "pred_top3": " | ".join(preds[c]["names"])})
    cnt = lambda key: dict(Counter(x[key] for x in per))
    out["rank_win_loss_tie"] = {"authority_vs_hybrid": cnt("authority_vs_hybrid"),
                                "authority_vs_generic": cnt("authority_vs_generic"),
                                "ties_where_gold_absent_from_both": sum(x["rank_hybrid"] == x["rank_authority"] == POOL + 1 for x in per)}
    out["_per_claim"] = per

    # ---- authority prediction accuracy vs HUMAN gold publishers (no role labels)
    acc = Counter()
    evald = [c for c in cids if c in preds and T[c]["gold_keys"]]
    for c in evald:
        g = T[c]["gold_keys"]
        if preds[c]["top1"] & g:
            acc["top1"] += 1
        if preds[c]["keys"] & g:
            acc["top3"] += 1
        else:
            names = [n.lower() for n in preds[c]["names"] if len(n) >= 4]
            if any(n in t.lower() for n in names for t in T[c]["gold_texts"]):
                acc["attributed_only"] += 1
            else:
                acc["no_match"] += 1
    n = len(evald)
    out["authority_accuracy_vs_human_gold"] = {
        "n": n, "top1_match": f"{acc['top1']}/{n} = {acc['top1'] / n:.3f}",
        "top3_match": f"{acc['top3']}/{n} = {acc['top3'] / n:.3f}",
        "no_key_match_but_name_in_gold_text": acc["attributed_only"], "no_match": acc["no_match"],
        "note": "target = publishers of ALL human gold URLs (news/fact-check pages included) -> lower bound"}
    if roles:
        from authority_resolution import load_targets
        tg, _, _ = load_targets()
        ev = [c for c in tg if tg[c] and c in preds]
        out["authority_accuracy_vs_pilot_primary"] = {
            "n": len(ev), "top1": round(sum(bool(preds[c]["top1"] & tg[c]) for c in ev) / len(ev), 3),
            "top3": round(sum(bool(preds[c]["keys"] & tg[c]) for c in ev) / len(ev), 3)}

    # ---- candidate-pool coverage (hybrid ranking, full list)
    cov = {}
    for K in (50, 100, 200, None):
        tag = f"top{K}" if K else "all_candidates"
        pub = sum(any(cand_key(u) in preds[c]["keys"] for u, _ in rk["hybrid"][c][:K]) for c in gold_c)
        gpub = [c for c in gold_c if any(cand_key(u) in preds[c]["keys"] for u in T[c]["gold"])]
        gin = sum(any(u in T[c]["gold"] and cand_key(u) in preds[c]["keys"] for u, _ in rk["hybrid"][c][:K]) for c in gpub)
        cov[tag] = {"claims_with_predicted_publisher_doc": f"{pub}/{len(gold_c)}",
                    "claims_whose_predicted_publisher_gold_doc_is_in_pool": f"{gin}/{len(gpub)}"}
    out["candidate_pool_coverage"] = cov

    # ---- memorisation probe subset
    if probe is not None:
        rec = {}
        for c in cids:
            p = probe.get(c)
            fc = registered_domain(T[c]["fc_article"] or "") if T[c]["fc_article"] else ""
            d = registered_domain(str((p or {}).get("fact_checker_domain") or "")) if p else ""
            rec[c] = bool(p and fc and d and d == fc)
        out["memorisation_probe"] = {"n_probed": sum(c in probe for c in cids),
                                     "self_reported_recognised": sum(bool((probe.get(c) or {}).get("recognised")) for c in cids),
                                     "likely_recognised_(fact_checker_domain_correct)": sum(rec.values())}
        for name, sub in (("not_recognised", [c for c in gold_c if not rec[c]]),
                          ("recognised", [c for c in gold_c if rec[c]])):
            a = [hit("hybrid", c, 10) for c in sub]
            b = [hit("hybrid+authority", c, 10) for c in sub]
            g = [hit("hybrid+generic", c, 10) for c in sub]
            w, l, p = mcnemar(a, b)
            out["memorisation_probe"][f"subset_{name}"] = {
                "n": len(sub), "R@10_hybrid": round(sum(a) / max(len(sub), 1), 3),
                "R@10_generic": round(sum(g) / max(len(sub), 1), 3),
                "R@10_authority": round(sum(b) / max(len(sub), 1), 3),
                "authority_vs_hybrid": f"+{w}/-{l} p={p:.4f} (exploratory)",
                "authority_top3_acc_vs_human_gold": round(sum(bool(preds[c]["keys"] & T[c]["gold_keys"]) for c in sub) / max(len(sub), 1), 3)}
    return out


def _write(out, stem):
    per = out.pop("_per_claim")
    with open(stem.with_suffix(".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per[0]))
        w.writeheader()
        w.writerows(per)
    json.dump(out, open(stem.with_suffix(".json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False))


def cmd_evaluate():
    from authority_resolution import RAW as DEV_RAW
    roles = {}
    with open(ANNOTATIONS / "source_roles.csv", encoding="utf-8") as fh:
        for x in csv.DictReader(fh):
            roles[(int(x["claim_id"]), normalize_url(x["evidence_url"]))] = x["source_role"]
    probe = {}
    if PROBE_RAW.exists():
        for line in open(PROBE_RAW, encoding="utf-8"):
            x = json.loads(line)
            if x.get("pred"):
                probe[int(x["claim_id"])] = x["pred"]
    print("=== HELD-OUT ===")
    _write(analyse(load_heldout(), True, load_preds(PRED_RAW), probe=probe), HO / "validation_heldout")
    print("=== DEVELOPMENT (same code, exploratory) ===")
    _write(analyse(load_sample(), False, load_preds(DEV_RAW), roles=roles), HO / "validation_dev")


if __name__ == "__main__":
    {"sample": cmd_sample, "extract": cmd_extract, "rank": cmd_rank, "wikidata": cmd_wikidata,
     "predict": cmd_predict, "probe": cmd_probe, "evaluate": cmd_evaluate}[sys.argv[1]]()
