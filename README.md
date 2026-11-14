# Capstone Workspace: Source-Aware Misinformation Detection (IR_03)

This repository holds the complete capstone workspace: two **separate** research projects, the record of
how the workspace was recovered after two data-loss incidents (6 and 13 Nov 2026), and the shared research
roadmap. Large datasets, model files, private annotation keys and personal data are **not** in Git (see
[What is not in this repository](#what-is-not-in-this-repository)).

> **Status (14 Nov 2026).** Project A has a working retrieval and authority-prior pipeline, a frozen held-out
> evaluation and a live demo. Its **supervised claim-specific authority model is not trained**, because no
> human authority labels exist yet. The annotation protocol and a blank pilot packet are ready. Project B is
> implemented and tested on **synthetic fixtures only**: no real data, no trained research model, no empirical result.

## Folder structure

```
capstone/
├── README.md                              this file
├── RESEARCH_ROADMAP_2026-11-02.md         roadmap for both projects (as of 2 Nov 2026)
├── Source_Aware_Misinformation_Detector/  Project A (its own README, code, docs, results)
├── first_hand_authority_model/            Project B (its own README, code, tests, docs)
├── RECOVERY_STAGING_2026-11-13/           recovery reports, manifests and tools (published subset)
└── storage/                               shared notes on datasets and recovered material (published subset)
```

The Git history of Project A from before 14 Nov 2026 (when this repository contained only Project A at its
root) is preserved. Those files now live under `Source_Aware_Misinformation_Detector/`, and Git records the
move as renames, so `git log --follow <file>` still shows each file's full history.

## Project A: Source-Aware Misinformation Detection

`Source_Aware_Misinformation_Detector/` studies whether resolving the **claim-specific authority** of a source
(the publisher that issued or holds the fact at issue) improves evidence retrieval for fact verification on
AVeriTeC.

- **Implemented:** BM25, MiniLM and Hybrid RRF retrieval over AVeriTeC knowledge stores; generic,
  heuristic and stored-LLM authority priors; re-ranking.
- **Frozen held-out evaluation (n = 167 claims):** the LLM prior raised evidence Recall@10 from 0.251 to 0.293
  (p = 0.167). This gain is **not significant**. This is *evidence* recall, not authority recall.
- **PU (positive-unlabelled) relevance baseline:** a negative result. No learned model beat Hybrid RRF on the
  42 test claims. The trained model files were lost on 13 Nov. The metrics come from the recorded console output.
- **Ready but not yet run:** annotation guidelines, an agreement tool, a blank 200-pair pilot packet and the
  authority-model design.
- **Missing:** the reserved-180 outputs were lost. They are not reconstructed and not claimed.

Details: `Source_Aware_Misinformation_Detector/README.md` and
`Source_Aware_Misinformation_Detector/docs/monday_review_2026-11-16/` (start with `README.md` and `FINAL_STATUS.md`).

## Project B: First-Hand Authority Model

`first_hand_authority_model/` predicts, for a **claim–publisher pair**, the probability that the publisher has
first-hand authority to establish the claim's central fact. It contains schemas, a pipeline, four baselines,
evaluation code, a CLI and 68 pytest tests, all run on **synthetic fixtures only**. Real training is blocked
until the methodological decisions in `docs/DECISIONS.md` are made and dataset construction is authorised.
See `first_hand_authority_model/README.md` and `STATUS.md`.

## How the two projects relate

The two projects address the same theme (who is the authoritative source for a claim) but share **no code,
data or results**. Project B must never read Project A's frozen artefacts, reserved claims or gold labels, and
Project B's synthetic tests are not evidence for Project A. A possible later link (Project B scores used as a
feature in a future verdict classifier) is described in §5 of `RESEARCH_ROADMAP_2026-11-02.md`. It is proposed,
not implemented. Each project has its own README, requirements and `.gitignore`.

## Setup

Both projects use Python 3.13 on CPU.

**Project A**
```bash
cd Source_Aware_Misinformation_Detector
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```
Most scripts need the AVeriTeC knowledge-store extracts under `data/raw/`, which are not in Git. The
Project A README explains how to re-create them from the official dataset (network access, several GB).

**Project B**
```bash
cd first_hand_authority_model
pip install -r requirements.txt        # numpy, scipy, scikit-learn, pytest
```

## Demo (Project A)

On Windows, double-click `Source_Aware_Misinformation_Detector/run_demo.bat`. Or run:
```bash
cd Source_Aware_Misinformation_Detector
python -m streamlit run experiments/esa_nov2026/demo_app.py --server.port 8501
```
Then open `http://localhost:8501` and pick claim 268. The demo runs offline and makes no LLM or API calls (the
LLM authority predictions were generated in Sept 2026 and are stored). It needs the local knowledge-store data. Without the data, use the
static fallback pages in `results/esa_nov2026/demo/fallback/INDEX.html` and the screenshots in
`results/esa_nov2026/demo/screenshots/`. The presenter script is
`docs/monday_review_2026-11-16/DEMO_SCRIPT_7MIN.md`.

## Testing

```bash
# Project A (needs the local knowledge-store data)
cd Source_Aware_Misinformation_Detector
python experiments/esa_nov2026/test_demo_pipeline.py          # add --live for a full live recompute (slow)
python experiments/esa_nov2026/test_demo_app.py               # headless Streamlit UI test
python experiments/esa_nov2026/annotation/agreement.py --selftest

# Project B (synthetic fixtures; no data needed)
cd first_hand_authority_model
python -m pytest -q
```

## Data, privacy and limitations

- **AVeriTeC** (CC BY-NC 4.0) is not redistributed. Raw data and knowledge-store extracts (over 1 GB) stay local.
- **Sealed labels:** the reserved-180 gold file and the AVeriTeC test labels are never committed or used for training.
- **Annotation privacy:** the pilot answer key (`_KEY_DO_NOT_GIVE_TO_ANNOTATORS/`) is excluded. Third-party
  email addresses in the pilot excerpts are replaced with `[REDACTED_EMAIL]`. The unredacted originals are
  kept in a local-only backup.
- The updated review deck, which contains team registration numbers, is kept out of Git.
- Evidence recall is not authority recall. The sample sizes are small (n = 167 held-out claims, n = 42 PU test
  claims). The setting is optimistic, because the AVeriTeC stores were built partly from gold-derived queries.

## What is not in this repository

| Not included | Why |
|---|---|
| `Source_Aware_Misinformation_Detector/data/raw/`, extra ranking files (`results/rankings_*.jsonl.gz`) | large; re-creatable |
| AVeriTeC train knowledge-store sample (about 1.2 GB) | lost on 13 Nov; re-extraction needs approval (`storage/datasets/README_RECOVERY_NOTE.md`) |
| Trained models (`*.joblib`), feature caches, `__pycache__` | binaries or caches |
| Pilot answer key, sealed reserved-180 gold | leakage control |
| Unredacted pilot backup and git-migration backups (`storage/backups/`) | private, local-only |
| Claude session transcripts, scratchpads and recycle-bin metadata (`RECOVERY_STAGING_2026-11-13/_preserved_sources/`) | private conversation data |
| `RECOVERY_STAGING_2026-11-13/reconstructed/project_*` | verified byte-identical duplicates of the live project files (only the two later update banners differ) |
| Review deck with team SRNs | personal data |
| Project B's nested `.git` | Project B's files are tracked here directly |
