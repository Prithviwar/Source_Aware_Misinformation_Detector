"""Step 11a: build the BLIND annotation package for a second (human) annotator.

Every gold evidence URL row of data/annotations/source_roles.csv, deduplicated by
(claim_id, normalised URL), in a seeded random order. The file contains the
claim, the URL, a title/snippet from the knowledge store and the gold QA pair the
URL was cited for (the pilot annotator saw the same context). It contains NO
pilot label, source_type, confidence or notes.

Writes data/annotations/second_annotator_template.csv (annotator fills
`annotator_label` with primary / secondary / derived / unclear, optional `notes`)
and data/annotations/second_annotator_key.csv (item_id -> claim_id, url_norm; the
key is only needed for scoring and holds no labels either).
Guidelines: data/annotations/second_annotator_guidelines.md.

`python second_annotator_package.py --heldout` builds the same package for every
human gold web URL of the held-out validation sample (data/processed/averitec_heldout.jsonl):
data/annotations/heldout_annotator_template.csv + heldout_annotator_key.csv. There is
no pilot label for those URLs; a human annotation there enables primary recall on
the held-out set.
"""
import csv
import random
import re
import sys

from common import ANNOTATIONS, PROCESSED, load_ks, load_sample, normalize_url, read_jsonl, registered_domain

SEED = 7
# Columns the HUMAN fills (everything else is context and must stay unchanged).
FILL_COLS = ["annotator_id", "annotator_label", "publisher_name", "multiple_primary_sources", "other_primary_sources",
             "authority_rationale", "confidence", "notes"]
ALLOWED = {"annotator_label": ["primary", "secondary", "derived", "unclear"],
           "multiple_primary_sources": ["yes", "no", "unsure"],
           "confidence": ["high", "medium", "low"]}
CLAIM_COLS = ["claim_id", "claim_text", "claim_speaker", "claim_date", "claim_country",
              "annotator_id", "authority_1_name", "authority_1_domain_or_account", "authority_2_name",
              "authority_2_domain_or_account", "authority_3_name", "authority_3_domain_or_account",
              "multiple_legitimate_authorities", "authority_rationale", "confidence", "notes"]
CLAIM_ALLOWED = {"multiple_legitimate_authorities": ["yes", "no", "unsure"], "confidence": ["high", "medium", "low"]}


def write_xlsx(csv_path, cols, allowed=ALLOWED):
    """Excel copy of a template with dropdowns for the constrained columns (CSV stays canonical)."""
    try:
        from openpyxl import Workbook
        from openpyxl.worksheet.datavalidation import DataValidation
    except ImportError:
        return
    with open(csv_path, encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    wb = Workbook()
    ws = wb.active
    ws.title = "annotate"
    for r in rows:
        ws.append(r)
    ws.freeze_panes = "B2"
    for name, vals in allowed.items():
        if name in cols:
            col = ws.cell(row=1, column=cols.index(name) + 1).column_letter
            dv = DataValidation(type="list", formula1='"' + ",".join(vals) + '"', allow_blank=True)
            dv.add(f"{col}2:{col}{len(rows)}")
            ws.add_data_validation(dv)
    wb.save(csv_path.with_suffix(".xlsx"))


def claim_sheet(prefix, claims):
    """Claim-level sheet: the annotator names the authoritative publisher(s) for each claim BEFORE looking at
    the evidence rows. This is the MANUAL oracle authority (and tests whether several authorities are common).
    It shows only claim + inference-time metadata: no evidence, no model prediction."""
    path = ANNOTATIONS / f"{prefix}_claim_authority_template.csv"
    order = sorted(claims, key=lambda r: random.Random(SEED + int(r["claim_id"])).random())
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=CLAIM_COLS)
        w.writeheader()
        for r in order:
            w.writerow({"claim_id": r["claim_id"], "claim_text": r["claim"], "claim_speaker": r.get("speaker_or_entity"),
                        "claim_date": r.get("claim_date"), "claim_country": r.get("location_ISO_code")})
    write_xlsx(path, CLAIM_COLS, CLAIM_ALLOWED)


def title_and_snippet(text: str) -> tuple[str, str]:
    text = (text or "").strip()
    if not text:
        return "", "(no text in the AVeriTeC knowledge store: open the URL)"
    first = re.split(r"\n|(?<=[.!?])\s", text, maxsplit=1)[0]
    return first[:150], re.sub(r"\s+", " ", text[:400])


def main():
    heldout = "--heldout" in sys.argv
    if heldout:
        smp = read_jsonl(PROCESSED / "averitec_heldout.jsonl")
        rows = [{"claim_id": r["claim_id"], "evidence_url": g["source_url"]}
                for r in smp for g in r["gold_evidence"] if g["is_web_source"]]
        prefix = "heldout_annotator"
    else:
        smp = load_sample()
        with open(ANNOTATIONS / "source_roles.csv", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        prefix = "second_annotator"
    sample = {int(r["claim_id"]): r for r in smp}
    seen, items = set(), []
    ks_text = {}
    for x in rows:
        cid, u = int(x["claim_id"]), normalize_url(x["evidence_url"])
        if (cid, u) in seen:
            continue
        seen.add((cid, u))
        if cid not in ks_text:
            ks_text[cid] = {}
            for d in load_ks(cid):
                k = normalize_url(d["url"])
                if len(d["text"]) > len(ks_text[cid].get(k, "")):
                    ks_text[cid][k] = d["text"]
        title, snip = title_and_snippet(ks_text[cid].get(u, ""))
        qa = next((g for g in sample[cid]["gold_evidence"] if g.get("source_url_norm") == u), {})
        items.append({"claim_id": cid, "claim_text": sample[cid]["claim"],
                      "claim_speaker": sample[cid].get("speaker_or_entity"),
                      "claim_date": sample[cid].get("claim_date"), "claim_country": sample[cid].get("location_ISO_code"),
                      "evidence_url": x["evidence_url"], "source_domain": registered_domain(u), "evidence_title": title, "evidence_snippet": snip,
                      "question_it_answered": qa.get("question", ""), "answer_given": (qa.get("answer") or "")[:300],
                      "url_norm": u})
    random.Random(SEED).shuffle(items)
    cols = ["item_id", "claim_id", "claim_text", "claim_speaker", "claim_date", "claim_country", "evidence_url",
            "source_domain", "evidence_title", "evidence_snippet", "question_it_answered", "answer_given"] + FILL_COLS
    with open(ANNOTATIONS / f"{prefix}_template.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for i, it in enumerate(items, 1):
            w.writerow({**it, "item_id": i, **{c: "" for c in FILL_COLS}})
    with open(ANNOTATIONS / f"{prefix}_key.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "claim_id", "url_norm"])
        for i, it in enumerate(items, 1):
            w.writerow([i, it["claim_id"], it["url_norm"]])
    write_xlsx(ANNOTATIONS / f"{prefix}_template.csv", cols)
    claim_sheet(prefix, [sample[c] for c in sorted({it["claim_id"] for it in items})])
    print(f"{len(items)} items from {len({i['claim_id'] for i in items})} claims; "
          f"{sum(i['evidence_title'] == '' for i in items)} without KS text")


if __name__ == "__main__":
    main()
