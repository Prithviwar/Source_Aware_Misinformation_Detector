"""Step 7: how much temporal information does AVeriTeC expose?

AVeriTeC provides only `claim_date`. There is no evidence publication date, no
update date and no event date field. We therefore measure what can be recovered
cheaply:
  * a publication date embedded in the URL path (/2020/10/30/, /2020-10-30, /20201030)
  * the Wayback capture timestamp of gold URLs (an upper bound on "existed by",
    NOT a publication date)
  * a year mentioned in the claim text (proxy for event time)
and compare them to the claim date, for gold evidence and for KS documents.
"""
import re
from collections import Counter
from datetime import date

from baseline_retrieval import claim_docs
from common import RESULTS, load_sample, normalize_url, strip_wayback

MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
TEXT_DATE = re.compile(rf"\b(?:{MONTH}\s+\d{{1,2}},?\s+(?:19|20)\d{{2}}|\d{{1,2}}\s+{MONTH},?\s+(?:19|20)\d{{2}}|(?:19|20)\d{{2}}-\d{{2}}-\d{{2}})\b")
PUB_CUE = re.compile(rf"(?:published|posted|first published|date)\s*(?:on|:)?\s*(?:\w+day,?\s*)?(?={MONTH}|\d)", re.I)
UPD_CUE = re.compile(rf"(?:updated|last modified|modified)\s*(?:on|:)?\s*(?:\w+day,?\s*)?(?={MONTH}|\d)", re.I)

URL_DATE = [
    re.compile(r"/(20\d{2}|19\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])(?:/|$|[-_])"),
    re.compile(r"[/_-](20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?:\D|$)"),
    re.compile(r"/(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?:\D|$)"),
]
URL_YM = re.compile(r"/(20\d{2})/(0[1-9]|1[0-2])(?:/|$)")
WAYBACK_TS = re.compile(r"archive\.org/web/(\d{8})")


def url_date(url: str):
    u = strip_wayback(url)
    for rx in URL_DATE:
        m = rx.search(u)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), "day"
            except ValueError:
                pass
    m = URL_YM.search(u)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1), "month"
    return None, None


def parse_claim_date(s: str):
    try:
        d, m, y = (int(x) for x in s.split("-"))
        return date(y, m, d)
    except Exception:
        return None


def main():
    sample = load_sample()
    c = Counter()
    after_examples, old_examples = [], []
    for r in sample:
        cd = parse_claim_date(r["claim_date"])
        c["claim_date_parsed"] += cd is not None
        years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", r["claim"])]
        c["claim_mentions_year"] += bool(years)
        for g in {g["source_url"] for g in r["gold_evidence"] if g["is_web_source"]}:
            c["gold_urls"] += 1
            wb = WAYBACK_TS.search(g)
            c["gold_wayback_ts"] += bool(wb)
            if wb and cd:
                ts = date(int(wb.group(1)[:4]), int(wb.group(1)[4:6]), int(wb.group(1)[6:8]))
                c["gold_captured_after_claim"] += ts > cd
            d, gran = url_date(g)
            if d:
                c["gold_url_date"] += 1
                if cd and d > cd:
                    c["gold_url_date_after_claim"] += 1
                    after_examples.append((r["claim_id"], r["claim_date"], str(d), strip_wayback(g)[:110], r["claim"][:90]))
                if cd and (cd - d).days > 365:
                    c["gold_url_date_older_1y"] += 1
                    old_examples.append((r["claim_id"], r["claim_date"], str(d), strip_wayback(g)[:110], r["claim"][:90]))
        gold_norm = {g["source_url_norm"] for g in r["gold_evidence"] if g["is_web_source"]}
        for doc in claim_docs(r["claim_id"], audit=True):
            if doc["url_norm"] in gold_norm:
                head = doc["text"][:2000]
                c["gold_docs_in_ks"] += 1
                c["gold_docs_nonempty"] += bool(doc["text"].strip())
                c["gold_text_any_date_first2k"] += bool(TEXT_DATE.search(head))
                c["gold_text_pub_cue_date"] += bool(PUB_CUE.search(head))
                c["gold_text_update_cue_date"] += bool(UPD_CUE.search(head))
                c["gold_any_date_signal(url|text)"] += bool(url_date(doc["url"])[0] or TEXT_DATE.search(head))
            c["ks_docs"] += 1
            d, _ = url_date(doc["url"])
            if d:
                c["ks_url_date"] += 1
                if cd and d > cd:
                    c["ks_url_date_after_claim"] += 1
                    c[f"ks_after_claim_type:{doc['ks_type']}"] += 1

    pct = lambda a, b: f"{c[a]}/{c[b]} ({c[a] / c[b]:.1%})" if c[b] else "n/a"
    print(dict(c))
    import json
    json.dump(dict(c), open(RESULTS / "temporal_audit.json", "w"), indent=1)
    print("gold docs in KS with non-empty text:", pct("gold_docs_nonempty", "gold_docs_in_ks"))
    print("  ...any date string in first 2k chars of text:", pct("gold_text_any_date_first2k", "gold_docs_in_ks"))
    print("  ...'published/posted' cue + date:", pct("gold_text_pub_cue_date", "gold_docs_in_ks"))
    print("  ...'updated/modified' cue + date:", pct("gold_text_update_cue_date", "gold_docs_in_ks"))
    print("  ...any date signal (URL or text):", pct("gold_any_date_signal(url|text)", "gold_docs_in_ks"))
    print("claim_date parsed:", pct("claim_date_parsed", "claim_date_parsed"))
    print("claims mentioning a year:", f"{c['claim_mentions_year']}/{len(sample)}")
    print("gold URLs with a date in the URL:", pct("gold_url_date", "gold_urls"))
    print("  ...dated AFTER the claim:", pct("gold_url_date_after_claim", "gold_url_date"))
    print("  ...more than 1 year older than the claim:", pct("gold_url_date_older_1y", "gold_url_date"))
    print("gold URLs with Wayback capture ts:", pct("gold_wayback_ts", "gold_urls"),
          "; captured after claim date:", pct("gold_captured_after_claim", "gold_wayback_ts"))
    print("KS docs with a date in the URL:", pct("ks_url_date", "ks_docs"))
    print("  ...dated AFTER the claim:", pct("ks_url_date_after_claim", "ks_url_date"))
    print("\nGOLD EVIDENCE DATED AFTER CLAIM:")
    for e in after_examples:
        print(" ", e)
    print("\nGOLD EVIDENCE >1 YEAR OLDER THAN CLAIM:")
    for e in old_examples:
        print(" ", e)


if __name__ == "__main__":
    main()
