"""Synthetic end-to-end test of the reserved-side code (no network, no LLM, no real reserved data).

Builds a fake world in a temp dir (8 claims, KS docs, inputs + sealed records, Wikidata cache,
D raw, T keys), redirects every reserved path and the execution log there, stubs the manifest
gates, and runs: frozen cmd_rank -> reserved_x -> Family R score (frozen analyse, probe=None)
-> Family N score. Also unit-tests the A/B/C and N decision rules. One summary event is written
to the real execution log.
"""
import json
import random
import sys
import tempfile
from pathlib import Path

import v2common
from v2common import log_event

REAL_LOG = v2common.EXEC_LOG
checks = []


def check(name, cond):
    checks.append((name, bool(cond)))


def rules():
    import family_R_replication as FR
    from family_N_score import classify
    base = lambda d, p, lo, d4, p4: {"primary_endpoint": {"diff_R@10": d, "p": p, "bootstrap95CI": [lo, 0.2]},
                                     "secondary_family_holm": [{"test": "R@10 vs generic", "diff": d4, "p_holm": p4}]}
    check("R: A", FR.decide(base(0.1, 0.01, 0.02, 0.05, 0.03), True)["outcome"] == "A")
    check("R: A needs test-4 Holm", FR.decide(base(0.1, 0.01, 0.02, 0.05, 0.06), True)["outcome"] == "B")
    check("R: A needs test-4 diff>0", FR.decide(base(0.1, 0.01, 0.02, 0.0, 0.01), True)["outcome"] == "B")
    check("R: A needs CI lower>0", FR.decide(base(0.1, 0.01, 0.0, 0.05, 0.01), True)["outcome"] == "B")
    check("R: C at diff 0", FR.decide(base(0.0, 1.0, -0.05, 0.05, 0.01), True)["outcome"] == "C")
    check("R: C at negative diff", FR.decide(base(-0.05, 0.01, -0.1, 0.05, 0.01), True)["outcome"] == "C")
    d = FR.decide(base(0.1, 0.01, 0.02, 0.05, 0.03), False)
    check("R: unrun probe wording + A note", d["notes"][0] == FR.NOT_RUN and len(d["notes"]) == 2)
    check("R: unrun probe, B has only the wording", FR.decide(base(0.1, 0.2, -0.01, 0.05, 0.3), False)["notes"] == [FR.NOT_RUN])
    t = lambda p, d, lo, hi: {"p": p, "diff": d, "CI95": [lo, hi]}
    tx = lambda p, d: {"p_holm": p, "diff": d}
    check("N: Supported", classify(t(0.01, 0.1, 0.02, 0.2), tx(0.02, 0.05)) == "N-Supported")
    check("N: Partial", classify(t(0.01, 0.1, 0.02, 0.2), tx(0.2, 0.05)) == "N-Partial")
    check("N: Inconclusive p>=0.05", classify(t(0.2, 0.1, -0.02, 0.2), tx(0.01, 0.05)) == "N-Inconclusive")
    check("N: Inconclusive p/CI disagree", classify(t(0.04, 0.1, -0.01, 0.2), tx(0.01, 0.05)) == "N-Inconclusive")
    check("N: Harm", classify(t(0.01, -0.1, -0.2, -0.02), tx(0.5, -0.05)) == "N-Harm")


def world(tmp: Path):
    import authority_resolution as AR
    from common import normalize_url
    rng = random.Random(7)
    pubs = ["health.gov", "who.int", "nytimes.com", "cnn.com", "someblog.net", "uni.edu", "acme.com",
            "twitter.com/acmeceo", "wikipedia.org", "facebook.com/pageA"]
    words = "vaccine election budget policy minister court ruling data statistics report company product".split()
    ids = list(range(9001, 9009))
    inputs, sealed, mentions, cache, draw = [], [], {}, {}, []
    (tmp / "ks").mkdir()
    for n, cid in enumerate(ids):
        claim = f"The minister said the {words[n]} {words[n + 1]} figure doubled in 2020"
        docs = []
        for j in range(40):
            p = pubs[j % len(pubs)]
            url = f"https://www.{p}/a{cid}-{j}" if "/" not in p else f"https://{p}/posts/{cid}{j}"
            body = " ".join(rng.choice(words) for _ in range(60))
            if j % 7 == n % 7:
                body = claim + " " + body
            docs.append({"doc_idx": j, "url": url, "url_norm": normalize_url(url), "text": body if j != 5 else "",
                         "n_chars": len(body), "ks_type": None, "ks_query": None})
        with __import__("gzip").open(tmp / "ks" / f"{cid}.jsonl.gz", "wt", encoding="utf-8") as fh:
            fh.writelines(json.dumps(d) + "\n" for d in docs)
        gold_urls = [docs[(n * 3) % 40]["url"], docs[(n * 3 + 11) % 40]["url"]] + (["http://Metadata"] if n % 2 else [])
        if n == 7:
            gold_urls = ["https://not-in-ks.org/x"]  # web gold present but unreachable
        rec = {"claim_id": cid, "claim": claim, "speaker_or_entity": "Jane Minister" if n % 3 else None,
               "claim_date": "01-02-2020", "location_ISO_code": "US",
               "gold_label": ["Refuted", "Supported"][n % 2], "fact_checking_article": "https://www.politifact.com/x",
               "gold_evidence": [{"source_url": u, "is_web_source": not u.endswith("Metadata"),
                                  "source_url_norm": None if u.endswith("Metadata") else normalize_url(u)} for u in gold_urls]}
        sealed.append(rec)
        inputs.append({k: rec[k] for k in ("claim_id", "claim", "speaker_or_entity", "claim_date", "location_ISO_code")})
        mentions[str(cid)] = {"mentions": ["Jane Minister"] if n % 3 else []}
        cache["Jane Minister"] = {"qid": "Q1", "label": "Jane Minister", "description": "politician",
                                  "websites": ["https://health.gov"], "handles": {}}
        base = dict(claim=claim, speaker=rec["speaker_or_entity"] or "None", date="01-02-2020", iso="US")
        prompt = AR.USER.format(**base, wd=AR.wd_context(mentions[str(cid)]["mentions"], cache))
        pred = None if n == 6 else {"claim_kind": "statement_by_someone",
                                    "top3": [{"publisher": "Health", "domain": "health.gov"},
                                             {"publisher": "Acme", "domain": "acme.com", "social_account": "twitter.com/acmeceo"}]}
        draw.append({"claim_id": cid, "cond": "L+Wctx", "prompt": prompt, "pred": pred, "cost": 0.0, "model": ["fixture"],
                     "error": None if pred else "unparseable"})
    w = lambda p, rows: p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    w(tmp / "inputs.jsonl", inputs)
    w(tmp / "sealed.jsonl", sealed)
    (tmp / "ho").mkdir()
    w(tmp / "ho" / "authority_raw.jsonl", draw)
    (tmp / "ho" / "wikidata_claim_mentions.json").write_text(json.dumps(mentions), encoding="utf-8")
    (tmp / "wd").mkdir()
    (tmp / "wd" / "wikidata_resolution.json").write_text(json.dumps(cache), encoding="utf-8")
    return ids


def patch(tmp: Path):
    import family_N_score, family_R_replication, paths_reserved, reserved_inputs, reserved_x, verify_manifests
    vals = {"HO_RES": tmp / "ho", "INPUTS": tmp / "inputs.jsonl", "SEALED": tmp / "sealed.jsonl",
            "KS_RESERVED": tmp / "ks", "WD_COPY": tmp / "wd" / "wikidata_resolution.json", "WD_DIR": tmp / "wd"}
    for m in (paths_reserved, family_R_replication, reserved_inputs, reserved_x, family_N_score):
        for k, v in vals.items():
            if hasattr(m, k):
                setattr(m, k, v)
    v2common.EXEC_LOG = tmp / "log.jsonl"
    for m in (family_R_replication, reserved_x, family_N_score):
        if hasattr(m, "rel"):
            m.rel = lambda q: str(q)
    verify_manifests.require = lambda stages=(): {"stubbed": True}
    for m in (family_R_replication, family_N_score, reserved_x):
        m.verify_manifests.require = verify_manifests.require


def main():
    import os
    os.environ["HF_HUB_OFFLINE"] = "1"
    rules()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ids = world(tmp)
        patch(tmp)
        import family_N_score, family_R_replication as FR, reserved_x
        import validation_heldout as V
        from paths_reserved import redirect
        from reserved_inputs import load_reserved
        from t_resolver import postprocess
        redirect()
        V.cmd_rank()
        reserved_inputs_ok = True
        try:
            import reserved_inputs as RI
            RI.N_RESERVED = len(ids)
            cl = load_reserved()
        except Exception as e:
            reserved_inputs_ok, cl = repr(e), []
        check("reserved_inputs loads; D and T Wikidata strings equal", reserved_inputs_ok is True and all(c["wd_matches_D"] for c in cl))
        keys = {}
        for n, c in enumerate(cl):
            pk = sorted({V.cand_key(u) for u, _ in c["pool"]} - {""})
            fake = None if n == 0 else {"abstain": n == 1, "selections": [{"key": k} for k in pk[n % 3: n % 3 + 2]]}
            k, s, f = postprocess(fake, pk)
            keys[str(c["claim_id"])] = {"keys": k, "status": s, "flags": f, "selections": (fake or {}).get("selections")}
        (tmp / "ho" / "T").mkdir()
        (tmp / "ho" / "T" / "keys.json").write_text(json.dumps(keys), encoding="utf-8")
        (tmp / "selection.json").write_text(json.dumps({"family_N_executed": True, "selected_version": 1}), encoding="utf-8")
        reserved_x.main()
        v2common.log_event("reserved_gold_gate_approved", note="fixture")
        FR.score()
        famR = json.loads((tmp / "ho" / "family_R.json").read_text(encoding="utf-8"))
        st = json.loads((tmp / "ho" / "probe_status.json").read_text(encoding="utf-8"))
        check("Family R: frozen analyse ran on redirected paths", famR["n_claims"] == len(ids))
        check("Family R: missing D prediction counted", famR["n_missing_predictions"] == 1)
        check("Family R: no probe section when probe=None", "memorisation_probe" not in famR and st["probe_executed"] is False)
        v2common.log_event("family_R_score_done", note="fixture")
        family_N_score.main()
        famN = json.loads((tmp / "ho" / "family_N.json").read_text(encoding="utf-8"))
        check("Family N: eligible = Family R gold_c", famN["n_eligible"] == famR["n_gold_reachable"])
        check("Family N: consistency gate passed and decision made", famN["decision"].startswith("N-"))
        check("Family N: D failure excluded and counted", famN["exclusions"]["D_unparsed"] == 1)
        check("Family N: unreachable web gold counted", famN["exclusions"]["web_gold_unreachable"] >= 1)
        try:
            FR.score()
            check("Family R: refuses a second scoring pass", False)
        except SystemExit:
            check("Family R: refuses a second scoring pass", True)
    v2common.EXEC_LOG = REAL_LOG
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print("PASS" if ok else "FAIL", n)
    log_event("reserved_pipeline_fixture_test", n=len(checks), n_fail=len(bad), failures=bad,
              note="synthetic data in a temp dir; gates stubbed; no reserved data, network or LLM")
    sys.exit(0 if not bad else 2)


if __name__ == "__main__":
    main()
