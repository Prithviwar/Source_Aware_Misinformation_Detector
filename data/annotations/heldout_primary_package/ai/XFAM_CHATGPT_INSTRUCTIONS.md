# Cross-family check with ChatGPT: instructions for the manual step

**Status (2026-10-02): ready.** The protocol is frozen (`FROZEN_HASHES.json`).
- `xfam_subset_prompts_NO_LABELS.csv` was regenerated from the **frozen** evidence prompt, SHA-256 `87eae8309006267df275f5f1249f1d5824a8ce8f841ba0f7c081028f1b1b8a3f`. Every row is identical to what the Claude runner sends for the same item.
- Do **not** use `xfam_subset_prompts_NO_LABELS_SUPERSEDED_round1prompt.csv`. It was built with the round-1 prompt (`417a609c…`) and is kept only as a record.

**What this is.** A **sensitivity analysis of AI–AI agreement**. It is not human validation, and the labels are not ground truth. Every label produced here is **MODEL_GENERATED**.

## Input

`xfam_subset_prompts_NO_LABELS.csv` holds 94 rows:
- every gold evidence URL of 40 held-out claims, sampled with seed 2028 from the 177 non-pilot claims;
- one row per item, with columns `item`, `claim_id`, `system_prompt`, `user_prompt`, and empty label columns.

## How to run each item

This keeps conditions as close as possible to the Claude annotator: one isolated call per item, no tools, no memory.

1. Open a **new Temporary Chat** in ChatGPT, so there is no memory or chat history.
2. Make sure there are **no custom instructions**, and that **web search/browsing and all tools are off**.
3. Paste the row's `system_prompt`, a blank line, then its `user_prompt`, as **one message**. Paste nothing else and add no comments.
4. Copy the JSON object from the answer. If the answer is not valid JSON, send the same message once more in a **new** Temporary Chat. If it fails again, leave the row's labels empty and write `FAILED` in `notes`.
5. Use a new Temporary Chat for every item.

Write down the exact ChatGPT model name shown in the interface (e.g. `GPT-x`) and the date.

## Output file

Save the result in this folder as `MODEL_GENERATED_evidence_xfam_runX_CHATGPT_<MODEL>.csv`, UTF-8. It needs exactly these columns:

| Column | Content |
|---|---|
| `item` | copied from the input |
| `claim_id` | copied from the input |
| `label` | from the JSON: `primary` / `secondary` / `derived` / `unclear` |
| `publisher_name` | from the JSON |
| `authority_rationale` | from the JSON |
| `confidence` | from the JSON: `high` / `medium` / `low` |
| `notes` | from the JSON (or `FAILED`) |
| `annotator_id` | `MODEL_GENERATED_CHATGPT_<MODEL>` on every row |

Do not edit any label after saving. The comparison uses `python experiments/score_ai_primary.py agreement <Claude labels> <ChatGPT labels>`. It reports percentage agreement and Cohen's κ, and describes the result only as **AI–AI agreement**.
