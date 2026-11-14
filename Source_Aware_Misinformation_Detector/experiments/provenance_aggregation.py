"""Step 12: does counting repeated reporting of one underlying source as independent
evidence distort a (deliberately simple) verification verdict?

Evidence set per claim: hybrid top-10 (non-empty docs). For the two focus claims
(#354, #374) also the union of the bm25 and dense top-10.

Per document, ONE clean LLM call (claude -p, no tools, fresh context, never sees
the gold label, gold URLs or other documents) returns
  stance              supports | refutes | not_enough_info | irrelevant   (w.r.t. the claim)
  underlying_source   who originally produced the key information this document
                      relies on (name + domain if known), and
  relation            is_the_source | reports_or_quotes_source | copies_source |
                      independent_analysis | unclear
  interested_party    is that underlying source the claimant / claim subject or a
                      party with a stake in the claim being true?

Source families (heuristics, NOT verified provenance):
  F0 none           every document is its own family              (= naive voting)
  F1 near-duplicate word 5-gram containment >= 0.5 (shorter doc in longer), or the
                    same normalised URL path on two domains (bbc.com / bbc.co.uk)
  F2 + attribution  F1 plus documents whose stated underlying source resolves to
                    the same organisation (domain, else normalised name)
Verdict rule (same for every condition): each family's stance = majority of its
members' supports/refutes; verdict = Supported if S>R, Refuted if R>S,
Conflicting if S=R>0, NEE if no stance.  Variant "+discount": families whose
underlying source is flagged interested_party do not vote.

Gold labels are read only in summarise(). Outputs:
  results/provenance_stance_raw.jsonl, results/provenance_aggregation.csv,
  results/provenance_aggregation_summary.json, results/provenance_families.csv
"""
import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from authority_resolution import org_domain
from baseline_retrieval import claim_docs, load_rankings
from common import RESULTS, load_sample
from provenance_audit import components, shingles

MODEL = "claude-sonnet-5-5"
CLAUDE = os.environ.get("CLAUDE_CODE_EXECPATH") or shutil.which("claude.exe") or shutil.which("claude")
RAW = RESULTS / "provenance_stance_raw.jsonl"
FOCUS = (354, 374)
TOP = 10
MAXCH = 4000

SYSTEM = """You analyse ONE web document for a fact-checking study. You have no tools. Output ONLY one JSON object, no prose."""
USER = """Claim: {claim}
Claimant/speaker: {speaker}   Claim date: {date}

Document URL: {url}
Document text (may be truncated):
<<<
{text}
>>>

Return JSON:
{{"stance": "<supports | refutes | not_enough_info | irrelevant>  (does THIS document's content support or refute the claim?)",
  "key_evidence": "<= 25 words from the document that drive the stance, or empty",
  "underlying_source_name": "<who originally produced the key information this document relies on for the claim; the document's own publisher if it is first-hand>",
  "underlying_source_domain": "<that source's web domain if known, else null>",
  "relation": "<is_the_source | reports_or_quotes_source | copies_source | independent_analysis | unclear>",
  "interested_party": <true if that underlying source is the claimant, the subject of the claim, or has an evident stake in the claim being judged true; else false>}}"""


def evidence_sets(sample):
    hyb, bm, de = load_rankings("hybrid"), load_rankings("bm25"), load_rankings("dense")
    out = {}
    for r in sample:
        cid = int(r["claim_id"])
        docs = {d["url_norm"]: d for d in claim_docs(cid) if d["text"].strip()}
        urls = [u for u, _ in hyb[cid] if u in docs][:TOP]
        if cid in FOCUS:
            for rk in (bm, de):
                urls += [u for u, _ in rk[cid] if u in docs and u not in urls][:TOP]
                urls = list(dict.fromkeys(urls))
        out[cid] = [docs[u] for u in urls]
    return out


def call(item):
    with tempfile.TemporaryDirectory() as empty:
        p = subprocess.run([CLAUDE, "-p", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
                            "--model", MODEL, "--system-prompt", SYSTEM, "--output-format", "json"],
                           input=item["prompt"], capture_output=True, text=True, encoding="utf-8", cwd=empty, timeout=300)
    try:
        env = json.loads(p.stdout)
        m = re.search(r"\{.*\}", env.get("result", ""), re.S)
        pred = json.loads(m.group(0)) if m else None
        return {k: v for k, v in item.items() if k != "prompt"} | {"pred": pred, "cost": env.get("total_cost_usd"),
                                                                    "error": None if pred else "unparseable"}
    except Exception as e:
        return {k: v for k, v in item.items() if k != "prompt"} | {"pred": None, "error": repr(e) + p.stderr[-500:]}


def run_stance(sample, ev):
    done = {}
    if RAW.exists():
        for line in open(RAW, encoding="utf-8"):
            x = json.loads(line)
            if x.get("pred"):
                done[(x["claim_id"], x["url"])] = x
    items = []
    for r in sample:
        cid = int(r["claim_id"])
        for d in ev[cid]:
            if (cid, d["url_norm"]) not in done:
                items.append({"claim_id": cid, "url": d["url_norm"], "prompt": USER.format(
                    claim=r["claim"], speaker=r.get("speaker_or_entity") or "None", date=r.get("claim_date"),
                    url=d["url_norm"], text=d["text"][:MAXCH])})
    print(f"stance calls: {len(done)} cached, {len(items)} to run", flush=True)
    with ThreadPoolExecutor(8) as ex, open(RAW, "a", encoding="utf-8") as fh:
        for n, res in enumerate(ex.map(call, items), 1):
            fh.write(json.dumps(res, ensure_ascii=False) + "\n")
            fh.flush()
            if res["pred"]:
                done[(res["claim_id"], res["url"])] = res
            if n % 50 == 0 or not res["pred"]:
                print(f"[{n}/{len(items)}] {res['claim_id']} {res['url'][:50]} {res['error'] or 'ok'}", flush=True)
    return done


def _name(s):
    s = re.sub(r"\(.*?\)", "", (s or "").lower())
    s = re.sub(r"\b(the|official|office|of|press|release|statement|website|account|department)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


def source_key(p):
    d = org_domain(str(p.get("underlying_source_domain") or ""))
    return ("d:" + d) if d else ("n:" + _name(p.get("underlying_source_name")))


def families(docs, preds, mode):
    n = len(docs)
    if mode == "F0":
        return [{i} for i in range(n)]
    sh = [shingles(d["text"]) for d in docs]
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            pi, pj = docs[i]["url_norm"].partition("/")[2], docs[j]["url_norm"].partition("/")[2]
            same_path = len(pi) > 15 and pi == pj
            if same_path or (sh[i] and sh[j] and len(sh[i] & sh[j]) / min(len(sh[i]), len(sh[j])) >= 0.5):
                edges.append((i, j))
    if mode == "F2":
        keys = [source_key(p) if p else None for p in preds]
        own = [org_domain(d["url_norm"]) for d in docs]
        for i in range(n):
            for j in range(i + 1, n):
                if not preds[i] or not preds[j] or preds[i].get("relation") == "independent_analysis" \
                        or preds[j].get("relation") == "independent_analysis":
                    continue
                ki, kj = keys[i], keys[j]
                if ki and kj and len(ki) > 3 and (ki == kj or ki == "d:" + own[j] or kj == "d:" + own[i]):
                    edges.append((i, j))
    return components(n, edges)


def verdict(docs, preds, fams, discount=False):
    S = R = 0
    for f in fams:
        st = Counter(preds[i]["stance"] for i in f if preds[i] and preds[i].get("stance") in ("supports", "refutes"))
        if discount and any(preds[i] and preds[i].get("interested_party") is True for i in f
                            if preds[i] and preds[i].get("stance") in ("supports", "refutes")):
            continue
        if st["supports"] > st["refutes"]:
            S += 1
        elif st["refutes"] > st["supports"]:
            R += 1
    v = "Supported" if S > R else "Refuted" if R > S else ("Conflicting" if S else "NEE")
    return v, S, R


def summarise(sample, ev, done):
    gold = {int(r["claim_id"]): r["gold_label"] for r in sample}
    norm = {"Conflicting Evidence/Cherrypicking": "Conflicting", "Not Enough Evidence": "NEE"}
    conds = [("F0", False), ("F1", False), ("F2", False), ("F0", True), ("F2", True)]
    rows, famrows = [], []
    for r in sample:
        cid = int(r["claim_id"])
        docs = ev[cid]
        preds = [done.get((cid, d["url_norm"]), {}).get("pred") for d in docs]
        row = {"claim_id": cid, "gold": norm.get(gold[cid], gold[cid]), "n_docs": len(docs),
               "n_stance_docs": sum(bool(p and p.get("stance") in ("supports", "refutes")) for p in preds)}
        for mode, disc in conds:
            fams = families(docs, preds, mode)
            v, S, R = verdict(docs, preds, fams, disc)
            tag = mode + ("+discount" if disc else "")
            row.update({f"{tag}_verdict": v, f"{tag}_S": S, f"{tag}_R": R, f"{tag}_n_families": len(fams)})
            if mode == "F2" and not disc:
                for k, f in enumerate(fams):
                    if len(f) > 1:
                        famrows.append({"claim_id": cid, "family": k, "size": len(f),
                                        "members": " | ".join(
                                            f"{docs[i]['url_norm'][:70]} [{(preds[i] or {}).get('stance')}; "
                                            f"{(preds[i] or {}).get('relation')}; src={(preds[i] or {}).get('underlying_source_name')}"
                                            f"{'; INTERESTED' if (preds[i] or {}).get('interested_party') else ''}]"
                                            for i in sorted(f))})
        rows.append(row)
    tags = ["F0", "F1", "F2", "F0+discount", "F2+discount"]
    s = {"claims": len(rows), "docs": sum(r["n_docs"] for r in rows),
         "stance_calls_ok": len(done), "llm_cost_usd": round(sum(x.get("cost") or 0 for x in done.values()), 2),
         "stance_distribution": Counter((x["pred"] or {}).get("stance") for x in done.values()),
         "relation_distribution": Counter((x["pred"] or {}).get("relation") for x in done.values()),
         "interested_party_docs": sum(bool((x["pred"] or {}).get("interested_party")) for x in done.values()),
         "mean_units": {t: round(sum(r[f"{t}_n_families"] for r in rows) / len(rows), 2) for t in ["F0", "F1", "F2"]},
         "claims_with_any_collapse": {t: sum(r[f"{t}_n_families"] < r["n_docs"] for r in rows) for t in ["F1", "F2"]},
         "accuracy_vs_gold": {t: round(sum(r[f"{t}_verdict"] == r["gold"] for r in rows) / len(rows), 3) for t in tags},
         "accuracy_by_gold_label": {t: {g: f"{sum(r[f'{t}_verdict'] == g for r in rows if r['gold'] == g)}/"
                                           f"{sum(r['gold'] == g for r in rows)}" for g in
                                        ["Refuted", "Supported", "Conflicting", "NEE"]} for t in tags},
         "verdict_changes_vs_F0": {}}
    for t in tags[1:]:
        ch = [r for r in rows if r[f"{t}_verdict"] != r["F0_verdict"]]
        s["verdict_changes_vs_F0"][t] = {
            "n": len(ch), "to_correct": sum(r[f"{t}_verdict"] == r["gold"] for r in ch),
            "from_correct": sum(r["F0_verdict"] == r["gold"] for r in ch),
            "claims": [f"{r['claim_id']}: {r['F0_verdict']}({r['F0_S']}-{r['F0_R']}) -> {r[f'{t}_verdict']}"
                       f"({r[f'{t}_S']}-{r[f'{t}_R']}) gold={r['gold']}" for r in ch]}
    b = s["verdict_changes_vs_F0"]
    for t in tags[1:]:  # exact McNemar on correctness vs naive
        w, l = b[t]["to_correct"], b[t]["from_correct"]
        from math import comb
        nn = w + l
        b[t]["mcnemar_p"] = 1.0 if nn == 0 else round(min(1, 2 * sum(comb(nn, i) for i in range(min(w, l) + 1)) / 2 ** nn), 3)
    with open(RESULTS / "provenance_aggregation.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(RESULTS / "provenance_families.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["claim_id", "family", "size", "members"])
        w.writeheader()
        w.writerows(famrows)
    json.dump(s, open(RESULTS / "provenance_aggregation_summary.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(s, indent=1))


def main():
    sample = load_sample()
    ev = evidence_sets(sample)
    done = run_stance(sample, ev)
    summarise(sample, ev, done)


if __name__ == "__main__":
    main()
