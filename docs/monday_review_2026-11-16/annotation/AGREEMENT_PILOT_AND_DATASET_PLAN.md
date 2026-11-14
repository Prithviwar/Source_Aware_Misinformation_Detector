# Agreement Measurement, Pilot and Dataset Construction Plan

**Status (2026-11-14): PLANNED. No human labels exist.** The pilot packet is built and blank (`data/annotations/authority_pilot_2026-11/`).

## 1. Why a new dataset is needed

| Resource examined | What it labels | Why it is not enough |
|---|---|---|
| AVeriTeC (dev/train) | Real claims, Q/A evidence, evidence URLs | Evidence URLs are **citation/relevance** choices and include news and fact-check pages; there is no authority label per document |
| NELA-GT-2020 | Publisher-level reliability (e.g. MBFC) | **Per publisher, not per claim**: it measures credibility, not claim-specific authority |
| Wikidata references | Statements linked to cited sources | Not ground truth for authority; would itself need human validation |
| AuFIN / AuRED | Authority of social-media accounts | Different task and domain (tweets and accounts, not web documents) |
| Project AI role labels (`heldout_primary_package/ai/`) | Claude-generated primary/secondary roles | **Model-generated** by the same model family as predictor D; not human, and not independent |

## 2. Pilot (before the main set)

| Item | Plan |
|---|---|
| Claims | 20 AVeriTeC **dev-sample** claims (seed 2060), **pilot only**: never used for training or final evaluation |
| Pairs | Frozen hybrid top-10 per claim = 200 pairs, shuffled within each claim; rank and evidence indicator hidden |
| Annotators | ≥ 2 team members independently (A, B), plus an adjudicator (mentor or third member) |
| Effort | about 200 × 1.5 min ≈ 5 h per annotator |
| Outputs | agreement report; list of guideline gaps; guide v1.1 |
| Go/no-go | Proceed to the main set if authority κ ≥ 0.60 (substantial) on the binary *authority hit*, and ≥ 0.40 on the 5-way label. Otherwise revise the guide and re-pilot on 10 new claims |

## 3. Main dataset (Phase II)

| Item | Plan |
|---|---|
| Claim source | AVeriTeC **train** split (the frozen 300-claim sample, `train_sample_split.json` sha `1b994a96…`, claim-disjoint fit/validation/test 179/60/61). Optionally expanded with more train claims under the same rules |
| Never used | the 200 held-out dev claims (frozen study), the 180 reserved dev claims, the AVeriTeC test split, sealed gold |
| Candidate pool per claim | hybrid top-20 (minimum); top-30 if budget allows. The hybrid top-100 caps any reranker at 0.671 (held-out); deeper annotation raises label coverage |
| Size estimate | 300 claims × 20 = 6,000 pairs. Realistic Phase-II target: **≥ 150 claims × 20 = 3,000 pairs** |
| Double annotation | **all** test pairs, independently; **≥ 20 %** of training pairs (random, stratified by claim); validation pairs single-annotated plus spot checks |
| Adjudication | every disagreement on double-annotated pairs; the adjudicated label is the gold label |
| Metadata separation | automatically collected fields (URL, publisher key, excerpt, retrieval rank and score, AVeriTeC evidence indicator) live in separate files from human labels; labels carry annotator ID and guide version |

## 4. Agreement statistics

Computed by `experiments/esa_nov2026/annotation/agreement.py` (self-test passes):

- **Cohen's κ** for two annotators, on relevance (4-way), authority (5-way) and the binary authority hit;
- **quadratic-weighted κ** on the ordinal parts (not < partial < relevant; not-auth < secondary < auth-secondary < primary), excluding `cannot_determine`;
- **Krippendorff's α (nominal)** for ≥ 2 annotators with missing values;
- confusion matrices to find systematically confused classes, e.g. primary vs authoritative-secondary.

Report agreement **before adjudication**, per label and overall, with *n* and the share of `cannot_determine`. Interpretation (Landis & Koch): 0.41–0.60 moderate, 0.61–0.80 substantial. If agreement stays low, report it honestly; low agreement is itself a finding about the task.

## 5. Adjudication template

`data/annotations/authority_pilot_2026-11/pilot_adjudication_template.csv` has these columns:
`pair_id, claim_id, relevance_A, relevance_B, authority_A, authority_B, relevance_final, authority_final, adjudicator, disagreement_type, guideline_section, adjudication_note`

`disagreement_type` is one of: `credibility_vs_authority`, `primary_vs_auth_secondary`, `relevance_scope`, `inaccessible_doc`, `annotator_error`, `guideline_gap`.

## 6. Timeline after Monday

| Week | Task |
|---|---|
| W1 | Mentor approves label scheme and §11 decisions; recruit annotators; walk through the guide with 3 worked examples |
| W2 | Pilot annotation (200 pairs), agreement, adjudication, guide v1.1 |
| W3–W6 | Main annotation in batches; agreement re-checked on each batch's double-annotated 20 % |
| W7 | Freeze dataset (hash manifest), then train and evaluate the authority model (see model design) |
