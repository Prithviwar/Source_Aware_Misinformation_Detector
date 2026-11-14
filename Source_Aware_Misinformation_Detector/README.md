# Claim-Specific Authority-Aware Evidence Retrieval for Fact Verification

A frozen held-out study of gains and failure modes on AVeriTeC.

This repository contains the research code, processed data, annotation materials, frozen
results, documentation and the finalized manuscript
([`AUTHORITY_RETRIEVAL_PAPER_SUBMISSION_FINAL.md`](AUTHORITY_RETRIEVAL_PAPER_SUBMISSION_FINAL.md)).

> **Reading guide.** The repository mixes several kinds of evidence. Each is labelled throughout:
>
> | Label | Meaning |
> |---|---|
> | **Preregistered** | Comparisons fixed in writing before the held-out evaluation was run |
> | **Pre-specified (not preregistered)** | Specified in a later addendum before the relevant labels existed |
> | **Exploratory** | Analyses added after the frozen evaluation; not covered by any protocol |
> | **AI-generated** | Labels produced by a language model (Claude Opus 5.5); **not** human annotation or human ground truth |
> | **Human-gold** | The evidence URLs chosen by the AVeriTeC annotators |
> | **Oracle / diagnostic** | Conditions that use gold information by design; upper bounds, not deployable systems |

---

## Overview

Evidence retrieval for automated fact verification usually ranks documents by topical relevance,
and some systems also weight documents by the general credibility of their publisher. This project
asks whether it helps to first identify, for each claim, the source that is authoritative for that
specific claim, and to use that identification when retrieving and ranking evidence.

On the preregistered human-gold endpoint, the answer is mixed and mostly negative: an LLM-predicted
authority prior gives a directional, non-significant improvement, and a pipeline that retrieves
documents directly from predicted authorities does not carry over from development to held-out
data. The most informative outcome is a decomposition of how authority-aware retrieval fails.

## Research Question

> Can explicitly identifying the source that is authoritative for a particular claim improve
> evidence retrieval compared with standard relevance- and credibility-based retrieval?

- **General source credibility** is whether a source or publisher is trustworthy in general. It is a
  property of the publisher and takes the same value for every claim.
- **Claim-specific authority** is whether a source actually issued, recorded, measured, announced,
  observed or holds the fact at issue in the particular claim.

The two can diverge. A national statistics office is the authority for a claim about the
unemployment figure it publishes, but not for a claim about a private company's earnings; a
respected newspaper can be highly credible and still be a secondary source for both.

## Research Design

```
claim --> relevance retrieval (BM25 + dense, RRF) --> hybrid top-100 candidates
      \-> authority prediction (LLM, top-3 publishers) --> prior over candidate publishers
                                                     \-> optional targeted retrieval from predicted publishers
      --> reranking: minmax(relevance within pool) + lambda * prior(url), lambda = 1
      --> evaluation against AVeriTeC human-gold evidence
```

All retrieval runs offline inside the AVeriTeC per-claim knowledge store. There is **no live or
open-web retrieval**.

### Systems in the frozen held-out evaluation

Defined in `experiments/source_targeted_eval.py` and `docs/source_targeted_preregistration.md`.

| ID | System | Candidate pool |
|---|---|---|
| A | Hybrid retrieval: reciprocal rank fusion (k = 60) of BM25 (`bm25s`) and dense retrieval (`all-MiniLM-L6-v2`); query = claim text | hybrid top-100 |
| B | A + generic credibility prior (claim-independent domain-type scores), lambda = 1 | hybrid top-100 |
| C | A + heuristic authority prior (generic prior combined with claim-entity and claim-country rules), lambda = 1 | hybrid top-100 |
| D | A + LLM authority prior: union of the publisher keys of the predictor's top-3 publishers, lambda = 1 | hybrid top-100 |
| E | Source-targeted retrieval only: site-restricted retrieval from predicted publishers, authority-first order, top M = 10 | targeted top-10 |
| F | Hybrid + source-targeted: hybrid top-100 union targeted top-10, fused by RRF | union |
| G | F reranked with the LLM authority prior, lambda = 1 | union |
| Ctrl | Size-matched control: hybrid top-(100 + number of documents F adds) | same size as F |
| H | **ORACLE (diagnostic only)**: the same pipeline with publisher keys from all human gold URLs; leaks gold by design | union |

The authority predictor (condition `L+Wctx` in `experiments/authority_resolution.py`) is Claude
Opus 5.5 called through the Claude Code CLI with no tools and no web access. It receives the claim
text, speaker, claim date and country, plus Wikidata facts for the claim's entities (Wikidata was
queried in 2026, not as of the claim date).

## Dataset and Evaluation

- **Source data:** the AVeriTeC development split (500 claims) and its per-claim knowledge store
  (CC BY-NC 4.0; Hugging Face `chenxwh/AVeriTeC`).
- **Development sample:** 120 claims (`data/processed/averitec_sample.jsonl`), label-stratified,
  seed 2026, used for design and tuning.
- **Held-out sample:** 200 claims (`data/processed/averitec_heldout.jsonl`) drawn from the 380
  development-split claims not used for design, stratified by label (124 Refuted, 48 Supported,
  15 Conflicting/Cherrypicking, 13 Not Enough Evidence), seed 2027. 180 development-split claims
  remain untouched.
- **Held-out gold evidence (this project's extraction):** 192 claims have at least one web gold
  URL; 422 gold URLs in total, of which 117 have empty text; **167 claims have at least one
  reachable (non-empty) gold document** - the main evaluation denominator. 25 claims have only
  empty web gold and 8 have no web gold.
- **Leakage controls** (project-side, see `docs/experiment_results.md` section 2): documents are
  sorted by URL and shuffled with a fixed per-claim seed (gold documents are stored first in the
  knowledge-store files); retrievers see only a normalised URL (archive-wrapped URLs were
  disproportionately gold); knowledge-store query-type fields are never read by retrieval code; the
  authority predictor never sees gold URLs, evidence, labels or justifications.

Note that the knowledge store itself was built by the AVeriTeC organisers partly from queries
derived from the gold questions and answers, so it is already enriched with relevant pages.

## Evaluation Metrics

- **R@K** (K = 1, 5, 10, 20, 50, 100): share of claims with at least one reachable gold document
  in the top K.
- **MRR@100:** mean reciprocal rank of the first reachable gold document within the top 100.
- **Pool coverage:** share of claims whose candidate pool contains at least one reachable gold
  document (before reranking).

Two endpoints are reported and are never mixed:

1. **Human-gold endpoint (preregistered, primary):** all reachable AVeriTeC gold documents of the
   167 gold-reachable held-out claims. Gold R@K also counts secondary pages (news, fact-checks).
2. **AI-labelled primary-evidence endpoint (pre-specified, not preregistered; exploratory):** only
   gold documents from publishers that Claude Opus 5.5 labelled as `primary`. It is conditional on
   72 of 192 annotated claims (101 have a primary label, 100 a usable publisher key, 72 a reachable
   primary document). The same model family also predicts authority, so this endpoint is **not
   independent validation** and **not human ground truth**.

## Main Results

### Human-gold endpoint, frozen held-out set (n = 167) - preregistered evaluation

Source: `results/source_targeted/results_heldout.json`.

| ID | R@1 | R@5 | R@10 | R@20 | R@50 | R@100 | MRR@100 | Pool coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 0.060 | 0.156 | 0.251 | 0.383 | 0.563 | 0.671 | 0.125 | 0.671 |
| B | 0.024 | 0.174 | 0.263 | 0.383 | 0.569 | 0.671 | 0.099 | 0.671 |
| C | 0.030 | 0.186 | 0.275 | 0.407 | 0.569 | 0.671 | 0.109 | 0.671 |
| D | 0.066 | 0.198 | 0.293 | 0.437 | 0.581 | 0.671 | 0.138 | 0.671 |
| E | 0.060 | 0.138 | 0.180 | 0.180 | 0.180 | 0.180 | 0.091 | 0.180 |
| F | 0.060 | 0.204 | 0.287 | 0.407 | 0.617 | 0.695 | 0.141 | 0.701 |
| G | 0.060 | 0.174 | 0.246 | 0.401 | 0.611 | 0.695 | 0.128 | 0.701 |
| Ctrl | 0.060 | 0.156 | 0.251 | 0.383 | 0.563 | 0.671 | 0.125 | 0.677 |
| H (oracle, diagnostic) | 0.479 | 0.754 | 0.868 | 0.880 | 0.886 | 0.886 | 0.602 | 0.886 |

**Preregistered tests** (exact McNemar; paired bootstrap 95% CI; Holm within each family).
Sources: `results/heldout/validation_heldout.json`, `results/source_targeted/results_heldout.json`.

| Test | Wins / losses | p | Holm p | Difference [95% CI] |
|---|---|---:|---:|---|
| D vs A, R@10 (primary endpoint) | +13 / -6 | 0.167 | - | +0.042 [-0.006, 0.096] |
| D vs A, R@5 | +11 / -4 | 0.118 | 0.373 | +0.042 [-0.006, 0.090] |
| D vs A, R@20 | +12 / -3 | 0.035 | 0.176 | +0.054 [0.012, 0.102] |
| D vs B, R@10 | +16 / -11 | 0.442 | 0.884 | +0.030 [-0.030, 0.090] |
| F vs Ctrl, pool coverage | +5 / -1 | 0.219 | 0.555 | +0.024 [0.000, 0.054] |
| G vs D, R@10 | +10 / -18 | 0.185 | 0.555 | -0.048 [-0.108, 0.012] |
| G vs A, R@10 | +21 / -22 | 1.000 | 1.000 | -0.006 [-0.084, 0.072] |

**No preregistered held-out comparison on the human-gold endpoint is statistically significant.**
The D vs A difference is directional. On the development sample the same comparison was +15/-5
(difference +0.101); on the held-out set it is +0.042. G reached R@10 0.354 against 0.242 for
hybrid on the development sample, but not on the held-out set.

Authority prediction accuracy against the publishers of all human gold URLs (n = 192): top-1
0.292 (56/192), top-3 0.391 (75/192). This target includes news and fact-check pages, so it is a
lower bound on authority accuracy.

### AI-labelled primary-evidence endpoint (n = 72) - pre-specified, not preregistered; exploratory

Source: `results/heldout_ai_primary/MODEL_GENERATED_ai_primary_evidence_recall_heldout.json`.
R@10: A 0.097, B 0.181, C 0.181, D 0.278, E 0.403, F 0.375, G 0.431, Ctrl 0.097, H 0.694.
The tests (D vs A 14/1, Holm p 0.00294; G vs A 25/1, Holm p < 0.001; G vs D 13/2, Holm p 0.00739;
F vs Ctrl coverage 10/0, Holm p 0.0039) describe an association within this conditional,
AI-labelled endpoint. Because the same model family produced the labels and the authority
predictions, they do not constitute independent validation, and by a rule fixed in advance they
cannot change the preregistered human-gold conclusion.

## Failure Analysis

Descriptive analysis of the frozen rankings (`results/source_targeted/error_analysis_heldout.json`);
it identifies where failures occur, not why each one happened.

- **Wrong authority prediction.** For 102 of 167 claims no predicted top-3 publisher matches any
  gold publisher. On these claims gold reaches the top 10 for 30 claims under A, 26 under D and 10
  under G.
- **A correct authority is not sufficient.** For 56 claims a predicted publisher has a reachable gold
  document; G still misses gold in the top 10 for 25 of them, and in 22 of those 25 the authority's
  gold document is outside the targeted candidate pool.
- **Source-targeting displacement.** G loses to D on 18 claims; in all 18, targeted documents occupy
  G's top 10 (mean 8.89 of 10), and the predicted authority was correct in only 2.
- **Collection coverage.** 55 of 167 claims have no gold document in the hybrid top-100; 117 of 422
  gold URLs are empty in the extracted knowledge store.
- **Multiple legitimate authorities.** The predictor labels 169 of 200 claims as having multiple
  legitimate authorities, so the label barely discriminates; these are model outputs, not
  validated categories.
- **AI-primary annotation limits.** Shared model family with the predictor; conditional 72-claim
  denominator; the annotator saw page title, snippet and the gold question/answer, not full pages.
  A planned circularity diagnostic and a cross-family labelling check have not been run.
- **Memorisation probe** (`results/memorisation_probe/summary_heldout.json`). Top-3 accuracy is
  essentially unchanged under paraphrase (0.396) and metadata removal (0.401) and falls under name
  masking (0.307). This shows reliance on named entities; the probe does not establish that
  memorisation is absent.
- **Provenance.** Word 5-gram heuristics of apparent duplication/derivation were run on the 120
  development claims only (`results/provenance_*`); they are not verified provenance and give no
  held-out conclusion.

## Experimental Progression

| Stage | Status | Where |
|---|---|---|
| Dataset audit; development-sample baselines, credibility and authority priors, pool, provenance and temporal audits (120 claims) | Exploratory, development | `docs/dataset_audit.md`, `docs/experiment_results.md`, `docs/feasibility_decision.md` |
| Authority-resolution study (LLM and Wikidata predictors; development pilot labels were AI-generated by Claude) | Exploratory, development | `docs/authority_resolution_study.md` |
| Frozen held-out evaluation, systems A-H (200 claims) | **Preregistered** | `docs/validation_preregistration.md`, `docs/source_targeted_preregistration.md`, `results/heldout/`, `results/source_targeted/` |
| Held-out memorisation probe and error analysis | Probe fixed before running; error analysis descriptive | `results/memorisation_probe/`, `results/source_targeted/error_analysis_*` |
| AI-labelled primary-evidence endpoint (replaces an unexecuted human annotation endpoint) | Documented deviation (Addendum 3); pre-specified, not preregistered | `data/annotations/heldout_primary_package/`, `results/heldout_ai_primary/` |
| Authority-quality ablation, Phase 1 (none / predicted top-1 / predicted top-3 / oracle) | **Exploratory** | `experiments/authority_quality_ablation/`, `results/authority_quality_ablation/` |
| Matched mismatched-authority perturbation, Phase 2 (79 claims) | **Exploratory** | `results/authority_quality_ablation_phase2/` |
| Tie-break seed robustness (seeds 2029-2048) | Descriptive robustness check | `results/authority_quality_ablation_phase2_seeds/` |

Exploratory results, all on the human-gold endpoint and all post-hoc relative to the frozen evaluation:

- **Phase 1** (n = 167): R@10 A0 0.251, predicted top-1 (D1) 0.305, predicted top-3 (D3, equal to
  system D) 0.293, oracle gold publishers (O, diagnostic) 0.659. D1 vs A0 +13/-4 (p 0.049, Holm
  0.098 within the exploratory family); D3 vs D1 +2/-4. The oracle uses the publishers of the very
  gold documents being scored, so it approaches the pool-coverage ceiling (0.671) and is partly
  circular.
- **Phase 2** (n = 79; claims where the predicted top-1 publisher appears in the pool): a
  *deliberately mismatched authority* (X1) - a pool-visible, non-gold publisher outside the
  predictor's top-3, of the same generic category and similar pool document count - gives R@10
  0.228 against 0.253 for A0 and 0.367 for D1 (X1 vs A0 +0/-2; X1 vs D1 +2/-13, Holm 0.022). X1 is
  not claimed to be factually wrong or non-authoritative.
- **Robustness:** the X1 R@10 result and both paired R@10 differences are identical across all 20
  tie-break seeds.

## Reproducibility

**Environment.** Python 3.13, CPU only. Dependencies in `requirements.txt`
(`bm25s==0.3.11`, `tldextract`, `fsspec`, `aiohttp`, `numpy`, `pandas`, `spacy>=3.8`,
`sentence-transformers>=5.0`, `torch`), plus:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

The dense model `sentence-transformers/all-MiniLM-L6-v2` is downloaded by `sentence-transformers`.

**Data not in the repository.** `data/raw/` is gitignored. To rebuild it:

- place the AVeriTeC `data/dev.json` from Hugging Face `chenxwh/AVeriTeC` in `data/raw/averitec/`
  (see `docs/dataset_audit.md`; no download script for this file is included);
- knowledge-store extracts are streamed from the Hugging Face dev knowledge-store zip with HTTP
  range requests: `python experiments/extract_knowledge_store.py` (development sample) and
  `python experiments/validation_heldout.py extract` (held-out sample). They are written to
  `data/raw/averitec/ks_sample/` and are required by every scoring script.

**External services.** LLM steps call the Claude Code CLI (`claude -p`, no tools): model
`claude-opus-5-5` in `authority_resolution.py`, `validation_heldout.py predict` and `probe`,
`memorisation_probe.py` and `ai_annotate.py`; model `claude-sonnet-5-5` in
`provenance_aggregation.py`. The binary is found on `PATH` or via the `CLAUDE_CODE_EXECPATH`
environment variable. `wikidata_authority.py` and
`validation_heldout.py wikidata` query the Wikidata API (cached results are in `results/`).

**Documented commands.**

- Development-sample pipeline: the command list in `docs/experiment_results.md`, section 7
  ("Reproduce").
- Held-out pipeline: `python experiments/validation_heldout.py <sample|extract|rank|wikidata|predict|probe|evaluate>`
  and `python experiments/source_targeted_eval.py heldout` ("run once"; see restrictions below).
- Read-only check that the frozen pools reproduce the published held-out gold table:
  `python experiments/score_heldout_primary.py selftest` (needs the knowledge-store extracts).
- AI-primary scoring: `python experiments/score_ai_primary.py score <roles.csv>`
  (see `data/annotations/heldout_primary_package/README.md`).
- Exploratory ablations (each script runs a reproduction gate against the frozen results first and
  refuses to overwrite existing outputs):
  ```bash
  python experiments/authority_quality_ablation/run_ablation.py
  python experiments/authority_quality_ablation/strata_paired.py
  python experiments/authority_quality_ablation/build_x1_assignment.py
  python experiments/authority_quality_ablation/run_x1.py
  python experiments/authority_quality_ablation/run_x1_seed_sensitivity.py
  ```

**Restrictions on frozen experiments.** The held-out rankings, authority predictions, AI annotations
and scores are frozen; their hashes are recorded in `docs/source_targeted_preregistration.md`,
`docs/validation_preregistration.md` and `data/annotations/heldout_primary_package/ai/FROZEN_HASHES.json`.
Re-running the prediction, annotation or held-out evaluation commands would make new LLM calls or
overwrite frozen outputs and is not needed to inspect or score the stored results. The dev-sample
ranking files `results/rankings_*.jsonl.gz` are gitignored and must be regenerated with the
section 7 commands before the dev-sample evaluation scripts can run.

## Repository Structure

```text
.
|-- AUTHORITY_RETRIEVAL_PAPER_SUBMISSION_FINAL.md   finalized manuscript
|-- README.md
|-- requirements.txt
|-- data/
|   |-- processed/            averitec_sample.jsonl (120 dev claims), averitec_heldout.jsonl (200 held-out claims)
|   |-- annotations/          pilot role labels, annotation templates, second-annotator packages
|   |   `-- heldout_primary_package/   primary-evidence protocol, guide, scorer sheet, CHANGELOG
|   |       |-- ai/                    AI-generated (MODEL_GENERATED_*) labels, prompts, frozen hashes, logs
|   |       `-- pilot/                 pilot handout and returned model-generated pilot files
|   `-- raw/                  (gitignored) AVeriTeC dev.json and knowledge-store extracts
|-- docs/                     literature review, dataset audit, results, feasibility decision, preregistrations
|-- experiments/              all retrieval, prediction, annotation, scoring and analysis scripts
|   `-- authority_quality_ablation/   exploratory Phase 1/2 ablation code, configs, READMEs
`-- results/                  frozen and exploratory outputs
    |-- heldout/                       held-out rankings, predictions, validation results, probe raw output
    |-- source_targeted/               A-H rankings, results, error analysis (dev and held-out)
    |-- heldout_ai_primary/            AI-labelled primary-evidence results
    |-- memorisation_probe/            probe outputs
    |-- authority_quality_ablation*/   exploratory ablation outputs
    `-- *.json, *.csv, log_*.txt       development-sample results and audits
```

## Limitations

- No independent human annotation of primary evidence was completed; the human primary-source
  endpoint was specified but not executed.
- The AI-generated evidence-role labels come from the same model family as the authority predictor.
- The AI-primary endpoint is conditional on 72 of 192 annotated claims.
- Evidence is often missing: 117 of 422 gold URLs are empty.
- Source targeting did not carry over from development data and can reduce recall.
- The evaluation is specific to AVeriTeC and its pre-built knowledge store; the held-out sample is
  small (167 gold-reachable claims).
- Provenance analyses cover development claims only.
- There is no open-web or live retrieval evaluation, so generalisation beyond this frozen
  evaluation is untested.
- Exploratory ablations (Phase 1 and 2) were run on the already-used held-out set; any method
  choice suggested by them would need a fresh, preregistered test.

## License and Data

No license file is included in this repository. The AVeriTeC data and knowledge store are released
by their authors under CC BY-NC 4.0.

## Citation

If you use this work, please cite the manuscript in this repository:
*Claim-Specific Authority for Evidence Retrieval in Fact Verification: A Frozen Held-Out
Evaluation on AVeriTeC and an Analysis of Failure Modes* (Rachit Mane). Publication details are not
yet available.
