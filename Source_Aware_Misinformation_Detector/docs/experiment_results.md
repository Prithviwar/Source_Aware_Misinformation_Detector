# Retrieval feasibility experiment: methods and results

*Run on 2026-09-29, CPU only (Windows laptop, Python 3.13). Every number here comes from files in `results/`, produced by the scripts in `experiments/`. Nothing was estimated by hand except the two pilot role annotations, which are marked as such.*

**Scope.** Retrieval is done **inside the per-claim AVeriTeC dev knowledge store (KS)**, about 771 usable documents per claim. That store was built by Google searches that partly used the gold questions, so it is already claim-specific and enriched with relevant pages. These results say nothing about finding authoritative sources on the open web.

---

## 1. Data

| Item | Value |
|---|---|
| Claims evaluated | **120** (dev, stratified: 70 Refuted, 30 Supported, 10 Conflicting/Cherrypicking, 10 NEE; seed 2026, `experiments/build_sample.py`) |
| Gold QA answers | 320, of which **30 have no web source** (`Metadata` placeholder or empty) |
| Unique gold web URLs (after normalisation) | **226** (231 before URL normalisation) |
| …present in the KS | 226 / 226 |
| …present but with **empty text** | **64** (28%) |
| …usable ("reachable") | **162** |
| Claims with ≥1 web gold URL / ≥1 reachable gold doc | 119 / **99** |
| Claims with no reachable gold (excluded from the "reachable" scores) | 21 |
| Pilot role annotation of gold URLs (**one annotator, not validated**) | 99 primary, 98 secondary, 22 derived, 7 unclear |
| …reachable | 62 primary, 77 secondary, 18 derived, 5 unclear |
| Claims with ≥1 pilot-primary gold / ≥1 **reachable** pilot-primary gold | 73 / **48** |
| KS documents (raw lines) | 118,197; **25,514 (21.6%) have empty text** |
| After URL deduplication | 117,998; 25,482 empty → **92,516 retrieval candidates** (mean 771 per claim) |
| Reachable primary docs whose text is not the real document (Wayback wrapper for PDF/XLS, Archive-Team boilerplate, unrelated text) | **9 / 62**. This removes every primary for 5 claims (95, 174, 218, 438, 460), leaving 43 "content-valid" claims (sensitivity analysis, §4.4) |

Source: `results/retrieval_summary.json` (`corpus`), `results/log_eval.txt`.

## 2. Leakage controls (verified before running)

Two concrete leaks existed in the original loader and were fixed in `experiments/baseline_retrieval.py`:

1. **File order leaks gold.** Gold-typed documents are stored *first* in every KS file (mean relative position 0.001). The old loader kept insertion order and used stable sorts, so any score tie (for example all zero-score BM25 documents) was broken in favour of gold. **Fix:** documents are sorted by URL and then shuffled with a fixed per-claim seed before ranking.
2. **The raw URL leaks gold.** 78/244 (32%) gold-typed KS URLs are `web.archive.org`-wrapped, against 2.2% of other documents. **Fix:** the retriever only sees `url_norm`, the un-archived, normalised URL.

What each condition may read (`retrieval_corpus()` returns only `{url_norm, text}`):

| Condition | Query | Document fields | Claim metadata | Never used |
|---|---|---|---|---|
| BM25 | claim text | `text` | – | `ks_type`, `ks_query`, `doc_idx`, raw `url`, gold URLs, labels, justification, QA pairs, role annotations |
| Dense (all-MiniLM-L6-v2) | claim text | first 1,000 chars of `text` | – | same |
| Hybrid (RRF k=60 of BM25 + dense) | claim text | as above | – | same |
| Generic credibility prior | – | `url_norm` → domain | – | same |
| Entity prior (claim-specific) | – | `url_norm` → domain / social handle | claim text (spaCy NER), `speaker` | same |
| Claim prior (claim-specific) | – | `url_norm` | claim NER, `speaker`, `location_ISO_code` | same |
| Full prior | – | `url_norm` | claim NER, `speaker`, `location_ISO_code` | same |
| Wikidata prior (post-hoc, claim-specific) | – | `url_norm` | claim NER + `speaker` → Wikidata P856/P2002/P2013/P2003 | same |
| **Oracle** (upper bound only) | – | `url_norm` | **domains of this claim's pilot-primary gold URLs (deliberate leakage)** | – |

`speaker` and `location_ISO_code` are in the unlabelled AVeriTeC test release, so they are available at inference time. Residual, disclosed issues:

- 9 gold docs contain Wayback boilerplate in their text. A claim-text query cannot match it.
- The KS itself was assembled partly from gold-question searches (inherent to AVeriTeC).
- The hand-written generic prior lists overlap sample gold domains (INTERGOV 4/13, ACADEMIC 3/16, MAJOR_NEWS 20/47, REFERENCE 3/3), so the generic prior may be slightly favoured.
- Wikidata was queried in 2026, not at the claim date.

## 3. Methods

- **Relevance:** `bm25s` (English stop words, no stemming) over the full text, truncated at 50k chars at extraction. `all-MiniLM-L6-v2` at `max_seq_length=128`, which is the model's training length. CPU budget: about 10 docs/s at 256 tokens on this machine, so 256 tokens would have taken 3–5 h. The dense run took 56 min.
- **Reranking:** `score = minmax(relevance within pool) + λ·prior(url)`, with λ ∈ {0.1, 0.25, 0.5, 1.0}. **λ = 0.25 with a top-100 pool was pre-specified as the headline.** The full grid, plus a "poolall" variant that re-scores all ~771 candidates, is reported as sensitivity analysis. Nothing was tuned on the sample.
- **Priors** (`experiments/authority_retrieval.py`, `wikidata_authority.py`):
  - *generic:* claim-independent. 1.0 for government / intergovernmental, 0.8 academic, 0.6 major news, 0.5 reference, 0.3 unknown, 0.2 platforms and blogs.
  - *entity:* 1 if the domain label or social handle matches a claim/speaker entity string.
  - *claim:* entity match OR a government domain of the claim's country.
  - *full:* max(generic with a foreign-government penalty, claim).
  - *wikidata:* 1 if the domain or handle is an official website/account (on Wikidata) of an entity in the claim or speaker field. Added **post hoc** after the entity prior turned out to fire in only 33/120 claims.
  - *oracle:* 1 if the domain equals a pilot-primary gold domain.
- **Metrics** (`experiments/evaluate_retrieval.py`):
  - R@K = hit@K (≥1 gold doc in the top K).
  - PrimR@K = ≥1 pilot-primary gold doc in the top K.
  - PrimDomR@K = ≥1 page from a pilot-primary gold domain.
  - MRR is computed over the top 100 (0 if absent).
  - Headline denominators: **99 claims with reachable gold** and **48 claims with a reachable pilot-primary doc**. "All" denominators (119 / 73, unreachable counts as a miss) are in `results/retrieval_results.csv`.
- **Statistics:** exact McNemar on per-claim hits and a paired bootstrap 95% CI (10,000 resamples) for each pre-specified comparison. Holm correction within the headline family (12 method comparisons × 6 hit metrics = 72 McNemar tests). Source: `results/significance.csv`.

## 4. Results

### 4.1 Main table (reachable denominators: gold n=99, pilot-primary n=48)

| Method | R@5 | R@10 | R@20 | Primary R@5 | Primary R@10 | Primary R@20 | MRR | Primary MRR | PrimDom R@10 |
|---|---|---|---|---|---|---|---|---|---|
| *random ranking (expected)* | 0.01 | 0.02 | 0.04 | – | – | – | – | – | – |
| **A. BM25** | 0.08 | 0.11 | 0.24 | 0.04 | 0.04 | 0.10 | 0.07 | 0.02 | 0.12 |
| **A′. Dense** | 0.15 | 0.24 | 0.33 | 0.02 | 0.10 | 0.19 | 0.11 | 0.03 | 0.23 |
| A″. Hybrid (RRF) | 0.14 | 0.24 | 0.36 | 0.02 | 0.06 | 0.17 | 0.10 | 0.03 | 0.15 |
| **B. BM25 + generic credibility** (λ=.25) | 0.07 | 0.10 | 0.24 | 0.02 | 0.04 | 0.17 | 0.07 | 0.02 | 0.17 |
| B. Dense + generic (λ=.25) | 0.15 | 0.25 | 0.31 | 0.02 | 0.15 | 0.19 | 0.11 | 0.03 | 0.31 |
| C. BM25 + entity (claim-specific) | 0.08 | 0.11 | 0.25 | 0.04 | 0.04 | 0.12 | 0.06 | 0.02 | 0.15 |
| C. BM25 + claim (entity + jurisdiction gov) | 0.07 | 0.11 | 0.26 | 0.02 | 0.08 | 0.17 | 0.06 | 0.02 | 0.21 |
| **C. BM25 + full (claim-specific + generic)** | 0.07 | 0.12 | 0.24 | 0.02 | 0.08 | 0.17 | 0.07 | 0.03 | 0.21 |
| C. Dense + full | 0.15 | 0.25 | 0.31 | 0.02 | 0.15 | 0.19 | 0.10 | 0.03 | 0.31 |
| C. Hybrid + full | 0.13 | 0.23 | 0.37 | 0.04 | 0.10 | 0.23 | 0.10 | 0.04 | 0.25 |
| C*. BM25 + Wikidata (post-hoc) | 0.08 | 0.11 | 0.26 | 0.04 | 0.04 | 0.15 | 0.06 | 0.02 | 0.17 |
| C*. Dense + Wikidata (post-hoc) | 0.18 | 0.25 | 0.34 | 0.08 | 0.12 | 0.21 | 0.12 | 0.04 | 0.27 |
| *Sensitivity: BM25 + generic, λ=1, all candidates* | 0.05 | 0.10 | 0.14 | 0.10 | 0.17 | 0.25 | 0.03 | 0.05 | 0.44 |
| *Sensitivity: BM25 + full, λ=1, all candidates* | 0.07 | 0.11 | 0.17 | 0.15 | 0.19 | 0.29 | 0.05 | 0.08 | 0.48 |
| *Sensitivity: BM25 + Wikidata, λ=1, all* | 0.10 | 0.14 | 0.27 | 0.08 | 0.12 | 0.21 | 0.08 | 0.07 | 0.19 |
| *Oracle primary domain, λ=.25 (LEAKS, upper bound)* | 0.10 | 0.15 | 0.31 | 0.08 | 0.12 | 0.25 | 0.09 | 0.06 | 0.40 |
| *Oracle primary domain, λ=1, all (LEAKS)* | 0.35 | 0.44 | 0.57 | **0.60** | **0.77** | **0.90** | 0.28 | 0.48 | 1.00 |

The full λ grid for every base and prior is in `results/retrieval_results.csv` (147 ranking conditions).

### 4.2 Paired tests (pre-specified headline family, λ=0.25, top-100 pool)

| Comparison | Metric | Baseline → treatment | Wins/losses (claims) | McNemar p | Holm p |
|---|---|---|---|---|---|
| BM25 → Dense | R@10 | 0.11 → 0.24 | 19 / 6 | **0.015** | – |
| BM25 → Hybrid | R@10 | 0.11 → 0.24 | 16 / 3 | **0.004** | – |
| BM25 → Dense | PrimR@10 | 0.04 → 0.10 | 5 / 2 | 0.45 | – |
| BM25 → +generic | PrimR@20 | 0.10 → 0.17 | 3 / 0 | 0.25 | 1.0 |
| BM25 → +full | PrimR@10 | 0.04 → 0.08 | 2 / 0 | 0.50 | 1.0 |
| BM25 → +full | PrimR@20 | 0.10 → 0.17 | 3 / 0 | 0.25 | 1.0 |
| BM25 → +entity | PrimR@20 | 0.10 → 0.12 | 1 / 0 | 1.0 | 1.0 |
| BM25+generic → BM25+full (claim-specific *vs* generic) | PrimR@10 / @20 | 0.04→0.08 / 0.17→0.17 | 2/0 · 0/0 | 0.5 · 1.0 | – |
| Dense+generic → Dense+full | PrimR@10 | 0.15 → 0.15 | 0 / 0 | 1.0 | – |
| Hybrid+generic → Hybrid+full | PrimR@20 | 0.21 → 0.23 | 1 / 0 | 1.0 | – |
| *Sensitivity:* BM25 → +full (all candidates, λ=.25) | PrimR@20 | 0.10 → 0.23 | 6 / 0 | 0.031 (uncorrected; not pre-specified) | – |
| *Sensitivity:* Dense → +claim (all candidates, λ=.25) | R@10 | 0.24 → 0.13 | 1 / 12 | 0.003 (a **loss**) | – |

**None of the 12 pre-specified authority comparisons is significant on any hit metric (smallest uncorrected p = 0.25; every Holm-adjusted p = 1.0).** The only reliable effect in the experiment is dense or hybrid retrieval beating BM25 on gold R@10. On the primary metrics, every authority-vs-baseline difference comes down to 0–6 claims out of 48.

### 4.3 Why the ceiling is low: pool diagnostics (`results/pool_diagnostics.json`)

| Base | Median best-gold rank | Gold in top-100 | Median best-primary rank | **Primary in top-100 (rerank ceiling)** |
|---|---|---|---|---|
| BM25 | 65 | 55/99 | 232 | **17/48** |
| Dense | 41 | 64/99 | 152 | 18/48 |
| Hybrid | 43 | 71/99 | 137 | 23/48 |

Under BM25, pilot-primary gold docs rank **much lower than secondary gold docs**: median rank 357 vs 117; 18/62 vs 37/77 are in the top 100. They are also shorter (median 3.6k vs 4.5k chars). A top-100 reranker cannot reach 31 of the 48 primary docs.

### 4.4 Sensitivity: content-valid primaries only (43 claims)

After removing the 5 claims whose only primaries are scraping junk (`results/sensitivity_content_valid_primary.txt`), the pattern is unchanged. PrimR@10:

| Method | PrimR@10 |
|---|---|
| BM25 | 0.05 |
| Dense | 0.12 |
| BM25 + generic | 0.05 |
| BM25 + full | 0.09 |
| BM25 + Wikidata | 0.05 |
| BM25 + full (λ=1, all candidates) | 0.21 |
| Oracle (λ=1, all candidates) | 0.81 |

### 4.5 Metric 3: what is at rank 1? (blind pilot annotation, 48 primary-reachable claims)

Only 3.4% of top-5 documents carry a gold role label, so the gold-URL annotation cannot measure derived-source rates. We therefore pooled each method's rank-1 document (156 unique items) and labelled them **blind to method and gold status**, from claim + URL + first 400 chars. The annotator was one person (Claude, pilot; not validated). Scheme:

- **P**: on-topic primary
- **A**: the claim-maker's own statement or page
- **O**: official/academic-looking but off-topic or wrong jurisdiction
- **S**: secondary
- **D**: derived (wiki, aggregator, forum, mirror)
- **U**: unclear

Files: `data/annotations/top1_blind_roles.csv`, `results/top1_role_rates.json`.

| Method (rank 1) | P | A | O | S | D | U |
|---|---|---|---|---|---|---|
| BM25 | 0.02 | 0.02 | 0.08 | 0.69 | 0.12 | 0.06 |
| Dense | 0.02 | 0.02 | 0.04 | 0.77 | 0.15 | 0.00 |
| Hybrid | 0.02 | 0.02 | 0.06 | 0.83 | 0.06 | 0.00 |
| BM25 + generic (λ=.25) | 0.02 | 0.06 | 0.12 | 0.65 | 0.10 | 0.04 |
| BM25 + full (λ=.25) | 0.02 | 0.06 | 0.10 | 0.67 | 0.10 | 0.04 |
| BM25 + Wikidata (λ=.25) | 0.04 | 0.02 | 0.08 | 0.67 | 0.12 | 0.06 |
| BM25 + full (λ=1, all candidates) | **0.12** | 0.08 | **0.52** | 0.25 | 0.02 | 0.00 |

Relevance retrieval puts a secondary source first 69–83% of the time and a derived one 6–15% of the time. A strong authority prior does make rank 1 look official (P+A+O = 72%), **but 52% are off-topic or wrong-jurisdiction official pages**, and it also costs gold R@20 (0.24 → 0.17).

## 5. Provenance: apparent duplication/derivation heuristics

Heuristic only: word-5-gram shingle containment. **This is not verified provenance.** Source files: `experiments/provenance_audit.py`, `provenance_primary_copies.py`, `results/provenance_top10.csv`, `provenance_primary_copies.csv`, `provenance_summary.json`.

**Top-K redundancy** (would naive majority voting double-count?):

| Base | Threshold (containment ≥) | Claims with a copy pair in top-10 | Docs absorbed in top-10 | Claims with a group of ≥3 copies in top-20 |
|---|---|---|---|---|
| BM25 | 0.5 | 40/120 | 59/1200 (4.9%) | 15/120 |
| BM25 | 0.3 | 48/120 | 76/1200 (6.3%) | 21/120 |
| Dense | 0.5 | 45/120 | 60/1200 (5.0%) | 21/120 |
| Dense | 0.3 | 52/120 | 78/1200 (6.5%) | 30/120 |

Other redundancy signals:

- 5.9% of BM25 top-10 docs carry a wire-service marker (Reuters/AP/AFP/PTI).
- 47% contain an attribution phrase ("according to…", "said in a statement").

**Copies of primary documents.** Out of 62 reachable primary docs:

| Containment of the primary's shingles | Primaries with ≥1 apparent copy elsewhere in the KS | Copies | Copies that outrank the primary (BM25 / dense) | Copies that name the primary publisher |
|---|---|---|---|---|
| ≥ 0.5 | 8 | 27 | 11 / 6 | 8 |
| ≥ 0.3 | 17 | 59 | 31 / 15 | 29 |

Some ≥0.5 "copies" are artefacts of the junk-text primaries (#95, #438 match forum boilerplate). The real cases are §6.3 of `feasibility_decision.md`.

## 6. Temporal audit (`experiments/temporal_audit.py`, `results/temporal_audit.json`)

| Quantity | Value |
|---|---|
| Date fields in the dataset | **only `claim_date`**. No evidence publication, update or event-date field exists (checked against every key in `dev.json`) |
| Claims with a parseable claim date | 120/120 |
| Claims whose text mentions a year (event-time proxy) | 14/120 |
| Gold URLs with a date in the URL path | 39/231 (16.9%); 5 of these dated *after* the claim, 16 more than a year older |
| Gold URLs with a Wayback capture timestamp (existence upper bound, *not* publication date) | 72/231; 69 captured after the claim date |
| Gold docs with an explicit "published/posted" date in the text | 3/226 (1.3%) |
| … with an "updated/modified" date | 1/226 (0.4%) |
| … with *any* date signal (URL or text) | 65/226 (28.8%). Not necessarily a publication date |
| KS docs with a URL date | 17,713/117,998 (15%); 1.7% of those after the claim date |

## 7. Reproduce

```bash
cd experiments
python baseline_retrieval.py --method bm25        # ~10 min
python baseline_retrieval.py --method dense       # ~1 h on 4 CPU threads
python baseline_retrieval.py --method hybrid
python authority_retrieval.py bm25 dense hybrid
python wikidata_authority.py bm25 dense hybrid    # uses results/wikidata_resolution.json cache (else ~15 min, rate-limited)
python evaluate_retrieval.py                      # tables + significance (~15 min)
python pool_diagnostics.py bm25 dense hybrid
python provenance_audit.py && python provenance_primary_copies.py bm25 dense
python temporal_audit.py
python export_top1_for_annotation.py && python top1_role_rates.py
python error_analysis.py
```

Requires the per-claim KS extracts in `data/raw/averitec/ks_sample/` (`extract_knowledge_store.py`), `en_core_web_sm`, and `sentence-transformers/all-MiniLM-L6-v2`.

## 8. Independent verification (second session, 2026-09-29)

A second session re-checked the results above before any further work. Script: `experiments/verify_results.py`. Output: `results/verification.json`.

**Reproducibility.**

- BM25 was re-run from scratch for all 120 claims. Top-100 rankings and scores are **identical** for 120/120 claims (max score difference 0.0).
- The retriever objects contain only the fields `text` and `url_norm`.
- Every headline number in §4.1 was recomputed **without** `evaluate_retrieval.py`, directly from the ranking files, the raw KS and `source_roles.csv`. All match to three decimals: BM25, dense, hybrid, +generic, +full, the λ=1 all-candidate setting, and the oracle.

**Code-level leakage audit.**

- Only `oracle_primary_domains()` reads `source_roles.csv`.
- No non-oracle prior reads gold URLs, `ks_type`, `ks_query`, labels or annotations.

**Artifact rankers** (can gold be found from form alone?). Ranking by text length or by URL length gives gold R@10 0.01 and PrimR@10 0.02, the same as random (0.02 / 0.02). Gold documents are not identifiable by length or URL shape. Median text length: gold 4.3k chars, non-gold 6.7k.

**Prior-list contamination.** The hand-written lists overlap sample gold domains:

- INTERGOV 4/13; all 4 (who.int, un.org, worldbank.org, oecd-ilibrary.org) are pilot-*primary* gold domains
- ACADEMIC 3/16
- MAJOR_NEWS 20/47
- REFERENCE 3/3

Every overlapping domain was removed and the priors re-scored. Structural rules (.gov, .edu, .int, .ac.) were kept.

| Method (λ=0.25, top-100) | PrimR@5 | PrimR@10 | PrimR@20 | R@10 |
|---|---|---|---|---|
| BM25 + generic, original → **decontaminated** | .02 → .02 | .04 → .06 | .17 → **.13** | .10 → .10 |
| BM25 + full, original → decontaminated | .02 → .02 | .08 → .08 | .17 → **.13** | .12 → .11 |
| Dense + generic, original → decontaminated | .02 → .02 | .15 → **.08** | .19 → .19 | .25 → .23 |
| Dense + full, original → decontaminated | .02 → .08 | .15 → .13 | .19 → .19 | .25 → .25 |
| Hybrid + full, original → decontaminated | .04 → .08 | .10 → .13 | .23 → .19 | .23 → .22 |

- The generic prior was indeed flattered by the lists; on the dense base its PrimR@10 halves.
- After decontamination, claim-specific (full) ≥ generic in all 9 base × K cells, but by only 0–3 of 48 claims each. Paired McNemar p ≥ 0.25 everywhere.
- Full vs. its relevance-only base: 0–3 wins per cell, p ≥ 0.25.

**Conclusion of the verification.** The results in §4 are reproducible and free of the leakage paths checked. List contamination slightly *inflated* condition B. Removing it gives a consistent but tiny, non-significant edge to claim-specific over generic priors. It does not change the decision in `feasibility_decision.md`.

Reproduce: `cd experiments && python verify_results.py` (~5 min; needs the rankings from §7).

## 9. Follow-up A: LLM authority resolution plugged into the reranker

Full write-up: `docs/authority_resolution_study.md`. Summary:

- **Resolution accuracy** (71 evaluable pilot-primary claims, claim + speaker + date + country only, no tools/web): LLM + Wikidata context names the pilot-primary publisher at top-1 0.63 and top-3 0.77. Wikidata official-site lookup alone: 0.06 / 0.11. Same-country frequency baseline: 0.11 / 0.20.
- **Pilot primary recall** (n=48): PrimR@10 rises from 0.04–0.10 to 0.44–0.46 at λ=1 re-scoring all candidates (+17 to +21 claims, p<.0001), against 0.15–0.21 for generic credibility at the same weight. Oracle: 0.75–0.79.
- **Human-gold recall, all 99 reachable-gold claims (circularity-free w.r.t. the pilot annotator):**

| Method (hybrid base) | R@5 | R@10 | R@20 |
|---|---|---|---|
| Hybrid | 0.14 | 0.24 | 0.36 |
| + generic credibility, λ=1, top-100 | 0.13 | 0.21 | 0.28 |
| + LLM-predicted authority, λ=.25, top-100 (pre-specified) | 0.16 | 0.28 | 0.39 |
| + LLM-predicted authority, λ=1, top-100 | **0.24** | **0.34** | **0.44** |

At λ=1 the hybrid gain over the base is +13/−3, +15/−5 and +10/−2 claims (p = .02, .04, .04). Over generic it is +14/−3, +17/−4 and +18/−2 (p = .01, .007, <.001). All p values are uncorrected. The pre-specified λ=.25 gain is not significant (p ≥ .22). All bases and settings are in `results/predicted_authority_retrieval.json` → `gold_recall_all_claims`.

**Caveats:** the λ=1 result is exploratory (sensitivity setting, 27 cells inspected, no multiplicity correction), and the LLM may have memorised these 2020 fact-checks.

## 10. Follow-up B: provenance-aware verdict aggregation probe

Script: `experiments/provenance_aggregation.py`. Outputs: `results/provenance_aggregation_summary.json`, `provenance_aggregation.csv`, `provenance_families.csv`, `provenance_stance_raw.jsonl`. The run was interrupted by a usage limit and resumed from cache, so **1,240/1,240 stance calls completed** (logs `log_provenance_aggregation_resume.txt`, `log_provenance_aggregation_final.txt`; about $11.9 of Sonnet 5.5 calls).

**Setup.**

- Evidence per claim is the hybrid top-10 non-empty documents, plus the BM25/dense top-10 for focus claims #354 and #374.
- One LLM call per document, which sees the claim and that document only (never the label or other documents). It returns the stance, the stated underlying source, the relation to that source, and an interested-party flag.
- Documents are grouped into "families":
  - **F0:** none (naive voting).
  - **F1:** near-duplicates (5-gram containment ≥ 0.5, or the same URL path on two domains).
  - **F2:** F1 plus a shared stated underlying source.
- **Verdict:** majority over families of supports vs refutes. "+discount" drops families whose source is flagged as an interested party.
- These are apparent duplication/derivation heuristics, **not verified provenance**.

| Condition | Mean voting units per claim | Claims with any collapse | Verdict accuracy vs gold (n=120) | Refuted | Supported | Conflicting | NEE |
|---|---|---|---|---|---|---|---|
| F0 naive | 10.33 | – | 0.633 | 55/70 | 21/30 | 0/10 | 0/10 |
| F1 near-dup | 9.87 | 37 | 0.633 | 55/70 | 20/30 | 1/10 | 0/10 |
| F2 + attribution | 8.06 | 88 | 0.633 | 55/70 | 19/30 | 2/10 | 0/10 |
| F0 + discount | – | – | 0.625 | 54/70 | 21/30 | 0/10 | 0/10 |
| F2 + discount | – | – | 0.617 | 53/70 | 19/30 | 1/10 | 1/10 |

- **Attribution grouping collapses a lot** (F2: 10.3 → 8.1 units; 88/120 claims affected). Near-duplicate grouping alone collapses little (37 claims), consistent with §5.
- **Verdicts barely change.**
  - F2 changes 5 verdicts (2 to correct, 2 from correct; McNemar p = 1).
  - F2 + discount changes 13 (3 to correct, 5 from correct; p = .73).
  - Family-level de-duplication does not improve accuracy on this sample.
- **It moves the right classes slightly.** Conflicting goes 0 → 2 of 10 under F2, e.g. #288 BLM "nuclear family": 7–2 Supported → 1–1 Conflicting (gold: Conflicting). F2 + discount gets #354 right: Supported 5–0 → NEE (gold: NEE), because every supporting document traces to the Edo State government's own release.
- **The interested-party discount is not safe as written.**
  - **#412 (Taiwan Su-35).** All 10 refuting documents cite Taiwan's Ministry of National Defense, which the LLM flags as "interested". The denial is discarded and the verdict goes Refuted → NEE. The interested party here *is* the primary authority on the fact.
  - **#95, #99, #388, #395** flip to NEE the same way.
  - Whether a source is interested depends on whether it asserts or denies a fact against its own interest. The flag does not capture that.
- **Concrete families** (`results/provenance_families.csv`):
  - **#374.** 8 documents (USA Today, Business Insider, The Intercept, …) share "Oregon law enforcement (FBI Portland, Douglas County Sheriff, …)" as their underlying source. `bbc.com` and `bbc.co.uk` copies of one story collapse via the same-path rule.
  - **#1.** 9 documents on the "Billie Eilish" leak trace to one Washington Post/Politico report; Yahoo Money and Yahoo Finance carry the identical syndicated article.
  - **#412.** 10 documents all relay the same MND statement.

## 11. Frozen held-out evaluation (200 claims, disjoint from dev)

*Added 2026-09-30. Nothing was re-run or re-tuned for this section. All numbers are copied from the frozen outputs:*

- *`results/heldout/validation_heldout.json` (pre-registered LLM-authority endpoint, `validation_heldout.py` SHA-256 `304984b6…dfbc5`)*
- *`results/source_targeted/results_heldout.json` (A–H ablation, written 15:03, `source_targeted.py` `6ec3172d…` and `source_targeted_eval.py` `a686a075…`, both equal to the hashes in `source_targeted_preregistration.md`)*

*The error analysis (§11.5) comes from `experiments/source_targeted_errors.py`, which only reads the saved rankings. Its recomputed G/D R@10 match the frozen tables exactly.*

**Denominators.**

- 200 held-out claims. 192 have ≥1 web gold URL; **167 have ≥1 reachable (non-empty) gold doc**.
- 422 gold URLs, 117 of them empty in the KS.
- **Held-out primary-source recall is N/A.** `data/annotations/heldout_annotator_template.csv` (422 rows) and the claim-authority template (192 rows) are both unfilled: 0 annotator labels. No primary number is estimated.

### 11.1 Held-out results (gold n=167; λ=1; top-100 pool unless noted)

| | Method | R@1 | R@5 | R@10 | R@20 | R@50 | R@100 | MRR@100 | Gold claim coverage (pool) | Gold doc coverage | Mean pool | Primary R@K |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | Hybrid | 0.060 | 0.156 | 0.251 | 0.383 | 0.563 | 0.671 | 0.125 | 0.671 | 0.505 | 100 | N/A |
| B | Hybrid + generic credibility | 0.024 | 0.174 | 0.263 | 0.383 | 0.569 | 0.671 | 0.099 | 0.671 | 0.505 | 100 | N/A |
| C | Hybrid + heuristic authority (`full`) | 0.030 | 0.186 | 0.275 | 0.407 | 0.569 | 0.671 | 0.109 | 0.671 | 0.505 | 100 | N/A |
| D | Hybrid + LLM authority | 0.066 | 0.198 | **0.293** | **0.437** | 0.581 | 0.671 | 0.138 | 0.671 | 0.505 | 100 | N/A |
| E | Source-targeted only | 0.060 | 0.138 | 0.180 | 0.180 | 0.180 | 0.180 | 0.091 | 0.180 | 0.108 | 8.4 | N/A |
| F | Hybrid + source-targeted | 0.060 | 0.204 | 0.287 | 0.407 | **0.617** | **0.695** | **0.141** | **0.701** | **0.548** | 105.7 | N/A |
| G | Hybrid + source-targeted + LLM authority | 0.060 | 0.174 | 0.246 | 0.401 | 0.611 | 0.695 | 0.128 | 0.701 | 0.548 | 105.7 | N/A |
| ctrl | Size-matched hybrid top-(100+added) | 0.060 | 0.156 | 0.251 | 0.383 | 0.563 | 0.671 | 0.125 | 0.677 | 0.511 | 105.7 | N/A |
| *H* | ***ORACLE*** *(publishers of all human gold URLs; leaks by design)* | *0.479* | *0.754* | *0.868* | *0.880* | *0.886* | *0.886* | *0.602* | *0.886* | *0.711* | *104.4* | *N/A* |

Also computed: BM25 R@10 0.180, dense R@10 0.251.

**Pre-registered tests.**

| Test | Wins/losses | p (exact McNemar) | Holm p | Δ, 95% bootstrap CI |
|---|---|---|---|---|
| **LLM-authority primary endpoint:** D vs A, R@10 | +13 / −6 | 0.167 | – | +0.042 [−0.006, 0.096] |
| D vs A, R@5 (secondary family) | +11 / −4 | 0.118 | 0.373 | +0.042 |
| D vs A, R@20 | +12 / −3 | 0.035 | 0.176 | +0.054 [0.012, 0.102] |
| D vs B, R@10 | +16 / −11 | 0.442 | 0.884 | +0.030 |
| D vs B, R@20 | +16 / −7 | 0.093 | 0.373 | +0.054 |
| **Source-targeted family:** coverage F vs size-matched control | +5 / −1 | 0.219 | 0.555 | +0.024 [0.000, 0.054] |
| R@10 G vs D | +10 / −18 | 0.185 | 0.555 | −0.048 [−0.108, 0.012] |
| R@10 G vs A | +21 / −22 | 1.000 | 1.000 | −0.006 [−0.084, 0.072] |

**No pre-registered held-out comparison is significant.**

- D (LLM authority) is directionally best at R@5/10/20.
- F has the best coverage, R@50, R@100 and MRR.
- G (the full proposed pipeline) is **below D** and equal to A at R@10.
- Descriptive, uncorrected: G vs A R@50 +11/−3 (p=0.057).

### 11.2 Development vs held-out (frozen config; dev figures are exploratory because dev was used for design)

| Method | Dev R@10 (n=99) | Held-out R@10 (n=167) | Dev R@20 | Held-out R@20 | Dev gold coverage | Held-out gold coverage | Dev primary coverage (n=48, pilot) | Dev PrimR@1/3/5/10/20 (pilot) |
|---|---|---|---|---|---|---|---|---|
| A Hybrid | 0.242 | 0.251 | 0.364 | 0.383 | 0.717 | 0.671 | 0.479 | .000/.021/.021/.062/.167 |
| B + generic | 0.212 | 0.263 | 0.283 | 0.383 | 0.717 | 0.671 | 0.479 | .000/.083/.083/.167/.250 |
| C + heuristic | 0.232 | 0.275 | 0.293 | 0.407 | 0.717 | 0.671 | 0.479 | .000/.104/.125/.188/.271 |
| D + LLM authority | 0.343 | 0.293 | 0.444 | 0.437 | 0.717 | 0.671 | 0.479 | .146/.229/.271/.354/.396 |
| E Targeted only | 0.283 | 0.180 | 0.283 | 0.180 | 0.283 | 0.180 | 0.562 | .208/.333/.417/.562/.562 |
| F Hybrid + targeted | **0.374** | 0.287 | **0.495** | 0.407 | 0.768 | 0.701 | 0.667 | .125/.250/.375/.500/.583 |
| G F + LLM authority | 0.354 | 0.246 | 0.465 | 0.401 | 0.768 | 0.701 | 0.667 | .167/.292/.417/.562/.583 |
| ctrl size-matched | 0.242 | 0.251 | 0.364 | 0.383 | 0.717 | 0.677 | 0.479 | – |
| *ORACLE* | *0.535* | *0.868* | *0.576* | *0.880* | *0.798* | *0.886* | *0.812* | *.375/.521/.625/.812/.812* |

The oracle target differs between splits: pilot-primary publishers on dev, all gold publishers on held-out. The two oracle rows are **not comparable**.

| Pre-registered test | Dev | Held-out |
|---|---|---|
| D vs A, R@10 | +15/−5, p=0.041, Δ +0.101 [0.020, 0.192] | +13/−6, p=0.167, Δ +0.042 [−0.006, 0.096] |
| Coverage F vs control | +5/−0, p=0.063 | +5/−1, p=0.219 |
| G vs D, R@10 | +10/−9, p=1.0 | +10/−18, p=0.185 |
| G vs A, R@10 | +23/−12, p=0.090 | +21/−22, p=1.0 |

- **Relevance baselines transfer:** A goes 0.242 → 0.251.
- **Every authority/targeting method except B and C loses on held-out:** D −0.05, E −0.10, F −0.09, G −0.11 R@10.
- The dev gain of G over A (+0.11) is **0.00** on held-out.
- The part that holds, weakly, is pool expansion: F coverage is +5 claims over the size-matched control on both splits, R@50/R@100 go up on both, and held-out F vs A R@10 is 0.287 vs 0.251. That last comparison was not pre-registered and was not tested.

### 11.3 Authority resolution accuracy (frozen L+Wctx predictor; target = publishers of ALL human gold URLs, a lower bound)

| Split | n | Top-1 | Top-3 |
|---|---|---|---|
| Dev | 117 | 0.385 | 0.479 |
| Held-out | 192 | 0.292 | 0.391 |
| *(Dev vs pilot-primary publishers, n=71; **different target, not comparable**)* | 71 | 0.634 | 0.775 |

The 0.77 top-3 reported in §9 is against the one-annotator pilot-primary subset. Against the same all-gold target, dev is 0.479 and held-out is 0.391.

### 11.4 Memorisation probe (held-out, 200 claims, all 6 probe conditions parsed 200/200; `results/memorisation_probe/summary_heldout.json`, $18.37)

Top-3 authority accuracy vs gold publishers, n=192, paired flips vs the original prompt:

| Condition | Top-1 | Top-3 | Top-3 gained/lost vs original | p |
|---|---|---|---|---|
| Original (claim + speaker + date + country) | 0.292 | 0.391 | – | – |
| Paraphrased claim | 0.292 | 0.396 | +4/−3 | 1.0 |
| **Metadata removed** (claim only) | 0.281 | 0.401 | +5/−3 | 0.727 |
| **Names masked** (persons/places/orgs/events → placeholders) | 0.229 | 0.307 | +3/−19 | **0.0009** |

**Recognition.**

- The model self-reports recognising 65/200 claims.
- It names the correct fact-checker domain for 29/200, the pre-registered "likely recognised" flag.
- Its recalled verdict matches gold for 98/200, below the all-"false" label prior of 124/200.
- Top-3 accuracy: likely-recognised 0.379 (n=29) vs not 0.393 (n=163); self-reported recognised 0.381 (n=63).
- Retrieval (from `validation_heldout.json`): on the 140 not-recognised claims, D R@10 is 0.286 vs hybrid 0.257 (+9/−5, p=0.42). On the 27 recognised claims it is 0.333 vs 0.222 (+4/−1, p=0.38).
- Recognised claims are **not** predicted better.

**Dev probe status.** `raw_dev.jsonl` has 719/720 calls cached. One call failed with a 429 session limit, and no dev summary file was written. Dev probe numbers are therefore not reported.

**Limits of the probe.**

1. Masking removes information the task legitimately needs: the authority often *is* the named entity (0.917 → 0.50 top-3 on the 24 claims naming the gold publisher). The masking drop shows reliance on names; it does not separate memorisation from reasoning.
2. Recognition flags are self-report or a fact-checker-domain proxy. They cannot detect memorised knowledge of *which outlets covered* a story.
3. The target is all gold publishers, including news and fact-check pages, so accuracy is a lower bound on "authority" accuracy.
4. The predictor and the probe are the same model family, and no post-cutoff or non-Claude resolver was tested.
5. Subgroups are small (n=24–63).

### 11.5 Error analysis (read-only over the frozen rankings; `results/source_targeted/error_analysis_{heldout,dev}.{json,csv}`)

G = hybrid + targeted + LLM authority. "Authority correct" means a reachable gold doc comes from one of the predicted top-3 publishers.

| Category | Held-out (n=167 gold claims) | Dev (n=99) |
|---|---|---|
| **Authority correct** (reachable gold from a predicted publisher) | 56 | 37 |
| …G hits gold@10 | 31/56 (0.55) | 28/37 (0.76) |
| **…authority correct but retrieval fails** | **25** | 9 |
| ……the right-publisher gold doc never entered the fused pool | 22/25 | 8/9 |
| ……in the pool but ranked >10 | 3/25 | 1/9 |
| ……G top-10 filled by predicted-publisher docs (median count of 10) | 10 | 10 |
| **Authority wrong** (no predicted key matches any gold publisher) | **102** (plus 9 matching only empty gold) | 54 (+8) |
| …gold@10: hybrid / D / G | 30 / 26 / **10** | 16 / 14 / 7 |
| **Gold outside the ordinary hybrid top-100** | 55/167 | 28/99 |
| …in G top-100 after targeting (all 5 then hit @10) | 5 | 5 |
| …authority was correct for them | 21 | 8 |
| Pilot-primary outside hybrid top-100 | N/A (no labels) | 25/48; 9 brought in, all 9 hit @10 |
| **Secondary outranks primary** in G (claims with both reachable) | N/A (no labels) | 6 of 15 (primary first in 9) |
| **Multiple legitimate authorities** (LLM's own label) | 144 claims: authority correct 55, G 35 vs D 44 hits | 91: correct 41, G 30 vs D 27 |
| …single clear authority | 20: correct 10, G 6 vs D 5 | 7: correct 4, G 4 vs D 6 |
| …claims with ≥2 distinct reachable gold publishers | 85/167 | 44/99 |
| **Missing/empty gold** | 8 claims with no web gold; 25 with web gold that is all empty; 117/422 gold URLs empty | 1; 20; 64/226 |
| **G vs D discordant claims** | +10 / −18. In all 18 losses ≥1 targeted doc is in G's top-10 (mean 8.9/10); authority was correct in only 2 | +10 / −9 (mean 7.9/10 targeted in losses) |

**What the error analysis shows.**

1. **Wrong authority is the dominant failure, and targeting amplifies it.** On held-out, 61% of reachable-gold claims have no correct predicted publisher. On those, G hits gold@10 for 10 claims, against 30 for plain hybrid. Authority-first ordering plus a λ=1 prior fills the top-10 with the wrong publishers' pages: all 18 G-vs-D losses have targeted docs in the top-10. D, which only re-orders the hybrid pool, loses less (26).
2. **Right publisher, wrong document.** When the publisher is right, targeting still fails for 25 claims. In 22 of them the gold page from that publisher never enters the site-restricted top-10, yet the top-10 is fully occupied by that publisher's other pages.
3. **The pool-reach problem is barely addressed.** 55/167 claims have gold outside the hybrid top-100. Targeting brings in 5, even though authority was right for 21 of them.
4. **Plurality of authorities is the norm.** The LLM labels 72% of held-out claims "multiple legitimate authorities", and 85/167 have gold from ≥2 publishers. In that group G is below D (35 vs 44 hits). In the small single-authority group (n=20) G is level with D (6 vs 5). How candidate 1 vs candidates 2–3 split the targeted slots was not measured.
5. **Missing text** removes gold for 25 held-out claims entirely.
6. On dev, secondary gold still outranks primary in 6/15 claims that have both.
