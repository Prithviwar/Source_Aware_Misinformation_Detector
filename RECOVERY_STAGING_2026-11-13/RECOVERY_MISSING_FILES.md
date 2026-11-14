# Missing files after recovery, 2026-11-13

Nothing on this list was fabricated, regenerated or replaced with a substitute.

## A. Project A: generated experiment outputs (script outputs; never saved by a Claude tool)

| Missing | What survives instead | Can it be regenerated? |
|---|---|---|
| `results/esa_nov2026/relevance_baseline/train_sample_split.json` (R1 split) | split SHA-256 `1b994a96974e3e7bbcda6994b1c0b08a5bbdbb580de42fcf383b5e11709e5765` recorded in the ESA report and in memory | **Yes, offline and deterministic** (`make_train_split.py`, seed 2051, reads the restored `train.json`). A matching hash would prove it byte-equivalent. **Not run; needs your OK.** |
| `results/esa_nov2026/relevance_baseline/EXTRACTION_MANIFEST.json/.md`, `extraction_log.jsonl`, `extraction_stdout*` | metadata in the ESA report §6 R2 (HF revision `2ca9dee2…`, 300/300 claims, 303,594 docs) | Only after re-extraction (network, needs approval) |
| `results/esa_nov2026/relevance_baseline/run1_pu/`: `models/`, `feature_cache/`, per-claim CSVs, `relevance_baseline_report.json` (original SHA-256 `0f49c165a0df6ce2366244d5b2289d236b04318bdff9a0cb645b121e8750e77c`), `run_stdout.log` | test R@10 values (Hybrid 13/42 = 0.310, LR 10/42 = 0.238, HGB 12/42 = 0.286, LR+MiniLM 8/42 = 0.190) as **historical reported results** in the restored ESA report | A re-run would be a **new run**, not the original. Needs the train KS sample first. |
| `results/esa_nov2026/` reproduce / recall-ceiling / promotion-stats / demo outputs, `SYNTHETIC_SMOKE_TEST/` | numbers quoted in the ESA report | Yes, offline scripts restored. Not run. |
| `results/authority_v2/**` (execution log `2dde4a69…`, freeze manifests, T_v1 dev outputs, Step-11 `reserved/authority_raw.jsonl` `86b2840c…`, wikidata stdout) | hashes in transcripts and docs | **Lost since 2026-11-06.** The Step-11 output involved LLM calls and cannot be recreated identically. |
| `data/processed/averitec_reserved180_gold.jsonl` (sealed), `ks_reserved180`, wikidata cache | none | **Do not regenerate** without your explicit approval (sealed-gold protocol) |
| `results/authority_bottleneck_diagnostics/`, `results/authority_bottleneck_diagnostics_audit/` | some hashes in transcripts (e.g. `gold_urls.csv` `7d79d968…`) | Yes, offline, with the restored scripts. Not run. |

## B. Shared storage
| Missing | Note |
|---|---|
| `storage/datasets/averitec_train_ks_sample/` (300 files, ~1.2 GB) | Not found anywhere. See re-extraction steps below. |
| `storage/backups/claude_session_backup_2026-11-06.zip` and the rest of that backup folder | Only the 41 Project B git objects survived (restored). |
| `storage/recovery_staging/*/files/`, `recovery_manifest.json`, `recovery_tools/` (2026-11-06) | The READMEs and RECOVERY_MANIFEST.md are restored. The file contents now live in Project A, and the 6 Nov tools are in `_preserved_sources/temp_scratchpads/398127e0…`. |

## C. Project B
| Missing | Note |
|---|---|
| `outputs/synthetic_smoke/` (git-ignored synthetic smoke-run outputs) | Regenerable with the CLI on synthetic data. This is not real-world output. |
| `First_Hand_Authority_Model_Handover_2026-10-29.md` (was in `Downloads\`) | It was pasted into a chat, not written by Claude. No copy survives. |

## D. Not Claude-generated; check email, Drive, teammates or the portal
- `Downloads\ESA_CapstoneProject_PPT.pptx`
- `Downloads\CapstoneProject_Phase-1_Review-2_PPT_Template.pptx`
- `Downloads\ESA_CapstoneProject_Report.zip`
- `ESA_CapstoneProject_Report\Page_1-2.docx`
- `ESA_CapstoneProject_Report\Page_3-8.docx`

`CapstoneProject_IR_03.pptx` and `Page_9.docx` still exist.

## E. Requested names that did not exist as separate files
- `docs/authority_v2_progress_report.md`: the original file is `docs/authority_v2_progress_report_steps1-9.md` (restored as an exact copy).
- "Dataset investigation" and "experiment configuration / reproducibility" documents: no separate Claude-written files existed beyond `docs/dataset_audit.md` (in the GitHub clone), `experiments/authority_v2/config.json` and the reproducibility sections of the ESA report (all restored or present).

## Re-extraction instructions for the train KS sample (DO NOT RUN without separate approval)
```
# prerequisites: the split manifest must exist (regenerate offline first, check sha 1b994a96…)
cd Source_Aware_Misinformation_Detector
python experiments/esa_nov2026/relevance_baseline/make_train_split.py
python experiments/esa_nov2026/relevance_baseline/extract_train_ks_sample.py --approved   # network, ~1.2 GB streamed from pinned HF revision 2ca9dee2…
python experiments/esa_nov2026/relevance_baseline/verify_extraction.py
set HF_HUB_OFFLINE=1   # avoid the metadata ping seen on 2026-11-08
```
Re-extracted data and any re-run would be **new artifacts**, to be labelled as a reproduction, not as the original 8 Nov outputs.
