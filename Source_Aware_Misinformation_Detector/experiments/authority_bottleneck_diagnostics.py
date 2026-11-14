"""Read-only diagnostics for docs/authority_resolution_bottleneck_analysis.md.

Status: EXPLORATORY / DIAGNOSTIC. Not preregistered. Uses gold by design (every number here is a
ceiling, an oracle or an error count, never a deployable system score). No LLM call, no retrieval
re-run, no frozen file is written.

  python authority_bottleneck_diagnostics.py

Inputs (all frozen, read-only): the 200 held-out claims, the frozen full bm25/dense/hybrid rankings
(each lists every non-empty knowledge-store document of the claim, so gold ∩ ranking = reachable
gold, which the gate checks against the stored counts), the frozen A-H top-100 rankings, the frozen
L+Wctx predictions and, for descriptive role counts only, the existing MODEL_GENERATED evidence-role
labels (no AI-primary recall is computed). The knowledge-store extracts (data/raw) are not needed.

Gate: before any analysis the script reproduces the stored reachable-gold counts, every stored
GoldR@{1,3,5,10,20} of systems A-H, the stored top-100 order of D, the stored targeted top-10 list of
every claim, and the Phase-1 oracle-publisher R@10. It stops if any check fails.

Outputs: results/authority_bottleneck_diagnostics/{summary.json, per_claim.csv, gold_urls.csv}.
Refuses to overwrite an existing output directory.
"""
import csv
import datetime
import gzip
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

from authority_resolution import NEWS_FC_HINT, SOCIAL, _alnum, _label, target_keys
from authority_retrieval import (MAJOR_NEWS, PLATFORMS, REFERENCE, claim_entities, country_of, entity_keys,
                                 entity_match, full_prior, generic_prior, is_gov, ISO_TO_TLD)
from authority_retrieval import rerank as rerank_any
from common import ANNOTATIONS, PROCESSED, RESULTS, read_jsonl
from source_targeted import RRF_K, cand_key, primary_authority_candidates
from validation_heldout import PRED_RAW, boot_ci, mcnemar

OUT = RESULTS / "authority_bottleneck_diagnostics"
KS = (1, 3, 5, 10, 20)
DEPTHS = (1, 3, 5, 10, 20, 50, 100, 200, 300, 500, 1000)
SYS = {"A": "hybrid", "B": "hybrid+generic", "C": "hybrid+heuristic", "D": "hybrid+llm_authority",
       "E": "targeted", "F": "hybrid+targeted", "G": "hybrid+targeted+llm_authority",
       "Ctrl": "control:hybrid_top(100+added)", "H_ORACLE": "ORACLE:targeted+prior"}
AI_ROLES = ANNOTATIONS / "heldout_primary_package" / "ai" / "MODEL_GENERATED_evidence_heldout_runA_CLAUDE_OPUS_5_5.csv"
AI_KEY = ANNOTATIONS / "heldout_annotator_key.csv"
# Heuristic list for describing gold publishers; NOT used by any retrieval method.
FACTCHECK = {"politifact.com", "snopes.com", "factcheck.org", "fullfact.org", "boomlive.in", "altnews.in",
             "leadstories.com", "factly.in", "africacheck.org", "checkyourfact.com", "truthorfiction.com",
             "healthfeedback.org", "sciencefeedback.co", "newsmeter.in", "newschecker.in", "vishvasnews.com",
             "poynter.org", "dubawa.org", "pesacheck.org", "verafiles.org", "misbar.com", "factcrescendo.com",
             "logically.ai", "logicallyfacts.com", "aap.com.au", "thequint.com", "newsmobile.in", "thelogicalindian.com",
             "polygraph.info"}
# Manual class for the 143 held-out gold publisher keys the rules above put in 'other_site' (classified by the
# analysing session from the domain name alone, 2026-10-28; descriptive only, not validated, never used by retrieval).
_OV = {
    "gov_intergov": "canada.ca gov.uk state.wi.us hse.ie ohchr.org opcw.org undocs.org",
    "news_like": "247sports.com abujapress.com alarabiya.net businessdesk.co.nz businessinsider.com businesstoday.in "
                 "cbs58.com cbslocal.com channelstv.com devex.com espn.com espncricinfo.com fortune.com fox32chicago.com "
                 "fox6now.com go.com hollywoodunlocked.com idiva.com india.com indiatoday.in insider.com jsonline.com "
                 "kqed.org khn.org lawenforcementtoday.com mcclatchydc.com metro.co.uk mirror.co.uk money.com newyorker.com "
                 "nme.com pbs.org qz.com radio-canada.ca reformer.com rt.com si.com techcrunch.com theatlantic.com "
                 "thelogic.co thenationonlineng.net thesource.com trtworld.com vanguardngr.com vox.com westafricareporters.com "
                 "yahoo.com tagesspiegel.de livescience.com nationalgeographic.com healthline.com scotusblog.com "
                 "lawfareblog.com theconversation.com thebulletin.org",
    "reference": "biography.com history.com imdb.com investopedia.com celebritynetworth.com thefamousinfo.com "
                 "worldometers.info worldpopulationreview.com census2011.co.in jagranjosh.com myblackhistory.net "
                 "achievement.org online-calculator.com",
    "transcript_or_record_aggregator": "c-span.org factba.se rev.com govtrack.us",
    "hosting_redirect_or_archive": "amazonaws.com cloudfront.net gannett-cdn.com perma.cc scribd.com bit.ly fb.com "
                                   "youtu.be google.com google.com.ph govdelivery.com multivu.com archihttps",
    "academic": "doi.org elsevierhealth.com auctoresonline.org recoverytrial.net asm.org",
    "ngo_thinktank_or_data_producer": "aaihs.org aarp.org acwm.org afj.org apic.org bbb.org crisisgroup.org csis.org "
                                      "dcfpi.org demandjustice.org dohainstitute.org globalcitizen.org health-desk.org "
                                      "id2020.org ipsos.com jwa.org kff.org milkeninstitute.org nature.org ncsl.org nfid.org "
                                      "nielsen.com pewresearch.org sdgindex.org sdgphilanthropy.org taxfoundation.org "
                                      "taxpolicycenter.org worldpoverty.io resist.bot metmuseum.org medicines.org.uk",
    "company_person_or_own_site": "chemed.com joebiden.com davidgarrow.com englandandcompany.co.uk sightwaycapital.com "
                                  "twosigma.com finflam.com publicprocurementinternational.com lacriminaldefenseattorney.com "
                                  "myfrs.com abruptearthchanges.com givesendgo.com lungmds.com spinalcord.com"}
DOMAIN_OVERRIDES = {d: cls for cls, ds in _OV.items() for d in ds.split()}
# official domains that authority_retrieval.generic_prior scores as 'unknown' (0.3) although they are government/UN sites
OFFICIAL_MISSED_BY_GENERIC = set(_OV["gov_intergov"].split())


def wilson(x, n, z=1.96):
    if n == 0:
        return None
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def prop(x, n):
    return {"x": x, "n": n, "p": round(x / n, 3) if n else None, "wilson95": wilson(x, n)}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dclass(key):
    """Heuristic publisher class of a publisher key (descriptive only)."""
    if not key:
        return "no_key"
    if key in DOMAIN_OVERRIDES:
        return DOMAIN_OVERRIDES[key]
    if "/" in key:
        return "social_account"
    if key in SOCIAL or key in PLATFORMS:
        return "platform_or_archive"
    g = generic_prior("http://" + key)
    if g == 1.0:
        return "gov_intergov"
    if g == 0.8:
        return "academic"
    if key in FACTCHECK:
        return "factcheck"
    if key in MAJOR_NEWS or NEWS_FC_HINT.search(key):
        return "news_like"
    if key in REFERENCE:
        return "reference"
    return "other_site"


SECONDARY_CLASSES = {"factcheck", "news_like", "reference"}


def loose(u):
    """Looser canonical form to look for gold URLs the frozen normaliser may have failed to match."""
    u = u.lower()
    u = re.sub(r"^(m|mobile|amp)\.", "", u)
    u = u.split("?")[0].split("#")[0]
    u = re.sub(r"(/amp|/index\.html?|\.amp|/)+$", "", u)
    m = re.match(r"^(twitter\.com|x\.com)/[^/]+/status(es)?/(\d+)", u)
    return f"twitter.com/status/{m.group(3)}" if m else u


def load_full(m):
    with gzip.open(RESULTS / "heldout" / f"rankings_{m}.jsonl.gz", "rt", encoding="utf-8") as fh:
        return {int(r["claim_id"]): [tuple(x) for x in r["ranked"]] for r in map(json.loads, fh)}


def first_rank(lst, tgt):
    return next((i for i, u in enumerate(lst, 1) if u in tgt), None)


def targeted_order(bm, de, keys_by_rank):
    """Exact offline re-implementation of source_targeted.targeted_rank for text_mode='claim'
    (BM25 query = claim text over the claim corpus, i.e. the frozen BM25 scores), order='authority'."""
    arank, lex = {}, {}
    for u, s in bm:
        k = cand_key(u)
        for r, keys in keys_by_rank:
            if k in keys and (u not in arank or r < arank[u]):
                arank[u] = r
                lex[u] = s
    if not arank:
        return []
    lex_order = sorted(arank, key=lambda u: (-lex[u], u))
    dense_order = [u for u, _ in de if u in arank]
    rrf = {u: 0.0 for u in arank}
    for lst in (lex_order, dense_order):
        for r, u in enumerate(lst, 1):
            rrf[u] += 1.0 / (RRF_K + r)
    return sorted(arank, key=lambda u: (arank[u], -rrf[u], u)), arank


def main():
    if OUT.exists():
        sys.exit(f"{OUT} exists; refusing to overwrite.")
    S = read_jsonl(PROCESSED / "averitec_heldout.jsonl")
    full = {m: load_full(m) for m in ("bm25", "dense", "hybrid")}
    stored = {}
    with gzip.open(RESULTS / "source_targeted" / "rankings_heldout.jsonl.gz", "rt", encoding="utf-8") as fh:
        for x in map(json.loads, fh):
            stored.setdefault(x["method"], {})[int(x["claim_id"])] = [u for u, _ in x["ranked"]]
    preds = {}
    for line in open(PRED_RAW, encoding="utf-8"):
        x = json.loads(line)
        if x.get("cond") == "L+Wctx" and x.get("pred"):
            preds[int(x["claim_id"])] = x
    frozen_tab = json.load(open(RESULTS / "source_targeted" / "results_heldout.json", encoding="utf-8"))["table"]

    # ---------------------------------------------------------------- gold (scoring side only)
    T = {}
    gold_rows = []
    for r in S:
        c = int(r["claim_id"])
        corpus = {u for u, _ in full["hybrid"][c]}
        web = [g for g in r["gold_evidence"] if g["is_web_source"]]
        gall = {g["source_url_norm"] for g in web}
        reach = gall & corpus
        gkeys = set().union(*[target_keys(g["source_url"]) for g in web]) if web else set()
        T[c] = {"gold": reach, "gold_all": gall, "gold_keys": gkeys, "corpus": corpus,
                "n_evidence_entries": len(r["gold_evidence"]), "iso": r.get("location_ISO_code"),
                "speaker": r.get("speaker_or_entity") or "", "claim": r["claim"], "date": r.get("claim_date")}
        lc = {loose(u) for u in corpus}
        seen = set()
        for g in web:
            u = g["source_url_norm"]
            if u in seen:
                continue
            seen.add(u)
            raw = g["source_url"] or ""
            gold_rows.append({"claim_id": c, "url_norm": u, "reachable": u in corpus, "medium": g["source_medium"],
                              "archived_wrapper": "archive.org/web/" in raw, "pdf": u.lower().endswith(".pdf") or g["source_medium"] == "PDF",
                              "publisher_key": cand_key(u), "class": dclass(cand_key(u)),
                              "loose_match_in_corpus": (u not in corpus) and loose(u) in lc,
                              "url_year": (re.search(r"/(20[0-2]\d)/", u) or [None, None])[1]})

    # ---------------------------------------------------------------- GATE
    gold_c = [c for c in T if T[c]["gold"]]
    gate = {"reachable_claims_167": len(gold_c) == 167,
            "reachable_docs_305": sum(len(T[c]["gold"]) for c in gold_c) == 305,
            "gold_urls_422": len(gold_rows) == 422}
    with open(RESULTS / "source_targeted" / "per_claim_heldout.csv", encoding="utf-8") as fh:
        gate["per_claim_n_gold_reachable"] = all(int(x["n_gold_reachable"]) == len(T[int(x["claim_id"])]["gold"])
                                                 for x in csv.DictReader(fh))
    hit = lambda lst, c, k: bool(T[c]["gold"] & set(lst[:k]))
    for sid, m in SYS.items():
        for k in KS:
            v = round(sum(hit(stored[m][c], c, k) for c in gold_c) / len(gold_c), 3)
            gate[f"{sid}_GoldR@{k}"] = v == frozen_tab[m][f"GoldR@{k}"]
    pk = {c: set().union(*[set(a["keys"]) for a in primary_authority_candidates(preds[c]["pred"])])
          if c in preds else set() for c in T}
    D_re = {c: [u for u, _ in rerank_any(full["hybrid"][c], lambda u, k=pk[c]: float(cand_key(u) in k), 1.0, 100)]
            for c in T}
    gate["D_top100_order"] = all(D_re[c] == stored[SYS["D"]][c] for c in T)
    tgt_full, tgt_arank = {}, {}
    for c in T:
        cands = primary_authority_candidates(preds[c]["pred"]) if c in preds else []
        res = targeted_order(full["bm25"][c], full["dense"][c], [(a["rank"], set(a["keys"])) for a in cands])
        tgt_full[c], tgt_arank[c] = (res if res else ([], {}))
    gate["targeted_top10_lists"] = all(tgt_full[c][:10] == stored[SYS["E"]][c] for c in T)
    O_pool = {c: [u for u, _ in rerank_any(full["hybrid"][c], lambda u, k=T[c]["gold_keys"]: float(cand_key(u) in k), 1.0, 100)]
              for c in T}
    gate["oracle_publisher_pool_R@10_0.659"] = round(sum(hit(O_pool[c], c, 10) for c in gold_c) / 167, 3) == 0.659
    print("GATE", json.dumps(gate))
    if not all(gate.values()):
        sys.exit("reproduction gate failed")

    out = {"status": "EXPLORATORY / DIAGNOSTIC, not preregistered; uses gold by design; no deployable system is scored",
           "created": datetime.datetime.now().isoformat(timespec="seconds"), "gate": gate}

    # ---------------------------------------------------------------- 1. ceilings
    n_all, n_web = len(T), sum(bool(T[c]["gold_all"]) for c in T)
    unreach = [g for g in gold_rows if not g["reachable"]]
    out["1_ceiling"] = {
        "claims": n_all, "claims_with_web_gold": n_web, "claims_no_web_gold": n_all - n_web,
        "claims_web_gold_all_unreachable": n_web - len(gold_c), "claims_reachable_gold": len(gold_c),
        "gold_urls": len(gold_rows), "gold_urls_reachable": len(gold_rows) - len(unreach), "gold_urls_unreachable": len(unreach),
        "claim_hit_ceiling_any_k": {"denominator_167_reachable(eval definition)": 1.0,
                                    "denominator_192_web_gold": prop(len(gold_c), n_web),
                                    "denominator_200_all": prop(len(gold_c), n_all)},
        "doc_level_recall_ceiling_at_k": {
            f"@{k}": {"over_167_reachable_docs": round(sum(min(k, len(T[c]["gold"])) / len(T[c]["gold"]) for c in gold_c) / len(gold_c), 3),
                      "over_192_all_web_gold_docs": round(sum(min(k, len(T[c]["gold"])) / len(T[c]["gold_all"])
                                                              for c in T if T[c]["gold_all"]) / n_web, 3)} for k in KS},
        "unreachable_by_medium": dict(Counter(g["medium"] for g in unreach)),
        "unreachable_by_class": dict(Counter(g["class"] for g in unreach)),
        "reachability_rate_by_class": {k: prop(sum(g["reachable"] for g in gold_rows if g["class"] == k),
                                               sum(g["class"] == k for g in gold_rows))
                                       for k in sorted({g["class"] for g in gold_rows})},
        "reachability_rate_by_medium": {k: prop(sum(g["reachable"] for g in gold_rows if g["medium"] == k),
                                                sum(g["medium"] == k for g in gold_rows))
                                        for k in sorted({g["medium"] for g in gold_rows})},
        "reachability_pdf": prop(sum(g["reachable"] for g in gold_rows if g["pdf"]), sum(g["pdf"] for g in gold_rows)),
        "reachability_archived_wrapper": prop(sum(g["reachable"] for g in gold_rows if g["archived_wrapper"]),
                                              sum(g["archived_wrapper"] for g in gold_rows)),
        "reachability_not_archived": prop(sum(g["reachable"] for g in gold_rows if not g["archived_wrapper"]),
                                          sum(not g["archived_wrapper"] for g in gold_rows)),
        "unreachable_with_loose_canonical_match_in_corpus": sum(g["loose_match_in_corpus"] for g in unreach),
        "unreachable_loose_match_examples": [g["url_norm"] for g in unreach if g["loose_match_in_corpus"]][:15],
        "claims_rescued_if_loose_matches_counted": sum(
            1 for c in T if not T[c]["gold"] and any(g["loose_match_in_corpus"] for g in unreach if g["claim_id"] == c)),
        "note": "unreachable = gold URL absent from the non-empty retrieval corpus; absent-from-KS and empty-text-in-KS "
                "cannot be separated without data/raw (not present in this checkout)"}

    # ---------------------------------------------------------------- 2. candidate generation curve
    cov = {}
    for m in ("bm25", "dense", "hybrid"):
        cov[m] = {f"top{d}": round(sum(hit([u for u, _ in full[m][c]], c, d) for c in gold_c) / 167, 3) for d in DEPTHS}
        cov[m]["all"] = 1.0
    cov["bm25_U_dense_top100"] = round(sum(bool(T[c]["gold"] & ({u for u, _ in full["bm25"][c][:100]} | {u for u, _ in full["dense"][c][:100]}))
                                           for c in gold_c) / 167, 3)
    hy_best = {c: first_rank([u for u, _ in full["hybrid"][c]], T[c]["gold"]) for c in gold_c}
    oop = sorted(hy_best[c] for c in gold_c if hy_best[c] > 100)
    sizes = sorted(len(full["hybrid"][c]) for c in T)
    out["2_candidate_generation"] = {
        "coverage_at_depth": cov,
        "corpus_size_per_claim": {"min": sizes[0], "median": sizes[len(sizes) // 2], "max": sizes[-1]},
        "hybrid_best_gold_rank_quantiles(167)": {q: sorted(hy_best.values())[int(q * 166)] for q in (0.25, 0.5, 0.75, 0.9)},
        "out_of_top100_claims": len(oop),
        "out_of_top100_best_rank_bins": dict(Counter("101-200" if r <= 200 else "201-300" if r <= 300 else "301-500"
                                                     if r <= 500 else ">500" for r in oop)),
        "F_union_pool_coverage": round(sum(bool(T[c]["gold"] & (set(stored[SYS["A"]][c]) | set(stored[SYS["E"]][c])))
                                           for c in gold_c) / 167, 3)}

    # ---------------------------------------------------------------- 3. decomposition per system
    pools = {sid: {c: set(stored[SYS["A"]][c]) for c in T} for sid in ("A", "B", "C", "D")}
    pools["E"] = {c: set(stored[SYS["E"]][c]) for c in T}
    pools["F"] = pools["G"] = {c: set(stored[SYS["A"]][c]) | set(stored[SYS["E"]][c]) for c in T}
    dec = {}
    for sid in ("A", "B", "C", "D", "E", "F", "G"):
        dec[sid] = {}
        for k in KS:
            h = sum(hit(stored[SYS[sid]][c], c, k) for c in gold_c)
            notpool = sum(not (T[c]["gold"] & pools[sid][c]) for c in gold_c)
            dec[sid][f"@{k}"] = {"hit": h, "lost_in_ranking(gold in pool, rank>k)": 167 - h - notpool,
                                 "lost_before_ranking(gold not in pool)": notpool,
                                 "R@k_167": round(h / 167, 3), "R@k_over_192": round(h / n_web, 3)}
    out["3_decomposition_167"] = dec
    out["3_note"] = "over 192 web-gold claims, a further 25 claims are lost before retrieval (unrepresentable gold)"

    # ---------------------------------------------------------------- 4. oracle ladder (diagnostic)
    def R(rank_fn):
        rk = {c: rank_fn(c) for c in gold_c}
        return {f"R@{k}": round(sum(hit(rk[c], c, k) for c in gold_c) / 167, 3) for k in KS}, rk

    hyb = {c: [u for u, _ in full["hybrid"][c]] for c in T}

    def prior_rank(c, keys, pool):
        if pool is None:  # lambda = infinity over the whole corpus: publisher docs first, hybrid order inside
            return sorted(hyb[c], key=lambda u, o={u: i for i, u in enumerate(hyb[c])}: (cand_key(u) not in keys, o[u]))
        return [u for u, _ in rerank_any(full["hybrid"][c], lambda u: float(cand_key(u) in keys), 1.0, pool)]

    nonnews = {c: {k for k in T[c]["gold_keys"] if dclass(k) not in SECONDARY_CLASSES} for c in T}
    ladder = {"A_hybrid(actual)": R(lambda c: hyb[c])[0],
              "D_pred_top3_pool100(actual)": R(lambda c: stored[SYS["D"]][c])[0],
              "ORACLE_url_rerank_pool100": {f"R@{k}": out["2_candidate_generation"]["coverage_at_depth"]["hybrid"]["top100"] for k in KS},
              "ORACLE_url_full_corpus": {f"R@{k}": 1.0 for k in KS}}
    ladder["ORACLE_pub_all_gold_pool100"], O1 = R(lambda c: prior_rank(c, T[c]["gold_keys"], 100))
    ladder["ORACLE_pub_all_gold_full_lambda1"], _ = R(lambda c: prior_rank(c, T[c]["gold_keys"], 10**9))
    ladder["ORACLE_pub_all_gold_full_sitefilter"], O3 = R(lambda c: prior_rank(c, T[c]["gold_keys"], None))
    ladder["ORACLE_pub_nonsecondary_gold_pool100"], _ = R(lambda c: prior_rank(c, nonnews[c], 100))
    ladder["ORACLE_pub_nonsecondary_gold_full_sitefilter"], _ = R(lambda c: prior_rank(c, nonnews[c], None))
    ladder["H_ORACLE_targeted(stored)"] = {f"R@{k}": frozen_tab[SYS["H_ORACLE"]][f"GoldR@{k}"] for k in KS}
    spec = []
    for c in gold_c:
        pubdocs = [u for u in hyb[c] if cand_key(u) in T[c]["gold_keys"]]
        spec.append((len(pubdocs), sum(u in T[c]["gold"] for u in pubdocs)))
    out["4_oracle_ladder"] = {
        "table": ladder,
        "claims_with_nonsecondary_gold_key": sum(bool(nonnews[c]) for c in gold_c),
        "publisher_specificity": {
            "median_corpus_docs_from_gold_publishers": sorted(s[0] for s in spec)[len(spec) // 2],
            "claims_where_every_gold_publisher_doc_is_gold": sum(s[0] == s[1] for s in spec),
            "claims_with_<=3_gold_publisher_docs": sum(s[0] <= 3 for s in spec),
            "claims_with_>=20_gold_publisher_docs": sum(s[0] >= 20 for s in spec)},
        "bootstrap_or_wilson": {
            "pool_coverage_hybrid_top100": prop(sum(hit(stored[SYS["A"]][c], c, 100) for c in gold_c), 167),
            "D_R@10": prop(sum(hit(stored[SYS["D"]][c], c, 10) for c in gold_c), 167),
            "ORACLE_pub_pool100_R@10": prop(sum(hit(O1[c], c, 10) for c in gold_c), 167),
            "ORACLE_pub_full_sitefilter_R@10": prop(sum(hit(O3[c], c, 10) for c in gold_c), 167)},
        "note": "ORACLE_pub uses publishers of the very gold docs being scored; when a publisher has only gold docs in the "
                "corpus it degenerates to a URL oracle. 'nonsecondary' drops news/fact-check/reference keys (heuristic list), "
                "approximating what a claim-specific authority resolver is supposed to name."}

    # ---------------------------------------------------------------- 5. authority failure taxonomy
    per = []
    D, Aname = SYS["D"], SYS["A"]
    for c in sorted(T):
        if c not in gold_c:
            continue
        x = preds.get(c, {}).get("pred") or {}
        cands = primary_authority_candidates(x)
        p_keys = pk[c]
        g_reach_keys = {cand_key(u) for u in T[c]["gold"]}
        g_classes = {dclass(k) for k in g_reach_keys}
        auth_gold = {u for u in T[c]["gold"] if cand_key(u) in p_keys}
        rD = first_rank(stored[D][c], T[c]["gold"])
        flags = {}
        # identity near-misses (possible alias / channel / handle mismatch)
        near = []
        for a in p_keys:
            for g in g_reach_keys | T[c]["gold_keys"]:
                if a == g:
                    continue
                la, lg = _label(a), _label(g)
                if "/" in a and "/" in g and a.split("/")[0] == g.split("/")[0]:
                    near.append(("same_platform_other_handle", a, g))
                elif len(la) >= 5 and len(lg) >= 5 and (la in lg or lg in la):
                    near.append(("channel_or_alias" if ("/" in a) != ("/" in g) else "label_overlap_alias", a, g))
        for t in (x.get("top3") or []):
            nm = _alnum(t.get("publisher") or "")
            for g in g_reach_keys:
                lg = _label(g)
                if len(lg) >= 5 and lg in nm and g not in p_keys:
                    near.append(("name_matches_gold_key", t.get("publisher"), g))
        spk = _alnum(T[c]["speaker"])
        artifact = any("/" in g and len(_label(g)) >= 4 and (_label(g) in spk or (len(spk) >= 4 and spk in _label(g))
                                                             or _label(g) in _alnum(T[c]["claim"])) for g in g_reach_keys)
        pgov = {country_of(k) for k in p_keys if "/" not in k and is_gov(k)}
        ggov = {country_of(k) for k in g_reach_keys if "/" not in k and is_gov(k)}
        juris = bool(pgov and ggov and not (pgov & ggov))
        pred_in_corpus = any(cand_key(u) in p_keys for u in hyb[c])
        pred_in_pool = any(cand_key(u) in p_keys for u in stored[Aname][c])
        if auth_gold:
            cat = "T1_pred_matches_reachable_gold_publisher"
        elif p_keys & T[c]["gold_keys"]:
            cat = "T2_pred_matches_only_unreachable_gold"
        elif artifact:
            cat = "T3_gold_is_claimant_or_subject_own_account"
        elif any(n[0] != "same_platform_other_handle" for n in near):
            cat = "T4_identity_near_miss(alias/channel/handle)"
        elif g_classes <= SECONDARY_CLASSES:
            cat = "T5_gold_publishers_all_secondary_type"
        elif juris:
            cat = "T6_jurisdiction_mismatch(gov vs gov)"
        elif g_classes & {"gov_intergov", "academic"}:
            cat = "T7_institutional_authority_missed"
        else:
            cat = "T8_other(gold=other/social/platform sites)"
        # within-authority crowding for T1: predicted-publisher non-gold docs above the authority's gold in D
        crowd = None
        if auth_gold and rD is not None:
            ra = first_rank(stored[D][c], auth_gold)
            if ra:
                crowd = sum(cand_key(u) in p_keys and u not in T[c]["gold"] for u in stored[D][c][:ra - 1])
        tl = tgt_full[c]
        pos_auth_in_targeted = first_rank(tl, auth_gold) if auth_gold else None
        per.append({
            "claim_id": c, "category": cat, "claim_kind": x.get("claim_kind"),
            "authority_situation": x.get("authority_situation"),
            "pred_top3": " | ".join(f"{a['publisher']} {a['keys']}" for a in cands),
            "pred_top_types": " ".join(str(t.get("publisher_type")) for t in (x.get("top3") or [])),
            "gold_reachable_keys": " ".join(sorted(g_reach_keys)), "gold_classes": " ".join(sorted(g_classes)),
            "n_gold_reachable": len(T[c]["gold"]), "n_gold_publishers": len(g_reach_keys),
            "near_miss": "; ".join(f"{a}:{b}~{g}" for a, b, g in near[:3]), "claim_artifact_flag": artifact,
            "jurisdiction_mismatch_flag": juris, "pred_publisher_in_corpus": pred_in_corpus,
            "pred_publisher_in_hybrid_top100": pred_in_pool, "n_pred_publisher_docs_corpus": len(tl),
            "rank_A": first_rank(stored[Aname][c], T[c]["gold"]), "rank_D": rD,
            "rank_G": first_rank(stored[SYS["G"]][c], T[c]["gold"]), "rank_full_hybrid": hy_best[c],
            "authgold_rank_full_hybrid": first_rank(hyb[c], auth_gold) if auth_gold else None,
            "authgold_pos_in_targeted_list": pos_auth_in_targeted,
            "authgold_authority_rank": min(tgt_arank[c][u] for u in auth_gold) if auth_gold and tgt_arank[c] else None,
            "pred_pub_nongold_docs_above_authgold_in_D": crowd,
            "D_hit10": rD is not None and rD <= 10, "A_hit10": hit(stored[Aname][c], c, 10)})
    cats = Counter(p["category"] for p in per)
    tax = {}
    for k in sorted(cats):
        xs = [p for p in per if p["category"] == k]
        tax[k] = {"n": len(xs), "A_hit@10": sum(p["A_hit10"] for p in xs), "D_hit@10": sum(p["D_hit10"] for p in xs),
                  "gold_in_hybrid_top100": sum(p["rank_full_hybrid"] <= 100 for p in xs),
                  "pred_publisher_in_corpus": sum(p["pred_publisher_in_corpus"] for p in xs)}
    t1 = [p for p in per if p["category"].startswith("T1")]
    t1_oop = [p for p in t1 if p["authgold_rank_full_hybrid"] > 100]
    ns_keys = {c: {cand_key(u) for u in T[c]["gold"]} - {k for k in {cand_key(u) for u in T[c]["gold"]}
                                                          if dclass(k) in SECONDARY_CLASSES} for c in gold_c}
    top1k = {c: (set(primary_authority_candidates(preds[c]["pred"])[0]["keys"])
                 if c in preds and primary_authority_candidates(preds[c]["pred"]) else set()) for c in gold_c}
    out["5_authority_taxonomy_167"] = {
        "categories": tax,
        "rule": "exclusive, first matching rule in the listed order; categories T3-T8 are heuristic and unverified",
        "T1_detail": {
            "n": len(t1),
            "D_hit@10": sum(p["D_hit10"] for p in t1),
            "authgold_in_hybrid_top100": sum(p["authgold_rank_full_hybrid"] <= 100 for p in t1),
            "authgold_in_top100_but_D_miss@10": sum(p["authgold_rank_full_hybrid"] <= 100 and not p["D_hit10"] for p in t1),
            "median_pred_pub_nongold_docs_above_authgold_in_D": sorted(p["pred_pub_nongold_docs_above_authgold_in_D"] for p in t1
                                                                       if p["pred_pub_nongold_docs_above_authgold_in_D"] is not None)[
                len([p for p in t1 if p["pred_pub_nongold_docs_above_authgold_in_D"] is not None]) // 2],
            "authgold_outside_top100": len(t1_oop),
            "of_which_pos_in_targeted_list<=10": sum(p["authgold_pos_in_targeted_list"] <= 10 for p in t1_oop),
            "<=20": sum(p["authgold_pos_in_targeted_list"] <= 20 for p in t1_oop),
            "<=50": sum(p["authgold_pos_in_targeted_list"] <= 50 for p in t1_oop),
            "any": len(t1_oop),
            "authgold_from_authority_rank": dict(Counter(p["authgold_authority_rank"] for p in t1)),
            "median_pred_publisher_docs_in_corpus": sorted(p["n_pred_publisher_docs_corpus"] for p in t1)[len(t1) // 2]},
        "pred_accuracy_vs_reachable_nonsecondary_gold_publishers": (lambda ids: {
            "n_claims": len(ids),
            "top3_match": sum(bool(pk[c] & ns_keys[c]) for c in ids),
            "top1_match": sum(bool(top1k[c] & ns_keys[c]) for c in ids)})(
            [c for c in gold_c if ns_keys[c]]),
        "T1_authgold_outside_top100_full_hybrid_rank_median": sorted(p["authgold_rank_full_hybrid"] for p in t1_oop)[len(t1_oop) // 2],
        "no_match_claims": {
            "n": sum(not p["category"].startswith(("T1", "T2")) for p in per),
            "pred_publisher_absent_from_corpus": sum(not p["pred_publisher_in_corpus"] for p in per
                                                     if not p["category"].startswith(("T1", "T2"))),
            "pred_publisher_absent_from_hybrid_top100": sum(not p["pred_publisher_in_hybrid_top100"] for p in per
                                                            if not p["category"].startswith(("T1", "T2")))},
        "by_claim_kind(MODEL OUTPUT)": {k: {"n": sum(p["claim_kind"] == k for p in per),
                                            "T1": sum(p["claim_kind"] == k and p["category"].startswith("T1") for p in per)}
                                        for k in sorted({str(p["claim_kind"]) for p in per})},
        "reachable_gold_doc_classes": dict(Counter(dclass(cand_key(u)) for c in gold_c for u in T[c]["gold"])),
        "predicted_publisher_types_all_ranks(MODEL OUTPUT)": dict(Counter(t.split()[0] if t else "none" for p in per
                                                                       for t in p["pred_top_types"].split(" ")))}

    # ---------------------------------------------------------------- 6. generic / heuristic over-boosting
    B, C = SYS["B"], SYS["C"]
    rows_by_id = {int(r["claim_id"]): r for r in S}
    ov = {}
    for sid, m in (("B_generic", B), ("C_heuristic", C), ("D_llm", D)):
        z = {}
        for k in (1, 10):
            a = [hit(stored[Aname][c], c, k) for c in gold_c]
            b = [hit(stored[m][c], c, k) for c in gold_c]
            w, l, p = mcnemar(a, b)
            z[f"@{k}_vs_A"] = {"wins": w, "losses": l, "p_exact_mcnemar(descriptive)": round(p, 4)}
        top10 = [u for c in gold_c for u in stored[m][c][:10] if u not in T[c]["gold"]]
        z["nongold_top10_docs"] = len(top10)
        z["nongold_top10_gov_intergov"] = sum(generic_prior(u) == 1.0 for u in top10)
        wrong_j = 0
        for c in gold_c:
            iso = T[c]["iso"]
            for u in stored[m][c][:10]:
                h = u.split("/")[0]
                if u not in T[c]["gold"] and iso and is_gov(h) and country_of(h) not in (None, ISO_TO_TLD.get(iso, iso.lower())):
                    wrong_j += 1
        z["nongold_top10_gov_other_jurisdiction"] = wrong_j
        z["top1_class_when_A_hit@1_lost"] = dict(Counter(dclass(cand_key(stored[m][c][0])) for c in gold_c
                                                         if hit(stored[Aname][c], c, 1) and not hit(stored[m][c], c, 1)))
        ov[sid] = z
    a_top10_nongold = [u for c in gold_c for u in stored[Aname][c][:10] if u not in T[c]["gold"]]
    ov["A_reference"] = {"nongold_top10_docs": len(a_top10_nongold),
                         "nongold_top10_gov_intergov": sum(generic_prior(u) == 1.0 for u in a_top10_nongold)}
    fp = tp = 0
    for c in gold_c:
        ek = entity_keys(claim_entities(rows_by_id[c]))
        for u in stored[Aname][c]:
            if entity_match(u, ek):
                tp += u in T[c]["gold"]
                fp += u not in T[c]["gold"]
    ov["C_entity_rule_matches_in_hybrid_top100"] = {"gold": tp, "nongold": fp}
    missed = [(c, u) for c in T for u in hyb[c] if cand_key(u) in OFFICIAL_MISSED_BY_GENERIC and generic_prior(u) < 1.0]
    ov["official_docs_scored_unknown_by_generic_prior"] = {
        "corpus_docs": len(missed), "claims": len({c for c, _ in missed}),
        "by_key": dict(Counter(cand_key(u) for _, u in missed)),
        "of_which_reachable_gold": sum(u in T[c]["gold"] for c, u in missed),
        "note": "rule gap in authority_retrieval.is_gov/INTERGOV (e.g. host 'gov.uk' -> 0.3 but "
                "'assets.publishing.service.gov.uk' -> 1.0); affects frozen B and C, not D"}
    out["6_overboosting"] = ov

    # ---------------------------------------------------------------- 7. displacement by the LLM prior / targeting
    disp = {}
    for sid, m in (("D", D), ("G", SYS["G"])):
        miss = [c for c in gold_c if (T[c]["gold"] & pools[sid][c]) and not hit(stored[m][c], c, 10)]
        disp[sid] = {"gold_in_pool_but_miss@10": len(miss),
                     "mean_top10_docs_from_pred_publishers_nongold": round(sum(sum(cand_key(u) in pk[c] and u not in T[c]["gold"]
                                                                                   for u in stored[m][c][:10]) for c in miss) / max(1, len(miss)), 2),
                     "claims_with_>=5_pred_publisher_nongold_in_top10": sum(sum(cand_key(u) in pk[c] and u not in T[c]["gold"]
                                                                               for u in stored[m][c][:10]) >= 5 for c in miss)}
    out["7_displacement"] = disp

    # ---------------------------------------------------------------- 8. multiplicity & temporal proxies
    out["8_other"] = {
        "claims_>=2_reachable_gold_publishers": sum(len({cand_key(u) for u in T[c]["gold"]}) >= 2 for c in gold_c),
        "claims_mixed_secondary_and_nonsecondary_reachable_gold": sum(
            bool({dclass(cand_key(u)) for u in T[c]["gold"]} & SECONDARY_CLASSES) and
            bool({dclass(cand_key(u)) for u in T[c]["gold"]} - SECONDARY_CLASSES) for c in gold_c),
        "gold_urls_with_year_in_path": sum(g["url_year"] is not None for g in gold_rows),
        "gold_urls_year_after_claim_year": sum(g["url_year"] is not None and T[g["claim_id"]]["date"] and
                                               int(g["url_year"]) > int(T[g["claim_id"]]["date"].split("-")[-1]) for g in gold_rows),
        "llm_predictor_calls": len(preds),
        "llm_predictor_cost_usd": round(sum(preds[c].get("cost") or 0 for c in preds), 2)}

    # ---------------------------------------------------------------- 9. MODEL_GENERATED role labels (descriptive only)
    key_url = {r["item_id"]: (int(r["claim_id"]), r["url_norm"]) for r in csv.DictReader(open(AI_KEY, encoding="utf-8"))}
    roles = {key_url[r["item"]]: r["label"] for r in csv.DictReader(open(AI_ROLES, encoding="utf-8"))}
    for g in gold_rows:
        g["ai_role_MODEL_GENERATED"] = roles.get((g["claim_id"], g["url_norm"]), "")
    rr = [g for g in gold_rows if g["reachable"]]
    out["9_MODEL_GENERATED_roles_descriptive"] = {
        "warning": "AI-generated (Claude Opus 5.5, same family as the predictor); not human labels; no recall computed",
        "matched_labels": sum(bool(g["ai_role_MODEL_GENERATED"]) for g in gold_rows),
        "all_gold_by_role": dict(Counter(g["ai_role_MODEL_GENERATED"] for g in gold_rows)),
        "reachable_rate_by_role": {k: prop(sum(g["reachable"] for g in gold_rows if g["ai_role_MODEL_GENERATED"] == k),
                                           sum(g["ai_role_MODEL_GENERATED"] == k for g in gold_rows))
                                   for k in sorted({g["ai_role_MODEL_GENERATED"] for g in gold_rows})},
        "reachable_in_hybrid_top100_by_role": {k: prop(sum(g["url_norm"] in set(stored[Aname][g["claim_id"]]) for g in rr
                                                           if g["ai_role_MODEL_GENERATED"] == k),
                                                       sum(g["ai_role_MODEL_GENERATED"] == k for g in rr))
                                               for k in sorted({g["ai_role_MODEL_GENERATED"] for g in rr})},
        "role_by_publisher_class": {k: dict(Counter(g["ai_role_MODEL_GENERATED"] for g in gold_rows if g["class"] == k))
                                    for k in sorted({g["class"] for g in gold_rows})}}

    # ---------------------------------------------------------------- provenance + write
    here = Path(__file__).resolve()
    out["provenance"] = {
        "script": str(here.relative_to(here.parents[1])), "script_sha256": sha(here),
        "imports_sha256": {f: sha(here.parent / f) for f in ("authority_resolution.py", "authority_retrieval.py", "common.py",
                                                            "source_targeted.py", "validation_heldout.py")},
        "inputs_sha256": {str(p.relative_to(here.parents[1])): sha(p) for p in (
            PROCESSED / "averitec_heldout.jsonl", RESULTS / "heldout" / "rankings_bm25.jsonl.gz",
            RESULTS / "heldout" / "rankings_dense.jsonl.gz", RESULTS / "heldout" / "rankings_hybrid.jsonl.gz",
            RESULTS / "source_targeted" / "rankings_heldout.jsonl.gz", RESULTS / "source_targeted" / "results_heldout.json",
            PRED_RAW, AI_ROLES, AI_KEY)},
        "python": sys.version.split()[0], "llm_calls": 0}
    OUT.mkdir(parents=True)
    json.dump(out, open(OUT / "summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    with open(OUT / "per_claim.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per[0]))
        w.writeheader()
        w.writerows(per)
    with open(OUT / "gold_urls.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(gold_rows[0]))
        w.writeheader()
        w.writerows(gold_rows)
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
