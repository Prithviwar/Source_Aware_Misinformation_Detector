# Real-data collection and training plan (DRAFT, NOT APPROVED)

**Written 2026-11-02.** This is a plan only. **No real data has been collected, no labels exist, no model has been trained on real data.** The 68/68 passing tests and the smoke run in `outputs/synthetic_smoke/` show that the *code mechanics* work on synthetic fixtures. They say **nothing** about real-world performance.

Nothing here changes `config/config.template.json`, the schemas, the role rules or the code. Items marked **[DECISION]** must be settled (and, where noted, mentor-approved) and recorded in `docs/DECISIONS.md` before the stage they block. Items marked **[PROPOSED]** are this plan's suggestions.

This project stays independent of `Source_Aware_Misinformation_Detector` (see §14 for the one future interface).

---

## 1. What the model predicts (from the repository)

For a **claim–publisher pair**, `p_first_hand = P(first-hand authority | claim, publisher, eligible features)`: the probability that this publisher has first-hand standing to establish the claim's **central factual proposition**.

It does **not** predict: whether the claim is true; whether a page is relevant or supportive; whether the publisher is generally reliable; how popular or often-retrieved the publisher is (`README.md`; `schemas/feature_schema.json` `prohibited_keys`).

## 2. What a claim–publisher pair is

One record = one claim (text, date, speaker, location) × one candidate publisher (an organisation, account or person resolved to a stable `publisher_id`, optionally a `publisher_family_id` for corporate groups). Every pair has the ten features in `schemas/feature_schema.json` (or the sentinels `UNKNOWN` / `NOT_COMPUTED`) and, for training, one human label per `schemas/label_schema.json`.

## 3. First-hand authority, operationally

A publisher is **FIRST_HAND_AUTHORITY** for a claim if it holds one of the positive **bases** for the claim's central proposition:

| Basis | Operational test | Example |
|---|---|---|
| `INSTITUTIONAL_ACT` | The publisher performed the act the claim is about (issued the policy, passed the law, made the ruling, took the action) | A ministry for a claim about its own regulation |
| `OFFICIAL_RECORD` | The publisher is the **designated** keeper of the record or statistic (O2: designation, not just "an official body") | The national statistics office for the unemployment rate it compiles |
| `ORIGINAL_RESEARCH` | The publisher produced the study or dataset the claim relies on | The journal or research group for a reported finding |
| `DIRECT_OBSERVATION` | The publisher directly witnessed the event (O1; **mentor confirmation required**) | A news outlet whose reporters were on the scene |

Rules already decided by the owner (mentor approval **not** recorded): O2 designated record-keeper only; O3 for quotations, judge the **content** of the quote, not the act of saying it; O4 an organisation can be first-hand about itself, always flagged `INTERESTED_PARTY`.

**NOT_FIRST_HAND_AUTHORITY** reasons: `REPORTS_OTHERS_ACT`, `EXPERT_COMMENTARY`, `REPUBLISHER_OR_AGGREGATOR`, `UNRELATED`, `OTHER`.
**CANNOT_JUDGE** reasons: `UNKNOWN_ENTITY`, `AMBIGUOUS_PROPOSITION`, `ROLE_CHANGED`, `INSUFFICIENT_EVIDENCE`.

---

## 4. Dataset schema

Already defined and enforced by code; summarised here.

| Field | Source | Model input? |
|---|---|---|
| `pair_id`, `claim_id`, `claim_group_id` | construction | No (IDs and grouping) |
| `claim_text`, claim date, speaker, location | claim source | Text is not a model feature in the current LR design; used by extractors |
| `publisher_id`, `publisher_family_id`, `publisher_resolved` | publisher resolution | Grouping / eligibility |
| 10 features: `action_type`, `claim_scope`, `claim_topic`, `publisher_type`, `publisher_jurisdiction_level`, `actor_relation`, `speaker_relation`, `jurisdiction_match`, `remit_match`, `active_at_claim_date` | extractors (§7) | **Yes** |
| `candidate_origin` ∈ {`retrieval`, `curated`} **[PROPOSED, O5; needs a small code change]** | construction | **Never** a feature; used for bias reporting |
| `label`: `final`, `basis`, `not_fha_reason`, `cannot_judge_reason`, `flags`, per-annotator records, `confidence` | human annotation | Target |
| `is_synthetic` | construction | Must be `false` for real runs |

---

## 5. Data sources and collection methodology

### 5.1 Claims **[PROPOSED; DECISION]**

**Recommended primary source: AVeriTeC *train* split (3,068 claims, CC BY-NC 4.0).**
- *Why:* decontextualised real-world claims with speaker, date and country, which match the features this model needs. It is research-licensed, and the research group already knows the data.
- **Exclusion:** all **500 AVeriTeC dev claims** are excluded (not only the reserved 180). The dev split is the source-aware project's development and evaluation material. Keeping it out means this model can later be used as a feature there without leakage (see §14). This extends the manifest's existing `excluded_sources` entry.
- AVeriTeC verdict labels, justifications and QA evidence are **not read** for this project (prohibited keys). Claim text and metadata only.

*Alternatives for the mentor:* ClaimReview-tagged fact-checks (wider topics; licence varies by publisher), or a hand-collected set from official press releases (cleaner, but costly and biased toward official sources).

### 5.2 Candidate publishers (O5: retrieval + curated) **[DECISION: exact protocol]**

Per claim, proposed:
1. **Retrieval origin.** From the claim's AVeriTeC train URL list (`data_store/urls/train_urls.zip`: URLs only, no 62 GB knowledge store needed), take the distinct publisher keys. **Ignore the `type` and `query` columns entirely** (they mark gold documents and gold questions). Sample up to *n_r* keys (proposed 6) with a fixed seed, **blind to order and type**. *Caveat to report:* the URL lists were partly generated from gold-derived queries, so they are enriched with relevant publishers.
2. **Curated origin.** A curator who has **not** seen the retrieval candidates writes down up to 2 publishers they believe could be first-hand (e.g. the agency named in the claim). Recorded as `curated`.
3. **Hard-negative origin [PROPOSED, links to the hard-negative decision]:** up to 1 publisher of the same `publisher_type` as a likely authority but a different jurisdiction or remit (e.g. another country's statistics office). Recorded separately so it can be analysed or dropped.

All origins are labelled by the same blind annotation process. **Positive rates and model metrics are reported by origin** (curated candidates are expected to be easier positives; this is a selection bias that must be measured, not hidden).

### 5.3 Publisher resolution

Map each key to a `publisher_id` (organisation-level), and optionally to a `publisher_family_id` (corporate group; needed if `merge_corporate_families=true`). Use Wikidata QIDs where available (snapshot date recorded); unresolved publishers get `publisher_resolved=false` and are scored `LIMITED`/`INELIGIBLE` per the schema rules.

---

## 6. Inclusion and exclusion criteria **[PROPOSED]**

**Claims: include** if the claim states a checkable factual proposition with an identifiable subject; English text; claim date present.
**Claims: exclude** if in any AVeriTeC dev claim (all 500); pure opinion/prediction with no factual proposition; satire-identification claims where the only question is "is this satire?"; near-duplicates of an already-included claim (grouped, not dropped, if they're kept).

**Pairs: include** each sampled candidate. **Exclude** candidates that are search pages, URL shorteners, archives or file hosts (`web.archive.org`, `bit.ly`, generic CDN domains), since they are not publishers. Social-media *platform* domains are excluded, but **accounts** on them (e.g. `twitter.com/<handle>`) are valid publishers.

---

## 7. Feature availability **[DECISION: `available_features`]**

Features must come from **extractors that never see the label** (and never from the annotators who label, unless as the separate, validation-only annotator-feature diagnostic).

| Feature | Proposed extractor | Dated source to record |
|---|---|---|
| `publisher_type`, `publisher_jurisdiction_level` | Wikidata P31/P17/P131/P1001 → frozen `publisher_type_map`; manual coding of unmapped publishers by a person not labelling FHA | Wikidata snapshot date |
| `action_type`, `claim_scope`, `claim_topic` | Rule/keyword coder or a separate pre-coder; O3 content rule applied to quotes | Coder version |
| `actor_relation`, `speaker_relation` | Entity linking of the claim's actor/speaker vs the publisher's QID (same/parent/subsidiary via P749/P355) | Wikidata snapshot |
| `jurisdiction_match`, `remit_match` | Claim location vs publisher jurisdiction; frozen `topic_remit_map` | Map version |
| `active_at_claim_date` | Wikidata inception/dissolution dates vs claim date | Snapshot |

Whether an LLM may be used as an *extractor* (not as an authority predictor, which is prohibited) is a **[DECISION]**. If allowed, its prompt and version are frozen before labels exist.

---

## 8. Annotation guidelines (outline for the annotation manual) **[PROPOSED]**

Annotators see: the claim text, date, location, speaker, and the publisher's identity (name, website, Wikidata description). **Not shown:** AVeriTeC verdict, justification, gold evidence, candidate origin, any model output, retrieval rank.

Decision procedure per pair:
1. **State the central factual proposition** in one sentence (stored for audit only; prohibited as a feature).
2. **Classify the proposition's action type**, applying O3 (quotes judged by content).
3. **Ask: did this publisher perform the act / keep the designated record / produce the research / directly observe the event, for *this* proposition, in *this* jurisdiction and time?**
   - Yes → `FIRST_HAND_AUTHORITY` + basis (+ `INTERESTED_PARTY` if it is about itself; `PARTIAL_ASPECT` if it covers only part of the proposition).
   - No → `NOT_FIRST_HAND_AUTHORITY` + reason.
   - Can't tell after a bounded check (proposed ≤ 5 minutes, using the publisher's own site and Wikidata) → `CANNOT_JUDGE` + reason.
4. **Designated record-keeper (O2):** accept designation only from a citable source (statute, the statistics office's own release calendar or methodology page, official open-data portal); record the URL. **[DECISION: the mentor approves this procedure]**
5. Flag `CLAIM_FAMILIAR` if the annotator already knows how this claim was fact-checked.
6. Confidence 1–5.

The manual includes 10–15 worked examples using **invented** publishers, covering each basis, each negative reason, quotes, self-reports and role changes.

---

## 9. Annotation quality and inter-annotator agreement

- **Pilot (before the main collection):** ~40 claims (≈ 300 pairs), **two independent annotators**, then adjudication. The pilot is used only to refine the manual and is **not** used for training or test. It is discarded or kept as a separate "pilot" set.
- **Agreement measures:** Cohen's κ on `final` (3-way, and binary FHA vs not-FHA); Krippendorff's α if more than two annotators or missing labels; agreement on `basis` among agreed positives; per-action-type breakdown; confusion between annotators.
- **Pass rule [DECISION: `min_annotator_agreement`]:** must be fixed **before** the pilot. Common conventions treat κ ≥ 0.6 as "substantial" and κ ≥ 0.8 as "almost perfect". This is offered as context, not decided here. If the pilot fails, revise the manual and re-pilot on new claims.
- **Main collection:** double annotation on a random ≥ 20% (proposed), single on the rest; agreement reported on the double-annotated part; disagreements adjudicated; unresolved → `final = null` (never a target).
- **Annotators:** human only; AI-generated labels are invalid under `label_schema.json`. Who the second annotator is (peer, mentor, paid) is a resource **[DECISION]**.

---

## 10. Sampling strategy and sizing **[PROPOSED; sizing DECISION]**

- **Claims:** stratified random sample from eligible train claims, stratified by AVeriTeC `claim_types` and by country (US vs non-US) for coverage. Used for sampling only, never as features. Fixed seed.
- **Size:** provisional target **300–400 claims × ~7–9 candidates ≈ 2,000–3,500 pairs**, to be confirmed after the pilot gives (a) the positive rate and (b) the pair-pruning loss of the publisher-disjoint split. The synthetic run lost **57% of pairs at hold-out fractions of 0.5**, so either collect more or lower `test_unit_fraction`/`val_unit_fraction` **[DECISION]**.
- **Effort (rough):** ~1–2 min per pair → ~50–100 h for one annotator on 3,000 pairs, plus ~20% for double annotation and adjudication.

## 11. Train / validation / test split and leakage prevention

Already implemented in `src/fha/split.py`; the plan adopts it:
- **Publisher-disjoint** (and family-disjoint if merging is chosen): test publishers never appear in training. This is the primary generalisation test (O6).
- **Claim-group-disjoint:** a claim and its near-duplicates (token Jaccard ≥ 0.8 + explicit `claim_group_id`) sit in one split only.
- Proportions 60/20/20 (config), with `val_seen`/`test_seen` and `val_unseen`/`test_unseen` subsets.
- **Hub publishers** (appear with many claims) are capped by `hub_max_claim_share` **[DECISION]**.
- **Temporal split:** only if `temporal_split_required=true` **[DECISION]**; code not implemented.
- **Test is opened once** (lock file). **Seen-publisher diagnostic on validation** before the test opens (O6 correction in DECISIONS.md §0.1; small code change pending).
- **Other leakage blocks:** prohibited keys rejected at load; features from extractors frozen before labelling; role rules frozen and hashed **before any label is seen**; `candidate_origin` never a feature.

## 12. Models

**Baselines (already implemented, synthetic-verified):**
1. `role_rules`: hand-written tiers (**must be approved and frozen before labels exist**).
2. `type_prior`: smoothed P(FHA | publisher_type).
3. `publisher_only_lr`: L2 logistic regression on publisher features.

**Proposed final model:** 4. `claim_conditioned_lr`: the same learner plus claim and claim×publisher features (one interaction `action_type × publisher_type`).

**Why logistic regression is the right final model here:** a few thousand pairs, ten categorical features and a research question about *which relations matter*. LR is well-calibrated, interpretable (coefficients map onto the authority definition) and hard to overfit. A transformer cross-encoder over (claim text, publisher description) is a possible **exploratory** follow-up, but only after the primary analysis and only on the same splits.

## 13. Training procedure, evaluation, error analysis

- **Training:** grouped, publisher-disjoint inner CV over `C ∈ {0.01, 0.1, 1, 10}`, `min_count ∈ {1, 3, 5}` by log loss; ties go to the simpler model; Platt recalibration on validation only if outside `calibration_acceptable` **[DECISION]**; `CANNOT_JUDGE` handled per `cannot_judge_policy` (proposed: exclude, with the two sensitivity runs) **[DECISION]**.
- **Primary metric:** AUPRC on **unseen-publisher** test pairs. **Primary comparison:** `claim_conditioned_lr` − `publisher_only_lr`, two-way (claim × publisher) bootstrap interval; outcome class needs `delta_min_auprc` fixed in advance **[DECISION]**.
- **Secondary:** AUROC, Brier, log loss, calibration slope/intercept, reliability table, NDCG@k and hit@k per claim, within-publisher AUROC, metrics by publisher type and action type, seen vs unseen, by `candidate_origin`, with/without `DIRECT_OBSERVATION` positives (O1 sensitivity).
- **Controls:** shuffled-pairing control (already implemented): a model that does not beat it is not using the claim.
- **Error analysis:** false positives by publisher type (e.g. news outlets wrongly rated first-hand), false negatives by basis, `INTERESTED_PARTY` pairs, `LIMITED`-information pairs, hard negatives.

## 14. Interface with the source-aware project (future, optional)

The first-hand authority model could later provide an authority feature to the source-aware verdict classifier (`Source_Aware_Misinformation_Detector/docs/proposals/verdict_classifier_training_proposal_DRAFT.md`). That is only safe if:
- no AVeriTeC dev claim (500) is in this project's data (§5.1);
- scores for any claim this project *trained* on are produced out-of-fold (cross-fitting) before they are used as features elsewhere;
- this project never reads source-aware frozen artifacts, reserved claims, gold labels, probes or scoring materials (already in the manifest's `excluded_sources`).

## 15. Compute

All modelling is CPU-only scikit-learn/numpy and runs in minutes on the current laptop. The real costs are **human annotation time** and **Wikidata extraction** (network, cached, snapshot-dated). Disk need is small (< 1 GB), but C: currently has ~2.1 GB free.

## 16. Reproducibility and documentation

Frozen before labelling and recorded in `docs/DATA_MANIFEST.json`: feature schema, label schema, `publisher_type_map`, `topic_taxonomy`, `topic_remit_map`, `role_rules` (hashes); KB snapshot dates; guideline version; annotator IDs (pseudonymous); agreement statistics; usage rights. Apply the `.gitattributes` LF policy (DECISIONS.md §1 item 8) **before** any hash is recorded. The model bundle stores its schema hash and refuses to load on mismatch (already implemented).

---

## 17. Ordered steps and what each needs

| # | Step | Needs |
|---|---|---|
| F0 | Mentor meeting: confirm O1–O4; answer DECISIONS.md §5 questions; settle the 16 null config decisions | **Mentor approval** |
| F1 | Record decisions + approvals (add approval-tracking to the guard); apply `.gitattributes`; O6 validation diagnostic code; `candidate_origin` field | Owner (code changes) |
| F2 | Write the annotation manual; approve and freeze `role_rules` | Owner drafts, **mentor approves** |
| F3 | Download AVeriTeC `train.json` + `train_urls.zip`; build claim sample; candidate generation | **Authorisation to start data collection** (network) |
| F4 | Feature extraction (Wikidata snapshot, coders); freeze extractor outputs | Owner |
| F5 | Pilot annotation (two annotators); agreement vs pre-set threshold | Second annotator |
| F6 | Main annotation; manifest `authorised=true` | — |
| F7 | `fha.cli train` (validation only), seen-publisher diagnostic on validation | — |
| F8 | Single test opening; report; model card | — |

**Current state: F0 not started. Real data collection and training remain blocked** (`fha.cli status` lists 18 blockers, re-checked 2026-11-02).
