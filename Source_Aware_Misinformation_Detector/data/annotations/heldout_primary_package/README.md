# Held-out primary-source annotation package

> **Status (2026-10-02).**
> - The **human** procedure below was pre-registered (Addendum 2) but **NOT executed**; no human labels exist.
> - The active path is **AI-labelled primary-evidence recall** (Addendum 3). AI evidence-level role labels are converted to this package's sheet format and scored with the unchanged scorer. See `AI_ANNOTATION_PROTOCOL.md` and the section "AI-labelled path" at the end.
> - All AI outputs are `MODEL_GENERATED_*` and are never human annotations.

## What this is for

- **Exactly 192 claims.** These are the **frozen held-out claims** (`data/processed/averitec_heldout.jsonl`, 200 AVeriTeC dev claims disjoint from the 120 development claims) that have ≥1 human gold web URL.
- The claim IDs and order are copied unchanged from `../heldout_annotator_claim_authority_template.csv` (seeded shuffle) and recorded in `MANIFEST.json`.
- The annotation is used **only** to measure the one pre-registered endpoint that is still missing: **held-out Primary Recall@1/3/5/10/20**. It also gives primary MRR@100 and primary candidate coverage.
- It does **not** feed any method, prior, tuning or re-ranking.
- The held-out rankings were frozen on 2026-09-30 and will **not** be re-run.

## Files

| File | Who uses it | Purpose |
|---|---|---|
| `heldout_primary_annotation.csv` | annotator | Blind sheet, 192 rows. The canonical format. |
| `heldout_primary_annotation.xlsx` | annotator | Same sheet with dropdowns. Fill either this or the CSV, not both. |
| `ANNOTATION_GUIDE.md` | annotator | Label definitions, columns, examples and rules. |
| `README.md` | project owner | This procedure. |
| `MANIFEST.json` | scorer | Claim order, allowed values, and SHA-256 of the blank sheet, the scorer and the frozen rankings. |
| `CHANGELOG.md` | project owner | Every wording/example change to the guide, with its reason. |
| `pilot/handout/` | annotator (pilot) | The 15-claim pilot sheet, pilot instructions, feedback form and a copy of the guide. |
| `pilot/PILOT_MANIFEST.json`, `pilot/PILOT_REVIEW_CRITERIA.md` | project owner | Pilot IDs, hashes and leak scan; the decision rule for clarifying the guide. |

Builder: `experiments/heldout_primary_package.py`. Scorer: `experiments/score_heldout_primary.py`.

## Human procedure (pre-registered, NOT executed)

1. **Recruit** one human annotator (two if possible, working independently). They must not have seen this project's results, docs or model outputs.
2. **Run the 15-claim pilot first** (see "Pilot" below). Then **give them only** `heldout_primary_annotation.csv` / `.xlsx` and `ANNOTATION_GUIDE.md`. Do not give them this README, `MANIFEST.json`, `CHANGELOG.md` or `pilot/PILOT_REVIEW_CRITERIA.md`: these describe the scoring. Also do **not** give them:
   - `../heldout_annotator_template.csv` / `.xlsx` (422 gold evidence URLs with snippets and gold QA)
   - `../heldout_annotator_key.csv`
   - `../heldout_annotator_claim_authority_template.*` (the older sheet; superseded by this one)
   - anything in `results/`, `docs/` or `data/processed/`
3. The annotator fills the sheet following `ANNOTATION_GUIDE.md`, in the given row order. Uncertainty is recorded explicitly through `confidence` (required), `authority_situation = unclear` and `notes`. **Multiple legitimate authorities are allowed** (`multiple_legitimate_authorities`, up to 3 listed).
4. **Save the returned file** as `data/annotations/heldout_primary_package/returned/heldout_primary_annotation_<INITIALS>.csv`. Never edit its labels.
5. **Validate the format.** This reads no gold and no rankings:
   `cd experiments && python score_heldout_primary.py check ../data/annotations/heldout_primary_package/returned/heldout_primary_annotation_<INITIALS>.csv`
   It reports the rows that need fixing, for example a bare `@handle`, a missing type, or `multiple_legitimate_authorities` with fewer than 2 entries. Send those rows back to the annotator; do not fix labels yourself.
6. **Score** (only once the check passes; see "Scoring" below). Run it once per annotator file.

## Human pilot (15 claims; pre-registered, NOT executed)

- **What it is.** `pilot/handout/` contains everything the annotator gets:
  - the pilot sheet (rows 1–15 of the frozen order, same schema; `.csv` and `.xlsx`);
  - `PILOT_INSTRUCTIONS.md`;
  - `PILOT_FEEDBACK.md`;
  - a byte-identical copy of `ANNOTATION_GUIDE.md`.
- **How it was built.** Built by `experiments/heldout_primary_pilot.py`. The script asserts that the canonical sheet is unchanged and runs the leak scan; the results are in `pilot/PILOT_MANIFEST.json`.
- **Returned files.** Store them in `pilot/returned/` as `heldout_primary_pilot15_<INITIALS>.csv|xlsx` plus `PILOT_FEEDBACK_<INITIALS>.md`.
- **Check.** `cd experiments && python check_pilot_annotation.py ../data/annotations/heldout_primary_package/pilot/returned/heldout_primary_pilot15_<INITIALS>.csv [second annotator's file]`. It reads no gold and no rankings.
- **Decide.** Apply `pilot/PILOT_REVIEW_CRITERIA.md`. Pilot sheets are never scored.

## Scoring (fixed before any label exists; reused unchanged for the AI-labelled endpoint)

`cd experiments && python score_heldout_primary.py score ../data/annotations/heldout_primary_package/returned/heldout_primary_annotation_<INITIALS>.csv`

It writes `results/heldout_primary/primary_results_heldout.json` and records the SHA-256 of the annotation file, the scorer and the frozen rankings.

**Primary documents of a claim.** These are the reachable (non-empty) human-gold documents of that claim whose publisher key equals a key the annotator listed. The publisher key is the registered domain, or platform/handle for social accounts. It is `cand_key`, the key used in the frozen evaluation.

**Denominator.** Claims with ≥1 such document. The scorer reports a funnel of excluded claims:

- claims marked `no_identifiable_primary` or `unclear`;
- claims whose listed authority has no gold URL;
- claims whose only gold documents are empty.

**Methods scored.** Unchanged frozen rankings:

- A hybrid
- B + generic credibility
- C + heuristic authority
- D + LLM authority
- E source-targeted only
- F hybrid + source-targeted
- G hybrid + source-targeted + LLM authority
- the size-matched control
- *ORACLE*: a diagnostic only. Its keys come from all gold publishers, so it will be optimistic here. Its coverage is N/A because its targeted pool was not saved.

**Metrics.** PrimR@1/3/5/10/20, PrimMRR@100, and primary claim coverage of the pool before re-ranking.

**Tests** (exact McNemar + paired bootstrap 95% CI, Holm across the 4):

- PrimR@10 G vs A
- PrimR@10 G vs D
- PrimR@10 D vs A
- primary coverage F vs size-matched control

**Sensitivity.** The same analysis excluding rows with `confidence = low`.

**Scorer check.** `python score_heldout_primary.py selftest` rebuilds every pool from the frozen files and asserts that it reproduces the published held-out *gold* table exactly. It does this without any annotation, and it passed on 2026-09-30.

## Differences from the earlier plan and limitations

- The pre-registration named the 422-row URL sheet (`heldout_annotator_template.csv`) as the source of held-out primary labels. That sheet shows the gold evidence URLs, snippets and gold QA. This package replaces it with a **claim-level, evidence-blind** sheet, so the annotator's notion of "the authority" cannot be anchored on the gold evidence.
  - The change was made before any held-out primary label existed.
  - It is recorded in `docs/source_targeted_preregistration.md`.
- **The primary definition differs from dev.** Dev "pilot-primary" was a per-URL role label from one AI annotator. Held-out primary is a gold URL from a publisher that a human named blind. **Dev and held-out primary numbers are therefore not identically defined.**
- Primary documents are restricted to **human-gold** URLs, the same universe as gold R@K. A primary page that exists in the knowledge store but was not cited by AVeriTeC does not count.
- 25 of the 192 claims have only empty gold documents. They cannot enter the denominator whatever the annotation says.
- A claim-level annotation cannot say which of several pages from the right publisher is the right *document*. Any gold page from a listed publisher counts.

## AI-labelled path (active; Addendum 3)

- **Main AI endpoint.** AI-labelled primary-evidence recall (AI-PrimR@1/3/5/10/20, AI-PrimMRR@100, AI-primary coverage).
  - Claude Opus 5.5, in an isolated `claude -p` context, labels each of the 422 held-out gold evidence URLs `primary / secondary / derived / unclear`.
  - `experiments/score_ai_primary.py` converts the labels to this package's 192-row sheet. It then runs `score_heldout_primary.py` unchanged, writing to `results/heldout_ai_primary/`.
  - Same 4 Holm-corrected tests. It cannot change validation outcome B.
- **Secondary, descriptive only.** A claim-level AI annotation with `ANNOTATION_GUIDE.md` (AI-named authority). It is circular with the authority predictor (same model), so it gets no tests and is never used to validate D.
- **Pilot.**
  - The 15 pilot claims are labelled at evidence level twice, as a stability check, and at claim level once.
  - They are reviewed under the AI addendum of `pilot/PILOT_REVIEW_CRITERIA.md`.
  - Then the protocol is frozen (`ai/FROZEN_HASHES.json`).
- **Model-generated pilots that already exist** (CLAUDE, RM, CHATGPT-MODEL in `pilot/returned/`) are kept as records of how the guide was revised. They are not scored.
- **Terminology.** Never call any of this human, human-validated, expert or ground truth.
