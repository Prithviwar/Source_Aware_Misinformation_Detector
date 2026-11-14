# Decisions

Each methodological decision maps to a key under `decisions` in `config/config.template.json`. A real run refuses to start while any key is `null`. **No configuration value has been changed to reflect the decisions below**; Section 1 lists the changes they would require. Nothing here records mentor approval unless it says so explicitly. The values in `config/synthetic_smoke.json` are placeholders that exist only to exercise code.

Status vocabulary: **OWNER-DECIDED** (specified by the project owner; mentor approval not recorded) · **OWNER-PROPOSED** (owner's intended approach, explicitly provisional) · **UNRESOLVED** (no decision) · **DESIGN-PROPOSED** (proposed in the design documents, not yet confirmed).

## 0. Project-owner decisions (recorded 2026-10-29)

Source: the project owner's message of 2026-10-29. Mentor approval: **not recorded for any item**.

| # | Config key | Decision | Status | Mentor confirmation |
| --- | --- | --- | --- | --- |
| O1 | `positive_bases` | `INSTITUTIONAL_ACT`, `OFFICIAL_RECORD`, `ORIGINAL_RESEARCH`, `DIRECT_OBSERVATION` are the intended positive bases | OWNER-PROPOSED (current proposed definition) | **Required** (owner flagged it) |
| O2 | `record_keeper_rule` | `designated_only`: for a statistic, positive only if the publisher is the designated record-keeper for that statistic, not merely an official body | OWNER-DECIDED | Recommended |
| O3 | `quotation_rule` | `content`: judge authority for the substantive content of a quoted statement, not for the fact that it was said | OWNER-DECIDED | Recommended |
| O4 | `self_report_rule` | `positive_with_interested_flag`: an organisation may be first-hand for information about itself, flagged `INTERESTED_PARTY` | OWNER-DECIDED | Recommended |
| O5 | `candidate_source` | Documented retrieval process **plus** curated additions; exact protocol to be confirmed | OWNER-PROPOSED (provisional) | Required once the protocol is written |
| O6 | (evaluation protocol) | Examine seen-publisher performance as a diagnostic first, then unseen-publisher generalisation. Publisher-disjoint unseen-publisher evaluation remains the **primary** generalisation test. Test results are never used to tune the model or select features | OWNER-DECIDED (principle); diagnostic design UNRESOLVED (see 2) | Recommended |

### 0.1 Conflicts found and proposed corrections

| Conflict | Where | Smallest safe correction (not applied) |
| --- | --- | --- |
| The *Technical Design* doc's recommended working definition left `DIRECT_OBSERVATION` **out** of the positive class pending mentor decision; O1 includes it | *First-Hand Authority Model: Technical Design* §4.3 (Claude Docs) | Record here that O1 supersedes the design recommendation **pending mentor confirmation**; leave the design doc unchanged as a historical record |
| `config/synthetic_smoke.json` uses three positive bases (no `DIRECT_OBSERVATION`) | Synthetic placeholder config | None needed: placeholders only, and the synthetic generator never emits `DIRECT_OBSERVATION`. Optionally align for consistency |
| O6 says "seen-publisher first". The current code evaluates only **unseen** pairs at the validation stage, and evaluates seen and unseen **test** pairs together at the single test opening. Read literally, "examine test seen-publisher results first, then decide" would allow test results to influence later choices | `src/fha/pipeline.py` (`run`, `render_markdown`) | Define the seen-publisher diagnostic on **validation** seen-publisher pairs (`val_seen`, already produced by the split) before the test is opened. At the single test opening, report `test_seen` and `test_unseen` together, with no changes between them. Needs a small code change and tests (Section 1, item 7) |
| The real-mode guard treats any non-null config value as resolved; it cannot distinguish "owner-decided" from "mentor-approved" | `pipeline.real_mode_blockers` | Add a `decision_approvals` block (`decided_by`, `approved_by`, `date` per key) and require `approved_by` for label-defining keys (O1–O4). Needs owner agreement before implementing |

## 1. Implications of the owner decisions (files that would need to change)

None of these changes has been made.

| # | Decision | File / setting | Required change | Implication |
| --- | --- | --- | --- | --- |
| 1 | O1–O4 | `config/config.template.json` | Set `positive_bases` to all four bases; `record_keeper_rule: "designated_only"`; `quotation_rule: "content"`; `self_report_rule: "positive_with_interested_flag"` | Do this only once approval status is settled; entering values removes four real-mode blockers |
| 2 | O1 | Labels and evaluation | `DIRECT_OBSERVATION` positives (e.g. news outlets with reporters on scene) enter the positive class | More news-type positives; publisher-type priors become weaker; annotation needs strict evidence rules for observation. Report results with and without `DIRECT_OBSERVATION` as a sensitivity analysis |
| 3 | O2 | `config/role_rules.draft.json` | Already consistent (`OFFICIAL_STATISTIC → STATISTICS_OFFICE` only) | The rule and the features use **publisher type** as a proxy for "designated record-keeper". Where a ministry or central bank is the designated producer, the proxy is wrong. The annotation manual needs a procedure for verifying designation; a future relation feature (`designated_record_keeper`) would need a documented source (research item) |
| 4 | O3 | Annotation manual; `action_type` extractor spec; `schemas/feature_schema.json` description text | Quoted claims are classified by the action in their **content** (e.g. `OFFICIAL_STATISTIC`); `UTTERANCE` reserved for claims about the act of speaking | No schema-level change; `speaker_relation` is expected to carry little positive weight for quoted statistics |
| 5 | O4 | Annotation manual | State which basis a self-report receives (proposed: `INSTITUTIONAL_ACT` for its own acts and conduct, `OFFICIAL_RECORD` for its own filed records); always add `INTERESTED_PARTY` | No schema change (flag already exists). Error analysis already reports flagged pairs |
| 6 | O5 | Data records; reports | Add a top-level metadata field `candidate_origin` ∈ {`retrieval`, `curated`} (never a model feature); report metrics and positive rates by origin | Curated additions risk making positives easy to find (curators add likely authorities). Selection bias must be measured by comparing origins |
| 7 | O6 | `src/fha/pipeline.py`, tests | Add a validation-stage seen-publisher diagnostic on `val_seen`; order the report seen → unseen; keep the single test opening | Small code change; no change to the primary test |
| 8 | Reproducibility (found during Git setup) | `.gitattributes` (new) | Add `* text=auto eol=lf` for `*.json`, `*.py`, `*.md` | Git's global `core.autocrlf` will check files out with CRLF line endings. `bundle.json` stores the feature schema's SHA-256 and refuses to load if it changes, so a fresh Windows clone could not reload a model trained elsewhere. Fixing the line-ending policy keeps hashes stable |

## 2. Remaining unresolved decisions

"Blocks" means the earliest stage that cannot responsibly start until the item is decided. Verified against `config/config.template.json` (all keys `null` except as noted) and `config/role_rules.draft.json` (status `DRAFT_UNAPPROVED`).

| Item | Why it matters | Decided by | Blocks |
| --- | --- | --- | --- |
| Mentor confirmation of O1 (`positive_bases`) | Defines the target | Mentor | **Data collection** (annotation manual) |
| Mentor confirmation of O2–O4 | Label rules; the guard cannot yet record approval | Mentor (owner has decided) | **Data collection** if the mentor disagrees |
| Designated-record-keeper verification procedure (from O2) | Annotators need a rule for establishing designation | Owner drafts, mentor approves | **Data collection** |
| Exact candidate-generation and curated-addition procedures (O5) | Negatives, selection bias, ranking metrics | Owner drafts, mentor approves | **Data collection** |
| `role_rules.draft.json` approval, version and hash | Baseline 1 must be frozen before labels are seen | Owner + mentor | **Data collection** (before labels exist) |
| `available_features` | Determines what is extracted and from which dated sources | Owner + mentor | **Data collection** |
| `temporal_split_required` | Requires reliable claim dates and dated knowledge-base snapshots to be collected | Mentor | **Data collection** (what metadata to record); temporal split code not implemented |
| `merge_corporate_families` | If true, `publisher_family_id` must be collected | Mentor | **Data collection** (metadata); training (split) |
| `min_annotator_agreement` | Pilot pass/fail rule must exist before the pilot | Mentor | **Data collection** (pilot annotation) |
| `annotator_feature_diagnostic_allowed` | If true, annotators must also record feature values | Mentor | **Data collection** (annotation form); diagnostic not implemented |
| `cannot_judge_policy` | Training target (proposal: `exclude`, with two sensitivity runs) | Mentor | **Training** |
| `hub_max_claim_share` | Composition of held-out publishers | Mentor | **Training** (split) |
| `test_unit_fraction`, `val_unit_fraction` | Pruning cost (57% of pairs discarded in the synthetic run at 0.5); affects how much data must be collected | Owner + mentor | **Data collection** (sizing); training (split) |
| `score_limited_pairs` | Unknown-value bias handling | Mentor | **Training** |
| `per_claim_weighting` | Training objective | Owner (low risk) | **Training** |
| `calibration_acceptable` | Recalibration trigger | Mentor | **Training** |
| Seen-publisher diagnostic design (O6) | Must not let test results influence choices | Owner + mentor | **Final evaluation** (pre-registration) |
| Hard-negative definition and metrics | Robustness metric not yet defined or implemented | Mentor | **Final evaluation** (pre-registration) |
| `delta_min_auprc` and its justification | Without it the outcome is `NOT_CLASSIFIABLE` | Mentor | **Final evaluation** (must be fixed before test labelling) |
| Guard support for recording approvals (Section 0.1) | Distinguishes owner decisions from mentor approval | Owner | Training (real-mode run) |

## 3. Proposed in the design and implemented (DESIGN-PROPOSED; confirm or reject)

| Decision | Where |
| --- | --- |
| L2 logistic regression, lbfgs, no class weights in the main model | `models.LogisticModel`, `config.model.class_weight` |
| One explicit interaction: `action_type × publisher_type`, cells kept only with ≥ `min_count` training pairs | `schemas/feature_schema.json` `derived_interactions`, `encoding.Encoder` |
| Missing values kept as an explicit `UNKNOWN` level; `NOT_COMPUTED` shares that column but is reported at inference | `encoding`, `pipeline.predict` |
| Information status rules (`INELIGIBLE`, `INSUFFICIENT`, `LIMITED`, `SUFFICIENT`) | `schema.info_status` |
| Hyperparameters (C, `min_count`) by log loss on grouped, publisher-disjoint inner folds; ties to simpler | `pipeline.tune_lr` |
| Platt recalibration on validation only, triggered by `calibration_acceptable` | `calibration`, `pipeline.fit_all` |
| Primary metric AUPRC on unseen-publisher test pairs; primary comparison claim-conditioned vs publisher-only | `config.evaluation` (consistent with O6) |
| Two-way bootstrap primary; claim-only and publisher-only also reported | `bootstrap` |
| Outcome classes SUPPORTED / UNSUPPORTED / INCONCLUSIVE / HARMFUL / NOT_CLASSIFIABLE | `bootstrap.classify_outcome` |
| Test opened once (lock file) | `pipeline.run` (consistent with O6) |

## 4. Implementation choices made in code (not in the design; reviewable)

| Choice | Reason | Alternative |
| --- | --- | --- |
| Full one-hot (no dropped reference level) | L2 makes coefficients identifiable; simpler contributions | Reference coding |
| Inner CV = repeated grouped publisher-disjoint holdouts, not strict k-fold | Strict k-fold with publisher-disjointness is not generally possible | — |
| Claim groups stratified only by "contains a positive" | Keeps positives in every split | Also stratify by action type or date |
| Near-duplicate grouping = token Jaccard ≥ 0.8 on `claim_text`, plus explicit `claim_group_id` | No embedding model download permitted | Embedding similarity + manual review |
| Ranking ties broken by `pair_id`; number of claims with ties reported | Deterministic | Expected metrics over tie orderings |
| Classification threshold for error analysis = max F1 on validation | Never chosen on test | Fixed threshold |

## 5. Questions to take to the mentor

1. Do you confirm all four positive bases, including direct observation (O1)? Should results also be reported without it?
2. Do you confirm the designated-record-keeper, quotation-content and self-report rules (O2–O4)? How should annotators verify that a body is the *designated* record-keeper?
3. Is excluding `CANNOT_JUDGE` acceptable as the main analysis, with the two sensitivity runs?
4. What exact candidate-generation and curated-addition protocol, and how should selection bias between the two origins be assessed (O5)?
5. Should the seen-publisher diagnostic run on validation seen-publisher pairs before the test is opened (O6)?
6. Corporate families and very common publishers in the hold-out? Which hold-out fractions, given the pruning cost?
7. Is a temporal test required?
8. Which features will genuinely be available, and from which dated sources?
9. Should `LIMITED` pairs be scored? May an annotator-feature diagnostic be run on validation only?
10. How is a "hard negative" defined for the robustness metrics?
11. What minimum meaningful difference, agreement minimum and calibration range, and how are they justified?
