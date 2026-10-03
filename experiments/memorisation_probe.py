"""Memorisation / knowledge-source probe for the LLM authority predictor.

Question: when the frozen predictor (authority_resolution.py, condition L+Wctx) names
the right publisher, is it RESOLVING the authority from the claim, or RECOGNISING a
fact-check / article it saw in training?

No prompt contains gold evidence URLs, gold domains, evidence text, labels, the
fact-checking article or any annotation. Gold is read only in `analyse`.

Conditions (one fresh `claude -p` call each, no tools, empty cwd; same model):
  recall        the PRE-REGISTERED probe prompt of validation_heldout.py, unchanged
                (recognised? which fact-checker + domain? verdict?)  [rerun: the first
                run produced 588/592 unparseable responses and kept no raw text]
  recall_ext    extended recall: fact-check URL guess, headline guess, and the primary
                source the remembered fact-check cited (name + domain)
  paraphrase    frozen authority prompt, claim REWORDED by a separate call
                (paraphrase_gen), same speaker/date/country/Wikidata context
  claim_only    frozen authority prompt, claim text only (speaker/date/country unknown,
                no Wikidata context)
  masked        frozen authority prompt, named entities and URLs/domains in the claim
                replaced by typed placeholders; speaker and date removed; country kept;
                no Wikidata context
The original L+Wctx predictions (already cached) are the reference condition.

  python memorisation_probe.py run heldout|dev
  python memorisation_probe.py analyse
"""
import csv
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from common import RESULTS, load_sample, registered_domain

OUT = RESULTS / "memorisation_probe"
PARA_SYSTEM = ("You rewrite short factual claims. Keep every fact, number, name and place exactly, but change the "
               "wording and sentence structure as much as possible. Do not add or remove information, do not "
               "comment on truth. Output ONLY the rewritten claim, one line.")
EXT_SYSTEM = "You have no tools and no web access. Answer from memory only. Output ONLY one JSON object, no prose."
EXT_USER = """Claim: {claim}
Claim date: {date}

Answer from memory only. If you do not specifically remember a published fact-check of THIS claim, say so and use null.
Return JSON:
{{"remember_fact_check": <true|false>,
  "fact_check_url": "<best recollection of the fact-check article URL, or null>",
  "fact_check_headline": "<best recollection of its headline, or null>",
  "primary_source_cited": {{"name": "<the official/primary source the fact-check relied on, or null>", "domain": "<its web domain, or null>"}},
  "how_sure": <0.0-1.0>}}"""

MASK_LABELS = {"PERSON": "PERSON", "ORG": "ORGANISATION", "GPE": "PLACE", "LOC": "PLACE", "NORP": "GROUP",
               "FAC": "FACILITY", "PRODUCT": "PRODUCT", "EVENT": "EVENT", "WORK_OF_ART": "TITLE", "LAW": "LAW"}
URL_RE = re.compile(r"(https?://\S+|www\.\S+|\b[\w-]+\.(com|org|gov|net|int|edu|in|uk|ng|ph|za|au|ca)(/\S*)?\b)", re.I)


def _cli(system, prompt):
    from authority_resolution import CLAUDE, MODEL
    with tempfile.TemporaryDirectory() as empty:
        p = subprocess.run([CLAUDE, "-p", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
                            "--model", MODEL, "--system-prompt", system, "--output-format", "json"],
                           input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=empty, timeout=300)
    return p


def call(item):
    base = {k: v for k, v in item.items() if k != "system"}
    try:
        p = _cli(item["system"], item["prompt"])
    except Exception as e:  # e.g. CLI binary briefly missing during an auto-update, timeout
        return {**base, "raw": "", "pred": None, "error": f"launch failed: {e!r}"}
    try:
        env = json.loads(p.stdout)
        text = env.get("result", "") or ""
        if item["cond"] == "paraphrase_gen":
            pred = {"text": text.strip().strip('"')} if text.strip() and not env.get("is_error") else None
        else:
            m = re.search(r"\{.*\}", text, re.S)
            pred = json.loads(m.group(0)) if m else None
        return {**base, "raw": text, "pred": pred, "cost": env.get("total_cost_usd"),
                "error": None if pred else f"unparseable (is_error={env.get('is_error')}, api={env.get('api_error_status')})"}
    except Exception as e:
        return {**base, "raw": (p.stdout or "")[-1500:] + (p.stderr or "")[-1500:], "pred": None, "error": repr(e)}


def run_calls(items, path, workers=4):
    done = {}
    if path.exists():
        for line in open(path, encoding="utf-8"):
            x = json.loads(line)
            if x.get("pred"):
                done[(x["claim_id"], x["cond"])] = x
    import time
    for attempt in range(8):
        todo = [i for i in items if (i["claim_id"], i["cond"]) not in done]
        print(f"{path.name}: {len(done)} cached, {len(todo)} to run (pass {attempt + 1})", flush=True)
        if not todo:
            break
        fails = Counter()
        with ThreadPoolExecutor(workers) as ex, open(path, "a", encoding="utf-8") as fh:
            for n, res in enumerate(ex.map(call, todo), 1):
                fh.write(json.dumps(res, ensure_ascii=False) + "\n")
                fh.flush()
                if res["pred"]:
                    done[(res["claim_id"], res["cond"])] = res
                else:
                    fails[res["error"][:60]] += 1
                if n % 50 == 0:
                    print(f"  [{n}/{len(todo)}] fails so far {dict(fails)}", flush=True)
        if fails:
            print("  failures:", dict(fails), "| sample raw:", res.get("raw", "")[:300], flush=True)
            if any("429" in f for f in fails):  # rate/session limit: back off before the next pass
                time.sleep(600)
    return done


_NLP = None


def mask(claim):
    global _NLP
    if _NLP is None:
        import spacy
        _NLP = spacy.load("en_core_web_sm")
    text = URL_RE.sub("[URL]", claim)
    doc = _NLP(text)
    seen, out, last = {}, [], 0
    for e in doc.ents:
        if e.label_ not in MASK_LABELS:
            continue
        key = (MASK_LABELS[e.label_], e.text.lower())
        if key not in seen:
            seen[key] = f"[{MASK_LABELS[e.label_]}_{sum(k[0] == key[0] for k in seen) + 1}]"
        out.append(text[last:e.start_char] + seen[key])
        last = e.end_char
    out.append(text[last:])
    return "".join(out)


def rows_for(split):
    import validation_heldout as V
    if split == "heldout":
        return V.load_heldout(), json.load(open(V.HO / "wikidata_claim_mentions.json", encoding="utf-8"))
    return load_sample(), json.load(open(RESULTS / "wikidata_claim_authorities.json", encoding="utf-8"))


def cmd_run(split):
    from authority_resolution import SYSTEM, USER, WD_CACHE, wd_context
    from validation_heldout import PROBE_SYSTEM, PROBE_USER
    from wikidata_authority import CACHE
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"raw_{split}.jsonl"
    sample, ment = rows_for(split)
    cache = json.load(open(CACHE if split == "heldout" else WD_CACHE, encoding="utf-8"))
    # stage 1: recall probes + paraphrase generation + claim-only + masked
    items = []
    for r in sample:
        cid = int(r["claim_id"])
        spk, date, iso = r.get("speaker_or_entity") or "None", r.get("claim_date") or "unknown", r.get("location_ISO_code") or "unknown"
        items += [
            {"claim_id": cid, "cond": "recall", "system": PROBE_SYSTEM,
             "prompt": PROBE_USER.format(claim=r["claim"], speaker=spk, date=date)},
            {"claim_id": cid, "cond": "recall_ext", "system": EXT_SYSTEM, "prompt": EXT_USER.format(claim=r["claim"], date=date)},
            {"claim_id": cid, "cond": "paraphrase_gen", "system": PARA_SYSTEM, "prompt": r["claim"]},
            {"claim_id": cid, "cond": "claim_only", "system": SYSTEM,
             "prompt": USER.format(claim=r["claim"], speaker="None", date="unknown", iso="unknown", wd="")},
            {"claim_id": cid, "cond": "masked", "system": SYSTEM, "masked_claim": mask(r["claim"]),
             "prompt": USER.format(claim=mask(r["claim"]), speaker="None", date="unknown", iso=iso, wd="")},
        ]
    done = run_calls(items, path)
    # stage 2: authority prediction on the paraphrase (same metadata + same Wikidata context as the original)
    items2 = []
    for r in sample:
        cid = int(r["claim_id"])
        pg = done.get((cid, "paraphrase_gen"))
        if not pg:
            continue
        mentions = ment[str(cid)]["mentions"]
        items2.append({"claim_id": cid, "cond": "paraphrase", "system": SYSTEM, "paraphrased_claim": pg["pred"]["text"],
                       "prompt": USER.format(claim=pg["pred"]["text"], speaker=r.get("speaker_or_entity") or "None",
                                             date=r.get("claim_date") or "unknown",
                                             iso=r.get("location_ISO_code") or "unknown", wd=wd_context(mentions, cache))})
    run_calls(items2, path)
    print("run done", split)


# ---------------------------------------------------------------------------- analysis (gold read here only)
FC_PHRASE = re.compile(r"\b(viral|video shows|photo shows|image shows|picture shows|post(ed|s)? (on|claims?)|"
                       r"facebook|whatsapp|twitter|tweet|instagram|social media|forward(ed)?|message)\b", re.I)
VERDICT = {"Refuted": {"false"}, "Supported": {"true"}, "Conflicting Evidence/Cherrypicking": {"misleading"},
           "Not Enough Evidence": {"unverifiable"}}


def load_raw(split):
    d = {}
    p = OUT / f"raw_{split}.jsonl"
    for line in open(p, encoding="utf-8"):
        x = json.loads(line)
        if x.get("pred"):
            d[(x["claim_id"], x["cond"])] = x
    n_calls = sum(1 for _ in open(p, encoding="utf-8"))
    return d, n_calls


def keys_of(pred, k=3):
    from authority_resolution import pred_keys
    top = ((pred or {}).get("top3") or [])[:k]
    return set().union(*[pred_keys(t) for t in top]) if top else set()


def slug_tokens(url):
    from common import normalize_url
    path = normalize_url(url or "").partition("/")[2]
    return {t for t in re.split(r"[^a-z0-9]+", path.lower()) if len(t) >= 3 and not t.isdigit()}


def analyse_split(split):
    import validation_heldout as V
    from authority_resolution import RAW as DEV_RAW, _label, load_targets
    sample, _ = rows_for(split)
    d, n_calls = load_raw(split)
    ref_raw = V.PRED_RAW if split == "heldout" else DEV_RAW
    orig = {}
    for line in open(ref_raw, encoding="utf-8"):
        x = json.loads(line)
        if x.get("cond") == "L+Wctx" and x.get("pred"):
            orig[int(x["claim_id"])] = x["pred"]
    T = V.gold_info(sample)
    targets = {"gold_publishers": {c: T[c]["gold_keys"] for c in T}}
    if split == "dev":
        tg, _, _ = load_targets()
        targets["pilot_primary"] = {c: set(v) for c, v in tg.items() if v}
    rows = {int(r["claim_id"]): r for r in sample}
    conds = ("orig", "paraphrase", "claim_only", "masked")
    P = {c: {"orig": orig.get(c), **{k: (d.get((c, k)) or {}).get("pred") for k in conds[1:]}} for c in rows}

    rep = {"split": split, "n_claims": len(rows), "n_probe_calls_logged": n_calls,
           "successful_parses": {k: sum((c, k) in d for c in rows) for k in
                                 ("recall", "recall_ext", "paraphrase_gen", "paraphrase", "claim_only", "masked")},
           "cost_usd": round(sum((x.get("cost") or 0) for x in d.values()), 2)}

    # ---- recognition
    rec = {}
    for c, r in rows.items():
        p = (d.get((c, "recall")) or {}).get("pred") or {}
        fc = registered_domain(r.get("fact_checking_article") or "") if r.get("fact_checking_article") else ""
        pd = registered_domain(str(p.get("fact_checker_domain") or "")) if p.get("fact_checker_domain") else ""
        e = (d.get((c, "recall_ext")) or {}).get("pred") or {}
        ov = slug_tokens(e.get("fact_check_url")) & slug_tokens(r.get("fact_checking_article"))
        fs = slug_tokens(r.get("fact_checking_article"))
        rec[c] = {"self_recognised": bool(p.get("recognised")), "fc_domain_correct": bool(fc and pd and fc == pd),
                  "verdict_correct": str(p.get("verdict") or "").lower() in VERDICT.get(r["gold_label"], set()),
                  "ext_remember": bool(e.get("remember_fact_check")),
                  "url_slug_overlap": round(len(ov) / len(fs), 2) if fs else 0.0,
                  "cited_source_keys": keys_of({"top3": [e.get("primary_source_cited") or {}]}) if e else set()}
        rec[c]["likely_recognised"] = rec[c]["fc_domain_correct"] or rec[c]["url_slug_overlap"] >= 0.5
    n = len(rows)
    rep["recognition"] = {
        "self_reported_recognised": sum(v["self_recognised"] for v in rec.values()),
        "fact_checker_domain_correct (pre-registered 'likely recognised')": sum(v["fc_domain_correct"] for v in rec.values()),
        "fact_check_url_slug_overlap>=0.5": sum(v["url_slug_overlap"] >= 0.5 for v in rec.values()),
        "likely_recognised (either signal)": sum(v["likely_recognised"] for v in rec.values()),
        "recall_verdict_matches_gold_label": f"{sum(v['verdict_correct'] for v in rec.values())}/{n}",
        "label_prior_all_false_baseline": f"{sum(r['gold_label'] == 'Refuted' for r in rows.values())}/{n}"}

    # ---- accuracy per condition, per target, per subset
    named = {}
    for c, r in rows.items():
        txt = re.sub(r"[^a-z0-9]", "", (r["claim"] + " " + str(r.get("speaker_or_entity") or "")).lower())
        named[c] = any(len(_label(k)) >= 3 and _label(k) in txt for k in T[c]["gold_keys"])
    subsets = {
        "all": list(rows),
        "likely_recognised": [c for c in rows if rec[c]["likely_recognised"]],
        "not_likely_recognised": [c for c in rows if not rec[c]["likely_recognised"]],
        "self_reported_recognised": [c for c in rows if rec[c]["self_recognised"]],
        "gold_publisher_named_in_claim_or_speaker": [c for c in rows if named[c]],
        "gold_publisher_not_named": [c for c in rows if not named[c]],
        "claim_has_url_or_domain": [c for c in rows if URL_RE.search(rows[c]["claim"])],
        "claim_has_factcheck/social_phrasing": [c for c in rows if FC_PHRASE.search(rows[c]["claim"])],
        "claim_without_factcheck/social_phrasing": [c for c in rows if not FC_PHRASE.search(rows[c]["claim"])],
    }
    acc = {}
    for tname, tgt in targets.items():
        acc[tname] = {}
        for sname, ids in subsets.items():
            ids = [c for c in ids if tgt.get(c) and all(P[c][k] for k in conds)]  # paired: all conditions parsed
            row = {"n": len(ids)}
            for k in conds:
                row[f"{k}_top1"] = round(sum(bool(keys_of(P[c][k], 1) & tgt[c]) for c in ids) / len(ids), 3) if ids else None
                row[f"{k}_top3"] = round(sum(bool(keys_of(P[c][k]) & tgt[c]) for c in ids) / len(ids), 3) if ids else None
            acc[tname][sname] = row
        ids = [c for c in rows if tgt.get(c) and all(P[c][k] for k in conds)]
        flips = {}
        for k in conds[1:]:
            a = [bool(keys_of(P[c]["orig"]) & tgt[c]) for c in ids]
            b = [bool(keys_of(P[c][k]) & tgt[c]) for c in ids]
            w, l, p = V.mcnemar(a, b)
            flips[f"orig->{k}"] = {"gained": w, "lost": l, "p": round(p, 4),
                                   "same_top1_key_as_orig": sum(bool(keys_of(P[c]["orig"], 1) & keys_of(P[c][k], 1)) for c in ids)}
        acc[tname]["_paired_flips_top3"] = flips
        cited = [c for c in ids if rec[c]["cited_source_keys"]]
        acc[tname]["_recall_ext_cited_primary_source"] = {
            "claims_with_a_cited_source": len(cited),
            "cited_source_in_target": sum(bool(rec[c]["cited_source_keys"] & tgt[c]) for c in cited),
            "cited_source_equals_orig_top1": sum(bool(rec[c]["cited_source_keys"] & keys_of(P[c]["orig"], 1)) for c in cited)}
    rep["authority_accuracy"] = acc

    # ---- examples
    tgt = targets.get("pilot_primary") or targets["gold_publishers"]
    mem, genuine = [], []
    for c in rows:
        if not tgt.get(c) or not all(P[c][k] for k in conds):
            continue
        o3, m3 = bool(keys_of(P[c]["orig"]) & tgt[c]), bool(keys_of(P[c]["masked"]) & tgt[c])
        masked_text = (d.get((c, "masked")) or {}).get("masked_claim", "")
        leak_in_mask = any(len(_label(k)) >= 3 and _label(k) in re.sub(r"[^a-z0-9]", "", masked_text.lower()) for k in tgt[c])
        info = {"claim_id": c, "claim": rows[c]["claim"], "masked_claim": masked_text,
                "target": sorted(tgt[c]), "orig_top3": sorted(keys_of(P[c]["orig"])), "masked_top3": sorted(keys_of(P[c]["masked"])),
                "para_top3": sorted(keys_of(P[c]["paraphrase"])),
                "fc_domain_correct": rec[c]["fc_domain_correct"], "url_slug_overlap": rec[c]["url_slug_overlap"],
                "cited_source": sorted(rec[c]["cited_source_keys"]), "self_recognised": rec[c]["self_recognised"]}
        cited_hit = bool(rec[c]["cited_source_keys"] & tgt[c])
        if o3 and (rec[c]["likely_recognised"] or (m3 and not leak_in_mask) or cited_hit):
            info["why_suspect"] = ", ".join(x for x, f in (("recognised fact-check", rec[c]["likely_recognised"]),
                                                           ("correct with names masked", m3 and not leak_in_mask),
                                                           ("recalled fact-check's cited source = target", cited_hit)) if f)
            mem.append(info)
        elif o3 and not rec[c]["likely_recognised"] and not rec[c]["self_recognised"] and not cited_hit and not m3 \
                and bool(keys_of(P[c]["paraphrase"]) & tgt[c]):
            genuine.append(info)
    rep["n_memorisation_suspect"] = len(mem)
    rep["n_no_obvious_memorisation_evidence"] = len(genuine)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, lst in (("suspect", mem), ("no_memorisation_evidence", genuine)):
        if lst:
            with open(OUT / f"examples_{name}_{split}.csv", "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(lst[0]))
                w.writeheader()
                w.writerows({k: (" ".join(v) if isinstance(v, list) else v) for k, v in x.items()} for x in lst)
    rep["examples_suspect"] = mem[:8]
    rep["examples_no_memorisation_evidence"] = genuine[:8]
    return rep


def cmd_analyse():
    out = {}
    for split in ("heldout", "dev"):
        if (OUT / f"raw_{split}.jsonl").exists():
            out[split] = analyse_split(split)
    json.dump(out, open(OUT / "summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=list)
    print(json.dumps(out, indent=1, ensure_ascii=False, default=list)[:20000])


if __name__ == "__main__":
    if sys.argv[1] == "run":
        cmd_run(sys.argv[2])
    else:
        cmd_analyse()
