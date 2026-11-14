> **Update 2026-11-14:** all `results/esa_nov2026/**` outputs listed in §14 were **lost on 13 Nov 2026**. The offline ones were **regenerated on 14 Nov** from frozen inputs, with identical values: reproduction check, recall ceiling, promotion stats, demo pages. The **PU run1_pu outputs (report JSON, per-claim CSV, models, feature cache) and the train knowledge-store extraction remain lost**. The PU metrics in §7.1 are confirmed by the original console output preserved in the session transcript (`results/esa_nov2026/relevance_baseline/run1_pu_RECORDED_OUTPUT_FROM_TRANSCRIPT/`). Current material for the 16 Nov review: `docs/monday_review_2026-11-16/`.

# Phase-I ESA: Implementation and Experiment Report

**Project A — Source-Aware Misinformation Detection** (PES University, B.Tech CSE AI & ML, team IR_03)
**Prepared:** 2026-11-08 by Claude Code with the project owner. **ESA deadline:** 2026-11-16.
**Scope:** Project A only (`C:\Users\Lenovo\Downloads\capstone\Source_Aware_Misinformation_Detector`). Project B (`first_hand_authority_model`) was not opened or modified.

### Evidence labels used in this report

| Label | Meaning |
|---|---|
| **[FROZEN]** | Number from a frozen, preregistered project result file. It was re-scored and reproduced exactly on 2026-11-08 (§3). |
| **[NEW-EXPL]** | New descriptive measurement made on 2026-11-08 from frozen rankings and predictions. It is exploratory, on claim sets the frozen study already used, and is **not** a new held-out test. |
| **[RECON]** | From files rebuilt from Claude transcripts after the 2026-11-06 deletion. Only partly verified. |
| **[LOST]** | Executed historically. The output file no longer exists. |
| **[PROPOSED]** | Design only. Not implemented or not trained. |

"Gold" throughout means the AVeriTeC annotators' evidence URLs for the public dev claims. These are **evidence/relevance citations, not authority labels**: they include news and fact-check pages. **Exception:** the PU relevance experiment (§6 R3, §7.1) does not use this dev gold. It uses AVeriTeC **TRAIN**-claim evidence-URL matches with non-empty text as **weak-positive relevance labels**. These are not human-verified authority labels and are separate from the held-out dev gold set.

---

## 1. Initial project and safety checks

| Check | Result |
|---|---|
| Git | Branch `main`, HEAD `9279eab`, up to date with `origin/main`. `git diff` was clean before this work: no tracked file was modified. Untracked before this work: 4 docs, `experiments/authority_v2/` (recovered 2026-11-06). |
| `core.autocrlf` | `true`. Checked-out scripts therefore have CRLF endings, and raw SHA-256 differs from the recorded freeze hashes. **After CRLF→LF normalisation, all 8 checked frozen files match their recorded hashes**, and the committed git blobs match too (§3.1). |
| Protected data | The sealed reserved-180 gold (`data/processed/averitec_reserved180_gold.jsonl`) **does not exist on disk** (lost 2026-11-06) and was never referenced. The reserved-180 knowledge-store extracts, inputs, rankings (v2 Step 10) and LLM predictions (v2 Step 11, sha `86b2840c…`) are also **[LOST]**. |
| Allowed data | 120 dev-sample claims (`data/processed/averitec_sample.jsonl`), 200 held-out claims (`averitec_heldout.jsonl`), their 320 knowledge-store extracts (`data/raw/averitec/ks_sample/`, 1.4 GB), and AVeriTeC `train.json` (claims only; no train knowledge store on disk). |
| Frozen outputs | `results/heldout/`, `results/source_targeted/`, `results/rankings_*.jsonl.gz`, AI-annotation files, `FROZEN_HASHES.json` and the preregistrations. **All were read only.** |
| Manifests and decision logs | `docs/authority_v2_preregistration.md` and `docs/authority_v2_decision_log.PARTIALLY_VERIFIED.md` were read only. The v2 freeze manifests are [LOST]. Nothing was recreated or edited. |
| Disk / compute | C: 244 GB total, 17.7 GB free. Windows 10, Python 3.13.2, CPU only (8 logical cores, 32 GB RAM). `bm25s 0.3.11`, `sentence-transformers 5.4.0`, `torch 2.6.0+cpu`, `scikit-learn 1.6.1`, spaCy 3.8.14 + `en_core_web_sm`. MiniLM is cached in `~/.cache/huggingface`. |
| LLM / API / network | **None used.** All LLM outputs shown are frozen files from Sept 2026. |

**Execution plan followed:**
1. Read-only inventory and hash gate.
2. Reproduce the frozen held-out and dev tables from frozen rankings.
3. Live re-run of BM25, MiniLM and RRF on a few claims.
4. Demo CLI and HTML.
5. Authority-promotion statistics.
6. Stage-wise recall decomposition.
7. Relevance-baseline code, an offline train split and a synthetic smoke test.
8. Reports.

All new code is in `experiments/esa_nov2026/` and all new outputs are in `results/esa_nov2026/`. The protected reserved claims are refused by the code (`esa_common.assert_allowed`).

## 2. Existing implementation verified

| Component | File (frozen) | How it works | Input it needs |
|---|---|---|---|
| Corpus | `experiments/baseline_retrieval.py` `claim_docs`, `retrieval_corpus` | Per-claim AVeriTeC knowledge store; deduplicated by normalised URL (keeping the longest text); sorted, then shuffled with a per-claim seed (2026); empty documents dropped. The retriever sees only `{url_norm, text}`. | `data/raw/averitec/ks_sample/<id>.jsonl.gz` |
| **BM25** | same, `rank_bm25` | `bm25s` with English stop words and no stemming, over the full document text. Query = claim text. | as above |
| **MiniLM dense** | same, `rank_dense` | `all-MiniLM-L6-v2` (frozen, not fine-tuned), first 1,000 characters, 128 word pieces, cosine similarity | as above + cached model |
| **Hybrid RRF** | `validation_heldout.cmd_rank` | Σ 1/(60 + rank) over the full BM25 and dense lists | both full rankings |
| Rerank | `authority_retrieval.rerank` | Hybrid top-100: `minmax(score) + λ·prior(url)`, λ = 1, stable sort | prior function |
| **B: generic credibility prior** | `authority_retrieval.generic_prior` | Claim-independent URL type: gov/intergov 1.0, academic 0.8, major news 0.6, reference 0.5, other 0.3, platform 0.2 | URL only |
| **C: heuristic claim prior** | `authority_retrieval.full_prior` | max(generic, 1.0 if the domain/handle matches a spaCy entity of the claim or speaker, or is a government domain of the claim's country) | claim, speaker, ISO country, URL |
| **D: LLM authority prior** | `authority_resolution.py` (L+Wctx) + `source_targeted.primary_authority_candidates` | Claude Opus 5.5 (no tools, no web) predicted the top-3 publishers per claim. Prior = 1 if the document's publisher key is one of them. | **frozen predictions**: `results/authority_resolution_raw.jsonl` (120 dev), `results/heldout/authority_raw.jsonl` (200 held-out) |

Historical status of the review items:
- (1)–(3) BM25, MiniLM and Hybrid RRF: **implemented and evaluated** on 120 dev and 200 held-out claims **[FROZEN]**.
- (4) "Initial LLM-based authority predictions for 180 claims": these were the authority-v2 Step-11 predictions on the reserved 180. They were **executed on 2026-11-01** (180/180 parsed, reported cost USD 4.19 [RECON, transcript log excerpt]), but the **output file is [LOST]**. They were **not** re-run, because a re-run would be a new execution, not a recovery. LLM predictions that do exist: 120 dev + 200 held-out (Sept 2026).
- (5) Supervised authority model: **[PROPOSED]** (§5, `docs/ESA_PROPOSED_AUTHORITY_MODEL_ARCHITECTURE.md`).

## 3. Retrieval experiments reproduced and demonstrated

### 3.1 Hash gate (`experiments/esa_nov2026/reproduce_check.py`)
All 8 files match the hashes recorded in `docs/validation_preregistration.md` and `docs/source_targeted_preregistration.md`:
- scripts, compared after LF normalisation: `validation_heldout.py`, `source_targeted.py`, `source_targeted_eval.py`, `score_heldout_primary.py`, `authority_resolution.py`, `authority_retrieval.py`, `baseline_retrieval.py`;
- the raw frozen rankings file `results/source_targeted/rankings_heldout.jsonl.gz`.

### 3.2 Re-scoring from frozen rankings — PASS
Systems BM25, dense, A, B, C and D were rebuilt with the frozen functions from the frozen full rankings and frozen predictions. They were scored with the frozen `source_targeted_eval.score`. **Every value is identical to the published tables**: GoldR@1/3/5/10/20/50/100, MRR@100, claim and document coverage, and denominators.

| System | Held-out R@10 (n = 167) | Dev R@10 (n = 99) |
|---|---|---|
| BM25 | 0.180 | 0.111 |
| MiniLM dense | 0.251 | 0.242 |
| A Hybrid RRF | 0.251 | 0.242 |
| B + generic prior | 0.263 | 0.212 |
| C + heuristic prior | 0.275 | 0.232 |
| D + LLM authority prior | 0.293 | 0.343 |

R@10 = claim-level hit rate: the share of claims with ≥ 1 reachable gold document in the top 10. Output: `results/esa_nov2026/reproduction/reproduction_check.json`.

### 3.3 Live re-computation — PASS
BM25, MiniLM and RRF were recomputed from scratch with the frozen functions for 6 claims (dev 1, 5, 7; held-out 2, 4, 10). **The top-100 order was identical to the stored rankings for all three methods on all 6 claims.** Live cost is about 2 min per claim on this CPU (claim 268: BM25 4–5 s, MiniLM 97–131 s).

**Is a new run necessary?** No. The frozen rankings are complete, reproducible and sufficient for the demonstration. Live mode exists to show that the pipeline really runs.

### 3.4 Demonstration (`experiments/esa_nov2026/demo.py`)
- **Input:** any of the 320 allowed claims; reserved or other claim ids are refused. Optionally `--query` (a custom claim, retrieved live over that claim's knowledge store) or `--live`.
- **Output:** BM25, MiniLM and Hybrid top-K side by side, with each document's rank under the other two methods, the query terms it contains, and a top-K overlap count. Then the authority section (§4).
- **Files:** `results/esa_nov2026/demo/claim_<id>.{html,md,json}`.

**Why the rankings differ** (example: claim 2, held-out, frozen run): the three top-10 lists share **one** document.
- BM25 ranks pages that repeat the claim's exact words ("imran", "khan", "macron", "islam") highest, so news about the Macron controversy dominates.
- MiniLM matches meaning in the **first 1,000 characters only**. It ranks the actual gold tweet by `@PakConsulateFr` at **3**, a page BM25 puts at 432 because the tweet shares few claim words.
- RRF rewards agreement between the two lists. The gold tweet reaches hybrid rank 17, and the best gold rank is BM25 32, dense 3, hybrid 17.

So hybrid is a robust compromise, not always the best list for a given claim.

## 4. Authority-resolution demonstration

Same demo command. For the claim, the demo shows:
- the frozen LLM prediction: fact at issue, claim kind, top-3 publishers with domain or handle, and how many pool documents each predicted publisher has;
- the hybrid top-100 re-ranked by B, C and D, with the old rank, movement, prior value, publisher key and gold marker for each document.

**Illustrative claims** (chosen after inspecting frozen per-claim results, for teaching; not a validation):

| Claim | What it shows | Best gold rank: hybrid → D |
|---|---|---|
| **268**: Trump's 24 Sept 2020 executive order "legally ensures" pre-existing-condition protections | **Authority ≠ credibility.** B and C lift a `finance.senate.gov` press release to rank 2 because it is `.gov`. D lifts the executive order itself (`trumpwhitehouse.archives.gov`, publisher key `archives.gov`) from rank 28 to **1**. | 28 → 1 |
| **436**: US military will check purity and distribute COVID-19 vaccines | **Limitation.** Gold was already hybrid rank 1. Boosting the predicted publishers' documents pushes it to 16. | 1 → 16 |
| **2**: France cancelled 183 Pakistani visas | No predicted authority has any document in the pool, so D = hybrid. One gold document is the claim's own source tweet (`@PakConsulateFr`), which only MiniLM ranks high (3). | 17 → 17 |
| 89, 328, 464, 326 | Domain examples (§9) | 21→10, 43→3, 18→1, 24→28 |

**Publisher-level binary boosting promotes irrelevant documents** [NEW-EXPL] (`experiments/esa_nov2026/authority_promotion_stats.py`, held-out n = 167):
- **Why it happens:** the prior is 0/1 and the min-max relevance score is in [0, 1]. Every document of a boosted publisher therefore outranks every non-boosted one, whatever its relevance.
- **How often:** D placed **267** documents from below hybrid rank 50 into some claim's top 10. **263** of them are not AVeriTeC evidence documents. These are unlabelled, not proven irrelevant, but their relevance scores were in the bottom half of the pool.
- **Effect on claims:** 56 claims had ≥ 5 promoted non-gold documents in the top 10. In 6 claims, gold that was in the hybrid top 10 was pushed out.
- **Best gold rank vs hybrid:** D won on 20 claims, lost on 52 and tied on 95. This matches the frozen `rank_win_loss_tie` exactly.
- **B (generic) and C (heuristic)** promote more documents overall (861 and 834 into top-10s), but mostly from shallow ranks. B lost on 60 claims and won on 48.

**Known flaw found in a frozen heuristic** (documented, not changed): `is_gov` treats any host label `go` as government. As a result `abcnews.go.com` receives the government prior 1.0 (seen in claim 2's B/C list). This is an example of why publisher-type heuristics are brittle.

## 5. Model-training feasibility

| Question | Finding |
|---|---|
| Human claim–document **authority** labels? | **None exist.** The human primary-evidence protocol was "NOT executed" (`heldout_primary_package/README.md`), and no second annotation was obtained (`second_annotator_guidelines.md`). The AI role labels are Claude outputs (same model family as predictor D), not ground truth. |
| → Supervised authority classifier | **Not trained and not claimed.** Architecture only: `docs/ESA_PROPOSED_AUTHORITY_MODEL_ARCHITECTURE.md` [PROPOSED]. |
| Human **relevance** labels? | Yes, weakly: AVeriTeC train evidence URLs (`questions[].answers[].source_url`) are human-chosen evidence. They are a legitimate **weak positive** relevance target, **not** authority. Every other knowledge-store page is **unlabelled** (not a confirmed negative), so the task is positive-unlabelled (PU) learning. |
| Approved fitting split | AVeriTeC **train** (3,068 claims; 2,985 with ≥ 1 web evidence URL). Dev is fully allocated (120 + 200 + reserved 180). |
| Train candidate documents | **Extracted 2026-11-08 with owner approval:** only the 300 sampled claims' members (1.2 GB) were streamed from the official pinned train zips. See §6 R2. |
| → Relevance baseline | **Trained and evaluated 2026-11-08 as a PU relevance ranking baseline** (§6 R3, §7.1). It is not an authority model. |

## 6. Legitimate model training performed

**One model family was trained on real data: a positive-unlabelled (PU) *relevance* ranking baseline on AVeriTeC train claims. No authority model was trained.** No dev, reserved-180 or sealed gold data was accessed. No LLM/API calls were made and no additional data was downloaded. One Hugging Face Hub metadata request occurred when the cached MiniLM model was loaded (see the network note under R3).

1. **R1 — train-claim sample and claim-disjoint split (run, offline)**: `relevance_baseline/make_train_split.py`.
   - Reads only `train.json` (sha recorded in the manifest; identical to the official remote copy).
   - 300 train claims with ≥ 1 web evidence URL, label-stratified (Refuted 169, Supported 84, NEE 27, Conflicting 20). The label is used only to balance the sample; it is never a feature.
   - Seed 2051, chosen because the project had not used it before.
   - Split: **fit 179 / validation 60 / test 61 claims**. Claim-disjoint (asserted; re-checked before training: 0 shared IDs, 0 shared claim texts).
   - Manifest: `results/esa_nov2026/relevance_baseline/train_sample_split.json`, split sha256 `1b994a96974e3e7bbcda6994b1c0b08a5bbdbb580de42fcf383b5e11709e5765`.
2. **R2 — train knowledge-store extraction (run 2026-11-08, owner-approved, network)**: `extract_train_ks_sample.py`, verified by `verify_extraction.py`.
   - Source: Hugging Face `chenxwh/AVeriTeC` at revision `2ca9dee23a2a6fa64c5bd918e0cd28ed0aa09031`, licence CC BY-NC 4.0, the three official `data_store/knowledge_store/train/train_*.zip` files. Only the 300 claims' zip members were streamed via HTTP range requests (about 6.2 GB of traffic out of 63.5 GB); the full store was not downloaded.
   - Output: 300/300 files, 1,279,659,817 bytes, 303,594 documents (82,200 with empty text), in `capstone/storage/datasets/averitec_train_ks_sample/`. All 593 train evidence URLs were found in their claim's file (alignment check); 343 have non-empty text.
   - Manifest: `results/esa_nov2026/relevance_baseline/EXTRACTION_MANIFEST.{json,md}` (status OK; file-list sha256 `8bd0ac72a57c9bb5a7bcb63df86c13ca46668e2d21f714f74cfeaad6fa1c73a4`), plus `extraction_log.jsonl`.
3. **Pre-run audit (2026-11-08).** The first version of `train_relevance.py` labelled 30 sampled non-evidence documents per fit claim as y = 0, half of them "hard negatives" taken from the hybrid top-100. That turned unlabelled documents into negatives. The run was stopped before any data was used. With owner approval the code was changed to the PU design below (Option B).
4. **R3 — PU relevance ranking baseline (run 2026-11-08, offline)**: `train_relevance.py`, run tag `run1_pu`.
   - **Labels (PU).** s = 1 ("labelled"): the document's normalised URL is one of the claim's AVeriTeC evidence URLs and its text is non-empty. This is a **weak positive relevance proxy**. Every other document is **unlabelled**, never a confirmed negative.
   - **Unlabelled sample (fit claims only).** 30 documents per fit claim are drawn **uniformly** from all of that claim's non-empty, non-labelled documents. The candidates are sorted by `url_norm`, then drawn with `random.Random(2052 * 100003 + train_idx)`. No rank-based or hard-negative selection is used. The policy, seed and helper are in `rb_common.py` (`SAMPLING_POLICY`, `SEED_UNLABELLED = 2052`, `sample_unlabelled`).
   - **Determinism check before the run.** `verify_unlabelled_sampling.py` passed (`results/esa_nov2026/relevance_baseline/unlabelled_sampling_check.json`):
     - 179 fit claims, 5,370 sampled, 0 problems;
     - no labelled URL was sampled, and every sampled URL comes from the claim's own collection;
     - a different `train_idx` gives a different draw from the same collection, so the draw is claim-specific;
     - two separate processes gave the same overall hash, `090ccf6fdc5897b939b486bdea835e570c5abbbc16c6def20c486b5b8623dd77`. The training run recorded the same hash.
   - **Classifier.** "Labelled vs unlabelled" (Elkan & Noto 2008, the non-traditional classifier). Its score is used **only to rank** documents. Under SCAR (selected completely at random) it is monotone in P(relevant | x). It does not give calibrated relevance probabilities.
   - **Fit data.** 179 fit claims (131 with ≥ 1 labelled document); 5,587 pairs = 217 labelled + 5,370 unlabelled.
   - **Features (17)**, all leak-safe: BM25, dense and RRF scores and ranks; document length; claim-term and number overlap; URL source type (generic prior, gov, PDF, social, path depth); claim-entity↔domain match; claim-country gov match. M3 adds the frozen MiniLM claim⊙doc product (384-d). The feature code receives only the claim text, speaker and location fields. Forbidden fields (asserted in code): AVeriTeC questions, answers, justification, verdict, fact-check article, gold indicators, KS `type`/`query`, `doc_idx`/file order, raw URL, pool publisher counts.
   - **Models:**
     - M1 logistic regression;
     - M2 HistGradientBoosting (200 iterations, learning rate 0.05);
     - M3 logistic regression + MiniLM (C = 0.1).
     All use `class_weight="balanced"`. Model selection is based **exclusively on validation claim R@10** (ties → simpler model); the rule was fixed in code before the run. Execution order: within one run, the script computes training, validation and test metrics for all models and the hybrid; it then applies the selection rule, which reads only the validation metrics. Test results therefore did **not** influence model selection, but test evaluation did not occur *after* selection in time. Each model was scored on the test claims exactly once, and there was no re-tuning or re-run. The primary test is exact McNemar on per-claim hit@10, selected model vs hybrid.
   - **Synthetic smoke test** (`--synthetic`, 18 invented claims) passed before the real run. It verifies only that the code runs end to end; its numbers are meaningless and are not results.
   - **Run.** Started 17:53, finished 20:12 (8,310 s), exit 0. Python 3.13.2, scikit-learn 1.6.1, NumPy 2.2.3, 8-core CPU.
   - **Network note.** No LLM/API calls and no additional downloads. One Hugging Face Hub **metadata request** occurred: `sentence-transformers` printed a warning ("unauthenticated requests") when it loaded the locally cached MiniLM. No file in the local model cache changed, and no data or model was downloaded. For a strictly offline re-run, set `HF_HUB_OFFLINE=1` (§13).
   - **Outputs** (`results/esa_nov2026/relevance_baseline/run1_pu/`):
     - `relevance_baseline_report.json` (sha256 `0f49c165a0df6ce2366244d5b2289d236b04318bdff9a0cb645b121e8750e77c`);
     - `per_claim.csv`;
     - `unlabelled_samples.json` (every sampled URL);
     - `models/M{1,2,3}_*.joblib` (the fitted rankers);
     - `run_stdout.log`;
     - `feature_cache/` (300 per-claim feature files; a re-run reuses them).

## 7. Evaluation metrics and actual results

**Definitions** (c = claim; G(c) = reachable gold documents, i.e. present in the knowledge store with non-empty text; W(c) = all web gold URLs; top_K(c) = first K of a ranking):
- **Claim-level Recall@K** (the project's R@K, a hit rate) = |{c ∈ C_eval : G(c) ∩ top_K(c) ≠ ∅}| / |C_eval|, where C_eval = {c : G(c) ≠ ∅}.
- **Document-level Recall@K** (micro) = Σ_c |G(c) ∩ top_K(c)| / Σ_c |G(c)|.
- **MRR@100** = mean over C_eval of 1/(rank of the first gold document), or 0 if no gold is in the top 100.

**Frozen preregistered held-out results [FROZEN, reproduced]**, n = 167 claims with reachable gold out of 200:

| System | R@5 | R@10 | R@20 | MRR@100 |
|---|---|---|---|---|
| A Hybrid | 0.156 | 0.251 | 0.383 | 0.125 |
| B + generic | 0.174 | 0.263 | 0.383 | 0.099 |
| C + heuristic | 0.186 | 0.275 | 0.407 | 0.109 |
| D + LLM prior | 0.198 | 0.293 | 0.437 | 0.138 |

The primary preregistered test, D vs A at R@10: +13/−6, exact McNemar p = 0.167, Δ = +0.042, 95% bootstrap CI [−0.006, 0.096]. **Not significant.** No preregistered held-out comparison was significant (README).

### 7.1 PU relevance ranking baseline — AVeriTeC train sample [NEW, run1_pu]

**Labels in this section** are AVeriTeC **TRAIN**-claim evidence-URL matches with non-empty text, used as **weak-positive relevance labels**; all other documents are unlabelled. They are not human-verified authority labels and are not the held-out dev gold set used in §7 and §8.

All systems rerank the **same hybrid RRF top-100 pool** for the **same eligible claims**: claims with ≥ 1 labelled (evidence, non-empty) document in their collection. "Pool coverage" is the empirical upper bound for any reranker of that pool. labelled-P@10 counts unlabelled documents as non-hits, so it is a **lower bound** on true precision@10, and only if the labelled documents are truly relevant. It also favours models that imitate fact-checker citation choices. Average precision is not reported, because it has no valid bound interpretation under incomplete labels.

**Pool coverage (upper bound)**

| Split | Claims | Eligible | Claim-level max R@100 | Doc-level max R@100 |
|---|---|---|---|---|
| Fit (training) | 179 | 131 | 85/131 = 0.649 | 102/217 = 0.470 |
| Validation | 60 | 37 | 29/37 = 0.784 | 39/64 = 0.609 |
| Test | 61 | 42 | 30/42 = 0.714 | 38/62 = 0.613 |

**Training (fit claims) — IN-SAMPLE, optimistic; not a performance estimate** (n = 131)

| System | R@1 | R@5 | R@10 | R@20 | doc R@10 | MRR@100 | labelled-P@10 (LB) |
|---|---|---|---|---|---|---|---|
| Hybrid RRF | 7/131 = 0.053 | 20/131 = 0.153 | 35/131 = 0.267 | 53/131 = 0.405 | 35/217 = 0.161 | 15.30/131 = 0.117 | 35/1310 = 0.027 |
| M1 logreg | 2/131 = 0.015 | 19/131 = 0.145 | 28/131 = 0.214 | 45/131 = 0.344 | 28/217 = 0.129 | 10.80/131 = 0.082 | 28/1310 = 0.021 |
| M2 HistGBDT | 59/131 = 0.450 | 84/131 = 0.641 | 85/131 = 0.649 | 85/131 = 0.649 | 101/217 = 0.465 | 69.92/131 = 0.534 | 101/1310 = 0.077 |
| M3 logreg+MiniLM | 5/131 = 0.038 | 19/131 = 0.145 | 30/131 = 0.229 | 50/131 = 0.382 | 31/217 = 0.143 | 13.34/131 = 0.102 | 31/1310 = 0.024 |

On its training claims M2 reaches the pool ceiling (85/131): the boosted trees have memorised the 217 labelled pairs. This is overfitting, not skill.

**Validation** (n = 37; used for model selection)

| System | R@1 | R@5 | R@10 | R@20 | doc R@10 | MRR@100 | labelled-P@10 (LB) |
|---|---|---|---|---|---|---|---|
| Hybrid RRF | 2/37 = 0.054 | 6/37 = 0.162 | 11/37 = 0.297 | 15/37 = 0.405 | 13/64 = 0.203 | 4.82/37 = 0.130 | 13/370 = 0.035 |
| M1 logreg | 1/37 = 0.027 | 2/37 = 0.054 | 7/37 = 0.189 | 12/37 = 0.324 | 9/64 = 0.141 | 2.58/37 = 0.070 | 9/370 = 0.024 |
| **M2 HistGBDT (selected)** | 3/37 = 0.081 | 7/37 = 0.189 | 9/37 = 0.243 | 14/37 = 0.378 | 10/64 = 0.156 | 5.76/37 = 0.156 | 10/370 = 0.027 |
| M3 logreg+MiniLM | 0/37 = 0.000 | 3/37 = 0.081 | 3/37 = 0.081 | 8/37 = 0.216 | 4/64 = 0.062 | 1.78/37 = 0.048 | 4/370 = 0.011 |

The selection rule chooses among the three models only. Hybrid RRF had a higher validation R@10 (0.297) than every learned model.

**Test** (n = 42; each model scored once; not used for selection)

| System | R@1 | R@5 | R@10 | R@20 | doc R@10 | MRR@100 | labelled-P@10 (LB) | hit@10 vs hybrid (W/L, exact McNemar p) |
|---|---|---|---|---|---|---|---|---|
| Hybrid RRF | 4/42 = 0.095 | 10/42 = 0.238 | 13/42 = 0.310 | 16/42 = 0.381 | 13/62 = 0.210 | 6.82/42 = 0.162 | 13/420 = 0.031 | — |
| M1 logreg | 2/42 = 0.048 | 6/42 = 0.143 | 10/42 = 0.238 | 18/42 = 0.429 | 11/62 = 0.177 | 4.89/42 = 0.117 | 11/420 = 0.026 | 3/6, p = 0.508 (secondary) |
| **M2 HistGBDT (selected)** | 6/42 = 0.143 | 11/42 = 0.262 | 12/42 = 0.286 | 14/42 = 0.333 | 12/62 = 0.194 | 8.55/42 = 0.204 | 12/420 = 0.029 | **0/1, p = 1.000 (PRIMARY)** |
| M3 logreg+MiniLM | 1/42 = 0.024 | 5/42 = 0.119 | 8/42 = 0.190 | 11/42 = 0.262 | 9/62 = 0.145 | 3.42/42 = 0.081 | 9/420 = 0.021 | 4/9, p = 0.267 (secondary) |

**Result.** **On the primary test metric, Recall@10, no learned relevance model improved over Hybrid RRF.** The validation-selected Gradient Boosting model scored 12/42 vs hybrid 13/42. Some secondary test metrics were higher for learned models: Gradient Boosting R@1 6/42 vs 4/42 and MRR@100 0.204 vs 0.162; logistic regression R@20 18/42 vs 16/42.
- Primary test: the selected M2 had 12/42 vs hybrid 13/42 at R@10 (0 wins, 1 loss; p = 1.000).
- M2 has a higher R@1 (6 vs 4) and MRR@100 (0.204 vs 0.162) on test. These are exploratory, untested secondary differences on 42 claims and must not be reported as an improvement.
- M1 and M3 are worse than hybrid at R@10 on both validation and test.

**Interpretation.**
- With 217 weak positives from 131 claims, a feature-based reranker does not improve on unsupervised fusion.
- M2 overfits: it reaches the pool ceiling on its own training claims but does no better than hybrid on validation and test.
- With only 42 test claims, only large differences could be detected. A true difference of a few points of R@10 cannot be ruled out in either direction.

The baseline's value for the ESA is as an honest, reproducible negative result. It shows that a relevance ranker trained only on citation proxies is not enough, which supports collecting real human labels in Phase II.

**PU assumptions and limitations (also stored in the report JSON)**
- **SCAR is very likely violated.** Fact-checkers choose evidence selectively: official pages, news, fact-check sites, pages their own searches surfaced. The model therefore learns "what fact-checkers cite", not relevance in general.
- **Incomplete positives.** Most relevant pages in a store are never cited, so the unlabelled sample contains relevant pages, and recall against labelled documents underestimates true recall.
- **Store construction.** AVeriTeC stores were built partly from gold-derived queries, so retrieval looks easier here than on the open web.
- **Empty-text evidence (scrape failures)** cannot be labelled. 90 of the 300 claims (48 fit, 23 validation, 19 test) are not eligible for evaluation for this reason.
- **Small samples.** 37 validation and 42 test claims. Exploratory secondary comparisons are uncorrected.
- **Balanced class weights** change calibration, not ranking validity under SCAR.
- **Not authority.** Evidence relevance is not claim-specific authority, and none of these results measure authority.

## 8. Recall-ceiling findings [NEW-EXPL unless marked]

Script: `experiments/esa_nov2026/recall_ceiling.py`. Output: `results/esa_nov2026/recall_ceiling/recall_ceiling.json`. Held-out set (200 claims):

| Stage | Measure | Value |
|---|---|---|
| **1. Collection coverage** | claims with web gold → claims with reachable gold | 167/192 = **0.870** (8 claims have no web gold at all) |
| | gold URLs reachable | 305/422 = **0.723** (117 empty in the store) |
| **2. Retrieval recall** (hybrid; 417–1,639 candidates per claim, median 781.5) | claim-level R@K | @10 0.251 · @20 0.383 · @50 0.563 · **@100 0.671** · @200 0.850 · @300 0.922 · @500 0.964 · @all 1.000 |
| | doc-level R@K (n = 305 docs) | @10 0.148 · @100 0.505 · @200 0.692 · @300 0.787 · @500 0.872 |
| | BM25 claim-level | @100 0.599 · @300 0.850 |
| | MiniLM claim-level | @100 0.701 · @200 0.904 · @300 0.940 |
| **3. Candidate-pool coverage** | hybrid top-100 = ceiling for any reranker | 112/167 = **0.671**. 55 claims are lost before reranking. |
| **4. Authority classification** (proxy) | LLM top-1 / top-3 publisher matches *any* gold publisher | 56/192 = 0.292 / 75/192 = 0.391 **[FROZEN]**. **True authority accuracy cannot be measured**: there are no human authority labels, and the target includes news and fact-check publishers. |
| **5. Final ranking** | claim R@10 and fraction of the pool ceiling (R@10 / 0.671) | A 42/167 = 0.251 (0.375) · B 0.263 (0.393) · C 0.275 (0.411) · **D 49/167 = 0.293 (0.438)** |

Dev set (n = 99, same definitions): collection 99/119; pool coverage 71/99 = 0.717; D R@10 34/99 = 0.343, which is 0.479 of the ceiling.

**Qualifications**
- The historical top-100/200/300 coverage figures (0.671 / 0.850 / 0.922) come from a **transcript-reconstructed, partly verified** report [RECON] (`storage/recovery_staging/bottleneck_analysis/...` around L246–252). They remain labelled reconstructed.
- The new measurement from the frozen full hybrid rankings **independently gives the same three values**. That is a consistency check, not a re-validation of the rest of the reconstructed report.
- All of these are **evidence-recall** ceilings against AVeriTeC gold, not authority ceilings.
- They are measured inside AVeriTeC's pre-built per-claim store, which was built partly from gold-derived queries. Open-web recall would be lower.
- **Interpretation:** the system reaches about 44% of what reranking the top-100 could reach. Raising the pool from 100 to 300 lifts the ceiling from 0.671 to 0.922, but triples the candidates to score and to annotate.
- No reserved-gold scoring was run.

## 9. Applicability across three domains

**No domain-specific validation has been conducted.** The claim examples below are real AVeriTeC held-out claims, used as illustrations. Their R@K values are single-claim observations.

### 9.1 Health and medical misinformation
- **Example:** claim 89, "Most deaths in the 1918 influenza pandemic originated from bacterial pneumonia caused by face masks." D's predicted authorities: NIAID/NIH and the *Journal of Infectious Diseases*. Best gold rank 21 → 10.
- **Authoritative documents:** the original study (journal article or PubMed record), the health agency's own guidance (WHO, CDC, NHS, ICMR), regulator decisions (FDA, EMA, CDSCO), trial registries.
- **Why credibility is not enough:** a credible newspaper reporting the study is still secondary. A `.gov` health page on a different disease is credible but not authoritative for this claim. Credible outlets also often mis-summarise studies.
- **How the module helps:** it identifies *which* study or agency holds the fact and prefers that document among relevant ones. The earlier finding that science and health claims had the weakest LLM authority accuracy (top-1 0.25, n = 71, AI-labelled target; `docs/authority_resolution_study.md`) is why a document-level learned model is needed.

### 9.2 Government, public policy and civic information
- **Examples:**
  - claim 268, executive order on pre-existing conditions. The legal text on the White House archive is first-hand; a Senate committee press release is credible but partisan commentary. Best gold rank 28 → 1 under D.
  - claim 328, "24 of every 100 kids in US schools speak Spanish". The National Center for Education Statistics is the data producer. 43 → 3.
- **Authoritative documents:** the Federal Register or gazette, the legislature's bill text, the statistics office release, the election commission, court records.
- **Why credibility is not enough:** many government domains are credible, but only the *issuing* body is authoritative. Jurisdiction matters too: a UK `.gov.uk` page is not an authority for a US law, which is why the heuristic prior has a country rule. Generic `.gov` boosting promotes the wrong agency.
- **How the module helps:** it maps the claim's entity and jurisdiction to the issuing body (the LLM uses Wikidata context) and ranks that body's relevant document first.

### 9.3 Science, research and technology misinformation
- **Examples:**
  - claim 464, North American bison reduced to 27 individuals. Authorities: U.S. National Park Service, Fish and Wildlife Service. 18 → 1.
  - claim 326, "COVID-19 was developed as a bioweapon". The predicted authority (US intelligence community) was boosted, but gold moved 24 → 28. This is a failure case.
- **Authoritative documents:** the peer-reviewed paper or preprint, the data repository, the agency or space-agency mission page, the standards body (for technology claims such as 5G), the company's own technical documentation.
- **Why credibility is not enough:** a university domain is credible but may host an unrelated department's page. Contested claims often have *no single authority*: the LLM labelled 169 of 200 held-out claims "multiple legitimate authorities". Publisher-level boosting then promotes many off-topic documents from a broad publisher.
- **How the module helps:** document-level relevance × authority (the proposed two-head model) would keep the relevant paper and drop the boosted but off-topic pages. Claim 326 shows that the current binary prior cannot do this.

## 10. Demo instructions

1. Open a terminal in the project folder: `cd C:\Users\Lenovo\Downloads\capstone\Source_Aware_Misinformation_Detector`
2. Run `python experiments/esa_nov2026/demo.py --list` to show the suggested claims.
3. Run `python experiments/esa_nov2026/demo.py --claim-id 268`. This takes about 25 s and needs no network. Open `results/esa_nov2026/demo/claim_268.html` in a browser.
4. Optional, slower (about 2 min): `--live` recomputes BM25 and MiniLM now; `--query "<text>"` retrieves for a custom query over that claim's documents (the LLM prior is then intentionally unavailable).
5. **Fallback if the live terminal fails:** the pre-generated `results/esa_nov2026/demo/claim_{268,436,2,89,328,464,326}.html` and `.md` files are genuine outputs. Screenshot them; do not edit them.

Full talk track: `docs/ESA_DEMO_SCRIPT.md`.

## 11. Known failures and limitations

- No human authority labels, so no supervised authority model and no true authority-accuracy measurement.
- The LLM authority prior's gain is directional and not significant (p = 0.167). D loses on best-gold rank for 52 of 167 claims.
- Binary publisher-level boosting promotes documents with low relevance scores (§4). There is also a brittle heuristic: `abcnews.go.com` is treated as government.
- The top-100 pool caps any reranker at 0.671 (held-out). Collection loss is 25 of 192 claims and 117 of 422 gold URLs empty.
- AVeriTeC gold includes secondary pages, so evidence recall is not authority recall.
- Retrieval runs only inside AVeriTeC's pre-built store, which was built partly from gold-derived queries. There is no open-web evaluation.
- New [NEW-EXPL] numbers use sets already used in the frozen study. They are descriptive, not a fresh test.
- The reserved-180 outputs (v2 Steps 10–11) are lost. Steps 12–15 were never run.
- The PU relevance baseline (trained on weak citation proxies, n_test = 42) did **not** improve over Hybrid RRF on the primary metric, Recall@10 (12/42 vs 13/42). Some secondary metrics were higher (R@1, MRR) but are exploratory and untested. The selected model overfits its training claims (§7.1). Its labels are a proxy, and SCAR is likely violated.
- Live retrieval takes about 2 min per claim on CPU.

## 12. Work remaining before 16 November

| # | Item | Needs |
|---|---|---|
| 1 | ~~R2 extraction~~ **done 2026-11-08** (owner-approved) | — |
| 2 | ~~R3 PU relevance baseline~~ **done 2026-11-08**: negative result (§7.1). Optionally add one demo slide with the test table | Team |
| 3 | Update Review-2 slides: reserved-180 predictions "executed, output lost"; demo now on held-out claims; cite the frozen held-out results | Team |
| 4 | Take screenshots of the demo HTML pages (claims 268, 436, 2) | Team |
| 5 | Rehearse the 10-minute demo (`docs/ESA_DEMO_SCRIPT.md`) | Team |
| 6 | Mentor approvals listed in `RESEARCH_PROPOSAL_INFORMATION_PACKAGE.md` §13 (label scheme, pool depth, annotation plan) | Mentor |
| 7 | Optionally commit `experiments/esa_nov2026/` and the docs (selected paths only, never `git add .`) | Your decision |

## 13. Exact commands to reproduce

```bash
cd C:/Users/Lenovo/Downloads/capstone/Source_Aware_Misinformation_Detector
python experiments/esa_nov2026/reproduce_check.py            # hash gate + re-scoring (~5 min)
python experiments/esa_nov2026/reproduce_check.py --live 3   # + live BM25/MiniLM/RRF for 3 claims per split (~10 min)
python experiments/esa_nov2026/demo.py --list
python experiments/esa_nov2026/demo.py --claim-id 268        # frozen rankings (~25 s)
python experiments/esa_nov2026/demo.py --claim-id 268 --live # recompute retrieval (~2 min)
python experiments/esa_nov2026/demo.py --claim-id 268 --query "Trump executive order protects people with pre-existing conditions"
python experiments/esa_nov2026/authority_promotion_stats.py  # binary-boost statistics (~5 min)
python experiments/esa_nov2026/recall_ceiling.py             # stage-wise recall (~5 min)

# --- Relevance baseline (AVeriTeC train sample; NOT authority) ---
python experiments/esa_nov2026/relevance_baseline/make_train_split.py            # R1 (already run; refuses to overwrite)
# R2 network step, ALREADY RUN with owner approval -- do not re-run without new approval:
#   python experiments/esa_nov2026/relevance_baseline/extract_train_ks_sample.py --approved
python experiments/esa_nov2026/relevance_baseline/verify_extraction.py           # offline re-check of the 300 files
python experiments/esa_nov2026/relevance_baseline/verify_unlabelled_sampling.py  # PU sampling determinism (~1 min)
python experiments/esa_nov2026/relevance_baseline/train_relevance.py --synthetic # code smoke test only (fake data)
HF_HUB_OFFLINE=1 python experiments/esa_nov2026/relevance_baseline/train_relevance.py --tag run2_pu_repro
#   ~2 h 20 min on an 8-core CPU (25.9 s per claim). Writes to results/esa_nov2026/relevance_baseline/<tag>/.
#   The script refuses to overwrite an existing report; run1_pu is the recorded run.
```

## 14. Files created or modified

**Modified:** none. No tracked or frozen file was changed.

**Created**
- **Code:**
  - `experiments/esa_nov2026/`: `esa_common.py`, `reproduce_check.py`, `demo.py`, `authority_promotion_stats.py`, `recall_ceiling.py`
  - `experiments/esa_nov2026/relevance_baseline/`: `rb_common.py`, `make_train_split.py`, `extract_train_ks_sample.py`, `verify_extraction.py`, `verify_unlabelled_sampling.py`, `features.py`, `train_relevance.py`
- **Outputs (`results/esa_nov2026/`):**
  - `reproduction/reproduction_check.json`
  - `recall_ceiling/recall_ceiling.json`
  - `authority/promotion_stats.json`, `authority/per_claim.csv`
  - `demo/claim_{2,89,268,326,328,436,464}.{html,md,json}`, `demo/claim_268_live.*`, `demo/claim_268_query.*`
  - `relevance_baseline/train_sample_split.json`
  - `relevance_baseline/EXTRACTION_MANIFEST.{json,md}`, `extraction_log.jsonl`, `extraction_stdout.log`, `unlabelled_sampling_check.json`
  - `relevance_baseline/run1_pu/`: `relevance_baseline_report.json`, `per_claim.csv`, `unlabelled_samples.json`, `models/*.joblib`, `run_stdout.log`, `feature_cache/`
  - `relevance_baseline/SYNTHETIC_SMOKE_TEST/relevance_baseline_report.json` (synthetic, not a result)
- **Data (outside the repo, per the storage rule):** `capstone/storage/datasets/averitec_train_ks_sample/` (300 files, 1.2 GB)
- **Docs:** `docs/ESA_IMPLEMENTATION_AND_EXPERIMENT_REPORT.md`, `docs/ESA_DEMO_SCRIPT.md`, `docs/ESA_PROPOSED_AUTHORITY_MODEL_ARCHITECTURE.md`
