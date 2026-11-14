"""Read-only audit of experiments/authority_bottleneck_diagnostics.py and
docs/authority_resolution_bottleneck_analysis.md (see docs/authority_resolution_diagnostic_audit.md).

Status: AUDIT / DIAGNOSTIC. No retrieval, no LLM or network call, no frozen file written.

  python authority_diagnostic_audit.py

Steps
  1. Re-run the diagnostic into results/authority_bottleneck_diagnostics_audit/rerun/ with every socket and
     subprocess call blocked, then compare its outputs with results/authority_bottleneck_diagnostics/.
  2. Check every headline number quoted in the report against the original summary.json.
  3. Probe the publisher-key, authority-matching and error-category rules (false positives / negatives).
  4. Scan the frozen predictor prompts for gold strings; list where gold fields are read in the frozen code.
  5. Verify frozen-file hashes (LF-normalised) against the preregistration records.

Writes results/authority_bottleneck_diagnostics_audit/{audit_summary.json, category_rule_audit.csv}; refuses to
overwrite the audit directory. The original diagnostic outputs are only read.
"""
import csv
import gzip
import hashlib
import json
import re
import socket
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AUD = ROOT / "results" / "authority_bottleneck_diagnostics_audit"
ORIG = ROOT / "results" / "authority_bottleneck_diagnostics"


# ---------------------------------------------------------------- guards: no network, no subprocess
def _blocked(*a, **k):
    raise RuntimeError("blocked by audit: network/subprocess call attempted")


socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
subprocess.Popen.__init__ = _blocked  # also covers subprocess.run / call / check_output

import authority_bottleneck_diagnostics as DG  # noqa: E402
from authority_resolution import org_domain, target_keys  # noqa: E402
from authority_retrieval import GOV_LABELS, generic_prior, is_gov  # noqa: E402
from common import PROCESSED, RESULTS, full_host, normalize_url, read_jsonl  # noqa: E402
from source_targeted import cand_key, primary_authority_candidates  # noqa: E402


def sha_lf(p):
    return hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sha_raw(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def get(d, path):
    for k in path.split("|"):
        d = d[k]
    return d


def is_gov_fixed(host):
    """Audit-only variant: also accept a host whose FIRST label is a government label (gov.uk, gob.mx, gov.br),
    and reject *.go.com (a commercial domain). Never used by any retrieval system."""
    labels = host.split(".")
    if host.endswith(".go.com") or host == "go.com":
        return False
    return is_gov(host) or (len(labels) >= 2 and labels[0] in GOV_LABELS and len(labels[-1]) == 2)


def main():
    if AUD.exists():
        sys.exit(f"{AUD} exists; refusing to overwrite.")
    AUD.mkdir(parents=True)
    out = {"status": "AUDIT, read-only; no retrieval, no LLM/network call", "guards": "socket+subprocess blocked"}

    # ============================================================ 1. rerun into the audit directory
    DG.OUT = AUD / "rerun"
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        DG.main()
    a, b = (json.load(open(p / "summary.json", encoding="utf-8")) for p in (ORIG, DG.OUT))
    diff_keys = [k for k in a if k not in ("created", "provenance") and a[k] != b.get(k)]
    prov_diff = {k: (a["provenance"][k], b["provenance"][k]) for k in a["provenance"] if a["provenance"][k] != b["provenance"][k]}
    out["1_rerun"] = {
        "completed_with_guards": True,
        "summary_sections_differing(excl. created/provenance)": diff_keys,
        "provenance_fields_differing": prov_diff,
        "per_claim.csv_identical": sha_raw(ORIG / "per_claim.csv") == sha_raw(DG.OUT / "per_claim.csv"),
        "gold_urls.csv_identical": sha_raw(ORIG / "gold_urls.csv") == sha_raw(DG.OUT / "gold_urls.csv"),
        "original_output_sha256": {f: sha_raw(ORIG / f) for f in ("summary.json", "per_claim.csv", "gold_urls.csv")}}
    S = a

    # ============================================================ 2. headline numbers in the report
    checks = {  # report statement -> (summary path, expected value)
        "200 claims": ("1_ceiling|claims", 200),
        "192 claims with web gold": ("1_ceiling|claims_with_web_gold", 192),
        "8 without web gold": ("1_ceiling|claims_no_web_gold", 8),
        "25 all-unreachable": ("1_ceiling|claims_web_gold_all_unreachable", 25),
        "167 reachable claims": ("1_ceiling|claims_reachable_gold", 167),
        "422 gold URLs": ("1_ceiling|gold_urls", 422),
        "305 reachable gold URLs": ("1_ceiling|gold_urls_reachable", 305),
        "117 unreachable gold URLs": ("1_ceiling|gold_urls_unreachable", 117),
        "ceiling 0.870 over 192": ("1_ceiling|claim_hit_ceiling_any_k|denominator_192_web_gold|p", 0.87),
        "Wilson [0.815,0.910]": ("1_ceiling|claim_hit_ceiling_any_k|denominator_192_web_gold|wilson95", [0.815, 0.91]),
        "ceiling 0.835 over 200": ("1_ceiling|claim_hit_ceiling_any_k|denominator_200_all|p", 0.835),
        "doc ceiling @1 0.682": ("1_ceiling|doc_level_recall_ceiling_at_k|@1|over_167_reachable_docs", 0.682),
        "doc ceiling @3 0.986": ("1_ceiling|doc_level_recall_ceiling_at_k|@3|over_167_reachable_docs", 0.986),
        "doc ceiling 192 @1/@3/@5 0.482": ("1_ceiling|doc_level_recall_ceiling_at_k|@1|over_192_all_web_gold_docs", 0.482),
        "doc ceiling 192 @3 0.720": ("1_ceiling|doc_level_recall_ceiling_at_k|@3|over_192_all_web_gold_docs", 0.72),
        "doc ceiling 192 @5 0.731": ("1_ceiling|doc_level_recall_ceiling_at_k|@5|over_192_all_web_gold_docs", 0.731),
        "0 loose canonical matches": ("1_ceiling|unreachable_with_loose_canonical_match_in_corpus", 0),
        "social reachable 6/28": ("1_ceiling|reachability_rate_by_class|social_account|x", 6),
        "gov reachable 71/106": ("1_ceiling|reachability_rate_by_class|gov_intergov|x", 71),
        "news reachable 122/146": ("1_ceiling|reachability_rate_by_class|news_like|x", 122),
        "PDF reachable 25/38": ("1_ceiling|reachability_pdf|x", 25),
        "archived reachable 97/151": ("1_ceiling|reachability_archived_wrapper|x", 97),
        "not archived 208/271": ("1_ceiling|reachability_not_archived|x", 208),
        "AI primary reachable 86/140": ("9_MODEL_GENERATED_roles_descriptive|reachable_rate_by_role|primary|x", 86),
        "AI secondary reachable 170/215": ("9_MODEL_GENERATED_roles_descriptive|reachable_rate_by_role|secondary|x", 170),
        "AI primary in top100 35/86": ("9_MODEL_GENERATED_roles_descriptive|reachable_in_hybrid_top100_by_role|primary|x", 35),
        "AI secondary in top100 104/170": ("9_MODEL_GENERATED_roles_descriptive|reachable_in_hybrid_top100_by_role|secondary|x", 104),
        "corpus median 782": ("2_candidate_generation|corpus_size_per_claim|median", 782),
        "pool coverage 0.671": ("2_candidate_generation|coverage_at_depth|hybrid|top100", 0.671),
        "hybrid top200 0.850": ("2_candidate_generation|coverage_at_depth|hybrid|top200", 0.85),
        "hybrid top300 0.922": ("2_candidate_generation|coverage_at_depth|hybrid|top300", 0.922),
        "dense top200 0.904": ("2_candidate_generation|coverage_at_depth|dense|top200", 0.904),
        "bm25 U dense 0.784": ("2_candidate_generation|coverage_at_depth|bm25_U_dense_top100", 0.784),
        "55 out of pool": ("2_candidate_generation|out_of_top100_claims", 55),
        "F pool coverage 0.701": ("2_candidate_generation|F_union_pool_coverage", 0.701),
        "D@10 49 hits": ("3_decomposition_167|D|@10|hit", 49),
        "D@10 63 lost in ranking": ("3_decomposition_167|D|@10|lost_in_ranking(gold in pool, rank>k)", 63),
        "D R@10 over 192 0.255": ("3_decomposition_167|D|@10|R@k_over_192", 0.255),
        "A R@10 0.251": ("4_oracle_ladder|table|A_hybrid(actual)|R@10", 0.251),
        "D R@10 0.293": ("4_oracle_ladder|table|D_pred_top3_pool100(actual)|R@10", 0.293),
        "O pub pool 0.659": ("4_oracle_ladder|table|ORACLE_pub_all_gold_pool100|R@10", 0.659),
        "O pub NS pool 0.467": ("4_oracle_ladder|table|ORACLE_pub_nonsecondary_gold_pool100|R@10", 0.467),
        "O pub full 0.832": ("4_oracle_ladder|table|ORACLE_pub_all_gold_full_sitefilter|R@10", 0.832),
        "O pub NS full 0.611": ("4_oracle_ladder|table|ORACLE_pub_nonsecondary_gold_full_sitefilter|R@10", 0.611),
        "H 0.868": ("4_oracle_ladder|table|H_ORACLE_targeted(stored)|R@10", 0.868),
        "median 29 gold-publisher docs": ("4_oracle_ladder|publisher_specificity|median_corpus_docs_from_gold_publishers", 29),
        "13 claims publisher=URL oracle": ("4_oracle_ladder|publisher_specificity|claims_where_every_gold_publisher_doc_is_gold", 13),
        "T1 56": ("5_authority_taxonomy_167|categories|T1_pred_matches_reachable_gold_publisher|n", 56),
        "T5 54": ("5_authority_taxonomy_167|categories|T5_gold_publishers_all_secondary_type|n", 54),
        "T7 25": ("5_authority_taxonomy_167|categories|T7_institutional_authority_missed|n", 25),
        "T1 auth gold outside top100 33": ("5_authority_taxonomy_167|T1_detail|authgold_outside_top100", 33),
        "targeted <=10: 11": ("5_authority_taxonomy_167|T1_detail|of_which_pos_in_targeted_list<=10", 11),
        "targeted <=50: 31": ("5_authority_taxonomy_167|T1_detail|<=50", 31),
        "accuracy NS top3 53/105": ("5_authority_taxonomy_167|pred_accuracy_vs_reachable_nonsecondary_gold_publishers|top3_match", 53),
        "accuracy NS n 105": ("5_authority_taxonomy_167|pred_accuracy_vs_reachable_nonsecondary_gold_publishers|n_claims", 105),
        "accuracy NS top1 39": ("5_authority_taxonomy_167|pred_accuracy_vs_reachable_nonsecondary_gold_publishers|top1_match", 39),
        "T1 oop median rank 265": ("5_authority_taxonomy_167|T1_authgold_outside_top100_full_hybrid_rank_median", 265),
        "pred absent from corpus 6": ("5_authority_taxonomy_167|no_match_claims|pred_publisher_absent_from_corpus", 6),
        "pred absent from top100 45": ("5_authority_taxonomy_167|no_match_claims|pred_publisher_absent_from_hybrid_top100", 45),
        "B nongold gov top10 762": ("6_overboosting|B_generic|nongold_top10_gov_intergov", 762),
        "B foreign gov 150": ("6_overboosting|B_generic|nongold_top10_gov_other_jurisdiction", 150),
        "A nongold gov top10 130": ("6_overboosting|A_reference|nongold_top10_gov_intergov", 130),
        "official missed 620 docs": ("6_overboosting|official_docs_scored_unknown_by_generic_prior|corpus_docs", 620),
        "official missed 113 claims": ("6_overboosting|official_docs_scored_unknown_by_generic_prior|claims", 113),
        "entity rule gold 4": ("6_overboosting|C_entity_rule_matches_in_hybrid_top100|gold", 4),
        "D displacement 19": ("7_displacement|D|claims_with_>=5_pred_publisher_nongold_in_top10", 19),
        "G displacement 68": ("7_displacement|G|claims_with_>=5_pred_publisher_nongold_in_top10", 68),
        "cost 4.38": ("8_other|llm_predictor_cost_usd", 4.38),
        "85 claims >=2 publishers": ("8_other|claims_>=2_reachable_gold_publishers", 85),
        "40 mixed": ("8_other|claims_mixed_secondary_and_nonsecondary_reachable_gold", 40),
    }
    res = {k: {"expected": v, "found": get(S, p), "ok": get(S, p) == v} for k, (p, v) in checks.items()}
    out["2_headline_checks"] = {"n": len(res), "n_ok": sum(r["ok"] for r in res.values()),
                                "failed": {k: r for k, r in res.items() if not r["ok"]}}
    out["2_definition_notes"] = {
        "claims_with_nonsecondary_gold_key(any gold, incl. unreachable)": S["4_oracle_ladder"]["claims_with_nonsecondary_gold_key"],
        "claims_with_reachable_nonsecondary_gold_publisher": S["5_authority_taxonomy_167"][
            "pred_accuracy_vs_reachable_nonsecondary_gold_publishers"]["n_claims"]}

    # ============================================================ 3. rule audit
    hs = read_jsonl(PROCESSED / "averitec_heldout.jsonl")
    per = list(csv.DictReader(open(ORIG / "per_claim.csv", encoding="utf-8")))
    gold = list(csv.DictReader(open(ORIG / "gold_urls.csv", encoding="utf-8")))
    hyb = {}
    with gzip.open(RESULTS / "heldout" / "rankings_hybrid.jsonl.gz", "rt", encoding="utf-8") as fh:
        for r in map(json.loads, fh):
            hyb[int(r["claim_id"])] = [u for u, _ in r["ranked"]]
    stored = {}
    with gzip.open(RESULTS / "source_targeted" / "rankings_heldout.jsonl.gz", "rt", encoding="utf-8") as fh:
        for x in map(json.loads, fh):
            stored.setdefault(x["method"], {})[int(x["claim_id"])] = [u for u, _ in x["ranked"]]
    preds = {}
    for line in open(RESULTS / "heldout" / "authority_raw.jsonl", encoding="utf-8"):
        x = json.loads(line)
        if x.get("cond") == "L+Wctx" and x.get("pred"):
            preds[int(x["claim_id"])] = x
    reach = {}
    for g in gold:
        if g["reachable"] == "True":
            reach.setdefault(int(g["claim_id"]), set()).add(g["url_norm"])

    # 3a. gold publisher keys: target_keys(raw source_url) vs cand_key(url_norm)
    mism = []
    for r in hs:
        seen = set()
        for g in r["gold_evidence"]:
            if not g["is_web_source"] or g["source_url_norm"] in seen:
                continue
            seen.add(g["source_url_norm"])
            tk, ck = target_keys(g["source_url"]), cand_key(g["source_url_norm"])
            if tk != {ck}:
                mism.append({"claim_id": r["claim_id"], "url": g["source_url_norm"][:100], "target_keys": sorted(tk), "cand_key": ck})
    NONPUB = {"twitter.com", "facebook.com", "youtube.com", "instagram.com", "linkedin.com", "google.com", "google.com.ph",
              "bit.ly", "youtu.be", "t.co", "fb.com", "amazonaws.com", "cloudfront.net", "gannett-cdn.com", "scribd.com",
              "perma.cc", "archive.ph", "archive.org", "govdelivery.com", "medium.com", "blogspot.com", "wordpress.com"}
    malformed = lambda k: (not k) or ("." not in k.split("/")[0]) or bool(re.search(r"https?|[^a-z0-9./_-]", k))
    gkeys = Counter(g["publisher_key"] for g in gold)
    out["3a_gold_publisher_keys"] = {
        "gold_urls": len(gold), "distinct_keys": len(gkeys),
        "target_keys_vs_cand_key_disagreements": len(mism), "examples": mism[:12],
        "malformed_keys": {k: n for k, n in gkeys.items() if malformed(k)},
        "non_publisher_keys(platform/redirect/hosting)": {k: n for k, n in gkeys.items() if k in NONPUB},
        "merging_keys_seen": {k: n for k, n in gkeys.items() if k in ("go.com", "archives.gov", "gov.uk", "blog.gov.uk")}}

    # 3b. predicted keys
    entries, nokey, badkey, keylist = 0, [], [], Counter()
    for c, x in preds.items():
        top = (x["pred"].get("top3") or [])[:3]
        cands = primary_authority_candidates(x["pred"])
        entries += len(top)
        if len(cands) < len(top):
            nokey.append((c, len(top) - len(cands)))
        for a in cands:
            for k in a["keys"]:
                keylist[k] += 1
                if malformed(k) or k in NONPUB:
                    badkey.append((c, a["publisher"][:50], k))
    out["3b_predicted_keys"] = {
        "claims_with_prediction": len(preds), "entries": entries,
        "entries_without_usable_key": sum(n for _, n in nokey), "claims_affected": [c for c, _ in nokey],
        "malformed_or_non_publisher_predicted_keys": badkey[:20], "n_malformed_or_non_publisher": len(badkey),
        "predicted_merging_keys": {k: keylist[k] for k in ("go.com", "archives.gov", "gov.uk", "gob.mx", "gov.br", "europa.eu", "un.org")
                                   if keylist[k]}}

    # 3c. T1 match quality: which key produced the match
    t1 = [p for p in per if p["category"].startswith("T1")]
    mk = Counter()
    rows = []
    for p in t1:
        c = int(p["claim_id"])
        pk = set().union(*[set(a["keys"]) for a in primary_authority_candidates(preds[c]["pred"])])
        keys = sorted({cand_key(u) for u in reach[c]} & pk)
        cls = sorted({DG.dclass(k) for k in keys})
        kind = ("merged_or_broad_key" if set(keys) & {"gov.uk", "archives.gov", "go.com", "europa.eu"} else
                "secondary_outlet_named" if set(cls) <= DG.SECONDARY_CLASSES else "specific_publisher")
        mk[kind] += 1
        auth = {u for u in reach[c] if cand_key(u) in pk}
        rows.append({"claim_id": c, "matched_keys": " ".join(keys), "matched_classes": " ".join(cls), "match_kind": kind,
                     "authgold_hit@10_in_D": bool(auth & set(stored["hybrid+llm_authority"][c][:10])),
                     "any_gold_hit@10_in_D": p["D_hit10"] == "True"})
    in_pool = [r for r, p in zip(rows, t1) if int(p["authgold_rank_full_hybrid"]) <= 100]
    out["3c_T1_match_quality"] = {
        "n": len(t1), "match_kind": dict(mk),
        "authgold_in_top100": len(in_pool),
        "authgold_itself_hit@10_in_D": sum(r["authgold_hit@10_in_D"] for r in in_pool),
        "any_gold_hit@10_in_D": sum(r["any_gold_hit@10_in_D"] for r in in_pool),
        "examples_broad_or_secondary": [r for r in rows if r["match_kind"] != "specific_publisher"][:12]}

    # 3d. gov-label rules: bare-suffix hosts and *.go.com
    bare, gocom = Counter(), Counter()
    for c, us in hyb.items():
        for u in us:
            h = full_host(u)
            if h.split(".")[0] in GOV_LABELS and generic_prior(u) < 1.0 and len(h.split(".")[-1]) == 2:
                bare[h] += 1
            if (h.endswith(".go.com") or h == "go.com") and generic_prior(u) == 1.0:
                gocom[h] += 1
    b_top10_gocom = sum(1 for c in reach for u in stored["hybrid+generic"][c][:10]
                        if u not in reach[c] and full_host(u).endswith(".go.com"))
    out["3d_generic_prior_gov_rule"] = {
        "official_bare_suffix_hosts_scored_below_1": dict(bare.most_common()),
        "n_docs": sum(bare.values()),
        "commercial_go.com_hosts_scored_gov_1.0": dict(gocom.most_common()), "n_docs_go.com": sum(gocom.values()),
        "B_nongold_top10_go.com_docs_counted_as_gov(of 762)": b_top10_gocom,
        "note": "frozen generic_prior uses full_host (www. stripped), so www.gob.mx / www.gov.br / www.gov.uk -> 0.3; "
                "'go' in GOV_LABELS makes abcnews.go.com / espn.go.com -> 1.0. Affects frozen B and C only."}

    # 3e. category rules re-evaluated with the fixed gov test (audit only; original categories unchanged)
    from authority_retrieval import country_of
    recat = []
    for p in per:
        c = int(p["claim_id"])
        if p["category"][:2] not in ("T7", "T8"):
            continue
        pk = set().union(*[set(a["keys"]) for a in primary_authority_candidates(preds[c]["pred"])])
        gk = {cand_key(u) for u in reach[c]}
        pg = {country_of(k) for k in pk if "/" not in k and is_gov_fixed(k)}
        gg = {country_of(k) for k in gk if "/" not in k and is_gov_fixed(k)}
        if pg and gg and not (pg & gg):
            recat.append({"claim_id": c, "from": p["category"][:2], "to": "T6", "pred_gov": sorted(pg), "gold_gov": sorted(gg)})
    out["3e_T6_false_negatives_from_gov_rule"] = {"n": len(recat), "claims": recat}

    # 3f. which keys did the NEWS_FC_HINT regex (not a list) classify as news?
    from authority_retrieval import MAJOR_NEWS
    regex_news = sorted({g["publisher_key"] for g in gold if g["class"] == "news_like"
                         and g["publisher_key"] not in MAJOR_NEWS and g["publisher_key"] not in DG.DOMAIN_OVERRIDES})
    out["3f_regex_news_keys(inspect for false positives)"] = regex_news

    # 3h. how much of the report's "non-gold gov/intergov in top-10" is the *.go.com false positive
    out["3h_nongold_top10_gov_counts_with_go.com"] = {}
    for m in ("hybrid", "hybrid+generic", "hybrid+heuristic", "hybrid+llm_authority"):
        ng = [u for c in reach for u in stored[m][c][:10] if u not in reach[c] and generic_prior(u) == 1.0]
        gc = sum(full_host(u).endswith("go.com") for u in ng)
        out["3h_nongold_top10_gov_counts_with_go.com"][m] = {"reported": len(ng), "of_which_go.com": gc,
                                                             "excluding_go.com": len(ng) - gc}

    # 3i. publisher class (heuristic) vs MODEL_GENERATED role (descriptive; circular, not validation)
    rg = [g for g in gold if g["reachable"] == "True"]
    t5 = [p["claim_id"] for p in per if p["category"].startswith("T5")]
    t5_aiprim = [c for c in t5 if any(g["claim_id"] == c and g["ai_role_MODEL_GENERATED"] == "primary" for g in rg)]
    out["3i_class_vs_MODEL_GENERATED_role"] = {
        "warning": "AI-generated labels, same model family as the predictor; agreement is not validation",
        "secondary_class_reachable_gold_by_role": dict(Counter(g["ai_role_MODEL_GENERATED"] for g in rg
                                                               if g["class"] in DG.SECONDARY_CLASSES)),
        "nonsecondary_class_reachable_gold_by_role": dict(Counter(g["ai_role_MODEL_GENERATED"] for g in rg
                                                                  if g["class"] not in DG.SECONDARY_CLASSES)),
        "T5_claims_with_AI_primary_reachable_gold": t5_aiprim, "T5_n": len(t5)}

    # 3j. T1 matches through merged / broad keys (manual inspection list)
    out["3j_T1_broad_key_matches"] = [
        {"claim_id": r["claim_id"], "matched_keys": r["matched_keys"],
         "pred": [(a["publisher"][:60], a["keys"]) for a in primary_authority_candidates(preds[r["claim_id"]]["pred"])],
         "reachable_gold": sorted(reach[r["claim_id"]])}
        for r in rows if r["match_kind"] == "merged_or_broad_key"]

    # 3g. T4 and T5 rule audit rows for manual review
    cat_rows = []
    for p in per:
        if p["category"][:2] in ("T4", "T5", "T7", "T8"):
            r = next(x for x in hs if int(x["claim_id"]) == int(p["claim_id"]))
            cat_rows.append({"claim_id": p["claim_id"], "category": p["category"], "claim": r["claim"][:160],
                             "gold_reachable_keys": p["gold_reachable_keys"], "gold_classes": p["gold_classes"],
                             "near_miss": p["near_miss"], "pred_top3": p["pred_top3"][:300]})
    with open(AUD / "category_rule_audit.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cat_rows[0]))
        w.writeheader()
        w.writerows(cat_rows)

    # ============================================================ 4. gold leakage
    gold_by_claim = {int(r["claim_id"]): r for r in hs}
    url_hits, fc_hits, dom_hits = [], [], []
    raw_lines = [json.loads(l) for l in open(RESULTS / "heldout" / "authority_raw.jsonl", encoding="utf-8")]
    for x in raw_lines:
        if x.get("cond") != "L+Wctx":
            continue
        c, pr = int(x["claim_id"]), (x.get("prompt") or "").lower()
        r = gold_by_claim[c]
        for g in r["gold_evidence"]:
            if g["is_web_source"] and g["source_url_norm"] and len(g["source_url_norm"]) > 15 and g["source_url_norm"].lower() in pr:
                url_hits.append((c, g["source_url_norm"]))
        fc = normalize_url(r.get("fact_checking_article") or "")
        if fc and fc.lower() in pr:
            fc_hits.append(c)
        doms = {cand_key(g["source_url_norm"]) for g in r["gold_evidence"] if g["is_web_source"]}
        if any(d and "." in d and re.search(r"\b" + re.escape(d) + r"\b", pr) for d in doms):
            dom_hits.append(c)
    frozen_reads = {}
    for f in ("baseline_retrieval.py", "source_targeted.py", "authority_retrieval.py", "authority_resolution.py"):
        txt = (HERE / f).read_text(encoding="utf-8")
        frozen_reads[f] = {k: len(re.findall(k, txt)) for k in ("gold_evidence", "ks_type", "ks_query", "source_roles",
                                                               "justification", "gold_label", "fact_checking_article")}
    out["4_leakage"] = {
        "predictor_prompts_scanned": sum(x.get("cond") == "L+Wctx" for x in raw_lines),
        "prompts_containing_a_full_gold_url": url_hits,
        "prompts_containing_fact_checking_article_url": fc_hits,
        "prompts_mentioning_a_gold_publisher_domain(via Wikidata context; legitimate inference-time input)": len(dom_hits),
        "claims_with_gold_domain_in_prompt": dom_hits,
        "string_counts_of_gold_fields_in_retrieval_modules": frozen_reads}

    # ============================================================ 5. frozen-file hashes
    E = ROOT / "experiments"
    full_expect = {
        E / "validation_heldout.py": "304984b62945def7ecbfeb49a7c5c4e4ff68b4d13f080e4bed9465a6235dfbc5",
        E / "source_targeted.py": "6ec3172da035e815b275224742f9bf0a64482b955748c5dfaafeab85dcbba223",
        E / "source_targeted_eval.py": "a686a075471b2fcb0ed5658a2fb372fc384d8f4f3437512e44f87fb386379e04",
        E / "score_heldout_primary.py": "114bf0cac69cce3d43f718360852568199f5af4abb660a85cf924a4f7d046ad2",
        ROOT / "results/source_targeted/rankings_heldout.jsonl.gz": "9105a5da66a287de70fdc6e7e9b5135200589d58c542d61787e7ed883cb66558"}
    fh_json = json.load(open(ROOT / "data/annotations/heldout_primary_package/ai/FROZEN_HASHES.json", encoding="utf-8"))["hashes"]
    loc = {"AI_EVIDENCE_PROMPT.md": "data/annotations/heldout_primary_package/ai/AI_EVIDENCE_PROMPT.md",
           "AI_CLAIM_PROMPT.md": "data/annotations/heldout_primary_package/ai/AI_CLAIM_PROMPT.md",
           "ANNOTATION_GUIDE.md": "data/annotations/heldout_primary_package/ANNOTATION_GUIDE.md",
           "ai_annotate.py": "experiments/ai_annotate.py", "score_ai_primary.py": "experiments/score_ai_primary.py"}
    for k, v in fh_json.items():
        full_expect[ROOT / loc[k]] = v
    prefix_expect = {  # recorded in validation_preregistration.md as prefix…suffix only
        E / "authority_resolution.py": ("58714a83", "0e97"), E / "authority_retrieval.py": ("ac4c2e80", "9312"),
        E / "baseline_retrieval.py": ("2730f0b3", "bd9b"),
        ROOT / "data/annotations/heldout_primary_package/heldout_primary_annotation.csv": ("cf063d5e", "")}
    hashes = {}
    for p, v in full_expect.items():
        lf, raw = sha_lf(p), sha_raw(p)
        hashes[str(p.relative_to(ROOT))] = {"ok": v in (lf, raw), "matched_form": "raw" if raw == v else "lf" if lf == v else None}
    for p, (pre, suf) in prefix_expect.items():
        m = [f for f, h in (("lf", sha_lf(p)), ("raw", sha_raw(p))) if h.startswith(pre) and h.endswith(suf)]
        hashes[str(p.relative_to(ROOT))] = {"ok": bool(m), "matched_form": m[0] if m else None,
                                            "note": "only prefix...suffix recorded in the preregistration"}
    x1 = (ROOT / "results/authority_quality_ablation_phase2/x1_assignment.sha256").read_text().split()[0]
    hashes["results/authority_quality_ablation_phase2/x1_assignment.csv"] = {
        "ok": x1 in (sha_raw(ROOT / "results/authority_quality_ablation_phase2/x1_assignment.csv"),
                     sha_lf(ROOT / "results/authority_quality_ablation_phase2/x1_assignment.csv"))}
    out["5_frozen_hashes"] = hashes

    json.dump(out, open(AUD / "audit_summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    out["provenance"] = {"script_sha256_raw": sha_raw(Path(__file__)), "diagnostic_script_sha256_raw": sha_raw(HERE / "authority_bottleneck_diagnostics.py")}
    json.dump(out, open(AUD / "audit_summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
