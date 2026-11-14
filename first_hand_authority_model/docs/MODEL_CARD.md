# Model card: first-hand authority model (DRAFT)

**Status: DRAFT. No real model has been trained. The Evaluation section is empty by design until an authorised real run exists.**

## Model

- **Task:** for a claim–publisher pair, estimate P(first-hand authority | claim, publisher, eligible features).
- **Architecture:** L2-regularised logistic regression over one-hot categorical features plus `action_type × publisher_type` interaction cells; optional Platt recalibration fitted on validation data.
- **Inputs:** precomputed features defined in `schemas/feature_schema.json`. Feature extractors are not part of this package.
- **Outputs:** `p_first_hand` or `null`, `info_status`, reasons, top contributions, warnings.

## Intended use

Ranking candidate publishers for a claim by how likely each is to hold first-hand standing for its central fact, as one input to a separate evidence-retrieval or review process.

## Prohibited interpretations

- Not the probability that a claim is true or false.
- Not a measure of a publisher's general reliability, reputation or popularity.
- Not evidence that a page is relevant to or supports a claim.
- A low or missing score caused by missing information (`LIMITED`, `INSUFFICIENT`) is not evidence that a publisher lacks authority.
- First-hand standing does not imply correctness: interested parties can have first-hand standing and still be wrong or misleading.

## Known limitations (from design and smoke testing)

- Depends on upstream feature extractors (claim type, topic, actor and speaker linking, knowledge-base relations) that do not yet exist.
- Knowledge-base coverage favours large institutions; `UNKNOWN` values may bias scores against small genuine authorities.
- Only scores candidates it is given; cannot find authorities outside the candidate list.
- Probabilities may be miscalibrated for unseen or rare publisher types.
- The label definition has open decisions (`docs/DECISIONS.md`); results may not transfer between definitions.
- Publisher-disjoint pruning discards many training pairs when candidates recur across claims (57% in the synthetic smoke run).

## Training data

None yet. Dataset construction is deferred until authorised.

## Evaluation

Not available. To be filled from an authorised real run's `report.json` (primary AUPRC difference with two-way bootstrap interval, outcome class, discrimination, calibration, ranking, within-publisher AUROC, error analysis, split diagnostics).
