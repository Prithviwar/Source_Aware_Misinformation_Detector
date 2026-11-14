# 28 October bottleneck analysis: transcript recovery (staging only)

Recovered 2026-11-06 from backup ZIP `claude_session_backup_2026-11-06.zip` (SHA-256 `074d9433…acb7`), session `390fe08e`. **Not copied into the project repository. The script has not been run.**

| Staged file | Original path | Status | SHA-256 |
|---|---|---|---|
| `files/experiments/authority_bottleneck_diagnostics.py` | `experiments/authority_bottleneck_diagnostics.py` | **TRANSCRIPT-RECONSTRUCTED, PARTIALLY VERIFIED** | `66a962c0e95259af52b895bc950f7aa71671e4f95bbfd100886900de363cb23b` |
| `files/docs/authority_resolution_bottleneck_analysis.md` | `docs/authority_resolution_bottleneck_analysis.md` | **TRANSCRIPT-RECONSTRUCTED, PARTIALLY VERIFIED** | `0fcd49b54fe0179302068196115a2ebe70e78d9bcd5183b2fa33d1a237e8fbcb` |

**No historical SHA-256 was ever recorded for either file**, so neither can be called byte-exact.

## How they were rebuilt
Every successful `assistant` tool call was replayed in order (`recovery_chronology.json` gives the hash after each step).

- **Script:** 1 `Write` (06:40 UTC), 7 `Edit`s, and 2 `sed -i` commands re-run with the identical expressions in Git Bash `sed` (one of them is line-addressed: 387, 393, 409). Final edit 06:49:51 UTC.
- **Document:** 1 `Write` (06:55:32 UTC) and 1 `Edit` (06:55:40 UTC).
- No later modification of either file appears in any transcript.

## Verification against the transcript history

| Check | Result |
|---|---|
| Script line count vs `wc -l` printed 2026-10-28 16:51 UTC | 608 = 608 |
| Script lines vs two `Read` outputs taken after the final edit (12:03 UTC) | 370 of 608 lines identical (lines 1–479 covered); lines 480–608 were not printed after the final edit |
| Script vs earlier `Read`, `grep -n` and `sed -n` outputs (06:44–06:45) | 50/50, 4/4, 16/16 and 12/12 printed lines identical |
| Document lines 15–50 vs printout of 2026-10-28 16:51 UTC | 36/36 identical |
| Document lines 1–25 vs printout of 2026-11-01 05:07 UTC | 25/25 identical |
| Document lines 51–856 | Not independently checked (never printed after writing) |
| CR bytes | 0 in both files |

## Notes
- **Both files predate the reserved-180 sample** (built 2026-10-29), so they cannot contain reserved labels or sealed gold. They analyse the already-used held-out and development sets.
- **The script's outputs are not recovered and were not recreated:** `results/authority_bottleneck_diagnostics/`, with historical hashes `7d79d968…`, `c9b93e64…`, `4188fcf6…`.
- **Not recovered (outside the approved scope):** the companion files from the same day, `experiments/authority_diagnostic_audit.py` and `docs/authority_resolution_diagnostic_audit.md`.
- `recovery_tools/` holds the read-only scripts used (`bn_events.py`, `bn_replay.py`).
