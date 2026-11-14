# Proposal (DRAFT, NOT APPROVED): training a source-aware verdict classifier on AVeriTeC

**Status:** design proposal written 2026-11-02. **Not approved. Nothing in this document has been executed.** No data has been downloaded, no model trained, no sealed material opened.

**Relationship to authority v2:** this is a **separate, future experiment**. It does not modify `docs/authority_v2_preregistration.md`, its config, manifests, logs or any frozen artifact, and it must not start in a way that interferes with authority-v2 Steps 12–15 (see §10).

---

## 0. What has and has not been done so far (to avoid confusion)

| Thing | Is it model training? | Status |
|---|---|---|
| BM25, MiniLM dense retrieval, RRF hybrid (Steps 10, earlier studies) | **No.** Ranking with a pretrained, *unchanged* MiniLM. Nothing was fitted to AVeriTeC labels | Done |
| Authority predictor D (Claude Opus 5.5, prompted; Step 11) | **No.** Zero-shot prompting; no weights updated | Done for reserved 180 |
| Prompt selection for T (V1, development) | **No.** Choosing a prompt is not training | Done |
| A classifier that outputs a verdict (Supported / Refuted / NEE / Conflicting) | **Yes** | **Never done.** This proposal |

The project so far answers: *"Does knowing the right source help find the right evidence?"* A verdict classifier answers a different question: *"Does source-aware evidence help decide whether a claim is true?"* This was hypothesis **H2** in `docs/00_literature_review_and_research_plan.md` (Part 2.4), which was planned but never run.

---

## 1. Research objective

**RQ-C.** Does adding source information to retrieved evidence (which publisher each passage comes from, and whether that publisher is a claim-specific authority) improve four-way AVeriTeC verdict prediction compared with (a) a claim-only model and (b) the same evidence with source information removed?

**Hypotheses (two-sided tests, directional expectations):**

| ID | Comparison | Role | What it isolates |
|---|---|---|---|
| H_C1 | Source-aware evidence model (M) > source-blind evidence model (B4), macro-F1 | **Primary** | The value of source information, with evidence held fixed |
| H_C2 | B4 > claim-only transformer (B3) | Secondary | The value of retrieved evidence at all |
| H_C3 | M > TF-IDF claim-only (B1) | Secondary | Overall gain over the simplest baseline |
| H_C4 | M > B4 on Refuted and on Conflicting per-class F1 | Secondary (descriptive if under-powered) | The original H2 expectation |

**Why H_C1 is primary:** the project's contribution is *source awareness*. Comparing M with B4 changes only one thing (source features present or absent) while keeping the passages, model and training budget identical. A comparison against a claim-only model would mix "more evidence" with "source information".

---

## 2. Prediction target and label definitions

The target is the AVeriTeC claim `label` (one per claim, assigned by annotators from professional fact-checks):

| Label | Meaning (AVeriTeC definition, paraphrased) | Dev count (of 500) |
|---|---|---:|
| Supported | Evidence supports the claim | 122 |
| Refuted | Evidence contradicts the claim, or none supports it where support would be expected | 305 |
| Not Enough Evidence | Evidence is insufficient to decide | 35 |
| Conflicting Evidence/Cherrypicking | Evidence both supports and refutes, or the claim is technically true but misleading | 38 |

The dev counts come from `docs/dataset_audit.md`. **The train-split distribution has not been computed in this project**; it is computed at step P1 (§12). Do not quote it from memory.

- **Primary task:** 4-way classification. **Primary metric:** macro-F1 (each class weighs equally, so the classifier cannot score well just by predicting "Refuted").
- **Secondary task (reported, not decision-making):** collapsed 2-way Supported vs Refuted on claims with those labels only.

The labels are *claim verdicts*. They are **not** evidence-level stance labels and **not** authority labels.

---

## 3. Data available and what each piece may be used for

### 3.1 AVeriTeC splits

| Split | Claims | Labels public? | In this project so far | Proposed use |
|---|---:|---|---|---|
| train | 3,068 | Yes | Schema statistics only; **not downloaded locally** | **Training + validation** |
| dev (320 development claims) | 320 | Yes | Used to design and tune retrieval, D and T; gold seen by the sessions | **Secondary test only**, explicitly flagged "seen during retrieval development". Never used for training or tuning |
| dev (180 reserved claims) | 180 | Yes, but **sealed** | Inputs, KS, rankings (Step 10) and D predictions (Step 11) exist; gold sealed until the authority-v2 gate | **Primary test**, opened only through its own gate (§10) |
| test | 2,215 | No (hidden) | Not used | Not usable without labels. *(Whether labels were released after the shared task is unverified; check before relying on it.)* |

### 3.2 Information per claim, and whether a model may see it

| Field / source | Level | Allowed as model input? | Reason |
|---|---|---|---|
| `claim` | claim | **Yes** | The thing being checked |
| `speaker`, `reporting_source`, `claim_date`, `location_ISO_code` | claim | **Yes**, in tiers (B2 isolates their effect) | Present in the hidden-test records, so a deployed system would have them. Speaker priors can be a shortcut (the LIAR critique), so they are measured separately |
| `original_claim_url` | claim | **No** (proposed) | Often points to the fact-check context or the viral post; risk of shortcut learning. Decision item D-C3 |
| `label` | claim | **Target only** | — |
| `justification`, `questions`/`answers` (gold QA evidence), `fact_checking_article` | claim / evidence | **Never** as input | Annotator output written *after* knowing the verdict: direct label leakage |
| `claim_types`, `fact_checking_strategies`, `required_reannotation` | claim | **Never** | Annotator-assigned |
| Knowledge-store `url`, `url2text` | document | **Yes**, through the retriever | Same pool the retrieval study used |
| Knowledge-store `type`, `query` | document | **Never** | `type=gold` marks gold evidence; `query` is often a gold question verbatim (audit §5) |
| Hybrid rankings (A order), D predictions, D-reranked order | derived | **Yes** | Gold-blind by construction (authority-v2 Steps 10–11 verified this for the reserved set) |
| Gold-informed lists (`DOMAIN_OVERRIDES`, FACTCHECK diagnostic list, X1 assignment, audit fixes) | derived | **Never** | Built using gold |

### 3.3 Can the source-aware retrieval outputs be used as inputs?

**Yes, with two conditions.**

1. **The same pipeline must run on the training claims.** A model trained on one kind of evidence and tested on another learns the wrong thing. The reserved set already has rankings (Step 10) and D predictions (Step 11). The 3,068 training claims have **neither**: their knowledge store must be extracted and ranked with the frozen retrieval code, and D (or a non-LLM authority signal) must be computed for them. This is the largest cost in the plan (§9).
2. **Reserved-set derived files are read-only inputs.** The classifier may read `results/authority_v2/reserved/rankings_hybrid.jsonl.gz` and `authority_raw.jsonl` but never writes there, and never reads `averitec_reserved180_gold.jsonl` except through the gate in §10.

T (Step 13) outputs are **not** required. Using them would make the classifier depend on authority-v2 steps that are not yet approved.

---

## 4. Input representation

Each claim is turned into **k retrieved passages** (proposed k ∈ {5, 10}, chosen on validation). Each passage carries a small **source descriptor**:

| Source feature | Values | Where it comes from |
|---|---|---|
| `publisher_key` | the frozen `cand_key(url)` (domain or social account) | `validation_heldout.cand_key` |
| `generic_prior_bucket` | {1.0, 0.8, 0.6, 0.5, 0.3, 0.2} as categories | frozen `authority_retrieval.generic_prior` (known defects kept and documented) |
| `is_predicted_authority` | 1 if `cand_key ∈ K_c(D)`, else 0 | D's top-3 publisher keys |
| `d_publisher_type` | D's `publisher_type` for the matched key, else `NONE` | D output |
| claim-level: `d_claim_kind`, `d_authority_situation` | categories | D output |
| `rank_position` | 1..k | ranking order |

**Plain-language view:** the model reads a short dossier, e.g. *"Claim: …; Passage 3 from who.int (government-type prior; predicted authority for this claim): '…'"*. The source-blind baseline B4 sees the same passages with the source lines deleted and URLs hidden.

**Which ranking supplies the passages?** The **A (hybrid) order** is the default, so the passages are identical for M and B4 and only the source features differ. A sensitivity run uses the D-reranked order (this changes *which* passages are seen, so it answers a different question and is reported separately).

---

## 5. Model architecture (recommended)

### 5.1 Main model M: evidence-aware cross-encoder with source-aware attention pooling

1. For each passage i, a pretrained encoder reads `[claim] [SEP] [passage_i]` and produces a vector h_i. *(Recommended: `microsoft/deberta-v3-base`, ~184M parameters; `roberta-base` as the fallback. Pin the exact revision at freeze.)*
2. The source descriptor is embedded into a small vector s_i (learned embeddings of the categorical features above).
3. An attention layer scores each passage from [h_i ; s_i], **which lets the model learn to trust some sources more**, and pools the passages into one claim vector.
4. The claim vector (plus embedded claim metadata in the metadata tier) goes to a 4-way softmax.

**Why this design, in plain terms:**
- *Cross-encoder* (claim and passage read together) is the standard, strong approach for "does this text support or refute that claim" (natural-language-inference-style reasoning).
- *Per-passage encoding with pooling* keeps each passage's source attached to it, which is the point of the project. Simply concatenating all passages into one 512-token string loses which text came from which publisher, and truncates heavily.
- *Base-size model:* with ~2,600 training claims, a large model would overfit and would not fit the available hardware (§9).
- **B4 uses exactly this architecture with s_i removed**, so H_C1 is a clean ablation.

### 5.2 What is deliberately *not* proposed as the main model

- **An LLM (e.g. Claude) asked for the verdict.** It is not trainable here, it would be evaluated on 2020 claims it may have memorised, and it would share a model family with D. It can be an optional, clearly labelled *reference* (B0-LLM), not a baseline the hypotheses depend on.
- **Fine-tuning MiniLM or the retriever.** That would change the frozen retrieval pipeline and is a different research question.

---

## 6. Baselines

| ID | Model | Inputs | Purpose |
|---|---|---|---|
| B0 | Majority class, plus stratified random | none | Floor; shows what macro-F1 means under imbalance |
| B1 | TF-IDF (word 1–2-grams) + logistic regression | claim | Simple, transparent, CPU-only |
| B2 | TF-IDF + one-hot metadata + LR | claim + speaker, reporting source, ISO, year | **Shortcut detector**: if metadata alone scores well, the dataset has a speaker/outlet prior |
| B3 | DeBERTa-v3-base fine-tuned | claim (+ metadata tier) | Strong text-only baseline |
| B4 | M architecture without source features | claim + same k passages, URLs hidden | **Primary comparator** (source-blind) |
| M | Main model | claim + k passages + source descriptors | Proposed system |
| B-LR-SRC | LR on TF-IDF(claim + passages) + aggregate source features (share of top-k from predicted authorities, mean prior) | — | Cheap, interpretable check that any source effect is not an artefact of the neural model |
| ORACLE-QA | B3 architecture fed the **gold QA answers** instead of retrieved passages | gold evidence | **Diagnostic upper bound only, validation split only.** Never a system |

Not every baseline must be built first. **Minimum set for a defensible result: B0, B1, B2, B4, M.** B3, B-LR-SRC and ORACLE-QA are recommended if compute allows.

---

## 7. Training, validation, hyperparameter selection, final test

```
AVeriTeC train (3,068) ──► group-aware stratified split ──► TRAIN (~85%)  : fit weights
                                                         └► VAL   (~15%)  : early stopping, HP choice, threshold-free model selection
dev 320 (retrieval-development claims) ─────────────────► SECONDARY TEST (flagged), opened after Freeze C2
dev 180 reserved (sealed) ──────────────────────────────► PRIMARY TEST, opened once, after Freeze C2 + separate approval
```

- **Grouping:** claims are grouped before splitting so near-duplicates never straddle train/val. Groups: identical `fact_checking_article` URL, or claim-text near-duplicates (token Jaccard ≥ 0.8; embedding similarity optional). Stratify by label.
- **Hyperparameters (validation only):** learning rate {1e-5, 2e-5, 3e-5}, k ∈ {5, 10}, up to 5 epochs with early stopping on val macro-F1, class-weighted cross-entropy (weights ∝ 1/√frequency, fixed in advance), batch size fixed by memory. **3 seeds per configuration.** Choose by mean val macro-F1; ties go to the smaller k, then the lower learning rate.
- **B4 and M get the identical grid and seed budget** (otherwise a difference could come from tuning effort).
- **Final model:** the selected configuration's 3 seed models, probabilities averaged (fixed in advance). Per-seed test scores are also reported.
- **Freeze C2:** weights, configs, code and the prediction script are hashed into a manifest **before** any test label is read. After that there is no retraining, no feature changes and no threshold changes.

---

## 8. Evaluation metrics and statistics

- **Primary:** macro-F1 (4-way) on the eligible reserved claims.
- **Secondary:** per-class F1 (esp. Refuted, Conflicting), accuracy, balanced accuracy, confusion matrix, collapsed S/R macro-F1, expected calibration error.
- **Inference:** paired bootstrap of the macro-F1 difference (10,000 resamples, fixed seed, claim-level resampling), 95% percentile CI; exact McNemar on per-claim correctness as a secondary check; Holm over the secondary hypotheses.
- **Decision rule (proposed):** H_C1 supported if the macro-F1 difference > 0 and its 95% CI lower bound > 0.
- **Power: be honest.** 180 claims with ~13–15 per minority class (dev rates) give wide intervals: macro-F1 CIs of roughly ±0.07–0.10 are likely (*estimate, unverified; to be computed by simulation at P2*). **A non-significant result will not show "no benefit".** Results on the 320 secondary set are reported beside it, flagged.
- **The official AVeriTeC score is not applicable:** it scores generated question–answer evidence, which this model does not produce. State this explicitly.
- **Error analysis:** by label, D's `claim_kind`, whether gold is in the pool (pool coverage), whether a predicted authority appears in the top-k, and B2-vs-M disagreement (does M lean on metadata?).

---

## 9. Leakage controls

| Risk | Control |
|---|---|
| Gold fields as inputs | Hard-coded **allow-list** of input fields (claim, speaker, reporting_source, claim_date, ISO); loader refuses any other key; unit test |
| KS `type`/`query` leak | Retriever reads `{url_norm, text}` only (frozen behaviour); string check in the freeze manifest, as in authority v2 |
| Gold-first KS ordering, archive-wrapped gold URLs | Reuse the frozen per-claim shuffle and URL normalisation |
| **Fact-check articles inside the knowledge store** (a PolitiFact/Snopes page effectively states the verdict) | Exclude documents from fact-checking domains using an **independent, pre-declared list** (e.g. a public signatory list, version and date recorded). *Not* the gold-informed FACTCHECK list. Report results with and without the filter |
| KS built partly from gold-derived queries | Cannot be removed; reported as a threat (pool is enriched with relevant pages for train, dev and reserved alike) |
| Reserved gold seen during design | Classifier developed only on train; reserved labels opened once, after Freeze C2, through the gate in §10 |
| Dev-320 contamination | Never used for training or tuning; reported as secondary and flagged |
| LLM memorisation (D is Claude Opus 5.5 on 2020 claims) | D outputs contain publisher guesses, not verdicts, but `fact_at_issue` text could carry verdict cues: **do not feed `fact_at_issue`/`why` text to the classifier**; use only the categorical D fields. Ablation without any D-derived feature (heuristic authority only) |
| Near-duplicate claims across train/val | Group-aware split (§7) |
| Hyperparameter peeking | All selection on validation; manifest-locked test opening; logs append-only |
| Future dependence on the first-hand authority model (Project 2) | If its scores are ever used as features, Project 2 must exclude all 500 AVeriTeC dev claims from its data, and its scores for *training* claims must be produced out-of-fold (cross-fitting) |

---

## 10. Interaction with authority v2 and the reserved set

The reserved 180 claims are committed to authority v2 (Families R and N). Using their labels to test a classifier is a **new use** that needs its own approval. Three options for the mentor:

| Option | Description | Pros | Cons |
|---|---|---|---|
| **C-1 (recommended)** | Develop and **freeze** the classifier (Freeze C2) on train **before** the reserved gold is used for anything. After authority-v2 Step 15 and a separate classifier-gate approval, score the frozen classifier once on the reserved 180 | Cleanest: no one has seen reserved labels when the classifier is designed | Authority-v2 scoring may have to wait for the classifier, or the classifier is frozen while authority v2 is paused after Step 14 |
| C-2 | Complete authority v2 first; then develop the classifier and test on reserved 180 | No scheduling interaction | The person developing the classifier will have seen reserved gold (verdict breakdowns, gold URLs) at Step 15: a documented contamination threat |
| C-3 | Do not use reserved 180 for the classifier; test on all 500 dev claims as a secondary-grade test | No interaction | No clean test set; all 500 claims have been seen in some form |

Whatever is chosen, the classifier never writes into `results/authority_v2/`, never edits authority-v2 manifests/logs, and opens the sealed gold file only through a **classifier-specific** gate entry logged in the classifier's own execution log (in addition to the authority-v2 gate already being crossed).

**Do not derive the reserved label distribution** (e.g. dev totals minus the 320 known claims) before the gate. It is a small but real peek at sealed gold.

---

## 11. Compute requirements (estimates; verify before committing)

| Item | Estimate | Basis |
|---|---|---|
| Free disk needed | **≥ 20 GB** before P3. *C: currently has ~2.1 GB free; this is a blocker* | Reserved KS extracts = 763 MB / 180 claims ≈ 4.2 MB/claim → ~13 GB for 3,068 train claims; can be cut to <1 GB by keeping only each claim's top-100 pool after ranking |
| Train KS streaming | ~13–15 h network | Step 8 took ~48 min for 180 claims from the 11.5 GB dev zip; train is 3 zips (~62 GB), range requests only |
| Ranking 3,068 claims (BM25 + MiniLM, CPU) | ~12–15 h CPU | Step 10 took ~50 min for 180 claims on this laptop |
| D predictions for train claims (optional) | ~USD 70–75, ~4 h | Step 11 actuals: USD 4.19 for 180 claims (~0.023/claim). Alternative: heuristic authority (system C), free |
| Fine-tuning (B3, B4, M; grid × 3 seeds) | ~10–25 GPU-hours on a T4/16 GB-class GPU | ~2,600 claims × k passages × 256 tokens; rough |
| Local hardware | **Not suitable for fine-tuning**: Quadro M2200 4 GB, PyTorch CPU build. B0–B2 and B-LR-SRC run on CPU | Checked 2026-11-02 |
| GPU options | Colab/Kaggle T4, or a university GPU | AVeriTeC is CC BY-NC 4.0; check that cloud upload is allowed by the university |

---

## 12. Proposed work packages (each needs the approval shown)

| # | Work package | Type | Approval needed |
|---|---|---|---|
| P0 | Mentor review of this proposal; choose option C-1/C-2/C-3; decide D-C1…D-C5 | Decision | Mentor |
| P1 | Write the classifier preregistration + decision log + execution log in a new `experiments/verdict_classifier/`; **Freeze C1** | Offline | Owner + mentor |
| P2 | Power simulation; download `train.json` (10 MB); label distribution and duplicate audit | Network (small) | Owner |
| P3 | Free disk; stream train KS; rank with frozen code; keep top-100 pools | Network + CPU | Owner (network) |
| P4 | Authority features for train (D via LLM, or heuristic) | LLM (cost) or offline | Owner (cost) |
| P5 | Baselines B0–B2 on validation | CPU | Owner |
| P6 | B3, B4, M training + HP selection on validation | GPU | Owner (compute environment) |
| P7 | **Freeze C2** (models + prediction code) | Offline | — |
| P8 | Secondary test on dev 320; primary test on reserved 180, once | Offline | **Separate reserved-gold approval** for the classifier, and authority-v2 status per §10 |
| P9 | Results write-up, model card | Offline | — |

### Open decisions for the mentor

- **D-C1:** test-set option C-1 / C-2 / C-3 (§10).
- **D-C2:** authority features for training claims: LLM D (cost, same model family as authority v2) or heuristic only, or both as an ablation.
- **D-C3:** whether `original_claim_url` / `reporting_source` are allowed inputs.
- **D-C4:** fact-check-domain filter: which independent list, and is "with filter" primary?
- **D-C5:** whether H_C1 (source-aware vs source-blind) is the right primary, versus H_C2 (evidence vs claim-only).

---

## 13. Expected outputs

- `docs/verdict_classifier_preregistration.md`, decision log, execution log, manifests C1/C2.
- Validation report (all models, all seeds, HP grid).
- Test report: macro-F1 with CIs, per-class F1, confusion matrices, paired comparisons, error analysis; secondary-set results flagged.
- Frozen model bundle (weights hashes, config, library versions) and a model card stating the intended use and the limitations above.

## 14. Reproducibility requirements

- Pinned versions of Python, PyTorch, transformers, sentence-transformers, bm25s, tldextract, scikit-learn; Hugging Face model revision hashes.
- Seeds for the split, bootstrap and each training run; deterministic flags where available; GPU type recorded.
- Raw-byte SHA-256 of all inputs and outputs, LF line endings for new text files (same convention as authority v2).
- Append-only execution log; scripts refuse to overwrite outputs; test lock file.
- Every reported number is regenerated from saved predictions by a single scoring script.
