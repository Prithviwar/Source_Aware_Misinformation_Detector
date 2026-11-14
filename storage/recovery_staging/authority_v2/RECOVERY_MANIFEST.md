# Authority-v2 recovery manifest (staging only)

Created 2026-11-06 in recovery Step 2. **Nothing here has been copied into the project repository.**

- **Source:** `storage\backups\claude_session_backup_2026-11-06.zip`, SHA-256 `074d9433dfba8eca9badc84c11d954f2ce8c8f55cc8236e802cfe188c730acb7`. It was read in place, never extracted, and left unchanged.
- **Machine-readable detail:** `recovery_manifest.json`. For every file it lists the hash, the full edit chronology with the hash after each step, the recorded historical hashes, and notes.
- **Tools used:** `recovery_tools\`. These scripts read the ZIP, replay the edits into a scratch folder, and stage the results. They print metadata only.

## How the files were rebuilt

1. **Real tool calls only.** Only `assistant` tool calls whose results were successful were used. Copies of earlier messages bundled into later API requests (`api-request-blob` records) were ignored.
2. **Replayed in timestamp order** across sessions 390fe08e, 95646328, f4f193f3 and 20816471.
3. **Every kind of change was replayed:**
   - `Write` and `Edit` tool calls;
   - 6 `sed -i` commands, re-run with the identical expression in Git Bash `sed`;
   - 3 `cat >>` heredoc appends to the decision log;
   - one Python `str.replace` patch to `fixture_test.py`;
   - the `cp` swap of `t_resolver.py` during the T_v1 resume, whose net effect is no change.
4. **Checked against historical hashes.** Each result was compared with every historical SHA-256 printed in the transcripts (Freeze 1, the dev manifest, Freeze 2 and the log events). **No file was altered to make a hash match.**

## Status labels

| Label | Meaning |
|---|---|
| EXACT ORIGINAL BYTES | An original copy of the file survived. The transcript replay is byte-identical to it. |
| TRANSCRIPT-RECONSTRUCTED, HASH-VERIFIED EXACT | Rebuilt from the transcripts. Its SHA-256 equals a hash recorded from the real file at the time, so its bytes are exactly the original's at that point. |
| PARTIALLY VERIFIED | Bytes are verified at an earlier state only. The final state was checked against transcript reads, not a hash. |
| TRANSCRIPT-RECONSTRUCTED, UNVERIFIED | Rebuilt from the transcripts, with nothing independent to check it against. |

## Staged files (27)

| File | Status | SHA-256 (prefix) | Hash first recorded |
|---|---|---|---|
| experiments/authority_v2/t_resolver.py | EXACT ORIGINAL BYTES | fd6c12ea5f19 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/v2common.py | HASH-VERIFIED EXACT | 59f62129fd1b | 2026-10-28 Freeze 1 |
| experiments/authority_v2/hash_gate.py | HASH-VERIFIED EXACT | 159e72dbd043 | 2026-10-28 Freeze 1 |
| experiments/authority_v2/freeze1.py | HASH-VERIFIED EXACT | c7266d9c0574 | 2026-10-28 Freeze 1 |
| experiments/authority_v2/config.json | HASH-VERIFIED EXACT | 43abb31c4751 | 2026-10-28 Freeze 1 |
| experiments/authority_v2/prompts/T_system_v1.md | HASH-VERIFIED EXACT | a47af8792975 | 2026-10-28 dev manifest |
| experiments/authority_v2/prompts/T_user_v1.md | HASH-VERIFIED EXACT | d305d40e76b1 | 2026-10-28 dev manifest |
| experiments/authority_v2/dev_data.py | HASH-VERIFIED EXACT | 08552502797a | 2026-10-28 dev manifest |
| experiments/authority_v2/dev_score.py | HASH-VERIFIED EXACT | 94226e01068c | 2026-10-28 dev manifest |
| experiments/authority_v2/x_control.py | HASH-VERIFIED EXACT | 7983a1d184ec | 2026-10-28 dev manifest |
| experiments/authority_v2/build_reserved_sample.py | HASH-VERIFIED EXACT | 134cc3f6394c | 2026-10-29 Freeze 2 |
| experiments/authority_v2/family_N_score.py | HASH-VERIFIED EXACT | 3517a72ee570 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/family_R_replication.py | HASH-VERIFIED EXACT | 0ce434b90223 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/fixture_test.py | HASH-VERIFIED EXACT | 0b6a27814105 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/freeze2.py | HASH-VERIFIED EXACT | b6da79181e81 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/freeze3.py | HASH-VERIFIED EXACT | bfa7ba51de72 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/leak_check.py | HASH-VERIFIED EXACT | 0f2db38c9b6b | 2026-10-29 Freeze 2 |
| experiments/authority_v2/make_manifest_dev.py | HASH-VERIFIED EXACT | 5c2b80783232 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/offline_checks.py | HASH-VERIFIED EXACT | b048d887bf83 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/paths_reserved.py | HASH-VERIFIED EXACT | 4cb6df357165 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/reserved_inputs.py | HASH-VERIFIED EXACT | 34f33ff62e51 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/reserved_x.py | HASH-VERIFIED EXACT | b262348ae256 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/select_version.py | HASH-VERIFIED EXACT | 8412285ccef1 | 2026-10-29 Freeze 2 |
| experiments/authority_v2/verify_manifests.py | HASH-VERIFIED EXACT | 07803277d00f | 2026-10-29 Freeze 2 |
| docs/authority_v2_preregistration.md | HASH-VERIFIED EXACT | 0c28aed80017 | 2026-10-28 Freeze 1 |
| docs/authority_v2_decision_log.md | PARTIALLY VERIFIED | 124acba72192 | none for the final version |
| docs/authority_v2_progress_report_steps1-9.md | UNVERIFIED | 04b902030146 | none |

Notes:

- **`t_resolver.py`.** The replay also reproduces the dev-manifest hash `9f98938e…`, which is the version used for the T_v1 dev run, before the additive `run_reserved()` edits.
- **Decision log.** Its bytes match `581ecc44…` at the Freeze-1 state (after DL-013). DL-014 and DL-015 were then appended through recorded heredocs. The final text is identical line by line (105 of 105 lines) to full transcript reads on 1, 2 and 3 November. Any manual edit made after 3 Nov 04:53 outside a Claude session would not be visible.
- **Progress report.** It was written once (1 Nov 05:10), and no later edit was seen. It has no hash and no later read to check it against.
- **Completeness.** `freeze2.py` hashes `*.py`, `prompts/*.md`, `config.json` and `selection.json`. Freeze 2 reported 25 files, which equals 21 staged `.py` files + 2 prompts + `config.json` + `selection.json`. So no v2 code file is missing. The other names that appear in the transcripts (`T_system.md`, `evaluate.py`, `predict_frozen_D.py`, `prepare_test.py`, `resolve_pool_authority.py`, `build_untouched_sample.py`, `docs/authority_v2_results.md`) were never created. They were planned names or text inside the docs.
- **Contents scan.** No staged file contains real evidence URLs or claim–label rows. The few URLs in `fixture_test.py` and `offline_checks.py` are synthetic test fixtures.

## Frozen repository dependencies (read-only check of the fresh GitHub clone)

All 17 git-tracked files whose hashes Freeze 1 recorded match the clone byte for byte: `experiments/common.py`, `wikidata_authority.py`, `extract_knowledge_store.py`, `build_sample.py`, the dev and held-out samples, the held-out rankings and predictions, the Wikidata caches and the source-targeted rankings.

## NOT staged: missing historical outputs (lost; must not be recreated as originals)

| Item | Recorded identity | Status |
|---|---|---|
| `results/authority_v2/reserved/authority_raw.jsonl` (Step 11, 180 predictions) | sha `86b2840c…c7c628299` | **MISSING.** Lost; a re-run would be a new run, not a recovery. |
| `results/authority_v2/logs/execution_log.jsonl` (43 entries) | not recorded | **MISSING.** Transcripts show its contents in parts; not to be rebuilt as an original. |
| `results/authority_v2/manifests/MANIFEST_freeze1.json`, `MANIFEST_freeze2.json`, `MANIFEST_dev_v1.json` | freeze1 `e1f5bc53…`, freeze2 `d94ca489…` | **MISSING.** Could be regenerated by the freeze scripts from verified inputs, but that would be a new file. |
| `results/authority_v2/selection.json`, `dev/T_v1/*` (320-claim dev LLM run) | hashes in transcripts | **MISSING** (LLM output) |
| `results/authority_v2/dev/T_v1_t_resolver_as_run.py.txt` | `9f98938e…` | **Derivable exactly** (the replay reproduces this state); not staged, because it is a results artefact. |
| `results/authority_v2/wikidata/*`, `reserved/wikidata_claim_mentions.json` | hashes in log | **MISSING.** Live Wikidata API; not reproducible byte for byte. |
| `results/authority_v2/reserved/rankings_{bm25,dense,hybrid}.jsonl.gz` | Step 10 hashes | **MISSING.** Recomputable later, then checked against the hashes. |
| `data/raw/averitec/ks_reserved180/` (180 files, 139,397 docs) | inventory `4d11f509…` | **MISSING.** Re-extractable later (download). |
| `data/processed/averitec_reserved180_inputs.jsonl` | `1e76ea9d…` | **MISSING.** Re-derivable from the verified `dev.json`. |
| `data/processed/averitec_reserved180_gold.jsonl` (SEALED) | `5806638d…` | **MISSING and PROTECTED.** Re-derive only with explicit owner approval, checked by hash only. |
| `results/authority_v2/logs/*_stdout.txt`, `ks_inventory_step8.json`, dry-run outputs | partly in log | **MISSING** |

## Related files outside the approved Step-2 scope (recoverable, not extracted)

- `experiments/authority_bottleneck_diagnostics.py`, `experiments/authority_diagnostic_audit.py` and their docs `docs/authority_resolution_bottleneck_analysis.md`, `docs/authority_resolution_diagnostic_audit.md` (28 Oct, pre-v2 analysis).
- `RESEARCH_ROADMAP_2026-11-02.md` and `docs/proposals/verdict_classifier_training_proposal_DRAFT.md`.
- The `first_hand_authority_model` project (separate; must not be merged).
