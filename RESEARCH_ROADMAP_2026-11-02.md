# Capstone research roadmap (as of 2026-11-02)

Two **separate** projects. They share no code, data or methodology. One optional future link is shown in §5.

| Project | Directory | Question |
|---|---|---|
| **P1** Source-aware misinformation detector (authority v2) | `Source_Aware_Misinformation_Detector/` | Does claim-specific authority resolution improve AVeriTeC evidence **retrieval**? |
| **P1B** Source-aware verdict classifier (proposed) | same repo, future `experiments/verdict_classifier/` | Does source-aware evidence improve **verdict** classification? |
| **P2** First-hand authority model | `first_hand_authority_model/` | For a claim–publisher pair, does the publisher have first-hand authority? |

Legend: ✅ **COMPLETED** (done and verified) · 📝 **PROPOSED** (designed, not approved) · ⏸ **AWAITING APPROVAL** · ⛔ **BLOCKED** (needs a resource or decision)

---

## 1. Completed work

### P1 authority v2 (15-step preregistered sequence)
| Step | What | Status | Evidence (execution log) |
|---|---|---|---|
| 1 | Preregistration, config, decision log; Freeze 1 | ✅ | `freeze1`, manifest `e1f5bc53…` |
| 2 | Implementation, D-recompute gate, dry runs | ✅ | `dev_d_recompute_gate`, `offline_checks` |
| 3–4 | T V1 on 320 dev claims; X; dev scoring; selection (V1 only, DL-015) | ✅ | `t_dev_run_done`, `dev_score_done` (W = −3), `selection` |
| 5 | Freeze 2 | ✅ | `freeze2`, manifest `d94ca489…` |
| 6–7 | `dev.json` download; reserved 180 built (gold sealed) | ✅ | `dev_json_download`, `reserved_sample_built` |
| 8 | Knowledge-store extraction (180) | ✅ | `step8_verification` |
| 9 | Wikidata missing mentions | ✅ | `step9_verification` |
| 10 | Ranking: BM25 + MiniLM + RRF k=60 (139,397 docs) | ✅ | `step10_verification` |
| **11** | **Reserved D: 180 parsed, 0 errors, USD 4.19** | ✅ **(executed 2026-11-01; independently re-verified 2026-11-02, nothing re-run)** | `reserved_D_done`, `step11_verification`, raw `86b2840c…` |

Earlier (frozen) studies: the dataset audit, the held-out evaluation of systems A–H (no significant preregistered human-gold result; D vs A R@10 +0.042, p = 0.167), the AI-primary endpoint, ablations. Manuscript finalised.

### P1B verdict classifier
Nothing executed. **No classifier has ever been trained.** Retrieval with a pretrained MiniLM and LLM prompting are not training.

### P2 first-hand authority model
✅ Framework, schemas, pipeline, 4 baselines, evaluation, CLI, docs; **68/68 tests pass on synthetic fixtures** (re-run 2026-11-02). ✅ Owner decisions O1–O6 recorded (mentor approval not recorded). No real data; no real model. Synthetic success ≠ real performance.

---

## 2. Remaining authority-v2 stages (P1)

| Step | What | Type | Status | Gate |
|---|---|---|---|---|
| 12 | Memorisation probe (180 calls, ≤ 540) | LLM | ⏸ | **Own approval entry in the execution log** (prereg §5, §8.5) + owner approval |
| 13 | Reserved T (180 calls, ≤ 540) | LLM | ⏸ | Owner approval (authorised in principle by DL-012; owner has approved step by step) |
| 14 | X on reserved; **Freeze 3** | Offline | ⏸ | Owner approval |
| 15 | Hash gate; **open sealed gold**; Family R then Family N scoring, once | Offline | ⏸ | **Reserved-gold approval entry** + Freezes 1–3 verify |
| — | `docs/authority_v2_results.md` | Writing | after 15 | — |

The probe (12) is optional for Family R (U11 defines how to report if it is skipped), but it is needed for Family N metrics (a) and (d).

## 3. What is needed to train the source-aware verdict classifier (P1B)

Full design: `Source_Aware_Misinformation_Detector/docs/proposals/verdict_classifier_training_proposal_DRAFT.md` 📝

| Need | Status |
|---|---|
| Mentor review; choose how the reserved 180 may be used (options C-1/C-2/C-3) | ⏸ **Mentor** |
| Classifier preregistration + Freeze C1 | 📝 |
| `train.json` (10 MB) + train knowledge store (~13 GB streamed, can be trimmed to <1 GB) | ⏸ owner (network) · ⛔ **disk: ~2.1 GB free on C:** |
| Rank 3,068 train claims with frozen retrieval (~12–15 h CPU) | 📝 |
| Authority features for train claims: LLM D (~USD 70–75 est.) or heuristic | ⏸ owner (cost decision) |
| GPU for transformer fine-tuning (local: 4 GB Quadro, CPU-only PyTorch) | ⛔ needs Colab/Kaggle/university GPU |
| Baselines B0–B2 (CPU) → B3/B4/M (GPU) → Freeze C2 → test once | 📝 |
| Reserved-180 labels for the classifier | ⏸ **separate gate**, after authority-v2 Step 15 |

## 4. What is needed to train the first-hand authority model (P2)

Full plan: `first_hand_authority_model/docs/REAL_DATA_AND_TRAINING_PLAN_DRAFT.md` 📝

| Need | Status |
|---|---|
| Mentor confirmation of O1–O4 and answers to DECISIONS.md §5 (11 questions) | ⏸ **Mentor** |
| 16 null config decisions + approved/frozen role rules + data manifest | ⛔ (`fha.cli status`: 18 blockers) |
| Annotation manual, designated-record-keeper procedure, candidate protocol (O5) | 📝 owner drafts → mentor approves |
| Small code changes: approval tracking, O6 validation diagnostic, `candidate_origin`, `.gitattributes` | 📝 owner approval |
| Second human annotator; pilot with pre-set agreement threshold | ⛔ resource |
| Data collection (AVeriTeC train claims, **all 500 dev claims excluded**) | ⏸ deferred to the holidays + authorisation |

## 5. Dependencies between projects

```
P1 authority v2 ── Steps 12–15 ──► results ──► manuscript update
      │                                  │
      │ (frozen retrieval code, reused   │ (Step 15 opens reserved gold → affects
      │  read-only)                      │  when P1B may be tested: options C-1/C-2/C-3)
      ▼                                  ▼
P1B verdict classifier  ◄──── optional authority feature ──── P2 first-hand authority model
                              (only if P2 excludes all 500 dev claims and
                               P2 scores on P1B training claims are out-of-fold)
```

- **P1 → P1B:** P1B reuses P1's frozen retrieval code (read-only) and reserved-set Step 10/11 outputs. The *timing* of P1 Step 15 vs P1B Freeze C2 is the main coupling (§3, option C-1 recommended).
- **P2 → P1B:** optional, later. P1B can be run without P2.
- **Shared upstream (optional):** P1B and P2 both want AVeriTeC *train* data. P2 needs only `train.json` + URL lists; P1B needs the full train knowledge store. They can be downloaded once, but each project keeps its own manifest.
- **P1 ↔ P2:** no dependency. P2 must never read P1 frozen artifacts, reserved claims, gold or probe materials.

## 6. What can proceed independently (and the approval each needs)

| Work | Depends on | Needs |
|---|---|---|
| P1 Step 12 or 13 | nothing new | owner approval (+ probe log entry for 12) |
| **Free disk space on C:** | nothing | owner action (recommended **now**, before any further step writes data) |
| P1B: mentor review of the proposal; write the classifier preregistration | nothing | mentor/owner |
| P1B: baselines B0–B2 on train/val | `train.json` only | owner (small download) |
| P2: mentor meeting; annotation manual; role-rule freeze; code changes | nothing | mentor/owner |
| P2: data collection | F0–F2 done | authorisation (deferred to holidays) |

## 7. Outstanding approvals (consolidated)

| # | Approval | Project | Who |
|---|---|---|---|
| A1 | Step 12 memorisation probe (own log entry) | P1 | Owner |
| A2 | Step 13 reserved T | P1 | Owner |
| A3 | Step 14 X + Freeze 3 | P1 | Owner |
| A4 | Step 15 reserved-gold gate + scoring | P1 | Owner |
| A5 | Classifier proposal; reserved-180 option C-1/C-2/C-3 | P1B | Mentor + owner |
| A6 | Train data download; LLM cost for train D; GPU environment | P1B | Owner |
| A7 | Classifier-specific reserved-gold gate | P1B | Owner (+ mentor) |
| A8 | O1–O4 confirmation; 16 config decisions; role-rule freeze; annotation manual | P2 | Mentor |
| A9 | Start of real data collection | P2 | Owner + mentor |
