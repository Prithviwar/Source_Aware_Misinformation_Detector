# Authority v2: decision log (append-only)

Entries are only ever appended; earlier entries are never edited. Each entry gives the date, the decision, who made it, its source, and its rationale. The preregistration is `docs/authority_v2_preregistration.md`.

---

## DL-001 (2026-10-28): design adopted
- **Decision:** Option 1. The reserved 180-claim set serves Family R (a reserved-set replication of the frozen D-vs-A validation) and Family N (T vs D, with the gold-blind X control). Family R is reported first.
- **Decided by:** project owner. **Source:** earlier design rounds.

## DL-002 (2026-10-28): defaults 1–6
- **Decision:**
  1. Wikidata cache copy with missing-only lookups;
  2. T parse failures become abstentions;
  3. the probe is a distinct step;
  4. prespecified development selection on 120 + 200 claims;
  5. T gets publisher keys and counts only, with no `DOMAIN_OVERRIDES`;
  6. X excludes T and D keys and matches same type, then nearest count.
- **Decided by:** project owner. **Source:** "confirmed defaults" message.

## DL-003 (2026-10-28): Family R rule A (U10)
- **Decision:** A requires all of: primary p < 0.05; a positive primary CI; and, for secondary test 4 ("R@10 vs generic"), diff > 0 **and** Holm-adjusted p < 0.05.
- **Decided by:** project owner (approval item 1). **Rationale:** the most faithful reading of "after Holm correction".

## DL-004 (2026-10-28): rule C
- **Decision:** a primary point-estimate R@10 difference ≤ 0 is C.
- **Decided by:** project owner (approval item 2).

## DL-005 (2026-10-28): unrun probe (U11)
- **Decision:** A/B/C criteria are not changed. If the probe is not run, the report states that the recognised-subset example in B could not be evaluated.
- **Decided by:** project owner (approval item 3).

## DL-006 (2026-10-28): probe handling (R-D10)
- **Decision:** the frozen script is unchanged. The wrapper calls `analyse()` with `probe=None` when the probe was not run and records the probe status in a separate file. The probe is a distinct, explicitly logged step.
- **Decided by:** project owner (approval item 4).

## DL-007 (2026-10-28): T output handling (U12)
- **Decision:**
  - parse failures are retried for up to 3 passes, then become `parse_failure` with no keys;
  - `abstain = true` overrides any selections (`abstain_conflict`);
  - keys are normalised by `strip()` and `lower()` only and must be exact members of the supplied pool;
  - duplicates are removed keeping the first; at most 3 keys are kept in model order (`truncated`);
  - `abstain = false` with no valid keys gives `empty_selection`;
  - a non-boolean `abstain` is a parse failure.
- **Decided by:** project owner (approval item 5).

## DL-008 (2026-10-28): Family N denominator
- **Decision:** use Family R's `gold_c`. D prediction failures are excluded and counted separately. T failures stay in as abstentions. Claims whose gold lies outside the top-100 stay in as misses.
- **Decided by:** project owner (approval item 6).

## DL-009 (2026-10-28): U1a, U1b, U2–U9
- **Decision:** apply the v5-review recommendations:
  - **U1a:** if no version is admissible, Family N is not run; Family R proceeds;
  - **U1b:** if the selected W ≤ 0, proceed and report;
  - **U2:** alphabetical code-point order;
  - **U3:** `.example` worked examples allowed in V2/V3;
  - **U4:** 5%;
  - **U5:** confidence is descriptive;
  - **U6:** T authority accuracy, descriptive;
  - **U7:** proceed and record, stopping only if a member is missing;
  - **U8:** same-type-only sensitivity check, descriptive;
  - **U9:** halt development scoring on a contradiction.
- **Decided by:** project owner (approval item 7). Rationales are in the preregistration, §10.

## DL-010 (2026-10-28): v5-review corrections incorporated
- **Decision:** corrections C1–C11 are incorporated into the preregistration. They cover:
  - the authority-accuracy population `evald`;
  - both probe subsets;
  - an inputs-only `HO_SAMPLE` before scoring;
  - T's development Wikidata block copied verbatim from D's stored prompt;
  - spaCy and `tldextract` versions in R-D6;
  - Family N descriptive metrics via `source_targeted_eval.score` definitions;
  - no cross-family correction;
  - Family N's eligible set equal to `gold_c`;
  - raw hashes of development inputs at freeze 1.
- **Decided by:** project owner (approval item 7, "apply the recommendations already documented").

## DL-011 (2026-10-28): open item, not resolved
- **Item:** the number of development versions beyond V1. The preregistration allows at most 3, but no review recommends a stopping rule.
- **Handling:** per the instruction "do not silently invent a resolution", no rule is invented. V1 is run. The project owner decides on V2/V3 after V1's development scoring, and that decision is appended here before any V2 call.

## DL-012 (2026-10-28): execution authorisation
- **Decision:** the project owner authorises implementation, development LLM/API calls, approved network access and downloads, reserved D/T calls, the separate memorisation probe, and the single preregistered scoring pass, following the gate order.
- The probe and reserved-gold gates still each get their own entry in `results/authority_v2/logs/execution_log.jsonl` at the time they are crossed.

## DL-013 (2026-10-28): approval re-confirmed; documents checked before freeze 1
- **Event:** the project owner re-sent the approval message (items 1–10, execution authorisation, execution discipline).
- **Check:** each item was compared with this log (DL-003 to DL-012) and the preregistration (§0, §2.2, §3.2, §4.1, §4.2, §5, §7, §10). All ten items are already recorded. **No preregistration text was changed.**
- **Still open:** DL-011 (development versions beyond V1). No recommendation exists, so none is invented. The owner decides after V1's development scoring.
- **Next:** freeze 1 (`MANIFEST_freeze1.json`), preceded by the frozen-file hash gate. If the gate fails, freeze 1 is not taken.
- **Recorded by:** the executing session. **Source:** the owner's approval message of 2026-10-28.

## DL-014 (2026-10-29): V1 completed and scored; DL-011 still open
- **Event:** the V1 development run was interrupted at 264/320 (4 empty-output CLI errors; 56 claims never called) and completed with the frozen `_run_calls` resume, using the manifest-matching resolver bytes (`9f98938e…`). The `run_reserved` version (`fd6c12ea…`) was restored afterwards. Per-claim attempts: 316 × 1, 4 × 2 (claims 330, 333, 334, 337); none exceeded 3. Execution-log entries: `t_dev_v1_interruption_and_resume_plan`, `t_dev_run_resume`, `t_dev_run_done`, `t_dev_v1_resume_closed`, `dev_score_done`.
- **V1 result (development, exploratory):** f = 0.000 (admissible); N = 266; W = −3 (S = −0.0113); T−X at R@10 = +30; T−D at R@20 = 0. Cost: USD 7.85 over 324 calls.
- **Owner message (2026-10-29):** proceed per the prespecified selection procedure up to three versions; run V2/V3 only "if the procedure calls for" them; stop if a rule is genuinely unspecified.
- **Check against §7:** the procedure caps versions at 3 and specifies how to choose among versions that exist. It does **not** specify whether V2/V3 are written. No threshold or criterion in §7 triggers a further version. DL-011 therefore remains open. No V2 prompt has been written, `selection.json` has not been created, and nothing reserved has been accessed.
- **Recorded by:** the executing session.

## DL-015 (2026-10-29): DL-011 resolved, final: development stops at V1
- **Decision:** prompt development stops at V1. No V2 or V3 will be written or run. The preregistered selection rule (§7) is applied to the versions that exist, i.e. V1 only.
- **Rationale:** §7 permits up to three versions but does not require additional versions, and contains no criterion that triggers one. Stopping at V1 involves no outcome-dependent rule. The decision was made after V1's development scoring (DL-014: f = 0, W = −3), which is disclosed; since no further version is created, development results cannot be improved by it. Thresholds (f ≤ 0.05) and the lexicographic rule are unchanged. U1b applies if the selected W ≤ 0: proceed, and report the development result alongside.
- **Constraints restated:** reserved gold is not accessed, and no reserved-set call is made, until the freeze-2 checks and hashes are verified and the later gates in §8 are passed.
- **Decided by:** project owner (message of 2026-10-29, choosing option 1). **Recorded by:** the executing session.
