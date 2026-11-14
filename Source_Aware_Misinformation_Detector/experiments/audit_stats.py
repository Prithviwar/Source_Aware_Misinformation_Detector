"""Step 1 numbers for docs/dataset_audit.md: schema coverage of the released
AVeriTeC splits and what the knowledge store looks like for our sample.
Prints a JSON report and saves it to results/audit_stats.json.
"""
import csv
import json
import statistics
from collections import Counter

from baseline_retrieval import claim_docs
from common import ANNOTATIONS, RAW, RESULTS, is_placeholder_url, load_ks, load_sample, normalize_url

MAX_CHARS = 50_000


def split_stats(name: str) -> dict:
    d = json.load(open(RAW / f"{name}.json", encoding="utf-8"))
    blank = lambda v: v is None or (isinstance(v, str) and not v.strip())
    fields = sorted({k for x in d for k in x})
    out = {"n_claims": len(d), "fields": fields,
           "missing_rate": {f: round(sum(blank(x.get(f)) for x in d) / len(d), 3) for f in fields}}
    if "label" in fields:
        out["labels"] = Counter(x["label"] for x in d)
        ans = [a for x in d for q in x["questions"] for a in q["answers"]]
        urls = [a.get("source_url") or "" for a in ans]
        out.update({
            "questions_per_claim": round(statistics.mean(len(x["questions"]) for x in d), 2),
            "answers": len(ans),
            "answer_type": Counter(a["answer_type"] for a in ans),
            "source_medium": Counter(a.get("source_medium") or "<empty>" for a in ans),
            "source_url_placeholder_or_empty": sum(is_placeholder_url(u) for u in urls),
            "source_url_wayback_wrapped": sum("archive.org/web/" in u for u in urls),
            "claim_types": Counter(t for x in d for t in x["claim_types"]),
            "strategies": Counter(t for x in d for t in x["fact_checking_strategies"]),
            "required_reannotation": sum(bool(x["required_reannotation"]) for x in d),
        })
    return out


def ks_stats(sample) -> dict:
    roles = {}
    with open(ANNOTATIONS / "source_roles.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            roles[(int(r["claim_id"]), normalize_url(r["evidence_url"]))] = r["source_role"]
    raw_counts, dedup_counts, empty, trunc, types = [], [], 0, 0, Counter()
    gold_total = Counter(); gold_in_ks = Counter(); gold_nonempty = Counter()
    gold_type_in_ks = Counter()
    for r in sample:
        raw = load_ks(r["claim_id"])
        raw_counts.append(len(raw))
        types.update(d["ks_type"] for d in raw)
        empty += sum(not d["text"].strip() for d in raw)
        trunc += sum(d["n_chars"] > MAX_CHARS for d in raw)
        docs = {d["url_norm"]: d for d in claim_docs(r["claim_id"], audit=True)}
        dedup_counts.append(len(docs))
        gold_urls_typed = {normalize_url(d["url"]) for d in raw if d["ks_type"] == "gold"}
        for g in {g["source_url_norm"] for g in r["gold_evidence"] if g["is_web_source"]}:
            role = roles.get((r["claim_id"], g), "unannotated")
            for key in ("all", role):
                gold_total[key] += 1
                if g in docs:
                    gold_in_ks[key] += 1
                    gold_nonempty[key] += bool(docs[g]["text"].strip())
            gold_type_in_ks["typed_gold_in_ks"] += g in gold_urls_typed
    n_raw = sum(raw_counts)
    return {
        "claims": len(sample),
        "docs_per_claim_raw": {"mean": round(statistics.mean(raw_counts), 1), "median": statistics.median(raw_counts),
                               "min": min(raw_counts), "max": max(raw_counts)},
        "docs_per_claim_dedup_by_url": {"mean": round(statistics.mean(dedup_counts), 1),
                                        "median": statistics.median(dedup_counts)},
        "ks_type_counts": types,
        "empty_text_rate": round(empty / n_raw, 3),
        "truncated_at_50k_chars_rate": round(trunc / n_raw, 4),
        "gold_web_urls": dict(gold_total),
        "gold_found_in_ks": dict(gold_in_ks),
        "gold_found_in_ks_nonempty": dict(gold_nonempty),
        "gold_urls_matching_a_ks_doc_typed_gold": gold_type_in_ks["typed_gold_in_ks"],
    }


def main():
    report = {s: split_stats(s) for s in ("train", "dev", "test")}
    report["ks_sample"] = ks_stats(load_sample())
    RESULTS.mkdir(exist_ok=True)
    json.dump(report, open(RESULTS / "audit_stats.json", "w", encoding="utf-8"), indent=1, default=dict)
    print(json.dumps(report, indent=1, default=dict))


if __name__ == "__main__":
    main()
