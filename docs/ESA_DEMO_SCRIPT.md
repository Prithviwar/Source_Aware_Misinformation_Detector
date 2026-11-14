# ESA Demo Script — 10 minutes (Project A, Source-Aware Misinformation Detection)

**Rule for the presenter:** every number on screen comes from a genuine project file. Say "frozen" for the preregistered results, "exploratory" for the Nov-2026 measurements, "lost" for reserved-180 outputs and "proposed" for the supervised model. Never say that an authority model was trained.

**Setup (before the panel):**
1. Open a terminal in `C:\Users\Lenovo\Downloads\capstone\Source_Aware_Misinformation_Detector`.
2. Pre-open `results/esa_nov2026/demo/claim_268.html`, `claim_436.html` and `claim_2.html` in browser tabs. These are the fallback if the terminal fails.
3. Test-run once: `python experiments/esa_nov2026/demo.py --claim-id 268` (about 25 s, offline).

---

### 0:00–1:00 Problem statement
- "Fact-checkers need *evidence*, and ideally evidence from the source that actually holds the fact. Search ranks by topical **relevance**. Some systems add publisher **credibility**. Neither asks: *who is the authority for this specific claim?*"
- Define three terms:
  - **relevance**: is the document about the claim?
  - **credibility**: is the publisher generally trustworthy?
  - **claim-specific authority**: did this source issue, record or hold the fact?

### 1:00–2:00 Data and pipeline
- AVeriTeC: real fact-checked claims, each with a pre-built store of about 780 candidate web documents (median 781.5 on held-out).
- Pipeline: claim → BM25 + MiniLM → Reciprocal Rank Fusion → hybrid top-100 → authority prior → re-ranked evidence.
- Evaluation: a frozen, preregistered held-out set of 200 claims; 167 have reachable gold evidence.

### 2:00–4:30 Live demo, part 1: retrieval (claim 268)
Run:
```
python experiments/esa_nov2026/demo.py --claim-id 268
```
- Read the claim: *"Trump's executive order on September 24, 2020 legally ensures health coverage protections for those with pre-existing conditions."*
- Point to the three columns:
  - **BM25** (exact words): its #1 is a CNBC article; gold first appears at rank 45.
  - **MiniLM** (meaning, first 1,000 characters): its #1 is an AAMC policy page; gold at 44.
  - **Hybrid RRF**: rewards agreement, so gold reaches rank 28. BM25 and MiniLM share only 2 of their top-10 documents.
- Say: "The three retrievers disagree a lot, which is why we fuse them. But even the fused list has the actual executive order down at rank 28."
- (Optional, if time and the panel ask whether it really runs: add `--live`. It recomputes everything in about 2 minutes, and we verified the result is identical to the stored rankings for 6 of 6 claims tested.)

### 4:30–6:30 Live demo, part 2: authority resolution (same output)
- Show the **frozen LLM prediction** (generated Sept 2026, not re-run): Federal Register, White House archive, Congress.
- **B (generic credibility):** rank 2 is a `finance.senate.gov` press release criticising the order. It is credible and `.gov`, but it is not the authority for what the order says.
- **D (LLM claim-specific authority):** rank 1 is now the executive order itself on `trumpwhitehouse.archives.gov` (an AVeriTeC evidence document), up from 28.
- Message: "Credibility is not authority. The right *publisher for this claim* matters."

### 6:30–7:45 Limitation (claim 436)
Show tab `claim_436.html`, or run `--claim-id 436`.
- Claim: *"The US military will check purity and distribute COVID-19 vaccines in the US."* The hybrid ranking already had a gold document at **rank 1**.
- D boosts every document from the predicted DoD, HHS and CDC domains. Its whole top-10 is from those publishers (vaccine-contract PDFs, a CDC "pay for vaccines" page), and gold falls to **16**.
- Aggregate (exploratory, 167 held-out claims): D lifted **267** documents from below rank 50 into a top-10, and **263** of them are not AVeriTeC evidence documents. D's best-gold rank won on 20 claims and lost on 52.
- Why: the prior is binary at publisher level and always outweighs relevance. **This is the motivation for a document-level model.**

### 7:45–8:45 Results and recall ceiling
- **Frozen held-out R@10:** Hybrid 0.251 → +generic 0.263 → +heuristic 0.275 → +LLM 0.293. D vs A: +13/−6, p = 0.167. That is **directional, not significant**, and we say so.
- **Where recall is lost (held-out):**
  - collection: 167/192 claims have reachable gold;
  - candidate pool: only 112/167 = 0.671 have gold in the top-100;
  - ranking: D reaches 49/167 = 0.293, about 44% of that pool ceiling.
- Measured from frozen rankings, the pool ceiling rises to 0.850 at top-200 and 0.922 at top-300. These match our earlier reconstructed figures.

### 8:45–9:30 Proposed supervised model (future work, clearly labelled)
- Show `docs/ESA_PROPOSED_AUTHORITY_MODEL_ARCHITECTURE.md`: two heads, P(relevant | c, d) and P(authoritative | c, d, relevant), combined multiplicatively so irrelevant pages cannot be promoted.
- Status:
  - **not trained**, because no human claim–document authority labels exist;
  - a separate **relevance** baseline (positive-unlabelled; logistic regression, gradient boosting, frozen-MiniLM features) was trained on a frozen, claim-disjoint 300-claim AVeriTeC train split. **On 42 test claims, none of the three models beat Hybrid RRF** (selected model R@10 12/42 vs 13/42, p = 1.0). This is an honest negative result: citation proxies alone are not enough, which motivates human labels.

### 9:30–10:00 Three domains and close
- Health (claim 89, 1918 influenza masks), government (claims 268 and 328), science (claims 464 and 326). These are illustrations only, with no domain validation yet.
- Close: "Phase I delivered a reproducible retrieval + authority pipeline and a frozen evaluation that shows where it fails. Phase II builds the human-labelled, document-level authority model."

---

## Likely viva questions — honest answers
- **Did you train an ML model?** Not an authority model: there are no human authority labels, and LLM or AVeriTeC labels are not authority ground truth. A separate positive-unlabelled **relevance** baseline was trained on AVeriTeC train claims. It did not beat the hybrid on test (12/42 vs 13/42 at R@10).
- **What about the 180 reserved claims?** Retrieval and LLM predictions were run on 2026-11-01. The output files were lost in a folder deletion on 2026-11-06. They were not re-run, because a re-run would be a new experiment, not a recovery. Their gold was never scored.
- **Is 0.293 vs 0.251 significant?** No: p = 0.167 on the primary test.
- **Why is AVeriTeC gold not authority?** It contains whatever the fact-checker cited, often news or fact-check pages.

## Screenshot plan (if a recorded demo is used)
Use only genuine pages from `results/esa_nov2026/demo/`:
1. `claim_268.html`, retrieval columns.
2. `claim_268.html`, LLM prediction plus the B vs D tables.
3. `claim_436.html`, the D table (boosted rows, gold at 16).
4. `claim_2.html`, MiniLM finding the source tweet at rank 3.
5. Terminal output of `reproduce_check.py` showing PASS.
