# Pilot review: when does the guide need clarifying? (fixed 2026-09-30, before any pilot label exists)

**Owner-facing. Do not put this file in the handout.**

## Hard constraints on the review

1. The review uses **only** four inputs:
   - the returned pilot sheet(s);
   - `check_pilot_annotation.py` output;
   - `PILOT_FEEDBACK.md`;
   - the annotator's questions.

   It never looks at gold evidence, gold publishers, rankings, model predictions or A–H results for these 15 claims. It never runs `score_heldout_primary.py score`.
2. Allowed changes: **wording, examples, the authority-type list and sheet mechanics** in `ANNOTATION_GUIDE.md` and `PILOT_INSTRUCTIONS.md`.
3. Not allowed: the primary-source definition, the scoring rule, the metrics and the tests. All of these are frozen in `docs/source_targeted_preregistration.md` Addendum 2, and the same goes for the scorer and the rankings.
4. Every guide change is logged in `../CHANGELOG.md` with date, reason and the pilot row(s) that motivated it. Then re-run `python heldout_primary_pilot.py`, which re-copies the guide and repeats the leak scan.
5. The pilot sheets are never scored.
   - If the guide changes in substance, the annotator re-does rows 1–15 in the full 192-row sheet under the final guide, without looking at their pilot answers.
   - If nothing changes, they may copy their pilot rows into rows 1–15.

## Triggers (any one means: clarify the guide, then start the 192)

| # | Signal (source) | Trigger |
|---|---|---|
| 1 | Format problems (`check_pilot_annotation.py`) | The same problem type in **≥ 3 rows**, e.g. bare `@handle`, missing type, "multiple" with 1 authority. The column instructions are unclear. |
| 2 | `authority_situation = unclear` | **≥ 4 of 15** rows |
| 3 | `confidence = low` | **≥ 5 of 15** rows |
| 4 | Authority type `other` | Used in **≥ 3 rows**, or the same missing type named twice in feedback. Extend the type list. |
| 5 | Listing secondary sources as authorities, i.e. news, fact-checkers, Wikipedia or aggregators named as primary (owner reads the names, **not** checked against gold) | **≥ 2 rows**. The "who issued the fact, not who is credible" rule needs a sharper example. |
| 6 | Feedback Q2: a definition was hard to apply | Any definition flagged by the annotator, including the "X said Y" rule. |
| 7 | Rule breach, e.g. searched the claim or used an AI tool (feedback, `research_used`) | Any breach. Restate the rule; the breaching rows must be redone. |
| 8 | Time (feedback) | Median above **4 min/claim**, i.e. more than about 60 min for the 15. Simplify or shorten the guide. |
| 9 | With 2 annotators (`agreement` block) | Situation agrees in **< 10/15** rows, **or** any-key overlap in **< 9** of the rows where both list an authority. Discuss the disagreeing rows. |

## If no trigger fires

Start the full 192-row sheet with the unchanged guide.

The thresholds are pragmatic, not statistical: 15 claims cannot estimate reliability precisely. The purpose is to catch unclear instructions before 4–6 hours of work.

## Addendum (2026-10-02): applying these criteria to an AI annotator (Addendum 3)

The original criteria above are unchanged and apply to human annotators, none of whom were used.

For the AI pilot, the inputs are:
- evidence-level runs A and B on the 34 gold URLs of the 15 pilot claims;
- one claim-level run on the 15 claims;
- the runner's error log;
- the labels, rationales and notes.

As before, the review never uses rankings, predictions, results, or other annotations as a reference for correctness.

| # | AI version of the trigger | Threshold |
|---|---|---|
| 1 | Unparseable or invalid output after the retry | ≥ 2 items in a run → fix the prompt's mechanics |
| 2 | `unclear` (evidence) or `authority_situation = unclear` (claim) | ≥ 25% of the items in a run |
| 3 | `confidence = low` | ≥ 33% of the items in a run |
| 4 | Claim level: type `other` | ≥ 3 of 15 claims |
| 5 | A news outlet, fact-checker, encyclopedia or aggregator labelled `primary` (evidence) or listed as an authority (claim). The owner reads the publisher names; this is not checked against any reference. | ≥ 2 items |
| 6 | The same definitional difficulty raised in rationales or notes | ≥ 2 items |
| 7 | Tool use or a rule breach | Impossible by construction (no tools). Checked by `num_turns` = 1 and no tool fields in the CLI output. Any breach → stop. |
| 8 | Time | Not applicable. Cost and latency are recorded, for information only. |
| 9 | Stability (run A vs B, evidence level) | Primary-vs-not agreement < 90%, **or** 4-way Cohen's κ < 0.70 → inspect the discordant items and clarify the wording |

- **If a trigger fires.** Change only the prompt's wording, examples or mechanics. Log the change in `../CHANGELOG.md`, re-run both evidence runs, and review again. At most 2 rounds; after that, freeze and report which triggers remained.
- **If none fires.** Freeze.
- **In all cases.** Pilot labels are never scored, and they are relabelled in the full run.

### Outcome of the AI pilot review (2026-10-02)

These are AI-generated labels (MODEL_GENERATED), not human annotation.

- **Round 1** (prompt `417a609c…`):
  - Stability passed: A/B 97.1%, 4-way κ 0.954; primary-vs-not κ 0.939.
  - Criterion 6 fired twice: (i) sub-question vs whole claim; (ii) re-hosted copies.
  - The prompt was clarified (`CHANGELOG.md`).
- **Round 2** (prompt `87eae830…`, the final permitted round):
  - Stability **passed**: primary-vs-not agreement 100%, κ 1.000; 4-way agreement 94.1%, κ 0.906.
  - Criteria 1–5, 7 and 9 did not fire; criterion 8 does not apply.
  - **Criterion 6 remained triggered**: a derived-vs-secondary ambiguity on items 79 and 205. It does not affect the primary-vs-not endpoint.
  - Item 148 is recorded as an isolated limitation in applying the background/definition rule.
- **Frozen** after round 2, without a further revision. See `ai/FROZEN_HASHES.json` and `docs/source_targeted_preregistration.md` Addendum 3.
