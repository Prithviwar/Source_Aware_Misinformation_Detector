# Authority v2: progress report, Steps 1–9

*Written 2026-11-01. Status report only: no experiment was run, no file was changed, and no reserved gold, probe or scoring material was opened to produce it.*

**Sources.** `docs/authority_v2_preregistration.md` (the preregistration), `docs/authority_v2_decision_log.md` (DL-001 to DL-015), `results/authority_v2/logs/execution_log.jsonl`, the manifests in `results/authority_v2/manifests/`, `results/authority_v2/selection.json`, and the development outputs in `results/authority_v2/dev/T_v1/`. Reserved-set figures are counts already recorded in the execution log; none was re-derived from reserved files.

**Status in one line.** Steps 1–9 of the 15-step sequence (preregistration §9) are complete and verified. Step 10 (offline ranking) **has not been run and is not approved**. No reserved gold has been read, and no reserved-set model call has been made.

---

## 1. Study recap

- **Question:** within a fixed hybrid top-100 pool, does better claim-specific authority resolution improve AVeriTeC gold-evidence retrieval?
- **Conditions** (only the boosted publisher set K_c differs):
  - **A:** no authority boost (the frozen hybrid order);
  - **D:** the frozen LLM authority predictor;
  - **T:** a new pool-grounded resolver that picks ≤ 3 publishers from the claim's pool, or abstains;
  - **X:** a gold-blind control matched to T on publisher type and pool count.
- **Family R:** reserved-set replication of D vs A (H_R1), reported first.
- **Family N:** T vs D (primary, H_N1), plus T vs X, T vs A, and @5/@20 secondaries.
- **Reserved set:** the 180 AVeriTeC dev claims not used in the earlier 120-claim and 200-claim sets.

---

## 2. Step-by-step record

| # | Step | Completed | Outcome |
|---|---|---|---|
| 1 | Preregistration, config, decision log; freeze 1 | 2026-10-28 22:25 | Frozen-file hash gate passed (17 files: 14 fully, 3 partially verified; no tracked git changes). `MANIFEST_freeze1.json` written |
| 2 | Implementation; D-recompute gate; dry runs | 2026-10-28 22:30 | D-recompute gate passed on all 320 claims; offline checks 24/24; synthetic dry run of X and the scorer (N = 266) |
| 3 | `MANIFEST_dev_v1`; T V1 over 320 development claims | 2026-10-29 08:19 | 257 selected, 63 abstain, 0 parse failures (f = 0.000); 324 calls; USD 7.85 |
| 4 | X build, development scoring, selection | 2026-10-29 08:25 | W = −3 (S = −0.0113); V1 selected; development stopped at V1 (DL-015) |
| 5 | Freeze 2 | 2026-10-29 08:26 | Offline checks 24/24; reserved-pipeline fixture test 22/22; leak string check passed; 25 files hashed |
| 6 | Download `dev.json` | 2026-10-29 08:29 | Pre-Step-6 gate passed; HTTP 200, 1,785,475 bytes, sha `49979372…` |
| 7 | Build reserved sample | 2026-10-29 08:29 | 500 dev records − 320 used = 180 reserved (ids 0–497); inputs file written; gold file sealed |
| 8 | Knowledge-store extraction | 2026-10-29 09:17 | 180/180 extract files; verification passed |
| 9 | Wikidata (missing mentions only) | 2026-10-29 09:41 | 200 new mentions looked up in a copy of the cache; frozen cache unchanged; verification passed |

### Step 1: preregistration and freeze 1
- Freeze 1 hashed three things: the preregistration, `config.json` and the decision log; the raw hashes of 12 development inputs and 4 wrapped frozen modules; and library versions (Python 3.13.2, spaCy 3.8.14, sentence-transformers 5.4.0, Claude CLI 2.1.312, among others).
- The frozen-file gate checks the original scripts, rankings, predictions, the canonical annotation sheet and the Phase-2 X1 assignment against their originally recorded hashes. All passed.

### Step 2: implementation and offline gates
- **D-recompute gate:** passed for all 320 claims. Specifically:
  - re-ranking the frozen hybrid top-100 with D's keys reproduces the stored `hybrid+llm_authority` ranking;
  - A equals the hybrid order;
  - the dev200 pools equal the frozen top-100;
  - the Wikidata blocks reconstruct D's stored prompts.
- **Dry run:** a synthetic T built from D's keys produced population N = 266 (99 of dev120 plus 167 of dev200).

### Step 3: T V1 development run
- The prompts (`T_system_v1.md`, `T_user_v1.md`) were written and hashed before any development call. They contain no worked examples.
- **Interruption:** the run stopped at 264/320 when the session ended. Four claims had empty CLI output (330, 333, 334, 337) and 56 had never been called. It was completed with the frozen `_run_calls` resume, which keeps the 260 parsed records unchanged. Each interrupted claim parsed on its second attempt; no claim needed more than 3.
- **Output flags:** invalid, duplicate and truncated keys, `abstain_conflict` and `empty_selection` were all 0.

### Step 4: development scoring and selection (exploratory)

Recall on the eligible development set (N = 266):

| Condition | R@1 | R@3 | R@5 | R@10 | R@20 |
|---|---|---|---|---|---|
| A | 0.053 | 0.109 | 0.150 | 0.248 | 0.376 |
| D | 0.083 | 0.154 | 0.214 | **0.312** | 0.440 |
| T (V1) | 0.094 | 0.139 | 0.196 | **0.301** | 0.440 |
| X | 0.026 | 0.053 | 0.098 | 0.188 | 0.368 |

Pairwise hit@10 (wins / losses / ties):

| Pair | Wins | Losses | Ties |
|---|---|---|---|
| T–D | 7 | 10 | 249 |
| T–X | 40 | 10 | 216 |
| T–A | 33 | 19 | 214 |
| D–A | 28 | 11 | 227 |

Other development results:
- **Selection:** V1 was admissible (f = 0 ≤ 0.05). W = −3, so rule U1b applies: proceed, and report the development result alongside.
- **Tie-break sums:** T−X at @10 = +30; T−D at @20 = 0.
- **T behaviour:**
  - on E: 217 selected, 49 abstain;
  - mean boosted documents per claim: 6.87;
  - 212 claims overlap with D's keys.
- **X:** 599 `same_type` slots and 22 `type_relaxed`. B_X ≠ B_T on 162 claims; mean B_X − B_T = −3.63 and median = −1, so X boosts slightly smaller publishers on average.

### Step 5: freeze 2
- The selected prompts, config, 25 scripts and `selection.json` were hashed into `MANIFEST_freeze2.json`.
- The leak string check confirmed that no gold-informed list (for example `DOMAIN_OVERRIDES`) is referenced by the T, X or wrapper code.
- The fixture test ran on synthetic data in a temporary directory, with no reserved data, network or LLM.

### Step 6: `dev.json`
- **Pre-Step-6 gate:** freezes 1 and 2 verified, the frozen-file gate passed, and every reserved output path was confirmed absent.
- **Download:** from the same Hugging Face repository as the frozen KS URL. ETag, size and SHA-256 are logged.

### Step 7: reserved sample
- 320 development records were reproduced from `dev.json`, and the 180 reserved claims were identified deterministically. There was no sampling.
- **Inputs file:** `data/processed/averitec_reserved180_inputs.jsonl` (sha `1e76ea9d…`), with claim, speaker, date and ISO code only.
- **Sealed gold file:** `data/processed/averitec_reserved180_gold.jsonl`, with raw sha `5806638d…` recorded at write time.

### Step 8: knowledge-store extraction
- Extraction was path-redirected to `data/raw/averitec/ks_reserved180/` (the remote archive is 11.5 GB).
- **Verification:** 180 files for 180 unique input ids; nothing missing, extra, unreadable or temporary; every claim has non-empty text.
- **Documents per claim:** 575–2,172 (median 953); 178,511 in total, 139,617 with non-empty text.
- The sealed-gold hash was unchanged.

### Step 9: Wikidata (missing mentions)
- The frozen `results/wikidata_resolution.json` (436 entries, sha `90dfd52b…`) was copied to `results/authority_v2/wikidata/wikidata_resolution.json`. Only mentions absent from the frozen cache were looked up, with the cache path redirected to the copy.
- **Outcomes:**
  - 261 distinct mentions across the reserved claims: 61 reused from the frozen cache, 200 new;
  - of the 200 new, 113 matched a Wikidata entry by label or alias, and 87 had no match (a successful request with no hit, not a failure);
  - 49 of the new entries have an official website (P856), and 45 have social handles;
  - 4 claims have no mentions at all.
- **Requests:** 200 searches and 3 presence batches all succeeded. There were 19 HTTP 429 rate-limit retries, all recovered, and no unrecovered failures.
- **Verification passed:**
  - the frozen cache is byte-identical to freeze 1;
  - the original 436 entries are unchanged;
  - the copy holds exactly 436 + 200 entries, with nothing changed or removed;
  - every mention is present in the cache.
- **Copy, diff and mentions files:** `495f6461…`, `6e2b7947…` and `ba9f7af9…`.
- **Later count clarification:** the owner queried the resolved count, and a recount from the saved artifacts confirmed resolved = 113 and unmatched = 87. An earlier chat figure of 23 rate-limit retries double-counted lines; the log shows 19. No logged values changed.

---

## 3. Key decisions (decision log and execution log)

| Ref | Decision |
|---|---|
| DL-001 | Option 1: the reserved 180 serve Family R (reported first) and Family N |
| DL-002 | Defaults 1–6: Wikidata cache copy with missing-only lookups; T failures become abstentions; the probe is a distinct step; development selection on 120 + 200 claims; T gets publisher keys and counts only; X design |
| DL-003 / DL-004 | Family R outcome A requires primary p < 0.05, a positive CI, and the Holm-adjusted R@10-vs-generic test; a point estimate ≤ 0 is outcome C |
| DL-005 / DL-006 | If the probe is not run, the A/B/C criteria are unchanged and its status is recorded separately |
| DL-007 | T output-handling rules (U12) |
| DL-008 | Family N denominator = Family R's `gold_c` |
| DL-009 / DL-010 | U1a, U1b, U2–U9 and corrections C1–C11 adopted |
| DL-012 / DL-013 | Execution authorised subject to the §8 gate order. The probe and reserved-gold gates each need their own log entry |
| DL-014 | V1 completed after a logged resume; scored f = 0, W = −3 |
| DL-015 | Development stops at V1; no V2/V3. Decided after V1's scores, which is disclosed. Thresholds unchanged |
| Execution log, `deviation_note` | `t_resolver.py` received an additive edit (`run_reserved`) during the V1 run. The as-run bytes reproduce the manifest hash (`9f98938e…`) and are saved; the development code path is byte-identical |
| Execution log, `selection` | V1 selected; `family_N_executed: true`; U1b applies |

Per-step approvals for Steps 6–9 were given in owner messages. The decision log records the blanket authorisation (DL-012), and the execution log records a gate check or verification at each step.

---

## 4. Frozen artifacts and preservation status (checked 2026-11-01)

| Artifact | Status |
|---|---|
| Original frozen files (17 in the frozen-file gate: scripts, rankings, `authority_raw.jsonl`, canonical annotation sheet, AI prompts, X1 assignment) | Git-tracked, with no tracked modifications at HEAD `9279eab`. The last full gate run passed at Step 8 |
| Frozen Wikidata cache `results/wikidata_resolution.json` | sha `90dfd52b…`, byte-identical to freeze 1 |
| Freeze 1: development inputs and wrapped modules (16 files) | All 16 hashes match `MANIFEST_freeze1.json` |
| Preregistration and `config.json` | Match freeze 1 (`0c28aed8…`, `43abb31c…`) |
| Decision log | Differs from its freeze-1 hash because DL-014 and DL-015 were appended, as the append-only design expects. Earlier entries were not edited |
| Freeze 2 (25 files) | All 25 hashes match `MANIFEST_freeze2.json` |
| Manifests and `selection.json` | Match the hashes in the execution log |
| Step 6–9 outputs (`dev.json`, inputs, KS inventory, Wikidata copy, diff, mentions) | All match the logged hashes |
| Sealed gold `averitec_reserved180_gold.jsonl` | Not opened or hashed in this session. Last recorded unchanged at Step 9 (2026-10-29 09:41) |
| Reserved outputs folder `results/authority_v2/reserved/` | Holds only `wikidata_claim_mentions.json`. No rankings, D, T, probe or X outputs; no freeze 3 |

Every gate flag is still `false`: probe approval, probe done, reserved-gold approval, both scoring passes, and freeze 3.

---

## 5. Limitations and caveats

**Development results**
1. **T did not beat D on development.** R@10 was 0.301 vs 0.312 (W = −3). The development figures are exploratory and come from one prompt version only. The reserved test of H_N1 therefore starts from a slightly negative development signal.
2. **Stopping at V1 was decided after seeing V1's scores** (DL-015). Because no further version was created, development results could not be improved by that choice. The decision is still outcome-informed and must be disclosed.
3. **The session that wrote T's prompt had seen development gold.** The preregistration permits this for development; the reserved set is unaffected.

**Execution irregularities** (both logged)
4. The V1 run was interrupted and resumed. Four claims received a second attempt that an uninterrupted run would not have needed.
5. `t_resolver.py` was edited mid-run. The edit was additive only, and byte-identity of the development path was verified.

**Gold exposure and leakage risks**
6. **`dev.json` contains gold for all 500 dev claims, including the reserved 180.** It sits git-ignored under `data/raw/averitec/`. Only `build_reserved_sample.py` read it, and that script prints counts only.
7. **The sealed gold file has no technical lock.** Both it and `dev.json` are protected by procedure only.
8. **The knowledge store was built partly from gold-derived queries** (a threat listed in the preregistration). Pool publishers and counts therefore correlate with gold for every condition.

**Wikidata**
9. **Two snapshots in one cache.** The 200 new entries were fetched from live Wikidata on 2026-10-29; the 436 frozen entries were fetched earlier.
10. **Unmatched and unverified mentions.**
    - 87 of the 200 new mentions (43.5%) found no match.
    - 4 reserved claims have no mentions at all.
    - Matching uses the top label or alias hit. Mis-resolution rates were not checked, and cannot be without inspecting reserved content.

**Statistics**
11. **Power is limited.** The approximate minimal detectable R@10 difference is 0.08–0.10 at n ≈ 150, so a non-significant reserved result would not show "no benefit".

**Bookkeeping**
12. **Nothing from authority v2 is committed.** None of the code, documents or results is in git. This is intentional (§8.1: no commits between freezes), but they currently exist only in this working tree.
13. **Encoding glitch in the log.** Two execution-log entries show `Â§` for `§`. The log is append-only, so it is left as is.

---

## 6. What remains in the preregistered protocol

| # | Step | Type | Gate / approval needed |
|---|---|---|---|
| **10** | **Ranking of the 180 reserved claims (frozen BM25, dense MiniLM, hybrid RRF; top-100 pools)** | Offline | **Explicit owner approval (not given)** |
| 11 | Reserved D: the frozen predictor, one run (180 calls, ≤ 540) | LLM | Owner approval |
| 12 | Memorisation probe (180 calls, ≤ 540) | LLM | Its own approval entry in the execution log (§8.5). If not run, the B-subset statement applies (DL-005) |
| 13 | Reserved T: the selected V1 (180 calls, ≤ 540) | LLM | Owner approval; T must match freeze 2 |
| 14 | X build; freeze 3 (reserved inputs, KS, rankings, Wikidata cache and diff, D/T/X and probe outputs, raw hash of the sealed gold) | Offline | Owner approval |
| 15 | Hash gate, then one scoring pass each for Family R and Family N | Offline | Freezes 1–3 and the frozen-file table verified, **and** a reserved-gold approval entry in the log (§8.4). Halt on any gate failure |
| — | `docs/authority_v2_results.md` (Family R reported first; development results alongside under U1b) | Docs | After Step 15 |

**Fixed stop conditions:** no interim analyses, no added claims, no re-runs after scoring, and one scoring pass per family.
