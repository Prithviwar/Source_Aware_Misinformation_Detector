# Likely Viva Questions and Answers

### Problem and concepts
**Q1. What is the research question?**
Can explicitly identifying the source that is authoritative *for a specific claim* improve evidence retrieval and ranking, compared with relevance-only and credibility-weighted retrieval?

**Q2. Credibility vs authority vs relevance?**
- **Credibility:** a property of the publisher, the same for every claim (Reuters is credible).
- **Authority:** a property of the (claim, document) pair. Is this source the origin, issuer or holder of *this* fact? (The statistics office for its own figure.)
- **Relevance:** does the page address the claim's fact at all?

**Q3. Why does authority matter for misinformation detection?**
A verdict is only as good as its evidence. Secondary reports mis-state figures and studies; the primary record settles the fact. Ranking the primary record first gives the verifier better evidence.

### Retrieval
**Q4. Why BM25 + MiniLM + RRF?**
They are complementary. BM25 does exact lexical matching; MiniLM does semantic matching. RRF is training-free, robust to score-scale differences, and rewards agreement. The two top-10 lists typically share only about 2 documents.

**Q5. Why is MiniLM not fine-tuned?**
There are no in-domain relevance labels beyond weak citations. The PU experiment shows that learning on citation proxies does not beat fusion. Fine-tuning is Phase-II work once human labels exist.

**Q6. What is the knowledge store?**
AVeriTeC's per-claim document collections (CC BY-NC 4.0). The demo loads 320 claim stores (120 dev-sample + 200 held-out), about 1.4 GB. Documents are de-duplicated by normalised URL and empty pages are dropped. There is no open-web search. The stores were built partly from gold-derived queries, so recall here is optimistic relative to the open web.

**Q7. What leakage controls exist?**
- The retriever sees only `{normalised URL, text}`: no KS `type`/`query`, no file order (gold is stored first), no raw archive-wrapped URL.
- Candidates are shuffled with a fixed seed.
- The LLM never saw evidence, labels or justifications.
- Evidence markers are display-only (tested).
- The 180 reserved claims and AVeriTeC test labels are never loaded.

### Evaluation
**Q8. What does Recall@10 = 0.251 mean?**
For 25.1% of the 167 claims with reachable evidence, at least one AVeriTeC evidence document is in the top 10. It is claim-level hit rate.

**Q9. Is the LLM prior's improvement significant?**
No. R@10 0.293 vs 0.251, +13/−6 discordant claims, exact McNemar p = 0.167, 95% bootstrap CI [−0.006, 0.096]. It is directional only. No preregistered held-out comparison was significant.

**Q10. Why McNemar?**
It is a paired binary outcome (hit@10 per claim) on the same claims. The exact test is appropriate for the small number of discordant pairs.

**Q11. What is the recall ceiling and why does it matter?**
Any reranker of the hybrid top-100 can at most reach 0.671: 55 of 167 claims have no evidence document in the pool. A source never retrieved cannot be selected by the authority module. Depth 300 raises the ceiling to 0.922.

**Q12. Why is evidence recall not authority recall?**
AVeriTeC evidence URLs include news and fact-check pages chosen to support the verdict. No human label says which document is authoritative. Authority Recall@K needs our new labels.

**Q13. Why did D lose on 52 claims?**
The prior is binary and publisher-level. Every page of a predicted publisher jumps above every other page, including off-topic ones. On held-out data D moved 267 documents from below rank 50 into a top-10, and 263 of those were not evidence documents (exploratory analysis).

### PU baseline
**Q14. What is PU learning here?**
- Positives: train-claim documents whose URL matches an AVeriTeC evidence URL and has text (217 weak positives).
- Everything else is *unlabelled*, not negative (5,370 sampled uniformly).
- The classifier "labelled vs unlabelled" ranks documents. Under the SCAR assumption that ranking is monotone in relevance.

**Q15. Why did it not beat Hybrid RRF?**
- Only 217 weak positives from 131 claims.
- SCAR is very likely violated: fact-checkers cite selectively.
- Gradient boosting memorised the training claims (in-sample R@10 85/131, equal to the pool ceiling).
- With 42 test claims, only large effects are detectable.

**Q16. Was model selection fair?**
Yes. The selection rule (validation R@10, ties → simpler) was fixed in code before the run. Test was scored once and did not influence selection.

**Q17. Is this the authority model?**
No. It is a relevance ranker trained on citation proxies. It is not an authority predictor and is never presented as one.

### Dataset and model
**Q18. Why not use NELA-GT-2020 or Wikidata?**
NELA labels publisher reliability, which is credibility, not claim-specific authority. Wikidata references link statements to cited sources but are not ground truth. AuFIN/AuRED concern social-account authority, a different task.

**Q19. How will you annotate?**
- Unit: claim–document pairs from the hybrid pool.
- Labels: separate relevance (4-way) and authority (5-way).
- At least 2 annotators: all test pairs double-annotated, ≥ 20% of training pairs; adjudication.
- Agreement: Cohen's κ, weighted κ and Krippendorff's α.
- Pilot: 20 claims / 200 pairs, already generated and blank.

**Q20. How do you prevent annotation leakage?**
Annotators never see the verdict, justification, Q/A, fact-check article, evidence indicator, rank or model predictions. Documents are shuffled within each claim. The key file is kept separately.

**Q21. What is the proposed model?**
- Two heads over (claim, document) features: retrieval scores, semantic similarity, document type, primary-source cues, domain/jurisdiction, provenance.
- Score = P(relevant) × (1 + β·P(authoritative)), so an authoritative but irrelevant page cannot outrank a relevant one.
- Model ladder: LR → gradient boosting → MiniLM features → cross-encoder (future).

**Q22. How will you compare it fairly?**
- Same human-annotated claim-disjoint test set and the same candidate pool for all systems: hybrid, generic, heuristic, LLM prior, relevance-only, proposed.
- Primary metric Authority Recall@10; McNemar + bootstrap; Holm correction.

### Integrity
**Q23. What happened to the reserved-180 results?**
They were executed historically (Review 2), but the output files were lost in a deletion incident. They are not used, not reconstructed, and not claimed.

**Q24. What is live in the demo and what is stored?**
- **Live:** BM25, MiniLM, RRF (or the frozen rankings, verified identical to a live re-run), priors B and C, and the reranking.
- **Stored:** the LLM predictions (Sept 2026) and the PU metrics.

**Q25. What is the separate "First-Hand Authority Model" project?**
A separate project with synthetic-only tests. Its results are not part of this project's evidence.
