# Preregistration: claim-specific authority resolution on the reserved AVeriTeC set (authority v2)

**Status:** final text for freeze 1, written 2026-10-28. It consolidates review draft v5, the v5 review corrections and the final review pass, together with the decisions approved by the project owner on 2026-10-28 (§0, §10, and `docs/authority_v2_decision_log.md`).

**Freezes**

- **Freeze 1:** this document and `experiments/authority_v2/config.json`, plus raw hashes of every development input that has no recorded freeze hash. Taken before any development LLM call.
- **Freeze 2:** after the development version is selected, and before `dev.json` is downloaded or the reserved claims are identified.
- **Freeze 3:** before any reserved gold is read.

**Unchanged by this study:** `docs/validation_preregistration.md`, `docs/source_targeted_preregistration.md` (with its addenda), and every frozen artifact (rankings, predictions, scorer code, the canonical annotation sheet and gold-informed materials).

**Counts.** Counts marked *(stored)* come from frozen artifacts or earlier session analyses. Scripts re-derive and log them at run time, and halt on any difference.

---

## 0. Approval status

| Item | Status |
|---|---|
| Option 1: the reserved set serves Families R and N. Conditions A/D/T/X. Two separate families, with Family R reported first and unconditionally | Approved |
| Defaults 1–6: Wikidata cache copy with missing-only lookups; T failures become abstentions; probe preregistered as a distinct step; prespecified development selection on 120 + 200 claims; T gets publisher keys and counts only, with no `DOMAIN_OVERRIDES`; X excludes T and D keys and matches same type, then nearest count | Approved |
| U1a, U1b, U2–U9 (recommendations of the v5 review) | Approved 2026-10-28 (§10) |
| U10, rule-C reading, U11, R-D10 (probe handling), U12 (T output rules), Family N denominator | Approved 2026-10-28 (§4, §2.2, §10) |
| Execution: implementation, development LLM calls, network and downloads, reserved D/T calls, the memorisation probe, the single scoring pass | Authorised 2026-10-28, subject to the gate order in §8. The probe and reserved-gold gates still get their own log entries |
| **Number of development versions beyond V1** | **Not decided.** No review contains a recommendation. Decided by the project owner after V1 is scored on development (§7) |

---

## 1. Research question and hypotheses

**RQ.** Within a fixed candidate pool, does improving claim-specific authority resolution improve AVeriTeC evidence retrieval compared with the frozen baseline?

**Family R: reserved-set replication of the preregistered procedure.**
- The procedure of `validation_preregistration.md` is applied to new claims.
- This is **not an exact replication**; deviations are listed in §4.1.
- **H_R1:** GoldR@10(D) > GoldR@10(A).
- The original five-test secondary family and the A/B/C decision rule apply. Their operational reading is fixed in §4.1.

**Family N: new experiment.** The hypotheses are directional; all tests are two-sided.

| Hypothesis | Comparison | Role |
|---|---|---|
| H_N1 | GoldR@10(T) > GoldR@10(D) | Primary |
| H_N2 | GoldR@10(T) > GoldR@10(X) | Secondary |
| H_N3 | GoldR@10(T) > GoldR@10(A) | Secondary |
| H_N4 | GoldR@5(T) > GoldR@5(D) | Secondary |
| H_N5 | GoldR@20(T) > GoldR@20(D) | Secondary |

**Dependence between the families.** Both families use the same claims, pools and D predictions. They are separate analyses of one dataset, not independent replications. Neither family's result enters the other's decision. There is no multiplicity correction across families; each family controls its own error rate as specified.

---

## 2. Conditions

### 2.1 Shared fixed components

- **Corpus:** frozen `baseline_retrieval.retrieval_corpus`. The retriever reads `{url_norm, text}` only.
- **Retrieval:**
  - BM25 via frozen `rank_bm25`;
  - dense via frozen `rank_dense` (`all-MiniLM-L6-v2`, 128 tokens, first 1,000 characters);
  - hybrid = RRF (k = 60) as in the frozen `validation_heldout.cmd_rank`;
  - the query is the claim text.
- **Fixed pool:** the hybrid top-100 per claim. **This experiment cannot test retrieval outside the pool.**
- **Rerank:** frozen `validation_heldout.rerank`, which computes `minmax(hybrid score in pool) + λ·1[cand_key(url) ∈ K_c]` with λ = 1.0 and a stable sort.
- **Publisher key:** frozen `validation_heldout.cand_key` = `social_key(url) or org_domain(url)`. Empty keys are never listed, selected or matched.
- **Scorer:** frozen `validation_heldout` hit definitions, `mcnemar`, `boot_ci` and `holm`.
- **Budget:** at most 3 boosted publishers.

### 2.2 Conditions (only the boosted key set K_c differs)

**A: no-authority ablation.** K_c = ∅, so A is the frozen hybrid order.

**D: frozen baseline.**
- K_c is the union of frozen `pred_keys` over the frozen L+Wctx predictor's top-3 entries (`validation_heldout.load_preds`).
- Frozen `SYSTEM`/`USER` prompts, model `claude-opus-5-5`, and the frozen `authority_resolution.call()`: `claude -p`, `--tools ""`, `--strict-mcp-config`, `--no-session-persistence`, an empty temporary directory, one call per claim, 300 s timeout.
- Wikidata context comes from the frozen `wd_context()`. Retries use the frozen `_run_calls`: 3 passes, 6 workers, each pass re-trying only claims still unparsed.
- **Development sets** use the existing frozen predictions: 120 in `results/authority_resolution_raw.jsonl` (cond `L+Wctx`) and 200 in `results/heldout/authority_raw.jsonl`.
- **The reserved set** gets one new run of this frozen predictor, shared by Families R and N.

**T: pool-grounded claim-specific resolver.**
- **Isolation:** model, CLI flags, isolation, timeout and the 3-pass/6-worker retry scheme are identical to D. T has its own frozen prompts (`experiments/authority_v2/prompts/T_{system,user}_v{k}.md`).
- **Inputs:**
  1. the claim, speaker, claim date and country ISO code, formatted as for D;
  2. the Wikidata block:
     - *development sets:* copied verbatim from the `prompt` field of D's stored record for the same claim. This is the text between the `Country (ISO): …` line and `Return JSON`;
     - *reserved set:* the frozen `wd_context()` string computed from the experiment's Wikidata cache. D and T receive the same string;
  3. the distinct non-empty `cand_key` values in the claim's hybrid top-100, each with its pool document count, in ascending Unicode code-point order of the key (U2).
- **Never provided:**
  - titles, URL paths, page text, ranks, scores;
  - gold URLs, gold publishers, labels, justifications, fact-check articles, roles;
  - `DOMAIN_OVERRIDES`, the diagnostic FACTCHECK list, the audit's government-rule fixes, the Phase-2 X1 assignment, or any other gold-informed list.
- **Instruction:** select at most 3 listed publishers that are first-hand authorities for the claim's central fact (using D's first-hand definition), or abstain.
- **Output (JSON):** `fact_at_issue`, `selections` (≤ 3 objects with `key`, `publisher_type`, `why`), `abstain` (boolean), `confidence` (descriptive only, U5).

**T output handling (U12, approved).** These rules are applied in this order and are deterministic.

1. **Extraction:** the frozen `call()` method. The first `{` to last `}` span (regex `\{.*\}`, DOTALL), then `json.loads`.
2. **Parsed:** the result is a JSON object with a list `selections` and a JSON boolean `abstain`. The following count as failures and are retried within the 3 passes:
   - CLI error, non-zero exit, timeout;
   - no JSON object, invalid JSON, a non-object;
   - a missing or non-list `selections`;
   - a missing or non-boolean `abstain` (for example the string `"true"`).
3. **Still unparsed after 3 passes:** K_c(T) = ∅, logged `parse_failure`, counted in f(v).
4. **`abstain = true`:** K_c(T) = ∅. Any supplied selections are ignored and logged `abstain_conflict`.
5. **Key validation:**
   - a selection's `key` must be a string;
   - it is normalised by `strip()` then `lower()` only, with no URL repair and no `www.` removal;
   - it must equal exactly a key in the supplied pool list, otherwise it is discarded and logged `invalid_key`;
   - a selection that is not an object, or has no string `key`, is discarded and logged `invalid_key`.
6. **Duplicates:** after normalisation the first occurrence is kept; later ones are logged `duplicate_key`.
7. **Truncation:** more than 3 valid keys are truncated to the first 3 in model order and logged `truncated`.
8. **`abstain = false` with no valid key left:** K_c(T) = ∅, logged `empty_selection`. This is reported separately from abstentions and parse failures.
9. **Result:** K_c(T) is the retained key set.

**X: gold-blind mismatched-authority control.**

Inputs are T's retained keys S = (p₁, …, pₙ) in T's order, all keys in K_c(D), and the claim's pool URLs. **X never reads gold, rankings beyond pool membership, outcomes, or random-number generators.**

1. **Pool attributes.** For each distinct non-empty pool key k:
   - **count(k)** is the number of top-100 pool documents with `cand_key` = k;
   - **type(k)** is the most frequent value of frozen `authority_retrieval.generic_prior(url_norm)` over those documents, from the set {1.0, 0.8, 0.6, 0.5, 0.3, 0.2}, compared as the exact floats returned. Ties go to the larger value. Known bucket defects (for example `*.go.com` scored 1.0) are applied as they stand and documented.
2. **Candidates.** Q = {distinct non-empty pool keys} \ (S ∪ K_c(D)). For logging, Q is kept sorted by code point.
3. **Tie-break digest.** d(q, i) = SHA-256 of `b"2029" + 0x1F + ascii(claim_id) + 0x1F + ascii(i) + 0x1F + utf8(q)`.
   - `claim_id` is the AVeriTeC dev index as ASCII decimal (no sign, no leading zeros);
   - `i` is the 1-based slot index;
   - `q` is the exact key string, UTF-8 encoded with no normalisation;
   - digests compare as 32-byte big-endian unsigned integers;
   - no Python `hash()`, no unordered-set iteration, no RNG.
4. **Slot matching**, for i = 1…n in T's order, each step choosing the argmin of (|count(q) − count(pᵢ)|, d(q, i), q by code point):
   - from Q_same = {q ∈ Q : type(q) = type(pᵢ)} if it is non-empty (flag `same_type`);
   - else from Q (flag `type_relaxed`);
   - else no match (flag `unmatched`).

   The chosen q is removed from Q.
5. **If T abstains or fails,** X = ∅ for that claim.
6. **Logged per claim and slot:** (pᵢ, qᵢ or null, flag, count(pᵢ), count(qᵢ), digest hex).
7. **Budget reporting:**
   - per claim: n_T, n_X, B_T = Σ count(pᵢ), B_X = Σ count(qᵢ);
   - across claims: the distribution, mean and median of B_X − B_T, the number of claims with B_X ≠ B_T, and the counts of `type_relaxed` and `unmatched` slots;
   - the share of X keys that are gold publishers, computed after scoring only, descriptive.

---

## 3. Populations, reachability and leakage controls

### 3.1 Two distinct quantities

**Corpus-level reachable gold.** R(c) is the set of the claim's normalised web gold URLs that match a non-empty retrieval-corpus document. This is the frozen `gold_info` semantics. **It determines eligibility.**

**Pool coverage.** Cov(c) = 1 if R(c) has a document in the claim's top-100. **It is a measured outcome, reported separately, and never an eligibility criterion.**

A claim whose R(c) lies entirely outside the pool stays in every denominator and is a miss for every condition at every k ≤ 100.

### 3.2 Populations

| Population | Size | Eligibility E | Reachability source |
|---|---|---|---|
| Development, 120 claims (`averitec_sample.jsonl`) | 120; **99** eligible *(counted 2026-10-28)* | stored `n_gold_reachable` ≥ 1 in `results/source_targeted/per_claim_dev.csv`, **and** a parsed frozen D prediction | The stored corpus-level count is used because the KS is not local. A hit needs only a gold URL in the top-k, since every ranked document is non-empty |
| Development, 200 used held-out claims | 200; **167** eligible *(earlier gate)* | R(c) ≠ ∅, reconstructed as web gold ∩ frozen full hybrid ranking, **and** a parsed frozen D prediction | `results/heldout/rankings_hybrid.jsonl.gz` |
| **Development total** | **320; N ≈ 266** | E = E₁₂₀ ∪ E₂₀₀ | – |
| **Reserved** | **180** | R(c) ≠ ∅ (frozen `gold_info` over the new extracts) **and** a parsed reserved D prediction: exactly `analyse()`'s `gold_c` | Computed at scoring, after freeze 3 |

- **Missing reachability (development 120):** a claim with no row or a missing or non-integer value is excluded from E and counted.
- **U9 (approved):** a stored count of 0 contradicted by a gold URL in that claim's frozen top-100 **halts development scoring**, which is then reported.

**Reserved exclusions**, counted and not imputed:
- KS extraction failure;
- D unparsed after 3 passes (excluded from both families, count reported separately);
- no web gold;
- web gold present but none reachable.

T and X failures never exclude a claim: T failures stay in as abstentions, so T = A for that claim and X = ∅.

**Denominators reported:** eligible (primary), claims with web gold, and all 180.

### 3.3 Reserved-set construction

- **Definition:** dev indices i ∈ [0, len(dev) − 1] not in the 120-claim or the 200-claim set, in ascending order. No sampling.
- Records are normalised with the frozen `build_sample.normalise`. **The run stops if the count is not 180.**
- **`data/processed/averitec_reserved180_inputs.jsonl`:** `claim_id`, `claim`, `speaker_or_entity`, `claim_date`, `location_ISO_code`.
- **`data/processed/averitec_reserved180_gold.jsonl`:** the full normalised records, sealed. Its raw hash is computed from the bytes at write time. The file is opened only by the scoring commands after freeze 3 and a recorded approval.
- `dev.json` itself holds gold for every claim. It is stored git-ignored under `data/raw/averitec/` and is read only by `build_reserved_sample.py`, which prints counts only.
- The KS extracts store the frozen audit-only fields `ks_type`/`ks_query`, as all earlier extracts do. No retrieval, T or X code reads them.

### 3.4 Wikidata (approved default 1)

- Copy the frozen `results/wikidata_resolution.json` to `results/authority_v2/wikidata/wikidata_resolution.json`, recording the raw hashes of both.
- Look up only the missing mentions through the frozen `cmd_wikidata` (frozen `search` and `fetch_presence`), with `wikidata_authority.CACHE` redirected to the copy.
- Log timestamps, new mentions, a key-level diff against the original, and library versions.
- **Frozen caches are never written.**

### 3.5 Leakage controls

- No reserved gold is read before freeze 3.
- T is developed only on the 320 already-used claims. There is no tuning or re-running after any reserved access.
- The gold-informed lists in §2.2 are excluded from T, X and all stratifiers. The T, X and wrapper scripts are reviewed for this before freeze 2, with a string check recorded in the freeze-2 manifest.
- **Reported threats:**
  - the KS was built partly from gold-derived queries, so pool publishers and counts correlate with gold;
  - the model may have memorised the 2020 claims;
  - the analysing session sees reserved gold once, at scoring;
  - the session that wrote T's prompt had seen development gold. This is permitted for development; the reserved set is untouched.

---

## 4. Analysis families

### 4.1 Family R: reserved-set replication of the preregistered procedure

**Fidelity to `validation_preregistration.md` and the frozen `validation_heldout.analyse()`:**

| Element | Preregistration | Frozen code | Family R |
|---|---|---|---|
| Primary population | ≥ 1 human gold web URL with non-empty KS text | `gold_c` = reachable gold **and** parsed prediction (l. 333) | Identical. Missing predictions are excluded, as in the script |
| Authority-accuracy population | ≥ 1 human gold web URL | `evald` = parsed prediction **and** ≥ 1 web gold publisher key, unreachable included (l. 391) | Identical |
| Primary | GoldR@10, D vs hybrid; exact McNemar, two-sided, α = 0.05; paired bootstrap 95% CI (10,000, seed 2026) | l. 351 | Identical |
| Secondary family (Holm over 5) | R@5 and R@20 vs hybrid; R@5, R@10 and R@20 vs generic | `fam` l. 355, `holm` l. 364 | Identical |
| Descriptive items | as listed | as coded, with K = (5, 10, 20) | Identical; nothing added |
| Probe | one call per claim; "likely recognised" = fact-checker registered domain equals the `fact_checking_article` domain | `cmd_probe` and the block at l. 430: both subsets, each with hybrid/generic/authority R@10, an exploratory McNemar and authority top-3 accuracy | Identical, if the probe is run |
| Decision rule | quoted below | not computed by the script | Applied by the wrapper with the approved reading below |

**Decision rule.** Verbatim from `validation_preregistration.md`:
- *"**A (strong enough to continue):** primary endpoint significant (p < 0.05) with a positive CI, **and** predicted > generic on R@10 after Holm correction."*
- *"**B (promising, not validated):** positive direction on the primary endpoint but not meeting A, e.g. p ≥ 0.05, or it beats hybrid but not generic, or it only holds on the recognised subset."*
- *"**C (not supported):** zero or negative difference on the primary endpoint."*

**Approved operational reading (U10, rule C, U11).**
- **A:**
  - the primary endpoint has p < 0.05;
  - its bootstrap CI is positive (lower bound > 0);
  - secondary test 4 ("R@10 vs generic") has diff > 0 **and** `p_holm` < 0.05;
  - a CI is not required for test 4.
- **C:** the primary point-estimate difference (`diff_R@10`) is ≤ 0.
- **B:** `diff_R@10` > 0 and not A.
- **Recognised-subset example in B (U11):**
  - the A/B/C criteria are not changed whether or not the probe runs;
  - if the probe was not executed, the report states: *"Probe not executed; the 'only holds on the recognised subset' example in rule B could not be evaluated"*, and if the outcome is A, also that the recognised-subset check could not be performed;
  - if the probe was executed, the recognised and not-recognised subset results are reported next to the decision, as in the original study.

**Mechanism.**
- A wrapper (`family_R_replication.py`) reassigns module-level path constants only:
  - `validation_heldout.HO`, `HO_SAMPLE`, `PRED_RAW`, `PROBE_RAW`, `KS_DIR`;
  - `common.KS_DIR`;
  - `wikidata_authority.CACHE`.
- It then calls the frozen function bodies `cmd_extract`, `cmd_rank`, `cmd_wikidata`, `cmd_predict` and `cmd_probe`.
- Before scoring, `HO_SAMPLE` points to the inputs-only file; the frozen pre-scoring commands read only input fields.
- At scoring, after freeze 3 and a recorded approval, the inputs and sealed gold are merged in memory and passed to `analyse(sample, True, load_preds(PRED_RAW), probe=…)`, followed by the frozen `_write` into the redirected `HO`.
- **R-D10 (approved):** the wrapper calls `analyse()` directly instead of `cmd_evaluate`.
  - If the probe has run, it passes the probe dict built exactly as `cmd_evaluate` builds it.
  - If the probe has not run, it passes `probe=None`, the function's declared default. This avoids the frozen `cmd_evaluate` behaviour of reporting every claim as "not recognised".
  - The probe status is written to a separate `probe_status.json`.
  - The frozen script is not modified.
- **Path redirection is the only other intervention.** Any further required change is a blocker, not a substitution.
- The frozen generic-prior defects are retained and documented: `*.go.com` is scored as government, and bare government-suffix hosts are scored as unknown.

**Deviations.**

| # | Deviation | Effect |
|---|---|---|
| R-D1 | The population is the 180 remaining dev claims, unstratified, instead of a seed-2027 stratified sample of 200 | The label mix differs |
| R-D2 | Expected eligible n is about 150, against about 160 planned | Lower power |
| R-D3 | Wikidata uses the copied cache plus new lookups in 2026-10/11 | Drift for new mentions |
| R-D4 | Same model ID; the backing model may differ. `modelUsage`, CLI version and dates are recorded | Exact model behaviour not reproducible |
| R-D5 | The KS is extracted later; the remote ETag/size is recorded (U7) | Possible change in the remote file |
| R-D6 | Library and model versions may differ and are recorded: MiniLM, `sentence-transformers`, `bm25s`, `tldextract` with its bundled suffix list, spaCy and `en_core_web_sm` | Small ranking or mention drift |
| R-D7 | The development re-analysis inside `cmd_evaluate` is not repeated | None for this test |
| R-D8 | If the probe is not executed, its items are reported "not executed" | A descriptive item is missing; see U11 |
| R-D9 | Systems E–G are excluded | Outside the reservation |
| R-D10 | `analyse()` is called directly with `probe=None` when no probe was run, and with `cmd_evaluate`'s dict construction when it was | Avoids a false "all not recognised" section |

**Blockers.** If any of these occurs, Family R is reported as **not executable** and nothing is substituted:
- a frozen hash-gate failure;
- `claude-opus-5-5` is unavailable;
- the dev KS file is unavailable;
- the frozen code cannot run unmodified under redirected paths.

### 4.2 Family N

**Eligible set.** Exactly Family R's `gold_c`. Scoring halts if they differ. D failures are excluded and counted, T failures are kept, and gold outside the top-100 is kept as a miss.

**Per-claim hits.** hᵐₖ(c) = 1 if R(c) has a document in condition m's top-k.

**Primary test: T vs D at k = 10.**
- Exact two-sided McNemar (frozen `mcnemar`).
- Δ = mean of (h_T − h_D).
- 95% percentile CI from frozen `boot_ci`: 10,000 resamples, `random.Random(2026)`.

**Secondary tests, Holm over exactly these four (frozen `holm`):**
1. T vs X at R@10.
2. T vs A at R@10.
3. T vs D at R@5.
4. T vs D at R@20.

Each reports the McNemar p, Holm-adjusted p, Δ and CI.

**Decision rule.** "Significant positive" means p < 0.05 and Δ > 0 and a CI lower bound > 0.

| Outcome | Condition |
|---|---|
| **N-Supported** | The primary is significant positive **and** T vs X has Holm-adjusted p < 0.05 with Δ_TX > 0 |
| **N-Partial** | The primary is significant positive, but T vs X is not. *T improves on D, but attribution to claim-specific selection over generic boosting is not established* |
| **N-Inconclusive** | Primary p ≥ 0.05, or the p-value and CI disagree. **Not evidence of no benefit** |
| **N-Harm** | Primary p < 0.05, Δ < 0 and CI upper bound < 0 |

The other three secondary tests are reported but do not change the classification.

**Interpreting T vs X.**
- **What it shows:** X boosts the same number of pool-visible publishers, matched on coarse type and count, without choosing them for the claim. T > X therefore indicates that the choice of publisher matters.
- **What it cannot separate:** authority from topical relevance.
- **Why it may be weaker than it looks:** coarse matching; X may pick a real authority by chance; fallbacks and budget imbalance; limited power.
- **A significant T > D alone does not show that authority selection beats generic boosting.**

**Consistency gate.** Family N's recomputed A and D rankings must equal Family R's, or scoring halts.

**Descriptive metrics.**
- R@1/@3 and MRR@100 use the frozen `source_targeted_eval.score` definitions, applied to the `gold_c` set (not to `score()`'s own reachable-only set).
- **U6:** T's authority accuracy vs all human-gold publishers, using `evald`'s definition.
- **U8:** T vs X restricted to claims whose X slots are all `same_type`.

---

## 5. Memorisation probe (distinct step with its own logged approval entry)

- **Purpose:** the Family R descriptive subset analysis, and a Family N check on whether T favours familiar fact-checking or secondary outlets.
- **Inputs:** claim, speaker and date.
- **Procedure:**
  - frozen `PROBE_SYSTEM`/`PROBE_USER` and `_probe_call` via the frozen `cmd_probe` (path-redirected);
  - one call per reserved claim;
  - 3 passes.
- **Outputs:** model self-reports. **These are model outputs used as stratifiers, not annotations or ground truth.**

**Metrics needing no probe calls** (Family N, descriptive):
- **(b)** the share of eligible claims where T, or D, selects the registered domain of `fact_checking_article`. Gold metadata, read at scoring only;
- **(c)** the share of T's selections that are self-declared `news`, or that fall in the frozen `MAJOR_NEWS`, `REFERENCE` or `PLATFORMS` lists or match `NEWS_FC_HINT`.

**Metrics needing probe calls:**
- the Family R subsets;
- **(a)** T's or D's selection equals the probe-named fact-checker domain;
- **(d)** T vs D at R@10 in the recognised and not-recognised subsets (exploratory).

**Limitations:** not being recognised does not prove the claim was not memorised; the probe and the resolvers share a model family; (b) and (c) are heuristics.

---

## 6. Metrics, ceilings, power and stop conditions

**Per condition (Family N):**
- GoldR@1, @3, @5, @10, @20 and MRR@100;
- hit@10 with a Wilson 95% CI;
- pool coverage, which is identical across conditions by design.

**Pairwise:** wins / losses / ties for T–D, T–X, T–A and D–A, at hit@10 and at best gold rank (absent = 101).

**Mechanism checks:**
- boosted documents per claim;
- T abstentions, parse failures, invalid, duplicate and truncated keys, `abstain_conflict`, `empty_selection`, and overlap with D;
- X flags and budget imbalance;
- displacement relative to A.

**Breakdowns** (descriptive): gold verdict, D's `claim_kind`, the number of reachable gold publishers, and the probe subsets.

**Oracle ceilings** (diagnostic only, never presented as performance): the URL oracle within the pool, which equals pool coverage, and the publisher oracle within the pool.

**Power** (approximation, unverified): with n ≈ 150 and 12–20% discordant claims, the minimal detectable R@10 difference is about 0.08–0.10. **A non-significant result does not show no benefit.**

**Stop conditions:**
- no interim analyses, added claims or re-runs after scoring;
- **halt before scoring** if any hash gate fails, the reserved count is not 180, T differs from freeze 2, freeze 3 is incomplete, or the A/D consistency gate fails;
- one scoring pass per family;
- a post-scoring fix is allowed only where code deviates from this text; both outputs are then reported, and the preregistered output stays primary.

---

## 7. Development selection rule

**Versions.**
- At most 3. V1 is written before any development call; V2 may follow only a completed V1, and V3 only a completed V2.
- **Whether V2 or V3 are written at all is not prespecified.** No review gave a recommendation. The project owner decides after V1's development scoring, and the decision is logged before any V2 call.
- **U3 (approved):** between versions only instruction wording may change, plus worked examples. Examples use invented names and `.example` domains and never name a development-gold publisher.
- Inputs, format, output schema, post-processing, model and isolation are fixed.

**Freezing each version.**
- Before its first call, version k's prompts, config and resolver are hashed into `MANIFEST_dev_v{k}.json`. The resolver refuses to run without a matching manifest.
- Each version runs once over all 320 claims within the 3-pass procedure. Resumption is only for completing transient failures. A started version cannot be abandoned or re-run.

**Development D.** Frozen predictions. Gate: D re-ranked from the frozen hybrid top-100 must equal the stored `hybrid+llm_authority` ranking in `results/source_targeted/rankings_{dev,heldout}.jsonl.gz` for all 320 claims (same URL order).

**Rule.**
- **Denominator:** E, N ≈ 266. Gold outside the pool remains in E.
- **Parse-failure rate:** f(v) = (claims of the 320 unparsed after 3 passes) / 320.
- **Admissible (U4):** f(v) ≤ 0.05.
- **Score:** W(v) = Σ_{c∈E} [h₁₀^{T(v)}(c) − h₁₀^{D}(c)], reported as S(v) = W(v)/N.
- **Selection among admissible versions,** lexicographic:
  1. max W(v);
  2. max Σ_E [h₁₀^{T(v)} − h₁₀^{X(v)}];
  3. max Σ_E [h₂₀^{T(v)} − h₂₀^{D}];
  4. min f(v);
  5. the earliest version.

**Exceptions.**
- **U1a (approved):** if no version is admissible, Family N is **not run** on the reserved set and is recorded as "not executed: admissibility failed". Family R proceeds.
- **U1b (approved):** if the selected version has W ≤ 0, **proceed**, and report the development result alongside.

**Freeze 2.** The selected prompts and config, all scripts and `selection.json` are hashed into `MANIFEST_freeze2.json` before `dev.json` is downloaded. All development outputs are kept and reported as exploratory.

---

## 8. Hashing, freezes and gates

1. **New text artifacts** are written with LF line endings and verified by raw-byte SHA-256. `core.autocrlf=true` is set in this clone, so new files are never committed or checked out between freezes.
2. **Frozen files** are verified against their originally recorded hashes in the recorded convention (`experiments/authority_v2/hash_gate.py`). Prefix…suffix records count as partially verified. **No existing artifact is rewritten or re-hashed to bless a change.**
3. **Manifests** are written once and never edited.
   - `MANIFEST_freeze1.json`: this preregistration, the config, the decision log at freeze time, and the raw hashes of these files, which have no recorded freeze hash:
     - the development inputs: `results/wikidata_resolution.json`, `results/wikidata_claim_authorities.json`, `results/heldout/wikidata_claim_mentions.json`, `results/source_targeted/rankings_dev.jsonl.gz`, `results/source_targeted/per_claim_dev.csv`, `results/authority_resolution_raw.jsonl`, `results/heldout/authority_raw.jsonl`, `results/heldout/rankings_{bm25,dense,hybrid}.jsonl.gz`, `data/processed/averitec_sample.jsonl`, `data/processed/averitec_heldout.jsonl`;
     - the wrapped frozen modules without a recorded hash: `common.py`, `wikidata_authority.py`, `build_sample.py`, `extract_knowledge_store.py`.
   - `MANIFEST_dev_v{k}.json`, `MANIFEST_freeze2.json` and `MANIFEST_freeze3.json` are as described in §7 and below.
   - `MANIFEST_freeze3.json`: the reserved inputs, KS extracts, rankings, Wikidata cache and diff, D/T/X outputs, probe outputs (if any), and the raw hash of the sealed gold file.
4. **Reserved-gold gate.** Scoring opens the gold file only if freezes 1–3 and the frozen-file table all verify, **and** an explicit approval entry is present in `results/authority_v2/logs/execution_log.jsonl`.
5. **Probe gate.** The probe command requires its own approval entry in the execution log.
6. **No overwriting.** Scripts refuse to overwrite outputs; logs are append-only and timestamped.

---

## 9. Paths, sequence and calls

**Paths:**
- **Documents:** `docs/authority_v2_preregistration.md`, `docs/authority_v2_decision_log.md`, and `docs/authority_v2_results.md` after execution.
- **Code and config:** `experiments/authority_v2/`.
- **Data:** `data/raw/averitec/dev.json` and `data/raw/averitec/ks_reserved180/` (git-ignored); `data/processed/averitec_reserved180_{inputs,gold}.jsonl`.
- **Results:** `results/authority_v2/`.

**Sequence:**

| # | Step | Type |
|---|---|---|
| 1 | Preregistration, config, decision log; freeze 1 | Offline |
| 2 | Implement; the D-recompute gate; dry runs of X and the development scorer | Offline |
| 3 | For each version k: `MANIFEST_dev_v{k}`, then T over 320 development claims | LLM |
| 4 | X build, development scoring, selection | Offline |
| 5 | Freeze 2 | Offline |
| 6 | Download `dev.json` | Network |
| 7 | Build the reserved sample | Offline |
| 8 | KS extraction | Network |
| 9 | Wikidata (missing mentions) | Network |
| 10 | Ranking | Offline (MiniLM is cached locally) |
| 11 | Reserved D | LLM |
| 12 | Probe, with its own log entry | LLM |
| 13 | Reserved T | LLM |
| 14 | X; freeze 3 | Offline |
| 15 | Hash gate; Family R scoring; Family N scoring, once | Offline |

**Call bounds:**
- development: 320 calls per version (≤ 960 with retries);
- reserved D: 180 (≤ 540);
- reserved T: 180 (≤ 540);
- probe: 180 (≤ 540).

Costs and runtimes are unverified estimates; actuals are taken from the logs and reported.

---

## 10. Resolved decisions

| ID | Decision (approved 2026-10-28) | Rationale |
|---|---|---|
| U1a | No admissible version: Family N not run; Family R proceeds | A treatment undefined for > 5% of claims would not be a meaningful test |
| U1b | Selected W ≤ 0: proceed and report the development result | Avoids using the reserved set conditionally on outcomes |
| U2 | T's publisher list in ascending code-point order | Removes order effects tied to retrieval rank or counts |
| U3 | V2/V3 may add worked examples with invented `.example` names | Flexibility, while limiting overfitting to development |
| U4 | Admissibility threshold f ≤ 5% | Conventional, and not so strict that U1a is likely |
| U5 | T's `confidence` is descriptive only | Using it would add an untuned parameter |
| U6 | T authority accuracy vs human-gold publishers, descriptive, Family N | Comparability with D |
| U7 | Remote KS ETag/size changed: proceed and record (R-D5); stop only if a member is missing | Corpus drift becomes a declared deviation |
| U8 | T vs X on fully same-type-matched claims, descriptive | Sensitivity analysis of X matching |
| U9 | Contradiction between the stored dev count and the top-100: halt development scoring | Protects the selection denominator |
| U10 | Rule A needs test 4 with diff > 0 **and** `p_holm` < 0.05 | Most faithful reading of "after Holm correction" |
| C-rule | C = primary point-estimate diff ≤ 0 | Literal reading |
| U11 | A/B/C unchanged; an unevaluable recognised-subset example is reported | No silent change of criteria |
| R-D10 | `analyse()` called directly; `probe=None` if the probe was not run; separate status file | The frozen script is untouched; no false subset |
| U12 | T output rules in §2.2 | Deterministic and logged |
| N-denominator | Family N uses `gold_c` | Same claims for both families |
| Open | Number of development versions beyond V1 | No recommendation exists; decided by the owner after V1 |
