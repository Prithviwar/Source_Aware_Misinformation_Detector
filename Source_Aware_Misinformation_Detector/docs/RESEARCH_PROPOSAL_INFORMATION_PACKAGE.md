# Research Proposal Information Package

**Project:** Source-Aware Misinformation Detection (Project A, team IR_03, PES University, B.Tech CSE AI & ML, Capstone Phase-I Review 2)
**Prepared:** 2026-11-07, by Claude Code, from a read-only inspection
**Purpose:** evidence-based input for writing the research proposal. **This file is not the proposal itself.**

> ### Instructions for the proposal writer (ChatGPT)
> 1. Every proposed item in this package is **proposed, not done**. Do not describe proposed work as completed.
> 2. Keep each label below with its claim. Do not upgrade a *historical* or *reconstructed* number to "verified".
> 3. **No supervised authority model exists, and no human authority labels exist.** Do not imply otherwise.
> 4. Project B (`first_hand_authority_model`) is a separate project. Do not include its work or numbers as Project A results.
> 5. Distinguish **document relevance**, **publisher credibility** and **claim-specific authority**. Also distinguish **retrieval recall** from **authority-classification recall**.
> 6. LLM (Claude) outputs are never human ground truth. AVeriTeC evidence URLs are fact-checker citations, not authority labels.
> 7. §15 lists unknowns. Do not fill them with guesses.

## Evidence labels

| Label | Meaning |
|---|---|
| **[V-FILE]** | Verified by reading a current project file. The path and line are given. |
| **[V-CODE]** | Verified by reading source code, which was not executed. |
| **[HIST]** | A number recorded in a frozen project result or document. Not recomputed in this inspection. |
| **[RECON]** | From a file rebuilt from Claude transcripts after the 2026-11-06 deletion. Only partly verified. |
| **[EXT]** | Verified on an external web page during the research conversation of 2026-11-07. URLs are in §14. |
| **[REC]** | A research recommendation from the assistant. It needs approval. |
| **[EST]** | An estimate. It is not a measurement. |
| **[UNKNOWN]** | Cannot be verified. Listed in §15. |

**Path abbreviations.** `P/` = `C:\Users\Lenovo\Downloads\capstone\Source_Aware_Misinformation_Detector\`. `S/` = `C:\Users\Lenovo\Downloads\capstone\storage\`. `L` = line number(s).

---

## 1. Executive Summary

- **What exists [V-FILE/V-CODE]:**
  - offline evidence retrieval over AVeriTeC's per-claim knowledge store: BM25, dense MiniLM, and Hybrid RRF;
  - three non-learned authority signals: a generic credibility prior, a heuristic claim prior, and an LLM (Claude Opus 5.5) top-3 publisher predictor with Wikidata context;
  - a **frozen, preregistered held-out evaluation** on 200 AVeriTeC dev claims, of which 167 have gold that can be scored;
  - the finished paper of that study (`P/AUTHORITY_RETRIEVAL_PAPER_SUBMISSION_FINAL.md`; README L5–7).
- **Main historical result [HIST]:** the LLM authority prior (D) improved Recall@10 over hybrid (A) from 0.251 to 0.293, but this was **not statistically significant** (exact McNemar p = 0.167; README L134, L146).
  - Here, Recall@K means the share of claims with at least one human-gold document in the top K.
- **Where recall was lost [RECON]:**
  - collection (33 of 200 claims had no reachable gold);
  - candidate generation (55 of 167 had gold outside the hybrid top-100);
  - ranking (63 of 167 for D).

  Re-ranking only the top-100 is capped at about 0.671. Historical coverage at top-300 was 0.922.
- **What does not exist [V-FILE]:**
  - a trained supervised authority model;
  - any human claim-specific authority labels. The human annotation protocol was designed but "**NOT executed**" (`P/data/annotations/heldout_primary_package/README.md` L4).
- **Authority-v2 (follow-up study) [RECON]:**
  - Steps 1–11 were executed on 2026-10-28 to 11-01. Step 10 was retrieval on the reserved 180 claims; Step 11 was LLM predictions for them.
  - **Their outputs were lost** in the 2026-11-06 deletion.
  - Steps 12–15 (scoring with sealed gold) were never run.
- **Dataset gap [EXT/V-FILE]:** no dataset examined provides human, claim-specific authority labels for **web documents**.
  - AVeriTeC gives real claims and source URLs.
  - NELA-GT-2020 and MBFC give publisher-level credibility only.
  - AuFIN and AuRED give claim-specific authority for Arabic (and, for AuRED, English) **Twitter accounts and tweets**.
- **Agreed direction:** a supervised, claim-specific, **document-level** authority model, trained on a new human-annotated label layer over AVeriTeC **train** claims, evaluated stage by stage against an empirical recall ceiling.
- **Important for Review 2 [V-FILE]:** the Review-2 slides (`C:\Users\Lenovo\Downloads\CapstoneProject_IR_03.pptx`, dated 2026-11-04) describe reserved-180 work and a demo that **depend on files that are now missing**. See Appendix A.

---

## 2. Verified Current Project Status

### 2.1 Retrieval [V-CODE]

| Component | Implementation | Evidence |
|---|---|---|
| Corpus | Per-claim AVeriTeC knowledge store. Deduplicated by normalised URL. Empty-text documents dropped. Shuffled with seed 2026. The retriever sees only `{url_norm, text}`. | `P/experiments/baseline_retrieval.py` L1–24, L40–57 |
| BM25 | `bm25s`, English stop words, full text. The query is the claim text. | same file, L60–68 |
| Dense | `sentence-transformers/all-MiniLM-L6-v2`, frozen (not fine-tuned), first 1,000 characters, `max_seq_length` 128 | same file, L77–87 (L82–83) |
| Hybrid | Reciprocal Rank Fusion, k = 60, over the full BM25 and dense lists | same file, L103–109; README L67 |
| Rerank pool | Hybrid top-100 (`POOL = 100`), λ = 1.0 | `P/experiments/validation_heldout.py` L38–45, L286–288 |

### 2.2 Authority-resolution components [V-CODE]

| Component | What it does | Evidence | Used in |
|---|---|---|---|
| Generic credibility prior | Scores the URL type only: gov/intergov 1.0, academic 0.8, major news 0.6, reference 0.5, unknown 0.3, platform 0.2. Ignores the claim. | `P/experiments/authority_retrieval.py` L79–91 | System B |
| Heuristic claim prior | 1 if the domain or handle matches a spaCy entity of the claim or speaker, or is a government domain of the claim's country | same file, L151–165 | System C |
| LLM authority predictor ("L+Wctx") | `claude -p`, model `claude-opus-5-5`, no tools or web. Inputs: claim, speaker, date, country, Wikidata facts. Output: top-3 publishers (domain or social account), claim kind, confidence. | `P/experiments/authority_resolution.py` L44, L54–79, L120–135 | Systems D, E, F, G |
| Wikidata lookups | Official websites (P856) and social handles of claim entities | `P/experiments/wikidata_authority.py`; `P/docs/authority_resolution_study.md` L23–30 | Dev study only |
| Rerank rule | `minmax(hybrid score in pool) + λ·prior`, λ = 1. The prior is **binary** at publisher level. | `authority_retrieval.py` L168–176 | B, C, D, G |
| Pool-grounded resolver T (authority-v2) | The LLM selects at most 3 publishers from those present in the pool, or abstains | `P/experiments/authority_v2/t_resolver.py` L1–16; `P/docs/authority_v2_preregistration.md` L80–103 | v2 dev only. Reserved scoring not run. |

**Key design fact [RECON].** The prior is 0 or 1, and the min-max score lies between 0 and 1. So every boosted document outranks every non-boosted one, and D acts as a hard publisher filter (`S/recovery_staging/bottleneck_analysis/files/docs/authority_resolution_bottleneck_analysis.md`, §1.4, about L115–125). The LLM's confidence and claim-type outputs are not used by D (same report, §1.2).

### 2.3 Experiments genuinely completed (outputs present in `P/results/`) [V-FILE]

| Experiment | Status | Evidence |
|---|---|---|
| Dataset audit (AVeriTeC) | Done | `P/docs/dataset_audit.md` |
| Development-sample retrieval and priors (120 dev claims) | Done, exploratory | `P/docs/experiment_results.md` §1–8; `P/results/retrieval_summary.json` |
| Authority-resolution study (LLM vs Wikidata, n = 71) | Done, exploratory. The target labels were AI-generated. | `P/docs/authority_resolution_study.md` L21–39, L64 |
| Frozen held-out evaluation, systems A–H (200 claims) | **Done, preregistered** | README L62–75, L127–156; `P/results/source_targeted/results_heldout.json`; `P/results/heldout/validation_heldout.json` |
| Memorisation probe (held-out) | Done | README L194–197; `P/results/memorisation_probe/` |
| AI-labelled primary-evidence endpoint (n = 72) | Done, exploratory, **AI labels** | README L104–112, L162–170 |
| Authority-quality ablations, Phase 1 and 2 | Done, exploratory | README L211–228 |

### 2.4 Historical, reconstructed, incomplete or unverified

| Item | Status | Evidence |
|---|---|---|
| Authority-v2 code (21 `.py` files, prompts, config) | In the repo. Rebuilt from transcripts. Most files are hash-verified exact. | `S/recovery_staging/authority_v2/RECOVERY_MANIFEST.md` L27–58 |
| v2 decision log | **Partly verified** (file name says so) | `P/docs/authority_v2_decision_log.PARTIALLY_VERIFIED.md`; manifest L56 |
| v2 progress report, Steps 1–9 | **Unverified**. Written 2026-11-01. It states that Step 10 "has not been run", which later events superseded. | `P/docs/authority_v2_progress_report_steps1-9.UNVERIFIED.md` L1–7 |
| v2 Step 10: BM25, dense and hybrid rankings on reserved 180 claims (139,397 documents; min 443 / median 758 / max 1,689 per claim) | **Executed 2026-11-01. Outputs MISSING.** | Execution-log excerpt `S/recovery_staging/evidence_package/execution_log_TRANSCRIPT_EXCERPT_NOT_ORIGINAL.json` L744–767; manifest L84 |
| v2 Step 11: LLM (D) predictions, 180/180 parsed, USD 4.19 | **Executed 2026-11-01. Output MISSING** (sha `86b2840c…`) | Same excerpt, L826–827; manifest L77 |
| v2 dev run T_v1 (320 claims) | Executed (DL-014). **Outputs missing.** | Decision log L93–98; manifest L80 |
| Reserved-180 knowledge-store extracts and reserved inputs file | **MISSING** | Manifest L85–86; `P/data/processed/` contains only the 120 and 200 samples |
| Reserved-180 Recall@K (v2 Steps 12–15) | **Never run.** Requires sealed gold. Not authorised. | `S/recovery_staging/evidence_package/RECOVERY_LIMITATIONS.md` items 3 and 7 |
| Bottleneck analysis (28 Oct): ceilings and decomposition | **[RECON]**, partly verified. Lines 51–856, which hold the ceiling numbers, were never independently checked. Its outputs are lost. | `S/recovery_staging/bottleneck_analysis/README.md` |

### 2.5 Direct answers to the status questions

1. **Implemented:** retrieval (BM25, dense, hybrid), three authority priors, an LLM predictor, source-targeted retrieval, evaluation scripts, an annotation-package builder and AI annotation [V-CODE].
2. **Retrieval methods implemented and evaluated:** BM25, MiniLM dense and Hybrid RRF, evaluated on 120 dev claims and 200 held-out claims [V-FILE]. On the reserved 180 they were run historically, but no evaluation was done [RECON].
3. **Authority components:** see §2.2.
4. **Experiments completed:** see §2.3.
5. **Verifiable results:** the frozen held-out tables in README L127–156, backed by result files in `P/results/` [HIST, files present].
6. **Historical, reconstructed or missing:** see §2.4.
7. **Supervised authority model:** **none** [V-FILE]. The repository has no training code for an authority classifier. Slide 8 of the Review-2 deck also says "Supervised authority prediction model… PROPOSED / FUTURE WORK".
8. **Human claim-document authority labels:** **none** [V-FILE]. `heldout_primary_package/README.md` L4 says "NOT executed; no human labels exist". `docs/authority_resolution_study.md` L64 says the human second annotation is "PENDING". `second_annotator_guidelines.md` L1–4 says "No human second annotation was obtained".
9. **Planned but not started:** human annotation (pilot and main), the supervised model, v2 Steps 12–15, the proposed controlled ablation (bottleneck report §6 says "not started").
10. **Technical limitations:** see §12. Main ones:
    - top-100 pool cap;
    - empty or missing gold documents;
    - publisher-level binary boosting;
    - no human labels;
    - LLM memorisation risk;
    - CPU only, about 20 GB free disk.

---

## 3. Completed Work vs Proposed Work

| Area | Completed | Proposed (not started) |
|---|---|---|
| Retrieval | BM25, MiniLM, Hybrid RRF on dev and held-out [V-FILE] | Scoring a deeper pool (e.g. top-300) [REC] |
| Authority | Heuristics and a zero-shot LLM predictor; frozen held-out evaluation | **Supervised claim-specific document authority model** |
| Labels | AI-generated role labels (Claude); AVeriTeC human evidence URLs | **Human relevance and authority labels** for claim-document pairs |
| Annotation design | Claim-level blind guide; per-URL role guidelines (both unexecuted) | Adapted two-output scheme; pilot; double annotation of the test set |
| Evaluation | Recall@K, MRR, pool coverage; McNemar, bootstrap, Holm | Stage-wise ceiling against human authority labels; Authority Recall@K |
| Datasets | AVeriTeC dev (used); train audited at schema level only | AVeriTeC train sample, knowledge-store extraction for the sample only |

---

## 4. Existing Datasets and Their Suitability

| Dataset | Content and size | Claim-document pairs? | Human claim-specific authority labels? | Credibility labels? | Licence | Suitability | Evidence |
|---|---|---|---|---|---|---|---|
| **AVeriTeC** | 4,568 real claims from 50 fact-checking organisations. Train 3,068, dev 500, test 2,215 (labels hidden). QA evidence with `source_url`. Per-claim knowledge store. | **Yes**: claim → evidence URL; knowledge-store documents | **No** | No | CC BY-NC 4.0 | **Primary base** for claims, candidate documents and text | [V-FILE] `P/docs/dataset_audit.md` L20–28, L49–61; `P/data/raw/averitec/README.md` L2; [EXT] NeurIPS paper, GitHub |
| **NELA-GT-2020** | 1,779,127 articles, 519 sources, 2020; source-level MBFC reliability (reliable / mixed / unreliable) | No | No | **Publisher-level only** | **[UNKNOWN]**: the Dataverse page did not load | Optional auxiliary credibility *feature* only | [EXT] arXiv 2102.04567; slide 6 |
| **AuFIN** (IP&M 2023) | 150 Arabic rumours, 1,044 authority accounts, pool of 395,231 accounts | Rumour → account | **Yes, but for Twitter accounts** | No | Not stated on the task page | Concept and metric model only (P@5, nDCG@5) | [EXT] QSpace record; CheckThat! 2023 Task 5 page |
| **CheckThat! 2023 Task 5** | AuFIN-based. Best P@5 0.260 vs BM25 0.087. | Same | Same | No | Not stated | Shows the task is hard; hybrid signals help | [EXT] |
| **AuRED / CheckThat! 2024 Task 5** | 160 rumours, 692 authority timelines (about 34k tweets), tweet-level evidence. Arabic, plus English in 2024. | Rumour → authority tweets | Authorities given; evidence labelled | No | Public GitHub; licence [UNKNOWN] | Design reference (R@5, MAP). Domain mismatch with web documents. | [EXT] ArabicNLP 2024; task page |
| **Wikidata** | Entities, official sites (P856), handles | No | No (a reference ≠ authority) | No | CC0 (stated in the project's literature review) | Entity → official-domain features (already used) | [V-FILE] `P/docs/00_literature_review_and_research_plan.md` L272; slide 11 |
| **Baly et al. 2018 (MBFC)** | 1,066 news sites, factuality (3 levels) and bias (7 levels) | No | No | Publisher-level | Repository public; licence [UNKNOWN] | Credibility feature only | [EXT]; slide 12 ref [8] |
| **Lin et al. 2023** | About 11.5k domains, PCA aggregate of 6 rating sets | No | No | Domain-level | "license unclear, **verify**" | Credibility feature with wider coverage | [V-FILE] lit review L147, L288; [EXT] |
| **PrimeFacts** (LREC 2026) | 13,106 PolitiFact articles, 49,718 hyperlinks; LLM-rewritten premises | Fact-check → cited URL | **No** | No | CC BY-NC 4.0, gated | Optional extra *weak* pairs only | [EXT] |
| **MultiFC, FEVER, LIAR, Fakeddit** | Discussed in the literature review | Snippets, Wikipedia, or none | No | No / speaker priors | Various ("verify") | Not suitable | [V-FILE] lit review L302–317 |

**Conclusion [V-FILE + EXT].** The project's own Review-2 slide 6 states the gap: "none labels which source is authoritative for a specific claim". The external check confirms it for web documents.

---

## 5. Research Gap

1. **No human claim-specific document authority labels exist** for web evidence. AVeriTeC labels evidence for verdict support. NELA and MBFC rate publishers. AuFIN and AuRED cover Twitter accounts. [V-FILE slide 6; EXT]
2. **Current authority methods are publisher-level and binary.** As a result they promote irrelevant pages from predicted publishers: at least 5 such pages in the top-10 for 19 claims under D and 68 under G [RECON, report §3.11]. They also cannot pick out the right document within a publisher.
3. **Zero-shot LLM identification is often wrong.**
   - Top-3 publisher accuracy against all gold publishers was 0.391 (n = 192) [HIST, README L159–160].
   - For 102 of 167 claims, no predicted publisher matched [HIST, README L178].
   - Science and health claims are the weakest (top-1 0.25, n = 71, AI-labelled target) [V-FILE, `authority_resolution_study.md` L38].
4. **The evaluation target is mismatched.** AVeriTeC gold includes news and fact-check pages. In 54 of 167 claims, all reachable gold is secondary [RECON §3.1]. So human-gold recall cannot measure authority.
5. **The candidate pool caps recall.** Re-ranking the top-100 cannot exceed about 0.671 [RECON L199; HIST README L131, pool coverage].

---

## 6. Recommended Methodology [REC unless marked]

1. **Unit of prediction:** one (claim, candidate document) pair, with **two outputs**: relevance and authority role. Rank by a combination tuned on development data only.
2. **Candidates:** BM25, dense and hybrid as implemented (§2.1). Investigate **hybrid top-N with N up to about 300**.
   - Historical coverage: top-100 0.671, top-200 0.850, top-300 0.922 [RECON, report L246–252].
   - Full BM25 and dense rankings are already computed per claim in the existing pipeline [V-CODE, `baseline_retrieval.py` L130–134, `top_n=None`].
3. **Document extraction:** stream only the sampled train claims' knowledge-store members with HTTP range requests. This is the same method used for dev (`P/docs/dataset_audit.md` L15; `P/experiments/extract_knowledge_store.py`). It needs approval and a storage preflight (§11).
4. **Preprocessing:** reuse the frozen `normalize_url`, `cand_key` (publisher key), deduplication and seeded shuffle [V-CODE, `P/experiments/common.py`; `baseline_retrieval.py` L40–57].
5. **Integration:** replace the binary publisher prior (`authority_retrieval.rerank`, L168–176) with model scores over the chosen pool, behind a flag. Keep publisher-level aggregation (maximum document score per publisher) as an optional input to source targeting.
6. **Status of existing requirements:**

| Requirement | Already documented? | Needs decision? |
|---|---|---|
| Candidate collection and retrieval | Yes (code, README) | Pool depth |
| Extraction method | Yes (range requests; dev precedent) | Approval, storage |
| Pair construction | No | Sampling sources and pairs per claim |
| Relevance annotation | No (only per-URL role labels exist) | Label scheme |
| Authority annotation guide | Partly: `ANNOTATION_GUIDE.md` (claim-level, blind) and `second_annotator_guidelines.md` (per-URL roles) | Adapt to two outputs |
| Annotator blinding | Yes, in the existing guide §6 L108–126 | Extend to document level |
| Splits | No (train split unused so far) | Train/validation/test sizes |
| Leakage controls | Yes for retrieval (`experiment_results.md` §2 L30–56) | Extend to model features and annotators |
| Model selection | No | M1–M4 scope |
| Baselines | Yes (A–G definitions, README L62–75) | Whether D needs new LLM calls |
| Metrics and statistics | Yes (R@K, MRR, McNemar, bootstrap, Holm in `validation_heldout.py` L286–320) | Primary endpoint |
| Integration | No | Supplement vs replace v2 |

---

## 7. Proposed Dataset and Annotation Design [REC]

### 7.1 One example = one claim-document pair

| Field group | Fields | Source |
|---|---|---|
| **Automatically available metadata (model inputs)** | Claim text, claim date, speaker, country ISO (all present even in the AVeriTeC test release: `dataset_audit.md` L28); spaCy entities; Wikidata facts; normalised URL; publisher key; registered domain; **automatically derived source type** (e.g. the `generic_prior` bucket, PDF flag, gov suffix); document text; BM25, dense and hybrid scores and ranks; publisher document count in the pool | Code and data, no human input |
| **Optional automatic features** | LLM predicted-publisher match (needs new LLM calls); NELA/MBFC/Lin credibility score | Needs approval |
| **Human annotation labels (targets)** | Relevance (relevant / partial / not relevant / cannot determine); authority (primary / authoritative secondary / secondary-derivative / not authoritative / cannot determine); confidence; rationale; `empty_or_broken` flag | Annotators |
| **Excluded (leakage)** | See §10 | — |

Note: the AVeriTeC knowledge store has **no title, date or domain metadata** (`dataset_audit.md` L98). Publisher and source type must therefore be derived from the URL. AVeriTeC `source_url` has "No publisher name, no date, no source type" (L57).

### 7.2 Labels
- Use the definitions from the earlier research conversation, consistent with the "primary" definition in the existing guide (`ANNOTATION_GUIDE.md` §2, L16–32).
- "Authoritative secondary" = independently holds or validates the fact, or is an official body republishing primary information with attribution.
- **A document counts as an authority hit only if it is relevant (or partly relevant) AND labelled primary or authoritative secondary.** Whether partial relevance counts needs mentor approval.
- Multiple valid authorities are allowed (existing guide §3, L34–44).

### 7.3 Annotation process
- **Pilot:** about 20 claims, two annotators, guide revised, then frozen.
- **Test set:** **two independent annotators on every pair**, with adjudication by a third person.
- **Training set:** about 20% double-annotated for agreement (Cohen's κ or Krippendorff's α). The rest single-annotated.
- **Candidate sampling per claim:** AVeriTeC gold URLs, hybrid top-10, deeper ranks (11–N), documents from predicted publishers, and random documents. Present them in random order.
- **Annotators must not see:** gold status, LLM outputs, system ranks, AVeriTeC questions and answers, justification, verdict label, or the fact-checking article. They must not search for the claim (existing guide §6, L117–126).

---

## 8. Model and Baseline Recommendations [REC]

| Model | Role | Data need | Compute |
|---|---|---|---|
| M1 Logistic regression on engineered features | Interpretable baseline | Hundreds of pairs | CPU |
| M2 Gradient boosting (LightGBM / XGBoost; LambdaMART later) | Main model | About 1k pairs | CPU |
| M3 Frozen MiniLM embeddings added as features | Text signal without fine-tuning | Same | CPU; model cached locally |
| M4 Fine-tuned cross-encoder, two heads | Stretch goal | Ideally 2k+ pairs or weak-label pretraining | GPU (e.g. Colab) [EST] |
| M5 Stacking with LLM scores | Ablation | New LLM calls | API cost |

**Baselines (existing definitions, README L62–75):**
- **A:** hybrid, no authority.
- **C:** heuristic prior.
- **D:** LLM top-3 publisher prior.

They must be recomputed on the new test claims. D predictions exist only for the 120 + 200 dev claims (`P/results/authority_resolution_raw.jsonl`, `P/results/heldout/authority_raw.jsonl`). Running D on new claims needs **new LLM calls** (approval).

**Historical precedent [RECON, report L642–656]:** a supervised authority classifier is "not feasible without annotation". A LambdaMART relevance ranker trained on AVeriTeC gold "learns to find secondary pages" and should be reported as a relevance baseline, not an authority method.

---

## 9. Evaluation Plan and Metrics

### 9.1 Stages [REC]
1. Collection coverage.
2. Retrieval recall at depths 100, 200 and 300.
3. Candidate-pool recall.
4. Authority classification: per-class P/R/F1, macro-F1, PR-AUC.
5. Final ranking: Authority Recall@5/10/20, Precision@K, MRR, nDCG@10.

### 9.2 Metric definition [V-CODE]
The project's R@K is **claim-level hit rate** (`best_rank` in `validation_heldout.py` L291–295; README "R@K… share of claims with at least one reachable gold document"). Keep it for comparability, and also report document-level recall.

### 9.3 Empirical ceiling [REC]
- A\*(c) = the documents for claim c that adjudicated human labels mark as relevant AND primary or authoritative secondary.
- Ceiling at each stage = the share of test claims whose A\*(c) survives to that stage.
- Report each system as achieved recall ÷ ceiling.
- The ceiling is a **lower bound**, because only sampled documents are judged. Report the number of unjudged documents in each system's top-10.

### 9.4 Assessment of the proposed design choices (not silently approved)

| Proposed choice | Supported by evidence? | Assumptions and risks | Needs approval? |
|---|---|---|---|
| **Primary comparison: supervised model vs existing LLM prior (D)** | D is the best deployable historical system on R@10 (README L134), and D vs A was the preregistered primary test (L146), so it is a meaningful bar. | (a) D on new train-split claims needs **new LLM calls**. (b) D was defined on the top-100; if the model scores the top-300, D must be run on the same pool or the comparison confounds pool depth with method. Report both. (c) A fallback primary comparator that needs no LLM calls is C (heuristic) or A. | **Yes** |
| **Primary metric: Authority Recall@10** | R@10 was the previous primary endpoint (README L146). | Claims with empty A\*(c) leave the denominator; report their count. The hit definition depends on the relevance gating rule. | **Yes** |
| **Deeper pool, about top-300** | Historical coverage 0.922 at 300 vs 0.671 at 100 [RECON] | Coverage was measured against AVeriTeC gold, not authority labels; it must be re-measured. More candidates also mean more annotation and more distractors. | **Yes** |
| **Two annotators on every test pair** | Standard practice. The existing package planned "two if possible" (`heldout_primary_package/README.md` L33). | Workload (§11) | **Yes** (resources) |
| **About 20% double annotation of training pairs** | Common practice [REC]; not documented in the project | The κ estimate may be noisy if the sample is small | **Yes** |
| **Adjudication** | Not documented | Needs a named adjudicator | **Yes** |
| **Claim-level split** | Necessary because pairs from the same claim share context | Near-duplicate or same-event claims across train and test are possible and not checked **[UNKNOWN]**. Consider grouping by event or fact-check article. | **Yes** |
| **AVeriTeC train split only** | Dev is fully allocated: 120 + 200 + 180 = 500 (README L86–90; preregistration §3.3). Train has labels and QA (`dataset_audit.md` L24). | The train knowledge store has not been inspected locally. Its construction is assumed to match dev **[UNKNOWN]**. | **Yes** |
| **Separate stage measurement** | Consistent with the historical decomposition [RECON §2.4] | — | Confirm |
| **Statistics** | McNemar, bootstrap CI and Holm are implemented (`validation_heldout.py` L297–320) | About 50 test claims detect only large effects. The historical D vs A gain (+0.042, n = 167) was not significant. | **Yes** (test size) |

---

## 10. Leakage and Bias Controls

### 10.1 Never used as model input; hidden from annotators

| Field or signal | Why | Evidence |
|---|---|---|
| AVeriTeC `questions`/`answers`, `justification`, `label`, `fact_checking_article` | They reveal the gold evidence and verdict | `dataset_audit.md` L30–61 |
| Gold-URL indicator | It is the target of the earlier evaluation | — |
| Knowledge-store `type` field | "`gold` marks the annotators' evidence documents: a label leak" | `dataset_audit.md` L93 |
| Knowledge-store `query` field | "Often a gold question verbatim: also a leak" | `dataset_audit.md` L94 |
| Knowledge-store file order | "Gold-typed documents are stored *first*" (mean relative position 0.001) | `experiment_results.md` L34 |
| Raw archive-wrapped URLs | 32% of gold URLs are archive-wrapped vs 2.2% of others | `experiment_results.md` L35 |
| `original_claim_url`, `cached_*` URLs | Link to the claim artifact or archives | `dataset_audit.md` L40–41, L58 |

### 10.2 Additional leakage and bias risks supported by the project
- **Hand-written domain lists can encode gold.** "Prior-list contamination… lists overlap sample gold domains" (`experiment_results.md` L249–263). Any curated feature list must be built without looking at test gold.
- **Pool statistics correlate with gold.** "The KS was built partly from gold-derived queries, so pool publishers and counts correlate with gold" (`authority_v2_preregistration.md` L199). Features such as publisher document count may partly encode gold. Measure this, and ideally ablate it.
- **LLM memorisation:** "the model may have memorised the 2020 claims" (preregistration L200). The memorisation probe found reliance on named entities but could not rule out memorisation (README L194–197).
- **Orchestrator exposure:** the earlier study notes that the orchestrating session had seen gold domains (`authority_resolution_study.md`, leakage controls). Keep any new LLM calls in isolated contexts, as before.
- **AI-label circularity:** the AI annotator and the predictor share a model family (README L189–193). Do not use AI labels as targets.
- **Annotator leakage:** searching the claim online finds the fact-check. The existing guide forbids it (L117–126).

### 10.3 Knowledge-store construction and gold-selection bias (correction 4)
- **[V-FILE] Dev knowledge store, as inspected by the project:**
  - it contains documents with `type: gold`, which are the annotators' own evidence documents;
  - it also contains documents returned by Google queries, whose `query` is "often a gold question verbatim" (`dataset_audit.md` L85–94).
- **[V-FILE] Official README:** the organisers provide "search results for up to 1000 URLs per claim using different queries" and added PDF text (`P/data/raw/averitec/README.md` L57). The test-set knowledge store was later updated "solving the potential data leaking problem" (L11). That update applies to the test set only.
- **Project statement:** "the knowledge store itself was built by the AVeriTeC organisers partly from queries derived from the gold questions and answers, so it is already enriched with relevant pages" (README L102–103).
- **Accurate bias statement for the proposal:** the train and dev knowledge stores contain the gold evidence documents themselves, plus pages retrieved with queries derived from the gold QA. Candidate pools are therefore enriched with evidence the fact-checkers used, and publisher patterns may correlate with gold. Recall measured in this collection is likely higher than open-web recall.
- **[UNKNOWN]** That the **train** knowledge store has the same composition. Only dev was inspected.

---

## 11. Resource and Feasibility Assessment

| Resource | Known facts | Label |
|---|---|---|
| Local AVeriTeC files | `dev.json`, `train.json` (10.2 MB), `test.json`, `dev_urls.zip` present in `P/data/raw/averitec/` | [V-FILE] (listing only) |
| Local knowledge-store extracts | `ks_sample/`: 320 files (120 dev + 200 held-out), 1.4 GB | [V-FILE] (du/ls) |
| Train knowledge store | About 62 GB in 3 zips; not downloaded | [V-FILE] `dataset_audit.md` L16, L24 |
| Dev knowledge store | 11.5 GB zip; extracted by range requests for sampled claims only | [V-FILE] L15 |
| Reserved-180 knowledge store | 139,397 documents historically; **missing locally** | [RECON] manifest L85 |
| Disk | C: 244 GB total, about **20 GB free** (2026-11-07). Storage rule: data goes under `capstone\storage\` with a preflight. | [V-FILE] (df) |
| Extraction estimate | Dev precedent: 320 claims ≈ 1.4 GB → about 4.4 MB per claim. For 200 train claims, roughly **0.9 GB**. | [EST], extrapolated; train documents may differ |
| Compute | Python 3.13, CPU only (README L232). The dense encoder was slow on CPU (about 10 documents/s at 256 tokens; `baseline_retrieval.py` L5–7). MiniLM is cached locally. | [V-FILE] |
| Annotation workload | (a) The earlier bottleneck report: about 300 URLs ≈ 15–20 h at 3–4 min per URL. (b) Assistant planning estimate (2026-11-07 conversation, not from project files): **about 120–130 annotator-hours** for about 150 train + 50 test claims, with the test set fully double-annotated. | (a) [RECON, EST] report L650–652; (b) [EST] |
| Annotators | At least 2 plus 1 adjudicator. Team of 4 listed on slide 1. | [REC] |
| New LLM calls | Needed only for baseline D or LLM features on new claims. Historical costs: USD 4.19 for 180 claims (Step 11); USD 7.85 for 324 calls (v2 dev). | [RECON] log excerpt L827; decision log L95 |
| Licence | AVeriTeC CC BY-NC 4.0 (`README.md` L331–332; HF README L2): non-commercial; a derived label layer must respect this. The repo has "No license file" (README L331). | [V-FILE] |

---

## 12. Risks and Limitations

- No human authority labels exist yet. Annotation time and consistency are the main risk.
- Collection coverage: 117 of 422 held-out gold URLs were empty (README L319). Government and social gold were under-represented in reachable documents (reachable: social 6/28, gov 71/106) [RECON §2.1].
- The model may learn **publisher shortcuts** (e.g. "gov domain = authority") instead of claim-document relationships. Mitigation: ablations and per-claim-type analysis.
- Small test sets have low statistical power.
- Knowledge-store selection bias (§10.3). LLM memorisation (§10.2).
- English-only data; AVeriTeC claims are mostly 2020 fact-checks [V-FILE, `authority_resolution_study.md` L65].
- Historical numbers (n = 167, 192, 200, 99, 71, 48) **use different denominators** and are not directly comparable with a new human-authority endpoint.
- The authority-v2 reserved outputs are lost. Rerunning would be a new execution, not a recovery (`RECOVERY_LIMITATIONS.md` item 3).

---

## 13. Decisions Requiring Mentor Approval

1. Definition of claim-specific authority and the three authority tiers.
2. Relevance and authority label scheme. Does partial relevance count for a hit?
3. Primary comparison (D, or C/A if no LLM calls) and primary metric (Authority Recall@10).
4. Candidate-pool depth (top-300?) and how baselines use the same pool.
5. Use of AVeriTeC train claims and knowledge store; sample size; storage preflight.
6. Whether a new human label layer is required.
7. Annotators, hours, adjudicator; test fully double-annotated; about 20% of train double-annotated.
8. Train/validation/test sizes; claim-level (and possibly event-level) grouping.
9. Model scope (M1–M3 core; M4 and M5 optional).
10. New LLM calls for baselines or features.
11. Whether this study **supplements or replaces** authority-v2. v2 Steps 12–15 are paused and its reserved outputs are lost.
12. How the Review-2 slides should describe the reserved-180 work and the demo (Appendix A).
13. Whether the Project B mention on slide 11 stays (clearly separated) or is removed.

---

## 14. References and Source File Paths

### 14.1 Project files inspected (read-only)
- `P/README.md`
- `P/AUTHORITY_RETRIEVAL_PAPER_SUBMISSION_FINAL.md` (existence and title only)
- `P/requirements.txt`
- `P/.gitignore`
- `P/docs/dataset_audit.md`
- `P/docs/experiment_results.md` (headings, §2)
- `P/docs/feasibility_decision.md` (headings)
- `P/docs/authority_resolution_study.md`
- `P/docs/00_literature_review_and_research_plan.md` (dataset and tool sections)
- `P/docs/authority_v2_preregistration.md` (L1–200)
- `P/docs/authority_v2_decision_log.PARTIALLY_VERIFIED.md`
- `P/docs/authority_v2_progress_report_steps1-9.UNVERIFIED.md` (header)
- `P/experiments/common.py`, `baseline_retrieval.py`, `authority_retrieval.py`, `authority_resolution.py`, `validation_heldout.py` (constants, rerank, stats), `source_targeted.py` (signatures), `authority_v2/t_resolver.py`, `authority_v2/hash_gate.py`
- `P/data/annotations/heldout_primary_package/ANNOTATION_GUIDE.md`, `.../README.md`, `P/data/annotations/second_annotator_guidelines.md`
- `P/data/raw/averitec/README.md` (official AVeriTeC dataset card)
- Directory listings of `P/results/`, `P/data/processed/`, `P/data/raw/averitec/`
- `S/recovery_staging/bottleneck_analysis/README.md` and `files/docs/authority_resolution_bottleneck_analysis.md`
- `S/recovery_staging/authority_v2/RECOVERY_MANIFEST.md`
- `S/recovery_staging/evidence_package/RECOVERY_LIMITATIONS.md`, `execution_log_TRANSCRIPT_EXCERPT_NOT_ORIGINAL.json` (event lines)
- `C:\Users\Lenovo\Downloads\CapstoneProject_IR_03.pptx` (slide text) and `CapstoneProject_Phase-1_Review-2_PPT_Template.pptx`

**Not opened:** the sealed reserved-180 gold (absent anyway), held-out label CSVs and annotation sheets, AI label files, `dev.json`, `train.json` contents, Project B.

### 14.2 External sources (verified 2026-11-07)
- AVeriTeC: https://proceedings.neurips.cc/paper_files/paper/2023/hash/cd86a30526cd1aff61d6f89f107634e4-Abstract.html ; https://arxiv.org/abs/2305.13117 ; https://github.com/MichSchli/AVeriTeC (CC BY-NC 4.0)
- NELA-GT-2020: https://arxiv.org/abs/2102.04567 ; https://ar5iv.arxiv.org/html/2102.04567 ; DOI 10.7910/DVN/CHMUYZ
- AuFIN: https://qspace.qu.edu.qa/handle/10576/60866 ; CheckThat! 2023 Task 5: https://checkthat.gitlab.io/clef2023/task5 ; overview: https://qspace.qu.edu.qa/handle/10576/60871
- CheckThat! 2024 Task 5: https://checkthat.gitlab.io/clef2024/task5 ; https://ceur-ws.org/Vol-3740/paper-27.pdf ; AuRED: https://aclanthology.org/2024.arabicnlp-1.3
- Baly et al. 2018: https://arxiv.org/pdf/1810.01765 ; https://github.com/ramybaly/News-Media-Reliability
- Lin et al. 2023: https://pmc.ncbi.nlm.nih.gov/articles/PMC10500312/
- PrimeFacts: https://arxiv.org/abs/2605.06006 ; https://huggingface.co/datasets/premsa/prime-facts

### 14.3 Review-2 slide references already used (slide 12)
[1] AVeriTeC; [2] NELA-GT-2020; [3] DPR; [4] RRF; [5] BM25; [6] Sentence-BERT; [7] MiniLM; [8] Baly et al. 2018; [9] Wikidata.

AuFIN, AuRED and CheckThat! are **not yet** in the slide references. Add them if the proposal uses them.

---

## Appendix A. Consistency between the proposal and the Review-2 presentation

The deck is `C:\Users\Lenovo\Downloads\CapstoneProject_IR_03.pptx` (13 slides, modified 2026-11-04, before the 2026-11-06 deletion). Guide on slide 1: Indu R.

| Slide | Statement | Current evidence | Action needed |
|---|---|---|---|
| 3, 4 | Mentor feedback: focus on the Authority Resolution Module (bottleneck); approach maximum recall; train an ML model; investigate datasets; build a real non-synthetic dataset if needed; claim-specific authority | Matches the agreed direction | Keep |
| 4, 5, 7, 8, 9 | "~139,397-document store" | That number is the **reserved-180** knowledge store (log excerpt L767). Those extracts are **missing locally** (manifest L85). | State it as historical, or re-extract (needs approval) |
| 4 | "Retrieval compared on 180 reserved claims… Recall@K evaluation pending" | Rankings were produced (Step 10) but are lost. Recall@K on the reserved set needs sealed gold (v2 Steps 12–15, not authorised). | Clarify |
| 4, 10 | "Recall@K evaluation ongoing/pending" | A **completed, frozen** Recall@K evaluation exists on 200 held-out claims (README L127–156), and the slides do not mention it | Consider citing the completed held-out results |
| 8, 10 | "Initial LLM authority predictions, 180 claims, COMPLETED" | Executed historically (180/180 parsed); **output file lost** | Say "completed; output lost in deletion" or similar |
| 9 | Demo: load the 139,397-document store, run a reserved claim, show the LLM prediction | **Not currently possible**: reserved knowledge store, inputs, rankings and predictions are missing | Change the demo, e.g. to a dev or held-out claim with existing rankings (needs a team decision) |
| 9 | "human-annotated claim–publisher dataset" | The agreed direction is **claim–document** pairs | Update the wording |
| 5 | Supervised model in Phase-II | Consistent with "proposed" | Align the proposal timeline |
| 10 | Timeline P1–P8, dates TBD | No dated timeline found in the repo | Team decision |
| 11 | Mentions Project B ("68 tests pass on synthetic fixtures") | Project B is separate | Keep clearly separated or remove (decision) |
| 11 | "Recall and authority are separate evaluations" | Consistent with this package | Keep |

**Mentor feedback source:** only the slides (slide 4) and the user's own messages. No separate mentor-feedback document was found in the repository.

---

## 15. Explicit Unknowns (cannot be verified from the repository)

1. The exact composition of the AVeriTeC **train** knowledge store (gold-typed documents, query types, empty-text rate). Only dev was inspected.
2. The per-claim size of train extracts. The 0.9 GB for 200 claims is an extrapolation.
3. Whether near-duplicate or same-event claims exist between candidate train and test claims.
4. Licences of NELA-GT-2020, AuFIN, AuRED, the Baly corpus and the Lin et al. ratings.
5. Real annotation speed for the proposed two-output scheme. No human pilot was ever run.
6. Achievable inter-annotator agreement.
7. Authority-label coverage in deep pools: historical coverage figures use AVeriTeC gold, not authority labels.
8. Whether the bottleneck-report numbers (lines 51–856) exactly match the lost original. They are transcript-reconstructed and were not independently checked.
9. The git status of the restored authority-v2 files. Not checked: no git commands were run.
10. Whether the earlier frozen held-out findings generalise beyond AVeriTeC's pre-built knowledge store. There is no open-web evaluation (README L324–325).
11. Team availability, GPU access and the Phase-II schedule.
12. Any mentor decisions made outside the repository and the slides.

*End of package. Prepared without running project scripts, training models, downloading data, making LLM or API calls, or modifying existing files. The only file written is this one.*
