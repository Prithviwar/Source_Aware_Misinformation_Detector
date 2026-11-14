# Project status

Last updated 2026-10-29. Statuses: `COMPLETE` (exists and verified), `IN PROGRESS`, `BLOCKED` (needs decision, data, permission or resource), `DEFERRED` (postponed by instruction).

## Milestones

| Milestone | Status | Deliverables | Verification evidence | Remaining blockers |
| --- | --- | --- | --- | --- |
| A. Audit and setup | COMPLETE | Separate project directory; `README.md`; this tracker; `config/config.template.json`; `schemas/feature_schema.json`; `schemas/label_schema.json`; `docs/REPRODUCIBILITY.md`; `docs/DECISIONS.md` | Files exist; schemas are loaded and enforced by the tests | — |
| B. Model pipeline | COMPLETE (synthetic-verified) | `encoding`, `models`, `calibration`, `schema` (validation, info status), `pipeline.predict`, JSON serialisation with checksum, CLI `predict` | 68/68 tests pass (`docs/test_results.txt`), covering missing features, unknown and unseen categories, malformed records, prohibited inputs, insufficient information, save/reload identity, tamper detection | Feature extractors deliberately not built (needs data and decisions) |
| C. Baselines and evaluation code | COMPLETE for listed items (synthetic-verified); gaps below are IN PROGRESS | Four models; publisher-disjoint split with diagnostics; AUPRC, AUROC, Brier, log loss, calibration slope/intercept, reliability table, NDCG@k, hit@k, within-publisher AUROC with publisher-resampled interval; AUPRC/AUROC by publisher type and action type; paired bootstrap (two-way, claim, publisher); outcome classification; error analysis; shuffled-pairing control; markdown and JSON reports | Smoke run `outputs/synthetic_smoke/` (stamped SYNTHETIC); tests for every metric, split disjointness, family merging, reproducibility, outcome classes | See "Known gaps" |
| D. Methodological decisions | IN PROGRESS | `docs/DECISIONS.md`: six project-owner decisions recorded (O1–O6, mentor approval not recorded), conflicts and file-level implications listed, remaining decisions tabulated by decider and blocking stage | Config deliberately unchanged, so `fha.cli status` still lists 18 blockers | Mentor confirmation of O1–O4; remaining decisions in DECISIONS.md §2 |
| E. Data readiness and training | DEFERRED, then BLOCKED | Data-manifest template; real-mode guards | Real-mode run refuses: unresolved decisions, unapproved rules, missing or unauthorised manifest, synthetic or AI-labelled data (tested) | Dataset construction deferred until holidays; decisions in D |
| F. Final evaluation | BLOCKED | Evaluation code ready; test lock implemented | — | Needs E |
| G. Package | BLOCKED | `fha.cli package` (refuses synthetic or unevaluated runs, tested); draft `docs/MODEL_CARD.md` | — | Needs F |

## Known gaps (not yet implemented)

| Item | Status | Why |
| --- | --- | --- |
| Temporal split | BLOCKED | Implement only if decision `temporal_split_required` is `true` and claim dates are reliable |
| Annotator-derived oracle-feature diagnostic (validation only) | BLOCKED | Decision `annotator_feature_diagnostic_allowed` |
| Hard-negative subset metrics | IN PROGRESS | Needs an agreed definition of "hard negative" (same type or topic, not first-hand) |
| Debiased calibration error, mixed-effects sensitivity model | DEFERRED | Optional in the design |
| Embedding-based near-duplicate grouping | BLOCKED | Would need a model download (not permitted); lexical Jaccard used |
| Validation-stage seen-publisher diagnostic (O6) | BLOCKED | Design to be confirmed (DECISIONS.md §0.1); small code change once agreed |
| `candidate_origin` metadata and per-origin reporting (O5) | BLOCKED | Waits for the candidate-generation protocol |
| Line-ending policy (`.gitattributes`) so schema hashes survive checkout | IN PROGRESS | Proposed in DECISIONS.md §1 item 8; not applied |

## Smoke-test observations (synthetic; mechanics only, not evidence)

- The pipeline runs end to end; all four models are scored on identical pairs; zero publisher/family and claim-group overlap between training and held-out sets.
- **Design finding:** with hold-out fractions of 0.5, pair pruning discarded 965 of 1,679 usable pairs (57%) because candidate publishers recur across claims. Real-data sizing and the hold-out fractions need a decision.
- Calibrators fitted on validation make validation calibration figures in-sample; the report now says so and keeps pre-calibration values.

## Change log

| Date | Change |
| --- | --- |
| 2026-10-29 | Project created; schemas, config, pipeline, baselines, evaluation, CLI, 68 tests, docs. Added per-category metrics and within-publisher interval. Smoke run executed on synthetic fixtures. Verified that no file in the frozen experiment was modified (all its recent modifications predate this work). |
| 2026-10-29 | Git initialised in this directory only; `.gitignore` excludes data, annotations, outputs, models, caches and secrets; baseline commit `0bf11fc`. Project-owner decisions O1–O6 recorded in `docs/DECISIONS.md` with conflicts, implications and remaining decisions; no config, schema or code changed. |

## Boundaries kept

No dataset search or construction; no annotation; no external API calls; no package installation; no downloads; nothing read from or written to `Source_Aware_Misinformation_Detector`. All synthetic outputs are labelled as such and the real-mode guard refuses synthetic records.
