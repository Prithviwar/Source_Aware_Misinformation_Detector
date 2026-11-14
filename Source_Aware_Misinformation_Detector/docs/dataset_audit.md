# AVeriTeC Dataset Audit

*Phase-1 audit, 2026-09-29. Everything below was read from the files themselves (Hugging Face repo [`chenxwh/AVeriTeC`](https://huggingface.co/chenxwh/AVeriTeC)), not from papers. Scripts: `experiments/`. Machine-readable numbers: `results/audit_stats.json`.*

<!-- KS_STATS_PLACEHOLDER -->

## 1. What was downloaded

| File (HF repo path) | Size | Used? |
|---|---|---|
| `data/train.json` | 10.2 MB | schema stats only |
| `data/dev.json` | 1.8 MB | **sample source** (labels public) |
| `data/test.json` | 0.9 MB | schema stats only: **no labels, no evidence** (hidden test) |
| `data_store/urls/dev_urls.zip` | 17.7 MB | inspected (per-claim URL lists with query "type") |
| `data_store/knowledge_store/dev_knowledge_store.zip` | **11.5 GB** | **not downloaded.** The 120 sampled claims' members were streamed with HTTP range requests (`experiments/extract_knowledge_store.py`) → `data/raw/averitec/ks_sample/` (~600 MB, gzip) |
| train/test knowledge stores (~62 GB + ~40 GB) | – | not touched |

Local disk had 13 GB free, so the full dev store could not have been downloaded anyway. Original files are kept unmodified in `data/raw/averitec/`.

## 2. Splits

| Split | Claims | Labels? | Gold QA evidence? | Knowledge store |
|---|---:|---|---|---|
| train | 3,068 | ✔ | ✔ | ✔ (3 zips, ~62 GB) |
| dev | 500 | ✔ | ✔ | ✔ (1 zip, 11.5 GB) |
| test | 2,215 | ✖ hidden | ✖ hidden | ✔ (+ `test_updated` after a date-leak fix) |

Test records only have `claim, claim_id, claim_date, speaker, original_claim_url, reporting_source, location_ISO_code`. **All labelled work must use train/dev.** Dev label distribution: Refuted 305, Supported 122, Conflicting Evidence/Cherrypicking 38, Not Enough Evidence 35.

## 3. Claim-level schema (train/dev)

| Field | Type / format | Notes |
|---|---|---|
| `claim` | str | decontextualised claim text |
| `label` | str | Supported / Refuted / Not Enough Evidence / Conflicting Evidence/Cherrypicking |
| `justification` | str | annotator's free-text rationale |
| `claim_date` | str `D-M-YYYY` (no zero padding, e.g. `1-10-2020`) | **the only date field in the dataset** |
| `speaker` | str or null | who made the claim (person, org, page). Free text, not linked to any KB. Null for 118/500 dev claims (23.6%) |
| `reporting_source` | str or null | where the claim appeared (e.g., "Facebook", "Twitter", "CNN"). Null for 90/500 dev claims |
| `original_claim_url` | str or null | link to the claim itself |
| `cached_original_claim_url` | str or null | archive link |
| `fact_checking_article` | str | URL of the professional fact-check the annotation is based on |
| `location_ISO_code` | str or null | e.g. `US`, `NG`, `IN`. The only jurisdiction signal |
| `claim_types` | list[str] | Event/Property 307, Numerical 119, Quote Verification 69, Causal 54, Position Statement 29 (dev) |
| `fact_checking_strategies` | list[str] | Written Evidence 443, Consultation 137, Numerical Comparison 95, Fact-checker Reference 37, Satirical Source Identification 10 (dev) |
| `required_reannotation` | bool | QA flag |
| `questions` | list | gold evidence as question → answers (below) |

## 4. Evidence-level schema (`questions[].answers[]`)

| Field | Notes |
|---|---|
| `question` | annotator's sub-question |
| `answer` | text answer (extractive / abstractive / boolean / unanswerable) |
| `answer_type` | dev: Extractive 707, Abstractive 361, Boolean 292, Unanswerable 39 |
| `boolean_explanation` | only for Boolean answers |
| **`source_url`** | **the only per-evidence source information.** Usually wrapped in `web.archive.org/web/<timestamp>/…`. No publisher name, no date, no source type |
| `cached_source_url` | archive copy |
| `source_medium` | Web text 1054, PDF 108, Metadata 79, Web table 40, Image/graphic 38, Other 24, Video 17, empty 39 (dev) |

**There is no evidence text beyond the short `answer`.** The full document text exists only in the knowledge store (and only if it was scraped successfully).

### Data-quality issues found in `source_url`
- `"Metadata"` (no scheme) used as a placeholder when the evidence is claim metadata, not a page. **11 of 261 answers in our sample have no web source.**
- Malformed prefixes: `https://web.archivehttps://…`, `http://https:/…`, and `…/https:/…` (single slash). `experiments/common.py::strip_wayback` repairs them.
- Search-result pages and tools used as "sources" (`twitter.com/search?...`, `search.justice.gov`, `calculator.net`).

### Example (dev #0)
```json
{"claim": "In a letter to Steve Jobs, Sean Connery refused to appear in an apple commercial.",
 "label": "Refuted", "claim_date": "31-10-2020", "speaker": null, "reporting_source": "Facebook",
 "questions": [
  {"question": "Where was the claim first published",
   "answers": [{"answer": "It was first published on Sccopertino", "answer_type": "Abstractive",
     "source_url": "https://web.archive.org/web/20201129141238/https://scoopertino.com/exposed-the-imac-disaster-that-almost-was/",
     "source_medium": "Web text"}]},
  {"question": "What kind of website is Scoopertino",
   "answers": [{"answer": "Scoopertino is an imaginary news organization ...", "answer_type": "Extractive",
     "source_url": "https://web.archive.org/web/20201202085933/https://scoopertino.com/about-scoopertino/"}]}]}
```

## 5. Knowledge-store schema (one JSON line per document, one file per claim)

```json
{"claim_id": "290", "type": "gold", "query": "_", "url": "https://twitter.com/NASCAR/status/1308213140983820288", "url2text": []}
{"claim_id": "290", "type": "question", "query": "When did Michael Jordan announce he is joining NASCAR as a team owner?",
 "url": "https://www.usatoday.com/story/sports/nascar/2020/09/21/...", "url2text": ["Michael Jordan, Denny Hamlin form new NASCAR team ...", "..."]}
```

| Field | Notes |
|---|---|
| `claim_id` | = index in `dev.json` (verified: KS 290 = dev[290], Michael Jordan/NASCAR) |
| `type` | how the document got into the store. **`gold` marks the annotators' evidence documents: a label leak.** Other values are query-generation strategies (see §7) |
| `query` | the Google query that returned the page. Often a gold question verbatim: **also a leak** |
| `url` | original (usually *un-archived*) URL, so matching to gold needs normalisation |
| `url2text` | list of text lines scraped with trafilatura. **Often empty** |

No publication date, no title field, no domain metadata, no HTML. **Our retrieval code never reads `type` or `query`.** They are kept in the extracts only for auditing.

`dev_urls.zip` has the same per-claim URL lists as TSV (`claim_id, type, url, query`) without text.
