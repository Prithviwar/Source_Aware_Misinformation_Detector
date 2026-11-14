# Pre-registration addendum: source-targeted retrieval (held-out test)

*Written 2026-09-30 09:30, after the design grid on the 120 **development** claims and **before** any held-out gold, held-out hybrid ranking or held-out score involving targeted retrieval was computed. It adds to `validation_preregistration.md` and changes nothing there. The frozen validation script (`validation_heldout.py`, SHA-256 `304984b6…dfbc5`) is unchanged.*

## Why this addendum

The development analysis showed that **31 of 48** pilot-primary documents lie outside the hybrid top-100, so no top-100 reranker can reach them. Source-targeted retrieval adds documents to the candidate pool *from the publishers the LLM predicts are authoritative*, instead of only re-ordering the relevance pool.

## Method (frozen)

Code: `experiments/source_targeted.py` (module) and `experiments/source_targeted_eval.py` (evaluation).

1. **Authority.** `primary_authority_candidates` = the frozen L+Wctx predictor's ranked top-3 publishers, each with its publisher keys (registered domain, or platform/handle). This is a list, not a single winner.
2. **Targeted query.** One query per candidate: `site:<key> <text>`. It is executed offline against the claim's AVeriTeC knowledge store:
   - **site filter:** keep docs whose publisher key (`cand_key`, as in the frozen validation) equals a candidate key;
   - **text:** BM25 over the whole claim corpus, restricted to the filtered docs;
   - **semantic:** the frozen dense claim-query score, restricted to the filtered docs.
3. **Targeted ranking.** Docs are ordered by authority rank first (candidate 1's docs, then 2, then 3). Within one authority they are ordered by RRF(k=60) of BM25 rank and dense rank.
4. **Fusion (method F).** The pool is hybrid top-100 ∪ targeted top-**M**, ranked by RRF of the two ranks.
5. **Authority rerank (method G).** `minmax(fused score) + λ·prior`, with λ = 1 and the same predicted-key prior as the frozen D.

**Frozen setting:** `text_mode = claim`, `order = authority`, `M = 10`, λ = 1.

### How it was chosen (development claims only)

18 configurations were run: text ∈ {claim, claim+entity, fact+entity} × order ∈ {rrf, authority} × M ∈ {10, 20, 50}. The selection rule was stated in code before running: maximise the dev value of (G gold R@10 + G pilot-primary R@10)/2, then prefer the smaller M, then the first listed. Four configurations tied at 0.458, all with authority-first order; the rule picked claim / authority / 10. Full grid: `results/source_targeted/devgrid.csv`.

- The dev criterion uses the **one-annotator pilot primary labels**, so the choice is tuned to them.
- Query-text variants hardly differ. The gain comes from the site filter plus authority order, not from query wording.

## Methods compared on the held-out set (all from the claim; gold used only for scoring)

| | Method | Candidate pool |
|---|---|---|
| A | hybrid | hybrid top-100 |
| B | hybrid + generic credibility (λ=1) | hybrid top-100 |
| C | hybrid + heuristic authority (`full` prior, λ=1) | hybrid top-100 |
| D | hybrid + LLM authority (frozen, λ=1) | hybrid top-100 |
| E | source-targeted only | targeted top-10 |
| F | hybrid + source-targeted | hybrid top-100 ∪ targeted top-10 |
| G | F + LLM authority rerank | same as F |
| ctrl | **size-matched control**: hybrid top-(100 + number of docs F adds) | same size as F |
| H | **ORACLE** (diagnostic, leaks by design) | same pipeline with gold-derived authority keys |

- C uses λ=1, not the development headline 0.25, so that B, C and D differ only in the prior.
- H on the held-out set uses the publishers of **all human gold URLs**, because there is no primary annotation there. It is an upper bound, never the proposed method.

## Endpoints

**Pre-registered family (exact McNemar, Holm across the 3 tests, paired bootstrap 95% CI):**

1. **Gold candidate coverage** (claim-level: ≥1 reachable gold doc in the pool): F vs the size-matched control. This asks whether targeted retrieval adds gold docs that simply going deeper in the hybrid list would not.
2. Gold R@10: G vs D.
3. Gold R@10: G vs A.

**Descriptive only:**

- R@1/3/5/20/50/100 and MRR@100.
- Document-level coverage and mean pool size.
- The same analysis on development claims (exploratory, since it was used for design).

**Primary-source recall on the held-out set is not measurable** until the human annotation (`heldout_annotator_template.csv`) is done. It is reported as N/A, not estimated.

## Hashes at freeze

- `source_targeted.py` SHA-256 `6ec3172da035e815b275224742f9bf0a64482b955748c5dfaafeab85dcbba223`
- `source_targeted_eval.py` SHA-256 `a686a075471b2fcb0ed5658a2fb372fc384d8f4f3437512e44f87fb386379e04`

## Addendum 2 (2026-09-30, after the frozen held-out run, before any held-out primary label exists)

The held-out primary endpoint is re-specified as follows. Rankings, methods, the configuration and the sample are unchanged.

- **Source of labels.** A blind, claim-level human annotation (`data/annotations/heldout_primary_package/`, 192 claims, same IDs and order as `heldout_annotator_claim_authority_template.csv`). It replaces the 422-row URL sheet, which exposes gold URLs, snippets and QA to the annotator.
- **Primary docs of a claim.** Reachable human-gold docs whose `cand_key` equals a key of an annotator-listed authority. Claims marked `no_identifiable_primary` or `unclear`, or with no such doc, are excluded and counted.
- **Metrics.** PrimR@1/3/5/10/20, PrimMRR@100, and primary claim coverage of the pool before re-ranking, for A–G, the size-matched control and the ORACLE. The ORACLE is a diagnostic only; its coverage is N/A because its pool was not saved.
- **Tests.** Exact McNemar and paired bootstrap, Holm across 4 tests:
  - PrimR@10 G vs A
  - PrimR@10 G vs D
  - PrimR@10 D vs A
  - primary coverage F vs size-matched control
- **Sensitivity.** The same analysis excluding `confidence = low`.
- **Frozen hashes (SHA-256).**
  - Scorer `experiments/score_heldout_primary.py`: `114bf0cac69cce3d43f718360852568199f5af4abb660a85cf924a4f7d046ad2`
  - Blank sheet: `cf063d5ebbb25c3c853f7bc1b26a3d19b621482b797e3592ce865d7b8637259c`
  - Frozen rankings `results/source_targeted/rankings_heldout.jsonl.gz`: `9105a5da66a287de70fdc6e7e9b5135200589d58c542d61787e7ed883cb66558`
- **Scorer check.** `score_heldout_primary.py selftest` reproduces the published held-out gold table exactly from the frozen files.

## Addendum 3 (2026-10-02): AI-labelled primary-evidence recall replaces the unexecuted human endpoint

*Written before any AI label for a held-out claim exists. The rankings, methods, configuration, sample, scorer (`114bf0ca…`), metrics and tests are unchanged.*

**1. Deviation.**
- The human, blind, claim-level primary-source annotation specified in Addendum 2 was **not carried out**; no independent human annotation was obtained.
- On 2026-10-02 the project owner decided to replace it with AI-generated labels. The Addendum 2 human endpoint is therefore recorded as **pre-registered, not executed**.
- This is also a deviation from `validation_preregistration.md` ("no new model-made pilot labels will be created"); see the deviation note there.

**2. Main AI endpoint: AI-labelled primary-evidence recall.** Metrics: AI-PrimR@1/3/5/10/20, AI-PrimMRR@100, and AI-primary claim coverage of the pool.
- **Labels.** One AI role label (`primary` / `secondary` / `derived` / `unclear`) per held-out gold evidence URL: the 422 rows of `data/annotations/heldout_annotator_template.csv`. The scheme is the per-URL one in `second_annotator_guidelines.md`, also used for the development pilot labels. Prompt: `ai/AI_EVIDENCE_PROMPT.md`.
- **AI-primary documents of claim c.** The reachable human-gold documents of c whose publisher key (`cand_key`) equals the key of at least one gold URL of c that the AI labelled `primary`. Another reachable gold document from the same publisher therefore also counts.
- **Conversion.** `experiments/score_ai_primary.py convert` produces the frozen scorer's 192-row sheet:
  - claims with no AI-primary publisher become `no_identifiable_primary` (excluded and counted);
  - row confidence is the lowest confidence among the claim's `primary` labels;
  - keys that the sheet format cannot express are excluded and counted. The `selftest` found 2 of 297 gold keys: a bare `twitter.com` and a malformed URL.
- **Scoring.** The frozen `score_heldout_primary.py` `score()` runs unchanged; only its output directory is redirected to `results/heldout_ai_primary/`.
- **Tests (unchanged from Addendum 2).** Exact McNemar and paired bootstrap 95% CI, Holm across 4:
  - AI-PrimR@10 G vs A;
  - AI-PrimR@10 G vs D;
  - AI-PrimR@10 D vs A;
  - AI-primary coverage F vs the size-matched control.

  Sensitivity: the same analysis excluding rows with `confidence = low`.
- **Interpretation rule (fixed now).** This endpoint **cannot change** the validation decision (outcome B in `validation_preregistration.md`). Recall of the human AVeriTeC gold evidence remains the human-grounded result.

**3. Secondary, descriptive only: AI-named authority (claim-level).**
- A blind claim-level AI annotation of the 192-claim package: claim, speaker, date and country, plus `ANNOTATION_GUIDE.md`. Prompt: `ai/AI_CLAIM_PROMPT.md`.
- The annotator is the same model as the authority predictor and gets the same inputs, so it is circular for D.
- It is reported only as (a) overlap with the predictor's top-3 keys and (b) a descriptive table with no tests. It is **never** used to validate D.

**4. Annotator and isolation.**
- **Model:** Claude Opus 5.5 (`claude-opus-5-5`), **the same model as the L+Wctx authority predictor used by D and G.**
- **Call:** `claude -p` with no tools, no MCP and no session persistence, in a new empty temporary directory, one call per item. No web access and no lookups.
- **Never shown:** predictions, rankings, method names, results, the verdict label or justification, the fact-check article, other gold URLs of the claim, or any other annotation.
- **Not produced by the orchestrating session.**
- **Outputs:** `data/annotations/heldout_primary_package/ai/MODEL_GENERATED_*`.
- Full protocol: `data/annotations/heldout_primary_package/AI_ANNOTATION_PROTOCOL.md`.

**5. Circularity diagnostics (pre-specified, descriptive).**
1. The share of AI-primary gold URLs whose publisher is in the predictor's top-3, against the same share for the other gold URLs.
2. Claim-level any-key overlap and authority-1 overlap between the AI-named authorities and the predictor's top-3.

Every write-up states that annotator and predictor are the same model, and that their shared notion of "first-hand" cannot be separated without an independent annotator.

**6. Cross-family sensitivity (optional; AI–AI agreement only).**
- **Subset:** 40 claims (seed 2028) from the 177 non-pilot claims, with all their gold URLs.
- **Labeller:** a different model family, using the same frozen evidence prompt.
- **Reported:** % agreement and Cohen's κ (4 labels; primary vs not), plus descriptive AI-PrimR@10 on the subset under both label sets.
- **No tests.** It is never described as validation. If it is not run, it is reported as not run.

**7. Pilot and freeze.**
- **Pilot:** the 34 gold URLs of the 15 pilot claims labelled twice (runs A and B), and the 15 claims labelled at claim level once. Reviewed under the AI addendum of `pilot/PILOT_REVIEW_CRITERIA.md`. Pilot labels are never scored.
- **Freeze:** after the review, the SHA-256 of `AI_EVIDENCE_PROMPT.md`, `AI_CLAIM_PROMPT.md`, `ANNOTATION_GUIDE.md`, `ai_annotate.py` and `score_ai_primary.py` is recorded below and in `ai/FROZEN_HASHES.json`. The runner refuses held-out labelling if any of these files differs.

**Freeze record.** *(Filled in after the pilot review, before any held-out label.)*

**8. Terminology (binding).**
- **Use:** "AI-labelled primary-evidence recall", "AI-named authority", "MODEL_GENERATED", "AI–AI agreement".
- **Never use:** human-annotated, human-validated, ground truth, expert annotation, independent human labels, reliability.

**Pre-pilot hash record (2026-10-02, before any AI label exists).** These are not the freeze gate. The freeze record above is filled in after the pilot review, and the runner checks against `ai/FROZEN_HASHES.json`. Copy: `ai/PRE_PILOT_HASHES.json`.

- `AI_EVIDENCE_PROMPT.md`: `417a609c1fa230c2f81293737417c99ebfb8a455e1806cc2df0aaeeda9efb6b0`
- `AI_CLAIM_PROMPT.md`: `5f4a7b0f2d8918ddfde20953984335cbccd43886b42eaf84d819ba73fa7227d2`
- `ANNOTATION_GUIDE.md`: `57efc6e49894411d982245913f5ff6572df33f2e6c2d9434b4877e486cfa0e71`
- `ai_annotate.py`: `5a51a84755bcc144593169f880b06577157aaea41bbe7f13acbdcb3dec3f1e67`
- `score_ai_primary.py`: `860b31a79953c3cef61078fbefee2867212bb04672c460dbf0daf406fd00662d`

**Pilot round 1 review and prompt revision (2026-10-02).**

- **Round 1:** evidence-level runs A and B (34 URLs each) and claim-level run A (15 claims). All outputs are MODEL_GENERATED.
- **Stability:** A/B agreement 97.1%, 4-way κ 0.954, primary-vs-not κ 0.939.
- **Criterion 6 fired twice.**
  - (i) Pages were judged primary relative to the fact-checkers' sub-question rather than the claim.
  - (ii) Copies of documents re-hosted by another organisation were treated inconsistently.
- **Decision by the project owner.** The operational definition for this endpoint is the **whole-claim** fact at issue, because the research question concerns claim-specific authority. Two sentences were added to `ai/AI_EVIDENCE_PROMPT.md` (verbatim in `CHANGELOG.md`):
  - "The fact at issue is the claim's central fact. A page that is first-hand only for background or definitions is labelled accordingly, not as primary for the claim."
  - The re-hosted-copies rule: a copy hosted by a different organisation is derived, even if that organisation is official; a document on its producer's own infrastructure is judged as that producer.
- **Hashes:** evidence prompt SHA-256 `417a609c…` → `87eae830…`. Nothing else changed.
- **Consequence for §2:** the AI evidence prompt now adds these two clarifications to the per-URL scheme of `second_annotator_guidelines.md`; it is no longer a verbatim copy.
- **Round 2** (final permitted round): evidence runs A and B only. If any criterion still fires, the protocol is not frozen and the held-out run stays locked.

**Pilot round 2 outcome and FREEZE (2026-10-02).** This is an AI-generated (MODEL_GENERATED, Claude Opus 5.5) annotation protocol. It is not human validation and not human ground truth.

- **Round 2:** evidence-level runs A and B on the 34 pilot gold URLs, using the revised prompt (`87eae830…`). 34/34 parsed in each run, no retries, `num_turns` = 1 throughout. The claim-level pilot was not re-run.
- **Stability (criterion 9): PASSED the predefined threshold.**
  - Primary-vs-not agreement **100%**, κ **1.000**.
  - 4-way agreement **94.1%**, 4-way κ **0.906** (thresholds: ≥ 90% primary-vs-not agreement, κ ≥ 0.70).
- **Criteria 1–5, 7 and 9 did not fire; criterion 8 does not apply.**
- **Criterion 6 remained triggered.** A recurring derived-vs-secondary ambiguity for reference-style pages appeared in items 79 (a Library of Congress glossary) and 205 (Biography.com). These are the only two A/B disagreements. **This ambiguity does not affect the primary-vs-not endpoint**: neither item is labelled primary in either run, and primary-vs-not agreement is 100%.
- **Limitation (recorded, no further prompt change).** Item 148 (a global UN SDG progress page, for a claim about Nigeria) is labelled primary in both runs, although its notes describe it as background. This is an isolated ambiguity in applying the background/definition rule.
- **Decision.** Under the AI addendum of `pilot/PILOT_REVIEW_CRITERIA.md` ("at most 2 rounds; after that, freeze and report which triggers remained"), and confirmed by the project owner, the protocol is **frozen without a further prompt revision**.
- **Pilot outputs.** All round-1 and round-2 pilot outputs are preserved in `ai/`. Pilot labels are never scored.

**Freeze record** (`ai/FROZEN_HASHES.json`, frozen at 2026-10-02T22:36:45):

- `AI_EVIDENCE_PROMPT.md`: `87eae8309006267df275f5f1249f1d5824a8ce8f841ba0f7c081028f1b1b8a3f`
- `AI_CLAIM_PROMPT.md`: `5f4a7b0f2d8918ddfde20953984335cbccd43886b42eaf84d819ba73fa7227d2`
- `ANNOTATION_GUIDE.md`: `57efc6e49894411d982245913f5ff6572df33f2e6c2d9434b4877e486cfa0e71`
- `ai_annotate.py`: `5a51a84755bcc144593169f880b06577157aaea41bbe7f13acbdcb3dec3f1e67`
- `score_ai_primary.py`: `860b31a79953c3cef61078fbefee2867212bb04672c460dbf0daf406fd00662d`

The runner refuses held-out labelling if any of these files differs. The cross-family (ChatGPT) input was regenerated from the frozen evidence prompt. The round-1-prompt export is kept, renamed `..._SUPERSEDED_round1prompt.csv`. The 192-claim held-out run is unlocked but **not started**.
