# Feasibility decision: does claim-specific source authority improve retrieval of authoritative evidence?

*2026-09-29, updated after the follow-up studies in §13 and the frozen held-out test in §14 (2026-09-30). Evidence: `docs/experiment_results.md` (full methods and tables) and `results/`. All experiments below were executed. None of the numbers is estimated.*

## 1. Research question

Given a claim, does explicitly modelling **which source is authoritative for this particular claim** retrieve authoritative (primary) evidence better than (A) relevance-only retrieval and (B) generic, claim-independent source credibility?

**Scope limit.** This was tested **within the AVeriTeC dev knowledge store**: about 771 usable, claim-specific documents per claim, gathered partly by searching with the gold questions. It answers "can authority-aware *ranking* select authoritative evidence from a claim-specific pool?". It says **nothing** about discovering authoritative sources on the open web.

## 2. Dataset and sample

- 120 stratified dev claims: 70 Refuted, 30 Supported, 10 Conflicting, 10 NEE.
- 226 unique gold web URLs (30 of 320 gold answers have no web source).
- 64 gold docs have empty text in the KS, so **162 gold docs are reachable, covering 99 claims**.
- 21.6% of all KS documents are empty; they are excluded from the candidate pool.
- **Pilot primary-source annotation** (one annotator, *not validated*): 99 primary / 98 secondary / 22 derived / 7 unclear gold URLs. Only **48 claims have a reachable pilot-primary document**, and 9 of the 62 reachable primary docs are scraping junk (43 content-valid claims).

These small denominators are the main statistical limitation.

## 3. Experimental setup

| | Condition | What it is |
|---|---|---|
| A | BM25, dense (MiniLM-L6, 128 tok), hybrid RRF | relevance only; query = claim text |
| B | + generic credibility prior | claim-independent: gov/IGO > academic > major news > reference > other > platforms |
| C | + entity prior | claim-specific: domain/handle matches an entity in the claim or speaker |
| C | + claim prior | entity match OR a government domain of the claim's country |
| C | + full prior | max(generic with a foreign-government penalty, claim prior) |
| C* | + Wikidata prior (**post hoc**) | claim-specific: official website/accounts on Wikidata of claim/speaker entities |
| – | Oracle (**leaks by design**) | the domain of the claim's pilot-primary gold, as an upper bound for perfect authority resolution |

- **Scoring:** `minmax(relevance) + λ·prior`.
- **Headline:** λ=0.25 with a top-100 pool, pre-specified.
- **Sensitivity:** λ ∈ {0.1, 0.25, 0.5, 1} and re-scoring all candidates.

## 4. Leakage controls

- **Two real leaks were found and fixed before running.**
  1. Gold docs sit first in every KS file, and stable sorting broke ties in their favour. Fixed with a seeded shuffle.
  2. 32% of gold URLs are `web.archive.org`-wrapped vs 2% of other docs. Fixed: only the un-archived normalised URL is exposed.
- The retriever sees only `{url_norm, text}`. It never sees `ks_type`, `ks_query`, `doc_idx`, the raw URL, labels, QA pairs, the justification or role annotations.
- The authority priors read only the candidate URL, the claim text, `speaker` and `location_ISO_code`. The latter two are present in the unlabelled test release.
- **No prior uses the gold domain of the same claim, except the explicitly labelled oracle.**
- The field-by-field table is in `experiment_results.md` §2.

## 5. Metrics

- R@K: ≥1 gold doc in the top K.
- Primary R@K: ≥1 *pilot-primary* gold doc in the top K.
- MRR for gold and for primary.
- Rank-1 role distribution, from a blind pilot annotation of 156 rank-1 docs.
- Exact McNemar tests and paired bootstrap CIs per claim.

## 6. Results

### 6.1 Main table (reachable denominators: gold n=99, primary n=48; λ=0.25, top-100 pool unless noted)

| Method | R@5 | R@10 | R@20 | Primary R@5 | Primary R@10 | Primary R@20 |
|---|---|---|---|---|---|---|
| BM25 | 0.08 | 0.11 | 0.24 | 0.04 | 0.04 | 0.10 |
| Dense | 0.15 | 0.24 | 0.33 | 0.02 | 0.10 | 0.19 |
| Hybrid | 0.14 | 0.24 | 0.36 | 0.02 | 0.06 | 0.17 |
| Generic credibility (BM25 base) | 0.07 | 0.10 | 0.24 | 0.02 | 0.04 | 0.17 |
| Generic credibility (dense base) | 0.15 | 0.25 | 0.31 | 0.02 | 0.15 | 0.19 |
| Claim-specific authority, full (BM25 base) | 0.07 | 0.12 | 0.24 | 0.02 | 0.08 | 0.17 |
| Claim-specific authority, full (dense base) | 0.15 | 0.25 | 0.31 | 0.02 | 0.15 | 0.19 |
| Claim-specific, entity only (BM25) | 0.08 | 0.11 | 0.25 | 0.04 | 0.04 | 0.12 |
| Claim-specific, Wikidata (BM25, post hoc) | 0.08 | 0.11 | 0.26 | 0.04 | 0.04 | 0.15 |
| Strongest realistic setting: full, λ=1, all candidates | 0.07 | 0.11 | 0.17 | 0.15 | 0.19 | 0.29 |
| **Oracle authority** (leaks), λ=1, all candidates | 0.35 | 0.44 | 0.57 | 0.60 | 0.77 | 0.90 |

Counts:

- 120 claims evaluated.
- 99 usable for gold metrics and 48 for primary metrics; 21 claims have no reachable gold.
- 226 gold URLs; 99 pilot-primary annotations (62 reachable).
- 30 gold answers have no web URL (Metadata/empty); 64 gold URLs have empty KS text.

### 6.2 Statistics

- **No pre-specified authority comparison is significant.** That is 12 comparisons × 6 hit metrics; the smallest uncorrected p is 0.25 and every Holm-adjusted p is 1.0.
- Every primary-recall difference between an authority variant and its base is **0–6 claims out of 48**.
- **Claim-specific vs generic is a tie.** Dense+full and dense+generic give identical Primary R@10 (0.15, 0 discordant claims). On BM25, full beats generic on Primary R@10 by 2 claims (p = 0.5).
- The only robust effect is **dense/hybrid over BM25 on gold R@10**: 0.11 → 0.24 (p = 0.015 and p = 0.004).
- Pushing the prior harder (λ=1, all candidates) is the only setting that nominally helps primary recall: BM25 → +full gives PrimR@20 0.10 → 0.23, p = 0.031 uncorrected, not pre-specified. It **costs gold recall** (R@20 0.24 → 0.17), and on the dense base the claim prior *significantly hurt* R@10 (0.24 → 0.13, 1 win vs 12 losses, p = 0.003).
- With n = 48 and a one-annotator primary label, this experiment could only detect large effects. The realistic methods did not produce one.

### 6.3 Three findings that matter more than the table

1. **Relevance ranking systematically buries primary sources.** Under BM25, pilot-primary gold docs have median rank 357 vs 117 for secondary gold docs. Only 17/48 claims have a primary doc in the BM25 top-100 (23/48 for hybrid). A top-100 reranker cannot fix the other claims.
2. **The problem is authority *resolution*, not the ranking mechanism.** If you know the right publisher (oracle), the same simple reranker lifts Primary R@10 from 0.04 to 0.77 (0.81 on content-valid claims). Every realistic resolver we tried — string entity matching, jurisdiction-government rules, Wikidata official websites — recovers almost none of that headroom. Entity matching fires in only 33/120 claims; Wikidata finds an official domain or handle for 70/120 claims but reaches a document in the top-100 for only 23.
3. **The typical authority heuristics are aimed at the wrong entity.** Rank-1 on 48 claims, blind pilot labels:
   - Relevance methods put a secondary source first 69–83% of the time, a derived one 6–15%, and an on-topic primary 2%.
   - The strongest authority prior raises on-topic primary to only 12%, while **52% of its rank-1 documents are official but off-topic or wrong-jurisdiction pages**.
   - Claim-conditioned entity matching often boosts the **claim-maker or claim subject** instead of the authority on the fact (examples in §7).

### 6.4 Independent verification (second session)

See `experiment_results.md` §8 and `results/verification.json`.

- BM25 re-run from scratch reproduces all 120 rankings exactly.
- Headline metrics were recomputed with independent code and match.
- Length-only and URL-only "artifact rankers" score at random level, so there is no form-based gold leak.
- The hand-written generic lists contained sample gold domains (all 4 listed IGOs are pilot-primary gold domains). Removing them **lowers** generic credibility (e.g., dense+generic PrimR@10 0.15 → 0.08).
- After that, claim-specific ≥ generic in every cell, but by only 0–3 of 48 claims (p ≥ 0.25).
- This makes the "claim-specific vs generic is a tie" statement slightly too harsh: the direction favours claim-specific, but the effect is not distinguishable from noise. **The decision below is unchanged.**

## 7. Error analysis (`results/error_analysis.csv`, `results/log_error_analysis.txt`)

**BM25 finds gold/primary** (only 2 of 48 claims have a primary in the BM25 top 10):

- #484: TI-Defence report at rank 3.
- #387: gov.uk Test & Trace statistics at rank 4.
- #99, #190, #373: a *secondary* gold doc at rank 1 (bothlivesmatter.org.nz, factcheck.org, theprint.in).

In #373 and #99 the primary gold is empty in the KS, so it is unreachable for any method.

**BM25 returns secondary/derived instead:**

- #64: `mediabiasfactcheck.com/left-action` (a derived rating of the *claim spreader*) at rank 1. The NY Attorney General press release is at rank 31.
- #95: an advocacy explainer at rank 1; the NZ legislation page ranks 620, but its scraped text is Archive-Team boilerplate.
- #85: a newsclick fact-check at rank 1. The AMU "facts" page is at rank 422 and was also re-hosted verbatim by `amualumnigermany.com`, which ranks higher (405).
- #321: UCSF *magazine* at rank 1 instead of the Curry International TB Center (UCSF) handbook, the gold primary (rank 507).
- #74: roll-call news at rank 1; the Iowa Farm Bureau's own statement is at 189 (dense finds it at rank 4).

**Authority-aware reranking "improves":**

- #64 (31 → 11), #222 (17 → 10), #298 (15 → 10), #354 (34 → 16), #143 (19 → 12).
- Every gain is a modest rank move that comes from the **generic .gov/IGO tier** (e.g., ag.ny.gov, news.un.org, gov.uk, nigerianstat.gov.ng, oecd-ilibrary), not from resolving the claim-specific authority. No improved primary reaches the top 5.

**Authority-aware reranking fails or hurts:**

- **#354, Edo unemployment (label: Not Enough Evidence).** The entity + gov prior puts `edostate.gov.ng` at rank 1. That is the governor's own government, i.e. the interested claim-maker, not the national statistics office (gold primary: nigerianstat.gov.ng).
- **#399.** Entity matching boosts `dailytrust.com`, the outlet *whose report is being disputed*.
- **#466.** An off-topic `ojjdp.ojp.gov` PDF displaces the gold explainer.
- **#18.** Gold (secondary news) drops from rank 6 to 10 as higher-tier domains are pushed ahead.
- **#387.** The correct week's gov.uk statistics fall from rank 4 to 6: other gov.uk pages (an older week's PDF was already rank 1) get the same boost, so the prior cannot tell the right official document from the wrong one.

**Verdict of the error analysis.** The method is mostly exploiting generic domain heuristics. Where it is genuinely claim-conditioned, it tends to find the *speaker* or *subject* of the claim rather than the *authority on the fact*: person ≠ office (Buhari → thisisbuhari.com, not statehouse.gov.ng); subject ≠ adjudicator (Trump children → their own sites, not NY AG).

## 8. Provenance findings (apparent duplication/derivation heuristics, not verified provenance)

- **Top-K redundancy is real but modest in the AVeriTeC KS.**
  - 33–43% of claims have at least one near-copy pair in the top 10 (containment ≥ 0.5 / ≥ 0.3).
  - But only 5–6.5% of top-10 documents collapse into another document's group.
  - 12.5–25% of claims have a group of ≥3 copies in the top 20.
- **Copies can outrank their own primary source.**
  - 8 of 62 reachable primary docs have ≥1 apparent copy at containment ≥ 0.5 elsewhere in the KS; 17 at ≥ 0.3.
  - At ≥ 0.3, 31 copies outrank their primary under BM25 (15 primaries affected) and 15 under dense (10 primaries).
- **Concrete cases where naive majority voting would double-count one underlying source:**
  - **#374, Oregon wildfires, "police: activists didn't cause fires" (Supported).** The FBI Portland statement (`fbi.gov`, BM25 rank 122) is reproduced or quoted by OPB, The Intercept (rank 8), FlashAlert (re-post), a blog and ABC News. All five name the FBI. Six "agreeing" documents, one origin.
  - **#354, Edo unemployment 25% → 19% (Not Enough Evidence).** The state government's own release (`edostate.gov.ng`) is copied verbatim by `thenationonlineng.net` (containment 1.0) and reposted on Nairaland. Three "supporting" documents repeat one interested party's figure; the independent authority (national statistics office) does not confirm it. Majority voting would say *Supported*; the gold label is NEE.
  - **#210/#219/#222, Buhari Independence Day speech.** `channelstv.com` and `naijanews.com` carry the full text of the `statehouse.gov.ng` address (containment 0.89–1.0). Several "sources" repeat the speaker's own claims.
  - **#451, "Pedophilia legal in California" (Refuted).** The LegiScan mirror of the bill text ranks 10 under dense; the official `leginfo.legislature.ca.gov` text ranks 51.
  - **#288, BLM "nuclear family" (Conflicting).** The BLM "what we believe" page is quoted at ≥ 0.5 containment by five other sites (education, advocacy, blog pages) that rank near or above it.
- **Attribution phrases are common** ("according to…", "said in a statement": 47% of top-10 docs). So recovering *which* primary a secondary document relies on is plausible from text; 29 of 59 copies at ≥ 0.3 name the primary's publisher.

## 9. Temporal feasibility

- AVeriTeC's only date field is `claim_date` (120/120 claims).
- There is **no evidence publication, update or event date**.
- Recoverable signals are weak:
  - URL-path date: 39/231 gold URLs.
  - Explicit "published" date in text: 3/226 gold docs; "updated": 1/226.
  - Any date signal at all: 29% of gold docs.
  - Wayback capture timestamps: 72/231. These are "existed-by" bounds, not publication dates.
  - Only 14/120 claims mention a year.
- **The data do not support a meaningful temporal-alignment experiment.** Treat temporal reasoning as a later extension that needs its own date extraction (e.g., htmldate on re-fetched pages) and annotation.

## 10. Limitations

- The primary-source labels are a **one-annotator pilot** (the gold URL labels and the blind rank-1 labels come from the same annotator), with no inter-annotator agreement yet.
- n = 48 claims for primary metrics (43 content-valid). Power is only enough for large effects.
- "Gold" is a narrow target. Many non-gold KS documents are probably equally valid evidence, so absolute R@K understates usefulness. The *relative* comparisons are what matter here.
- The dense model is small and truncated to 128 tokens (CPU budget). Stronger retrievers or rerankers were not tested.
- The priors are simple hand-written heuristics. A learned or LLM-based authority resolver was **not** tested. The Wikidata variant was added post hoc.
- The generic prior lists partly overlap sample gold domains, which slightly favours condition B.
- Everything is inside the AVeriTeC KS; nothing here tests open-web discovery.

## 11. Go/no-go decision

**Outcome C for the methods tested, with a qualified pointer. Do not build the end-to-end authority-aware verification prototype yet.**

- Claim-specific authority, as implemented (entity/domain matching, jurisdiction rules, Wikidata official sites), **did not improve primary-source retrieval over generic credibility, nor significantly over relevance-only retrieval**. Where priors helped at all, the gain came from the generic .gov/IGO tier and cost gold recall at higher weights.
- The experiment does **not** show that the idea is worthless. The oracle shows very large headroom (Primary R@10 0.04 → 0.77) *if* the right publisher is known. It also shows that the relevance stage alone buries primaries.
- The bottleneck is therefore narrowed to one sub-problem: **resolving which institution is authoritative for the specific fact in the claim**. This is distinct from the speaker, the subject and any official-looking domain. None of the cheap resolvers solves it.

Provenance/duplicate-source reasoning looks **moderately promising, and more promising than ranking by authority**:

- There are real cases where copies outrank their primary.
- There are cases where majority voting would count one interested source several times (#354 would flip NEE → Supported).
- Attribution phrases are frequent.
- But in the AVeriTeC KS only about 5–6% of top-10 documents are near-duplicates. The effect is a minority phenomenon here and needs a dataset with more conflict and redundancy to show its value.

## 12. Recommended next research step (small, cheap, decisive)

1. **Validate the labels first.** Have a second annotator label the 226 gold URLs and the 156 blind rank-1 items with the same scheme (P/A/O/S/D/U), and report Cohen's κ. Without this, no primary-source claim is publishable.
2. **Directly measure the bottleneck: an authority-resolution study (no retrieval).**
   - Input: claim text, speaker and country.
   - Task: predict the top-3 publishers or domains that would be authoritative for the fact, using an LLM plus Wikidata "office/agency" lookups rather than person lookups.
   - Score against the pilot-primary domains on the 73 claims with a primary.
   - If the hit rate is high (e.g., ≥ 50% top-3), plug the predictions into the existing reranker. The oracle results say this would translate into large Primary R@K gains. Then run **source-targeted query generation** ("⟨authority⟩ ⟨fact⟩") so primaries enter the candidate pool.
   - If the hit rate is low, drop authority-aware retrieval as the main contribution.
3. **In parallel, a provenance-aware aggregation probe.** Collapse near-duplicate and attributed documents into origin clusters, flag claim-maker/interested-party sources (label A in our scheme), and test whether independence-weighted voting changes verdicts. Test on AVeriTeC's Conflicting and NEE claims and, as planned, on CONFACT. #354 and #374 are the motivating cases.
4. Keep temporal reasoning as an optional extension.

Only after step 2 or 3 shows a clear effect should a minimal end-to-end prototype be built, followed by a small live-web experiment.

## 13. Update after running §12 steps 2 and 3 (2026-09-29)

Both follow-ups were executed. Details are in `experiment_results.md` §9–10 and `authority_resolution_study.md`.

**Step 2, authority resolution. The go criterion was met, with caveats.**

- An LLM given only the claim, speaker, date and country names the pilot-primary publisher at top-3 = 0.77 (top-1 0.63). The pre-set threshold was ≥ 0.50.
- The cheap resolvers used earlier (Wikidata official sites) reach 0.11.
- Plugged into the unchanged reranker at λ=1, the predictions raise **human AVeriTeC gold** recall over all 99 reachable claims. Hybrid R@10 goes 0.24 → 0.34; BM25 R@10 goes 0.11 → 0.21 (p = .006).
- Generic credibility at the same weight *lowers* gold recall. This is the first result in the project where claim-specific authority clearly separates from generic credibility.
- It is **exploratory**:
  - λ=1 was not the pre-specified weight; at λ=.25 the gain is not significant.
  - There is no multiplicity correction.
  - LLM memorisation of 2020 fact-checks is uncontrolled.
  - The pilot-primary numbers are still annotated by the same model family that predicts them.

**Step 3, provenance-aware aggregation: no measurable verdict gain on AVeriTeC.**

- Attribution-based grouping collapses 22% of voting units, but verdict accuracy is unchanged (0.633 → 0.633, 2 gains and 2 losses).
- The interested-party discount hurts (0.617): it discards self-denials by the authority itself (#412 Taiwan MND).
- It fixes the motivating case #354 and moves 2 Conflicting claims in the right direction. That is too little evidence to make provenance aggregation the main contribution on this dataset.

**Revised decision.**

1. The core contribution candidate is now **claim-specific authority *resolution* (which institution is authoritative for this fact), used to target retrieval**. This is no longer domain heuristics. It is the only component with a measured, generic-beating effect on human gold.
2. Before building anything, confirm it:
   - (a) Collect the pending human second annotation (`data/annotations/second_annotator_template.csv`, 226 items) and report κ.
   - (b) Pre-register λ=1 and re-test on a fresh, disjoint AVeriTeC sample, ideally with claims after the model's training cutoff or with a non-Claude resolver, to address memorisation.
   - (c) Add source-targeted query generation so that primaries outside the top-100 enter the pool (31/48 are currently unreachable by reranking).
3. Provenance aggregation stays a secondary line. The interested-party signal needs a stance-aware definition (a self-interested *assertion* vs. an admission against interest) and a dataset with more conflicting and redundant evidence than AVeriTeC.
4. Temporal reasoning stays deferred (§9).
5. A live-web experiment comes only after 2(a)–(b) hold. Everything above is still within the AVeriTeC evidence corpus.

## 14. Update after the frozen held-out test (2026-09-30)

Full tables are in `experiment_results.md` §11. The test used 200 held-out claims, disjoint from dev; 167 have reachable gold. The configuration was frozen on dev (hashes match `source_targeted_preregistration.md`), and nothing was re-tuned. **Held-out primary recall is N/A**: the held-out primary annotation is unfilled.

**Held-out gold R@10 / R@20 / pool coverage.**

| Method | R@10 | R@20 |
|---|---|---|
| Hybrid | 0.251 | 0.383 |
| + generic | 0.263 | 0.383 |
| + heuristic | 0.275 | 0.407 |
| **+ LLM authority** | **0.293** | **0.437** |
| Targeted only | 0.180 | 0.180 |
| Hybrid + targeted | 0.287 | 0.407 |
| Hybrid + targeted + LLM authority | 0.246 | 0.401 |
| *Oracle (leaks)* | *0.868* | *0.880* |

Pool coverage: 0.671 for hybrid (and the re-rankers), 0.701 with targeting, 0.677 for the size-matched control.

**What held and what did not.**

1. **LLM authority re-ranking (D): direction replicates, significance does not.**
   - Dev: +15/−5 (p=0.041), Δ +0.10.
   - Held-out: +13/−6 (p=0.167), Δ +0.042, CI [−0.006, 0.096].
   - R@20: +12/−3 (p=0.035 uncorrected; Holm 0.18).
   - The effect is about half the dev size, and not established.
2. **Source-targeted retrieval (G, the proposed pipeline) does not generalise.**
   - Dev R@10 was 0.354 (+0.11 over hybrid). Held-out it is 0.246: 0.00 over hybrid (+21/−22) and −0.05 vs D (+10/−18, p=0.19).
   - The coverage gain over a size-matched control is +5/−1 (p=0.22, Holm 0.55).
   - The only consistent positive signal is pool expansion: F raises R@50/R@100 and coverage on both splits. It is small and not significant.
3. **Authority resolution is weaker than the pilot suggested.**
   - Against all human-gold publishers, top-3 is 0.479 on dev and **0.391 on held-out**.
   - The earlier 0.77 was against one-annotator pilot-primary labels and is not comparable.
   - Wrong authority (102/167 held-out claims) is the dominant failure. Targeting turns it into harm: on those claims G hits gold@10 for 10 of them vs 30 for plain hybrid.
4. **Memorisation is not the explanation.**
   - Paraphrase and metadata removal leave accuracy unchanged (p ≥ 0.73), and recognised claims are not predicted better.
   - Masking names drops top-3 to 0.307 (p=0.0009). This shows the resolver relies on names, which the task legitimately needs. It does not prove memorisation.
5. **The oracle headroom is still large** (R@10 0.868 with gold-derived publishers). The mechanism is fine *if* the authority is right. But the oracle uses all gold publishers, including news and fact-checkers, so it is an optimistic diagnostic, not an achievable target.

**Revised decision.**

- **Do not adopt the frozen source-targeted pipeline** (authority-first order, λ=1, M=10) as the contribution. It failed its pre-registered held-out tests and is worse than the simpler D.
- Claim-specific LLM authority re-ranking remains a **weak, unconfirmed** positive (directional on two splits, significant on neither held-out endpoint after correction).
- The go/no-go for the end-to-end system stays **no-go**. No frontend, extension, live-web, temporal or multimodal work until an authority-aware method passes a held-out test.
- The one pre-registered question that is still open is **primary-source** recall on held-out. The method targets primaries, while gold R@K counts secondary news pages as hits. That question can be answered **without re-running anything**: annotate, then score the existing frozen rankings in `results/source_targeted/rankings_heldout.jsonl.gz`.
