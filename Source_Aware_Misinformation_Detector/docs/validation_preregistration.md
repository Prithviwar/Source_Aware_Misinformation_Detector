# Validation pre-registration: claim-specific authority prediction → retrieval

*Written 2026-09-29, **before** the held-out sample was built, before any held-out retrieval, prediction or evaluation was run. The analysis script is `experiments/validation_heldout.py`; its SHA-256 at freeze time is recorded at the bottom of this file. Any later change to the script is listed in the "Deviations" section of `experiment_results.md` §11.*

## Why a fresh sample instead of splitting the 120 development claims

All 120 development claims were visible when weight λ=1 was observed to perform best (27 cells inspected). Any 80/40 split of those claims therefore gives a "held-out" part that already influenced the weight choice. The AVeriTeC dev set has 500 claims; **380 have never been touched** by any script, prompt or analysis in this project. A fresh sample from those 380 is a genuinely held-out test.

## Held-out sample (fixed)

- Population: AVeriTeC dev claims whose index is **not** in `data/processed/averitec_sample.jsonl`.
- Size: **200 claims**, stratified by label **proportionally to the remaining pool**: 124 Refuted, 48 Supported, 15 Conflicting/Cherrypicking, 13 Not Enough Evidence. Seed 2027.
- Why 200 and not all 380: the CPU dense-retrieval budget is ~28 s per claim (≈1.6 h for 200). On development data the key comparison produced ~20% discordant claims; with ~160 reachable-gold claims that gives ~32 discordant pairs, enough for an exact McNemar test to detect the development-sized effect. The remaining 180 claims stay untouched for a later replication.
- Output: `data/processed/averitec_heldout.jsonl`. Knowledge-store extracts go to the same `data/raw/averitec/ks_sample/` (files are keyed by claim id).

## Frozen method (no changes allowed after this point)

| Component | Frozen setting |
|---|---|
| Relevance retrieval | BM25 (`bm25s`), dense (`all-MiniLM-L6-v2`, 128 tok, first 1,000 chars), hybrid = RRF k=60. Query = claim text. Code unchanged from `baseline_retrieval.py`. |
| Authority predictor | Condition **L+Wctx** of `authority_resolution.py`: same SYSTEM and USER prompts, model `claude-opus-5-5`, `claude -p` with no tools, fresh context, empty working directory. Inputs: claim text, speaker, claim date, country ISO code, and Wikidata facts for spaCy entities of claim + speaker. **Prompt is not edited.** One call per claim. |
| Authority prior | prior(url) = 1 if the candidate's publisher key (registered domain, or platform/handle for social URLs) is in the claim's predicted top-3 publisher keys, else 0. |
| **Authority weight** | **λ = 1.0, fixed.** No other weight is evaluated on the held-out set. |
| Candidate pool | top-100 of the hybrid ranking (as in the development result being validated). |
| Scoring | `minmax(hybrid score within pool) + λ·prior`, stable sort. |
| Generic credibility comparator | `authority_retrieval.generic_prior` (unchanged), same λ = 1.0, same top-100 pool. |

## Evaluation populations

- **Gold recall (A):** held-out claims with ≥1 human AVeriTeC gold web URL whose knowledge-store text is non-empty ("reachable gold"). The count is reported; claims without reachable gold are excluded, not scored as misses.
- **Primary recall (B):** **not available on the held-out set.** There is no source-role annotation for the held-out gold URLs, and no new model-made pilot labels will be created. Primary recall is reported for the development set only (pilot labels, n=48). A human-annotation template for the held-out gold URLs is prepared so that it can be measured later.
- **Authority-prediction accuracy (C):** held-out claims with ≥1 human gold web URL. The target is the set of publisher keys of **all** human gold evidence URLs of the claim (no role labels). Levels:
  - top-1 match;
  - top-3 match;
  - "attributed" (no key match, but a predicted publisher's name occurs in the text of a reachable gold document);
  - no match.
  This is a *lower bound* for authority accuracy, because human gold also contains news and fact-check pages that the predictor is instructed not to name.

## Hypotheses and tests

**Primary endpoint (one test, α = 0.05, two-sided):**
- Gold R@10, hybrid + predicted authority (λ=1, top-100) vs hybrid.
- H0: the two methods have equal per-claim hit probability.
- Test: exact McNemar on per-claim hit@10.
- Also reported: difference in R@10 with a paired bootstrap 95% percentile CI (10,000 resamples, seed 2026).

**Secondary family (Holm-corrected across these 5 tests):**
1. R@5, predicted vs hybrid.
2. R@20, predicted vs hybrid.
3. R@5, predicted vs hybrid + generic (λ=1).
4. R@10, predicted vs hybrid + generic (λ=1).
5. R@20, predicted vs hybrid + generic (λ=1).

**Descriptive only (no tests):**
- BM25, dense and hybrid + generic recall.
- Per-claim rank wins/losses/ties: best gold rank within top-100, with "absent" treated as equal ranks.
- Candidate-pool coverage of predicted publishers at hybrid top-50/100/200/all.
- Authority-prediction accuracy.
- The memorisation-probe subset analysis.

## Memorisation probe (fixed before running)

- One extra call per held-out claim, same model, no tools. The model receives only claim, speaker and date, and is asked whether it recognises the claim as fact-checked, which organisation fact-checked it (name + domain), and the verdict.
- A claim is **"likely recognised"** if the named fact-checker's registered domain equals the registered domain of the claim's `fact_checking_article` URL.
- The primary-endpoint comparison is re-computed (descriptively, with McNemar p reported as exploratory) on the **not-recognised** subset.
- This is a proxy. Failing the probe does not prove the claim is absent from training data.

## Decision rule (fixed)

- **A (strong enough to continue):** primary endpoint significant (p < 0.05) with a positive CI, **and** predicted > generic on R@10 after Holm correction.
- **B (promising, not validated):** positive direction on the primary endpoint but not meeting A, e.g. p ≥ 0.05, or it beats hybrid but not generic, or it only holds on the recognised subset.
- **C (not supported):** zero or negative difference on the primary endpoint.

## Script hash at freeze

`experiments/validation_heldout.py` SHA-256 = `304984b62945def7ecbfeb49a7c5c4e4ff68b4d13f080e4bed9465a6235dfbc5` (frozen 2026-09-29 22:10, after a pre-freeze smoke test on the development claims only, which found and fixed one bug: duplicate knowledge-store URLs with an empty later copy were treated as unreachable. No held-out data had been retrieved or scored at that point.)

Imported code, SHA-256 at freeze: `authority_resolution.py` 58714a83…0e97, `authority_retrieval.py` ac4c2e80…9312, `baseline_retrieval.py` 2730f0b3…bd9b.

## Deviation (2026-10-02; after the frozen held-out run, before any held-out primary label)

**What changes.** Under "Evaluation populations", item **Primary recall (B)**, this document says that for the held-out set *"no new model-made pilot labels will be created"*. That commitment is **withdrawn**.
- No independent human annotation of the held-out gold evidence was obtained.
- On 2026-10-02 the project owner decided to measure held-out primary-evidence recall with **AI-generated** labels instead.
- The new endpoint is called **"AI-labelled primary-evidence recall"**. It is defined, frozen and constrained in `source_targeted_preregistration.md` Addendum 3.
- The annotator is Claude Opus 5.5, **the same model as the authority predictor frozen in this document**.

**What does not change.** Everything else in this document stays as written:
- the sample;
- the frozen method;
- the primary endpoint (gold R@10, D vs A);
- the secondary family;
- the memorisation probe;
- the decision rule and the reported **outcome B**.

**The AI-labelled endpoint cannot change outcome B.**
