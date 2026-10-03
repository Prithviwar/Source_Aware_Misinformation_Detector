"""Step 10: authority-resolution study (NO retrieval).

Question: given only a claim (+ inference-time metadata), can an LLM, optionally
with Wikidata, name the publisher that is AUTHORITATIVE FOR THIS CLAIM, i.e. the
pilot-primary publisher of the claim's gold evidence?

Conditions (top-3 ranked publishers per claim):
  W        Wikidata only: official websites / social handles (P856, P2002, P2013,
           P2003) of the entities named in the claim or speaker field, in mention
           order (cache from wikidata_authority.py; no LLM).
  L        LLM only: claim, speaker, claim_date, location_ISO_code.
  L+Wctx   same prompt + the Wikidata facts for the claim's own entities.
  L+Wgnd   post-hoc grounding of L+Wctx: every predicted publisher NAME is
           looked up on Wikidata; its official website is added as an alternative
           domain for that rank (fixes guessed/hallucinated domains).

Model inputs NEVER include: gold URLs or domains, evidence text, QA pairs,
justification, label, fact-checking article, original_claim_url, reporting_source,
or any role annotation. The pilot primary label (data/annotations/source_roles.csv)
is read ONLY in evaluate(), after all predictions are cached.

LLM: `claude -p` (Claude Code CLI) with --tools "" (no tools, no web access),
a replaced system prompt, no session persistence, run from an empty directory,
so every call is an independent fresh context. The model that ORCHESTRATED this
study had seen gold domains; the predictor never did.

Outputs: results/authority_resolution_raw.jsonl (cached raw responses),
         results/authority_resolution_predictions.csv, results/authority_resolution_summary.json
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import ANNOTATIONS, RESULTS, full_host, load_sample, normalize_url, registered_domain

MODEL = "claude-opus-5-5"
# Windows: the npm `claude` entry is a .cmd shim; call the real binary so argv is passed verbatim.
CLAUDE = os.environ.get("CLAUDE_CODE_EXECPATH") or shutil.which("claude.exe") or shutil.which("claude")
RAW = RESULTS / "authority_resolution_raw.jsonl"
WD_CACHE = RESULTS / "wikidata_resolution.json"
WD_NAME_CACHE = RESULTS / "wikidata_publisher_resolution.json"
SOCIAL = {"twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com", "linkedin.com"}
NEWS_FC_HINT = re.compile(r"(news|times|post|herald|tribune|guardian|reuters|apnews|bbc|cnn|factcheck|politifact|snopes|"
                          r"fullfact|boomlive|altnews|leadstories|afp|telegraph|journal|daily|express|gazette)", re.I)

SYSTEM = """You are an expert fact-checking researcher. You identify WHO IS AUTHORITATIVE FOR A SPECIFIC CLAIM.

Definition. The authoritative (primary) source for a claim is the publisher of first-hand evidence about the fact at issue:
- the government body, intergovernmental body, court, legislature or regulator that issued, recorded or holds the relevant fact, data, law or decision;
- the organisation or company itself, when the claim is about its own actions, products, policies or statements;
- the original research/data producer;
- for claims about what someone said or posted: that person's or account's own statement/post/official channel.
It is NOT simply a generally credible website. News outlets, fact-checkers, encyclopedias and aggregators report ABOUT facts; do not name them unless the outlet itself is the originator or subject of the fact.

Rules. You have no tools and no web access; answer from knowledge. Give your best ranked guesses even if unsure. Several sources may be legitimately authoritative; say so. Output ONLY one JSON object, no prose, no code fences."""

USER = """Claim: {claim}
Speaker/claimant field: {speaker}
Claim date: {date}
Country (ISO): {iso}
{wd}
Return JSON with exactly these keys:
{{"fact_at_issue": "<the specific checkable fact, one sentence>",
  "relevant_entity": "<main person/organisation the claim is about or attributed to>",
  "claim_kind": "<one of: statement_by_someone | action_or_policy_of_org | official_statistic_or_data | law_or_legal_decision | scientific_or_health_fact | event_occurrence | other>",
  "authority_situation": "<one of: single_clear_authority | multiple_legitimate_authorities | no_clear_authority>",
  "top3": [
    {{"publisher": "<name>", "domain": "<registered web domain, e.g. who.int, or null>", "social_account": "<platform/handle e.g. twitter.com/WHO, or null>", "publisher_type": "<government | intergovernmental | court_or_legislature | regulator_or_database | organisation | company | person | research | news | other>", "why": "<short>"}},
    ... exactly 3 items, most likely first ...
  ],
  "confidence": <0.0-1.0 that the top-1 publisher is right>}}"""


# ---------------------------------------------------------------- inputs

def wd_context(mentions, cache) -> str:
    lines = []
    for m in mentions:
        v = cache.get(m, {})
        if not v.get("qid"):
            lines.append(f"- '{m}': no Wikidata item found")
            continue
        sites = ", ".join(v.get("websites", [])[:3]) or "none"
        hs = "; ".join(f"{p}: {', '.join(x[:2])}" for p, x in v.get("handles", {}).items()) or "none"
        lines.append(f"- '{m}' -> {v.get('label')} ({v.get('description') or 'no description'}); "
                     f"official website: {sites}; accounts: {hs}")
    if not lines:
        return "Wikidata facts for entities named in the claim/speaker: (no entities detected)\n"
    return "Wikidata facts for entities named in the claim/speaker (automatic lookup, may be wrong or irrelevant):\n" + "\n".join(lines) + "\n"


def inputs(sample, target_ids):
    wd_claims = json.load(open(RESULTS / "wikidata_claim_authorities.json", encoding="utf-8"))
    cache = json.load(open(WD_CACHE, encoding="utf-8"))
    out = []
    for r in sample:
        cid = int(r["claim_id"])
        if cid not in target_ids:
            continue
        base = dict(claim=r["claim"], speaker=r.get("speaker_or_entity") or "None",
                    date=r.get("claim_date") or "unknown", iso=r.get("location_ISO_code") or "unknown")
        out.append({"claim_id": cid, "cond": "L", "prompt": USER.format(**base, wd="")})
        out.append({"claim_id": cid, "cond": "L+Wctx",
                    "prompt": USER.format(**base, wd=wd_context(wd_claims[str(cid)]["mentions"], cache))})
        out.append({"claim_id": cid, "cond": "L+Wctx_rerun",  # identical prompt, independent call: stability
                    "prompt": USER.format(**base, wd=wd_context(wd_claims[str(cid)]["mentions"], cache))})
    return out


# ---------------------------------------------------------------- LLM calls

def call(item):
    with tempfile.TemporaryDirectory() as empty:
        p = subprocess.run(
            [CLAUDE, "-p", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
             "--model", MODEL, "--system-prompt", SYSTEM, "--output-format", "json"],
            input=item["prompt"], capture_output=True, text=True, encoding="utf-8", cwd=empty, timeout=300)
    try:
        env = json.loads(p.stdout)
        text = env.get("result", "")
        m = re.search(r"\{.*\}", text, re.S)
        pred = json.loads(m.group(0)) if m else None
        return {**item, "raw": text, "pred": pred, "cost": env.get("total_cost_usd"),
                "model": list(env.get("modelUsage", {}) or [MODEL]), "error": None if pred else "unparseable"}
    except Exception as e:
        return {**item, "raw": p.stdout[-2000:] + p.stderr[-2000:], "pred": None, "error": repr(e)}


def run_llm(items):
    done = {}
    if RAW.exists():
        for line in open(RAW, encoding="utf-8"):
            x = json.loads(line)
            if x.get("pred"):
                done[(x["claim_id"], x["cond"])] = x
    todo = [i for i in items if (i["claim_id"], i["cond"]) not in done]
    print(f"LLM calls: {len(done)} cached, {len(todo)} to run", flush=True)
    with ThreadPoolExecutor(6) as ex, open(RAW, "a", encoding="utf-8") as fh:
        for n, res in enumerate(ex.map(call, todo), 1):
            fh.write(json.dumps(res, ensure_ascii=False) + "\n")
            fh.flush()
            if res["pred"]:
                done[(res["claim_id"], res["cond"])] = res
            print(f"[{n}/{len(todo)}] claim {res['claim_id']} {res['cond']} {'ok' if res['pred'] else res['error']}", flush=True)
    return done


# ---------------------------------------------------------------- keys & matching

def org_domain(host_or_url: str) -> str:
    """Registered domain, with gov.uk (a public suffix) collapsed to one publisher."""
    s = (host_or_url or "").strip().lower()
    if not s or s in ("null", "none"):
        return ""
    host = full_host(s if "://" in s else "http://" + s)
    if host == "gov.uk" or host.endswith(".gov.uk") and registered_domain(host) in ("", "service.gov.uk", "www.gov.uk"):
        return "gov.uk"
    d = registered_domain(host) or host
    return "twitter.com" if d == "x.com" else d


def social_key(url_or_handle: str) -> str | None:
    s = normalize_url(url_or_handle or "")
    host, _, path = s.partition("/")
    host = host.replace("mobile.", "").replace("m.", "", 1) if host.startswith(("mobile.", "m.")) else host
    dom = registered_domain(host) or host
    if dom not in SOCIAL or host not in (dom, "in." + dom):
        return None
    path = path.split("?")[0]
    handle = path.split("/")[0].lstrip("@") if path else ""
    if handle in ("company", "pg", "people", "in"):
        handle = path.split("/")[1] if "/" in path else ""
    if not handle or handle in ("search", "status"):
        return None
    return f"{'twitter.com' if dom == 'x.com' else dom}/{re.sub(r'[^a-z0-9_.]', '', handle.lower())}"


def target_keys(url: str) -> set[str]:
    """Publisher keys of one pilot-primary gold URL. archive.ph snapshots hide the publisher -> empty."""
    u = normalize_url(url)
    dom = org_domain(u)
    if dom in ("archive.ph", "archive.org", ""):
        return set()
    if dom in SOCIAL:
        m = re.findall(r"from(?:%3A|:)([A-Za-z0-9_]+)", url)
        if m:
            return {f"twitter.com/{h.lower()}" for h in m}
        k = social_key(u)
        return {k} if k else {dom}  # e.g. blog.twitter.com = Twitter the company
    return {dom}


def pred_keys(p: dict) -> set[str]:
    keys = set()
    if p.get("domain"):
        d = org_domain(str(p["domain"]))
        if d and d not in SOCIAL:
            keys.add(d)
        elif d in SOCIAL:  # e.g. "blog.twitter.com" for Twitter-the-company
            keys.add(d)
    if p.get("social_account"):
        k = social_key(str(p["social_account"]))
        if k:
            keys.add(k)
    for d in p.get("_grounded", []):
        keys.add(org_domain(d))
    return keys - {""}


# ---------------------------------------------------------------- Wikidata grounding of predicted names

def ground_names(done):
    from wikidata_authority import fetch_presence, search
    cache = json.load(open(WD_NAME_CACHE, encoding="utf-8")) if WD_NAME_CACHE.exists() else {}
    names = sorted({t["publisher"] for x in done.values() if x["cond"] == "L+Wctx"
                    for t in (x["pred"].get("top3") or []) if t.get("publisher")} - set(cache))
    print(f"Wikidata grounding: {len(names)} new publisher names", flush=True)
    for i, n in enumerate(names, 1):
        cache[n] = search(n)
        if i % 25 == 0:
            json.dump(cache, open(WD_NAME_CACHE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    need = sorted({v["qid"] for v in cache.values() if v.get("qid") and "websites" not in v})
    for q, pres in fetch_presence(need).items():
        for v in cache.values():
            if v.get("qid") == q:
                v.update(pres)
    json.dump(cache, open(WD_NAME_CACHE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return cache


# ---------------------------------------------------------------- evaluation (the ONLY place gold is read)

def load_targets():
    tg, artifact = defaultdict(set), defaultdict(list)
    urls = defaultdict(list)
    with open(ANNOTATIONS / "source_roles.csv", encoding="utf-8") as fh:
        for x in csv.DictReader(fh):
            if x["source_role"] == "A_primary":
                cid = int(x["claim_id"])
                tg[cid] |= target_keys(x["evidence_url"])
                urls[cid].append(normalize_url(x["evidence_url"]))
                artifact[cid].append("claim artifact" in x["notes"] or "speaker's own" in x["notes"]
                                     or "spread the claim" in x["notes"])
    return tg, urls, {c: all(v) for c, v in artifact.items()}


def rank_of_hit(ranked: list[set[str]], gold: set[str]):
    for i, ks in enumerate(ranked, 1):
        if ks & gold:
            return i
    return None


def evaluate(sample, done, name_cache):
    tg, urls, artifact_only = load_targets()
    wd_claims = json.load(open(RESULTS / "wikidata_claim_authorities.json", encoding="utf-8"))
    evaluable = sorted(c for c in tg if tg[c])
    iso_of = {int(r["claim_id"]): r.get("location_ISO_code") for r in sample}
    text_of = {int(r["claim_id"]): _alnum(r["claim"] + " " + str(r.get("speaker_or_entity"))) for r in sample}
    rows, per = [], defaultdict(dict)
    for cid in sorted(tg):
        row = {"claim_id": cid, "claim": next(r["claim"] for r in sample if int(r["claim_id"]) == cid),
               "pilot_primary_urls": " | ".join(urls[cid]), "target_keys": " ".join(sorted(tg[cid])),
               "evaluable": bool(tg[cid]), "primary_is_claim_artifact_only": artifact_only[cid]}
        w = wd_claims[str(cid)]
        wr = [{d} for d in w["domains"]][:3]
        wr += [{f"{p}/{h}" for p in ("twitter.com", "facebook.com", "instagram.com")} for h in w["handles"]][:max(0, 3 - len(wr))]
        conds = {"W": wr, "G": [{d} for d in generic_guess(cid, tg, iso_of)]}
        for cond in ("L", "L+Wctx", "L+Wctx_rerun"):
            x = done.get((cid, cond))
            top = (x["pred"].get("top3") or [])[:3] if x else []
            conds[cond] = [pred_keys(t) for t in top]
            if cond == "L+Wctx":
                g = []
                for t in top:
                    v = name_cache.get(t.get("publisher"), {})
                    g.append(pred_keys({**t, "_grounded": [d for d in v.get("websites", [])]}))
                conds["L+Wgnd"] = g
                p = x["pred"] if x else {}
                row.update(relevant_entity=p.get("relevant_entity"), fact_at_issue=p.get("fact_at_issue"),
                           claim_kind=p.get("claim_kind"), authority_situation=p.get("authority_situation"),
                           confidence=p.get("confidence"),
                           top1=_fmt(top[0]) if top else "", top2=_fmt(top[1]) if len(top) > 1 else "",
                           top3=_fmt(top[2]) if len(top) > 2 else "",
                           top_types=" ".join(str(t.get("publisher_type")) for t in top))
            if cond == "L" and x:
                row["L_top1"] = _fmt(top[0]) if top else ""
        for cond, ranked in conds.items():
            h = rank_of_hit(ranked, tg[cid])
            per[cond][cid] = h
            row[f"{cond}_hit_rank"] = h
            row[f"{cond}_covered"] = bool(ranked and any(ranked))
        row["authority_named_in_claim"] = any(_label(k) in text_of[cid] for k in tg[cid] if len(_label(k)) >= 3)
        rows.append(row)

    summ = {"n_claims_with_pilot_primary": len(tg), "n_evaluable": len(evaluable),
            "not_evaluable(archive.ph-only targets)": sorted(set(tg) - set(evaluable)), "conditions": {}}
    named = {r["claim_id"]: r["authority_named_in_claim"] for r in rows}
    subsets = {"all": evaluable,
               "excl_claim_artifact_primaries": [c for c in evaluable if not artifact_only[c]],
               "authority_named_in_claim": [c for c in evaluable if named[c]],
               "authority_not_named_in_claim": [c for c in evaluable if not named[c]]}
    kinds = {r["claim_id"]: r.get("claim_kind") for r in rows}
    for k in sorted({v for v in kinds.values() if v}):
        subsets[f"kind={k}"] = [c for c in evaluable if kinds[c] == k]
    for cond in ("W", "G", "L", "L+Wctx", "L+Wctx_rerun", "L+Wgnd"):
        summ["conditions"][cond] = {}
        for sname, ids in subsets.items():
            hs = [per[cond][c] for c in ids]
            cov = [next(r for r in rows if r["claim_id"] == c)[f"{cond}_covered"] for c in ids]
            summ["conditions"][cond][sname] = {
                "n": len(ids), "top1": round(sum(h == 1 for h in hs) / len(ids), 3),
                "top3": round(sum(h is not None for h in hs) / len(ids), 3),
                "top1_count": sum(h == 1 for h in hs), "top3_count": sum(h is not None for h in hs),
                "coverage": round(sum(cov) / len(ids), 3)}
    lw = [done[(c, "L+Wctx")]["pred"] for c in evaluable if (c, "L+Wctx") in done]
    summ["L+Wctx_authority_situation"] = Counter(p.get("authority_situation") for p in lw)
    summ["L+Wctx_claim_kind"] = Counter(p.get("claim_kind") for p in lw)
    types = Counter(str(t.get("publisher_type")) for p in lw for t in (p.get("top3") or [])[:3])
    summ["L+Wctx_predicted_publisher_types(all ranks)"] = types
    summ["L+Wctx_top1_type"] = Counter(str((p.get("top3") or [{}])[0].get("publisher_type")) for p in lw)
    a = [c for c in evaluable if (c, "L+Wctx") in done and (c, "L+Wctx_rerun") in done]
    summ["stability_L+Wctx_vs_rerun"] = {
        "n": len(a),
        "same_top1_key": sum(bool(_top_keys(done, c, "L+Wctx", 1) & _top_keys(done, c, "L+Wctx_rerun", 1)) for c in a),
        "top1_hit_agree": sum((per["L+Wctx"][c] == 1) == (per["L+Wctx_rerun"][c] == 1) for c in a),
        "top3_hit_agree": sum((per["L+Wctx"][c] is not None) == (per["L+Wctx_rerun"][c] is not None) for c in a)}
    summ["llm_calls"] = len(done)
    summ["llm_cost_usd"] = round(sum(x.get("cost") or 0 for x in done.values()), 3)
    with open(RESULTS / "authority_resolution_predictions.csv", "w", newline="", encoding="utf-8") as fh:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    json.dump(summ, open(RESULTS / "authority_resolution_summary.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(summ, indent=1))


def _alnum(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _label(key: str) -> str:
    """'twitter.com/wbpolice' -> 'wbpolice'; 'who.int' -> 'who'; 'upsc.gov.in' -> 'upsc'"""
    return _alnum(key.split("/")[1]) if "/" in key else _alnum(key.split(".")[0])


def _top_keys(done, cid, cond, k):
    top = (done[(cid, cond)]["pred"].get("top3") or [])[:k]
    return set().union(*[pred_keys(t) for t in top]) if top else set()


def generic_guess(cid, tg, iso_of):
    """Claim-INDEPENDENT baseline (leave-one-out): the 3 most frequent pilot-primary publisher
    keys among the OTHER claims from the same country, backfilled with the global ranking.
    Tests whether 'guess the usual authorities' explains the LLM's score."""
    same, glob = Counter(), Counter()
    for c, keys in tg.items():
        if c == cid:
            continue
        glob.update(keys)
        if iso_of.get(c) == iso_of.get(cid):
            same.update(keys)
    ranked = [k for k, _ in same.most_common()] + [k for k, _ in glob.most_common()]
    return list(dict.fromkeys(ranked))[:3]


def _fmt(t):
    return f"{t.get('publisher')} [{t.get('domain') or ''}{' ' + t['social_account'] if t.get('social_account') else ''}] ({t.get('publisher_type')})"


def main():
    sample = load_sample()
    if "--all-claims" in sys.argv:
        # predictions (L+Wctx only) for the claims WITHOUT a pilot primary too, so the retrieval
        # plug-in (predicted_authority_retrieval.py) can be scored on gold recall over all claims.
        # No label is read; evaluate() still scores only the 73 pilot-primary claims.
        items = [i for i in inputs(sample, {int(r["claim_id"]) for r in sample}) if i["cond"] == "L+Wctx"]
        run_llm(items)
        return
    tg, _, _ = load_targets()  # only the SET OF CLAIM IDS is used before prediction (which claims to run)
    items = inputs(sample, set(tg))
    done = run_llm(items)
    if "--no-ground" in sys.argv:
        name_cache = json.load(open(WD_NAME_CACHE, encoding="utf-8")) if WD_NAME_CACHE.exists() else {}
    else:
        name_cache = ground_names(done)
    evaluate(sample, done, name_cache)


if __name__ == "__main__":
    main()
