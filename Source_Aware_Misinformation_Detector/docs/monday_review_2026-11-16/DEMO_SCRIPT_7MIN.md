# Monday Review Demo Script (7–8 minutes)

**Before the review (at least 15 minutes earlier):**
1. Double-click `Source_Aware_Misinformation_Detector\run_demo.bat`. Wait for the browser tab at `http://localhost:8501` to finish loading. The first start takes 1–2 minutes.
2. In the sidebar, pick claim **268** and press **Run pipeline** once, so the page is warm.
3. Keep `results\esa_nov2026\demo\fallback\INDEX.html` open in a second browser tab as a backup.
4. Close other heavy programs. Live MiniLM can take 2–8 minutes on this laptop.

**Golden rule for the live demo:** use **"Stored rankings (fast, exact)"** mode. Use "Recompute live" or "Custom claim" **only for claim 268**. Those two runs are pre-computed by `prepare_demo.py --live` and stored with their computation time, so they load instantly. Say that they were computed earlier by the same code.

---

### Step 1 — Opening and problem statement (0:00–0:45)

| | |
|---|---|
| **Do** | Show the app's title page (Pipeline demo tab). |
| **On screen** | Title, sidebar, an info box suggesting claim 268. |
| **Say** | "Fact-checking systems retrieve evidence, then decide. Our focus is the **Authority Resolution Module**. A retrieved page can be *relevant* without being the *authoritative* source for that specific claim. Since Review 2 we have measured retrieval recall, built a working pipeline demo, run a learned relevance baseline, and prepared the human annotation protocol. The supervised authority model itself is **not trained yet**; I will show why." |
| **Mentor Q** | *What exactly is "claim-specific authority"?* |
| **Answer** | "The source that issued, recorded or holds the fact at issue, e.g. the statistics office for its own figure. Credibility is a property of the publisher; authority is a property of the claim–document pair." |

### Step 2 — Claim input and processing (0:45–1:30)

| | |
|---|---|
| **Do** | Sidebar: *Suggested demo claims* → **268**, mode *Stored rankings*, K = 10, evidence markers ON → **Run pipeline**. Scroll to Steps 1–2. |
| **On screen** | The claim "Trump's 24 Sept 2020 executive order legally ensures pre-existing-condition protections"; speaker, date, country; 1,000+ candidate documents; BM25 query terms; spaCy entities and entity keys. |
| **Say** | "Input is the claim text. The query is the claim itself; we do not rewrite it. BM25 removes stop words. MiniLM embeds the same text. spaCy entities and the claim's country are used later by the heuristic authority prior." |
| **Mentor Q** | *Why not use query expansion or the AVeriTeC questions?* |
| **Answer** | "The AVeriTeC questions are written by fact-checkers who already know the answer, so using them would leak gold information. We use only what exists at prediction time." |

### Step 3 — BM25 (1:30–2:10)

| | |
|---|---|
| **Do** | Step 3 → **BM25 (lexical)** tab. |
| **On screen** | Top-10 with publisher, first-sentence title, URL, score, ranks under all three methods, matched query terms, snippet. |
| **Say** | "BM25 rewards exact word overlap: news pages repeating 'Trump executive order health' rank highest." |
| **Mentor Q** | *Which BM25 implementation and parameters?* |
| **Answer** | "`bm25s` 0.3.11, English stop words, no stemming, default k1/b, over the full document text." |

### Step 4 — MiniLM (2:10–2:50)

| | |
|---|---|
| **Do** | **MiniLM dense** tab, then **Side by side**. |
| **On screen** | A different top-10; the overlap metrics show only ~2 of 10 shared between BM25 and MiniLM. |
| **Say** | "MiniLM (all-MiniLM-L6-v2, not fine-tuned) matches meaning, using the first 1,000 characters of each page. The two lists overlap in only about 2 of 10 documents." |
| **Mentor Q** | *Why only 1,000 characters?* |
| **Answer** | "The model's trained input length is 128 word pieces, and CPU budget. It is a known limitation: a fact deep in a long page is invisible to the dense retriever." |

### Step 5 — Hybrid RRF (2:50–3:30)

| | |
|---|---|
| **Do** | **Hybrid RRF** tab. Point at the "Best evidence rank B / M / H" metric. |
| **On screen** | Hybrid top-10. Best evidence rank BM25 45, MiniLM 44, Hybrid 28. |
| **Say** | "Reciprocal Rank Fusion adds 1/(60 + rank) from both lists, so it rewards agreement. Here the AVeriTeC evidence document, the executive order text, is only at rank 28. That is a relevance ranking; it does not know who the authority is." |
| **Mentor Q** | *What does the evidence marker mean? Isn't that leakage?* |
| **Answer** | "It marks the URLs AVeriTeC annotators cited. It is used **only for display and evaluation**. It never enters any ranking; our test suite checks that the rankings are identical with markers on or off. And it is relevance evidence, not an authority label." |

### Step 6 — Authority Resolution Module (3:30–5:00)

| | |
|---|---|
| **Do** | Step 4: show the LLM prediction box, then tabs **B**, **C**, **D**. Then Step 5: the stacked bar chart. |
| **On screen** | Stored prediction: fact at issue; top-3 = Federal Register, White House archive, Congress. B/C lift `finance.senate.gov` to rank 2 (it is `.gov`). D lifts the executive order from 28 to **1**. The bar chart shows the relevance part vs the authority part. |
| **Say** | "B is a generic credibility prior: `.gov` scores 1.0, so a senator's press release criticising the order jumps to rank 2. That is *credibility*, not *authority*. D uses the LLM's predicted authorities. The prediction was generated in September with Claude, with no web access; **it is stored, not generated live**. D puts the order itself at rank 1. The final score is relevance plus prior. Because the prior is 0/1, every document of a boosted publisher jumps above everything else; that is the weakness the supervised model must fix." |
| **Mentor Q** | *Is the LLM called live?* |
| **Answer** | "No. The demo makes no LLM or network call. Predictions for the 320 claims were generated in Sept 2026 and frozen before evaluation." |
| **Mentor Q** | *Show a failure.* |
| **Answer** | Select **436** (evidence rank 1 → 16 under D) or **326** (24 → 28) and run. "Publisher-level boosting promotes off-topic pages. On the held-out set D won on 20 claims and lost on 52 by best evidence rank." |

### Step 7 — Evaluation results (5:00–6:10)

| | |
|---|---|
| **Do** | **Evaluation: frozen held-out** tab. |
| **On screen** | Table of R@1…R@100, MRR and pool coverage; primary test D vs A at R@10 = 0.293 vs 0.251, +13/−6, p = 0.167, CI [−0.006, 0.096]; Recall@K curves; pool ceiling 0.671; recall by depth. |
| **Say** | "200 held-out AVeriTeC dev claims, 167 with reachable evidence. The protocol was preregistered and the rankings frozen. The LLM prior improves Recall@10 from 0.251 to 0.293, but **p = 0.167, not significant**. And the hybrid top-100 contains evidence for only 67% of claims. A source that is never retrieved cannot be selected by any authority module, so recall caps everything. Going to top-300 lifts the ceiling to about 92%." |
| **Mentor Q** | *Is this authority recall?* |
| **Answer** | "No. It is **evidence recall** against AVeriTeC citations, which include news and fact-check pages. Authority Recall@K needs human authority labels, which is exactly what we are building." |
| **Mentor Q** | *What about the 180 reserved claims from Review 2?* |
| **Answer** | "Those predictions were executed, but the output files were lost in a data-loss incident. We do **not** use them and we do not claim them. Today's results use the frozen 200-claim held-out set, re-verified from stored rankings." |

### Step 8 — PU relevance baseline (6:10–7:00)

| | |
|---|---|
| **Do** | **PU relevance baseline** tab. |
| **On screen** | Red banner "NOT an authority model". Test table: Hybrid 13/42, LogReg 10/42, HistGBDT 12/42 (selected), LogReg + MiniLM 8/42; p = 1.0. |
| **Say** | "We also trained a learned relevance ranker on 300 AVeriTeC *training* claims, a separate dataset, using cited evidence URLs as weak positives and everything else as unlabelled: positive-unlabelled learning. On the 42 test claims, **no model beat Hybrid RRF**. Gradient boosting overfit its training claims. That is a valid negative result: citation proxies are not enough, and we need real human labels." |
| **Mentor Q** | *Where are the model files?* |
| **Answer** | "The trained model files were lost in the same deletion. The metrics shown are the original run's recorded console output. The scripts are restored, and re-running needs the 1.2 GB training store re-extracted (about 2.5 h, needs approval)." |

### Step 9 — Dataset gap and next steps (7:00–7:45)

| | |
|---|---|
| **Do** | Switch to the slides (dataset / next-steps slide), or open `docs/monday_review_2026-11-16/annotation/AUTHORITY_ANNOTATION_GUIDELINES.md`. |
| **Say** | "No existing resource labels which *document* is authoritative for a *specific claim*: AVeriTeC labels evidence, NELA labels publishers, Wikidata references are not ground truth. So we prepared the protocol: claim–document pairs, separate relevance and authority labels, two annotators, Cohen's κ / Krippendorff's α, adjudication, strict leakage rules. The 200-pair pilot packet is generated and blank. Next: a pilot with two annotators, then the main set on AVeriTeC train claims, then the two-head relevance × authority model compared with the heuristic and LLM baselines on the same human-labelled test set." |
| **Mentor Q** | *Is the model already designed?* |
| **Answer** | "Yes, on paper: `docs/monday_review_2026-11-16/AUTHORITY_MODEL_DESIGN.md`. Primary metric Authority Recall@10 on a claim-disjoint test set with a common candidate pool. It is not trained, and we will not claim it until real labels exist." |

---

## If the live app fails

1. Say: *"The live app has a problem; I'll show the stored outputs produced by the same code this morning."*
2. Open `results\esa_nov2026\demo\fallback\INDEX.html` → **Claim 268**. It has the same three retrieval lists, the stored LLM prediction and the B/C/D tables (highlighted rows = evidence documents).
3. Genuine screenshots of the running app, captured 14 Nov: `results\esa_nov2026\demo\screenshots\01…08.png`. For evaluation, show `results\esa_nov2026\figures\fig1…fig4.png` or the slides.
4. Terminal fallback (about 75 s): `python experiments\esa_nov2026\demo.py --claim-id 268`.
5. If Python itself fails: the slides contain the same figures; the cheat sheet has every number.
