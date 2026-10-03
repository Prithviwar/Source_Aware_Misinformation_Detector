# Source-Aware Misinformation Verification — Literature Review, Gap Analysis & Research Plan

*Status: Phase 0 (decide WHAT to build). Compiled 2026-09-29. No code, no results. Every number below comes from the cited paper or dataset page.*

> **How much to trust this document.** The key papers (CONFACT, RAVE, the AVeriTeC shared-task report, and Warren et al. CHI'25) were read in **full text**. VNL and CrediRAG were read from their arXiv HTML. **HeterMV** could only be read at abstract level: I couldn't find an open full text, and the publisher page returned HTTP 403. Anything marked **(verify)** is from memory or a secondary summary and should be checked before we rely on it.
> One warning from doing this review: an automated summary of the CONFACT PDF produced **fabricated statistics** (wrong dataset size, wrong models). Always check numbers against the PDF itself.

---

## 0. Executive summary (read this first)

1. **"Source-aware" means at least six different things in the literature**, and none of them is exactly our idea. The two most common meanings are (a) a **claim-independent credibility prior per publisher/domain** (RAVE, CrediRAG, CONFACT, CAG, AuthorityBench) and (b) **"source of the distortion"** (text vs. image vs. mismatch) in multimodal work (MMFakeBench, Verification-Notebook Learning). The second has nothing to do with publishers.
2. **Integrating generic source credibility into RAG fact-checking is already done, and the results are mixed.** CONFACT (IJCAI'25) shows that credibility filtering and credibility-weighted ranking can *hurt*. Putting source backgrounds into the generation prompt helps a little. We should not build "RAG + credibility score" and call it new.
3. **The gap we can defend.** In the papers reviewed, no system asks *"which source is authoritative for THIS claim?"*, for example the statistical agency with jurisdiction, the court, the speaker's own transcript, or the original study. No system labels evidence by **role relative to the claim** (primary / secondary report / derived copy / independent corroboration / unreliable), and none checks whether 10 articles are really 1 wire story repeated 10 times (**source independence**). Professional fact-checkers say plainly that this is what automated systems miss ([Warren et al., CHI 2025](https://arxiv.org/abs/2502.09083)). Classical truth-discovery work modelled source dependence (Dong et al., VLDB 2009, *Integrating conflicting data: the role of source dependence*), but that idea hasn't reached LLM fact-checking pipelines.
4. **Dataset reality.** Only **AVeriTeC** (text) and **AVerImaTeC** (image-text) have what we need: speaker and reporting-source metadata, claim dates, and **per-evidence source URLs chosen by annotators following professional fact-checks**. AVeriTeC also has a per-claim offline **knowledge store (~955 docs/claim, restricted to before the claim date, gold evidence documents guaranteed to be included)**. That combination lets us measure *whether a system reaches the right sources*, which other datasets don't allow. CONFACT is the right dataset for testing the conflict-resolution module alone.
5. **Temporal reasoning.** We need **temporal hygiene** now (no evidence published after the claim date; record dates in the schema). We do **not** need temporal *reasoning* yet. Source + time together is under-studied, which makes it a good later extension but a bad first build.
6. **First build.** A text-only, offline, reproducible pipeline on AVeriTeC with ≤10B open models (the same budget as the [AVeriTeC 2025 shared task](https://aclanthology.org/2025.fever-1.15/): 1 GPU, ~23 GB, <1 min/claim). Compare B0/B1/B2 against a **claim-conditioned source-resolution + role-aware aggregation** system, with **oracle** and **query-count-matched** controls.
7. **Step one is a data audit, not a model.** Measure how often the fact-checkers' gold evidence comes from *primary* sources, and how badly plain retrieval ranks those sources. If plain retrieval already finds them, the hypothesis is weak and we should pivot early (Section 2.4).

---

## PART 1 — Literature review

### 1.1 The five papers you named

#### (1) HeterMV — *Multi-view reasoning over source-aware heterogeneous evidence graph for multi-source fact verification* (2026)
*Access: abstract-level only. I couldn't find a preprint, and the likely Elsevier venue returned 403. Venue/DOI **(verify)**.*

| Aspect | Finding |
|---|---|
| Problem | Multi-source fact verification: claim veracity from heterogeneous *textual* evidence |
| Input | Claim + evidence split into **core evidence, context, reference documents** |
| Datasets / size | **Check-COVID (1,504 claims)**, **FEVEROUS-S (29,890 claims; a subset of FEVEROUS)** |
| Modality | Text |
| Retrieval | Gold-evidence setting **and** BM25 retrieval setting |
| Source-awareness mechanism | "Source-Aware Heterogeneous Evidence Graph": node **types** = evidence *channel* (core / context / reference). Four views: multi-source fusion, core-corroboration, context-infusion, knowledge-citation |
| Credibility representation | None apparent. "Source" means the evidence channel/type, not the publisher's trustworthiness |
| Source identity retained? | As a node type, yes. As a publisher identity, not evident |
| Provenance modelled? | Partially ("knowledge-citation view"), details unknown |
| Multiple sources? | Yes (heterogeneous channels) 
| Conflict handling | Cross-view consistency **contrastive learning**, with the core-corroboration view as anchor, to suppress "noisy" evidence |
| Architecture | Graph + directed multi-relational propagation + view-conditioned prompt tuning (a PLM backbone, not specified in the abstract) |
| Trained? | Yes (prompt tuning + contrastive objective) |
| Metrics / results | Micro-F1. Check-COVID **+3.06 (gold) / +3.27 (BM25)**; FEVEROUS-S **+1.72 / +1.41** over SOTA baselines |
| Code / data | Not found. Datasets public |
| Reproducible by us? | Not without code. The idea of typing evidence nodes can be reused |
| Gap | "Source" is an evidence *channel*, not an *authority relative to the claim*. Neither dataset has real publisher diversity: Check-COVID evidence is scientific papers and FEVEROUS is Wikipedia |

#### (2) RAVE — *Retrieval and Scoring Aware Verifiable Claim Detection* ([arXiv 2509.15793](https://arxiv.org/abs/2509.15793), ICASSP 2026) — full text read

| Aspect | Finding |
|---|---|
| Problem | **Verifiable-claim detection** (binary VERIFIABLE / NON-VERIFIABLE), *not* veracity |
| Input | Tweet or debate sentence |
| Datasets | **CT22-test** (CheckThat! 2022 COVID tweets), **PoliClaim-test** (debate transcripts). Sizes not given in the paper **(verify)** |
| Modality | Text |
| Retrieval | LLM zero-shot entity extraction (PERSON, ORG, LOCATION, EVENT, CLAIM_OBJECT) → **Google API** query per entity → snippets + metadata (domain, title, URL) |
| Source-awareness | Per-snippet **credibility from a hand-made domain-type table**: 1.00 Wikipedia/Reuters/BBC/Nature, 0.95 .gov, 0.85 .edu, 0.75 academic institutions, 0.65 established news, 0.50 .org, 0.40 .com (Table 1) |
| Credibility repr. | Scalar in [0.4, 1.0], **claim-independent** |
| Identity retained? | Yes. Domain, title and scores go into the prompt |
| Provenance | No |
| Multiple sources | Top-K=3 snippets |
| Conflict handling | None explicit |
| Scoring | `score = α·cos(claim, snippet) + (1−α)·cred`, α=0.6 tuned on CT22-dev |
| Models | **GPT-4o-08-06** (temp 0) for everything |
| Trained? | No |
| Metrics / results | Acc/P/R/F1. CT22 F1 **0.857** (text-only 0.842, Search-K 0.857). PoliClaim F1 0.695 vs 0.664. Gains are **small** (≈+1.5 F1 points), and "Search-K" ties on CT22 F1 |
| Code | "Will be released upon acceptance". Not confirmed |
| Reproducible? | Yes, trivially (heuristic table + any LLM + search API) |
| Gap | Credibility is a fixed domain table, the same for every claim. Wikipedia scores above .gov for *every* claim. That shows the gap directly: authority should depend on the claim |

#### (3) CrediRAG — *Network-Augmented Credibility-Based Retrieval for Misinformation Detection in Reddit* ([arXiv 2410.12061](https://arxiv.org/abs/2410.12061), WWW'25)

| Aspect | Finding |
|---|---|
| Problem | Binary fake/real classification of Reddit **posts** |
| Input | Post title + comment network |
| Datasets | Curated political-subreddit data 2016–18, labelled by matching posts to ISOT fake-news articles (±2 days, SBERT cos ≥ 0.7). Train 8,661 / test 3,479 nodes. Also r/Fakeddit (100k train / 8k test). *Abstract says ">200,000 posts" and the HTML summary says 60k+: inconsistent, **(verify)*** |
| Modality | Text + social graph |
| Retrieval | all-MiniLM-L6-v2 dense retrieval of top-20 news articles from **AskNews** (commercial news API) |
| Source-awareness | Initial post score = **mean Ad Fontes Media reliability** of the retrieved articles' outlets |
| Credibility repr. | Outlet-level scalar (Ad Fontes 0–64 → 0–1), claim-independent |
| Identity retained? | Only through the averaged score |
| Provenance | No |
| Conflict handling | None. Averaging |
| Architecture | RAG prior → post-post graph (shared commenters, stance-weighted edges) → 2-layer **GAT** |
| Trained? | Yes (GAT). Small-scale |
| Results | ISOT-Reddit Acc 86.67 / F1 0.811. Fakeddit Acc 94.37 / F1 0.920 (authors warn of label leakage from subreddit-level labels) |
| Code / data | Dataset release promised. Code not confirmed |
| Reproducible? | Partly. AskNews and Ad Fontes are commercial |
| Gap | Here "source credibility" is the credibility of *whoever wrote similar news*, used as a proxy label. It says nothing about the truth of the claim itself |

#### (4) *Resolving Conflicting Evidence in Automated Fact-Checking: A Study on Retrieval-Augmented LLMs* + **CONFACT** ([arXiv 2505.17762](https://arxiv.org/abs/2505.17762), IJCAI 2025; [data/code](https://github.com/zoeyyes/CONFACT)) — full text read

| Aspect | Finding |
|---|---|
| Problem | RAG fact-checking when retrieved docs **disagree** and come from sources of varying credibility |
| Input | Claim converted to a yes/no question (GPT-4) + retrieved documents |
| Dataset construction | 3,180 claims (566 AVeriTeC + 2,614 FactCheckQA; only Supported/Refuted or true/false kept) → Google top-10 per question (Sep 12–19, 2024), **archived on Wayback** → GPT-4 stance ×3 prompts, majority vote → **611 claims (17.8%) have conflicting stances** |
| Splits / size | **ModC** (GPT-4-found conflicts): 611 claims (125 Yes / 486 No), 2,469 sources. **HumC** (human-validated): 287 claims (51 Yes / 236 No), 1,418 sources. Evaluation-only, **heavily imbalanced** |
| Source annotation | Humans rated each source's **credibility 1–5** and **type**: Mainstream News / Government / Non-profit / Academic / Social Media / Other. MBFC ratings used as the "ground-truth media background" |
| Modality | Text |
| Retrieval | Fixed documents supplied (reproducible). Chunked into paragraphs, top-K=5 ranked |
| Source-awareness mechanisms | **SF** (filter low-credibility docs), **CW soft/hard** (`s = s_rel + λ·s_cred`), **SBA** (source background concatenated to each paragraph; direct / CoT / explicit-discern / ensemble). Backgrounds from MBFC (GT-MB) or MBFC + LLM-generated backgrounds from Google search (Hybrid-MB) |
| Identity retained? | Yes in SBA (paragraph paired with its source background) |
| Provenance | No |
| Conflict handling | This *is* the topic. Baselines include majority vote and "Discern-and-Answer" |
| Models | **LLaMA-3.1-8B, Qwen-2-8B (as written), Mistral-v0.3-7B** (vLLM, greedy, 2×A100-80GB). GPT-4o in the appendix, no clear gain |
| Trained? | No (a small credibility-score predictor was trained on Baly et al. 2018) |
| Metrics | Accuracy + Macro-F1 |
| Key results | Majority vote gets high accuracy but F1 ≈ 46–49 (it always predicts the majority "No"). SBA at generation time is best (e.g., Qwen ModC SBA_dir 79.87 / 73.06 vs DirA 77.58 / 70.82). **CW-soft/hard and SF often *reduce* performance.** Hybrid (auto-generated) backgrounds are **not better** than MBFC-only. **Human accuracy ~50%** on 20 claims in every condition |
| Code / data | Public GitHub. **No license file** seen. MBFC fields may not all be in the release **(verify)** |
| Reproducible? | **Yes.** 8B models, fixed docs. The best target for our conflict module |
| Gap | Credibility is still **publisher-level and claim-independent**. The source "type" is institution type, not **role relative to the claim**. No independence/dependence modelling. Binary yes/no only. Small and imbalanced |

#### (5) *Verification-Notebook Learning (VNL) for Source-Aware Multimodal Misinformation Detection* ([arXiv 2607.23581](https://arxiv.org/abs/2607.23581), 2026)

| Aspect | Finding |
|---|---|
| Problem | **4-way "source attribution"**: original / textual-veracity distortion / visual-veracity distortion / cross-modal mismatch. **"Source" = which modality the falsehood comes from**, not a publisher |
| Input | (caption, image, optional Wikipedia evidence) |
| Dataset | **MMFakeBench**: dev 700 / held-out val 300 / test 2,000 sampled (600/600/200/600) |
| Modality | Image + text |
| Retrieval | Wikipedia evidence via the MMD-Agent pipeline |
| Mechanism | Non-parametric: a Verifier–Editor loop distils a compact "notebook" of rules, cues and pitfalls (~22 notes, 547 tokens) from labelled dev data. The notebook is prepended at inference |
| Models | **GPT-4o** (frozen). bge-base-en-v1.5 for dedup |
| Trained? | No gradient training. Needs a labelled dev set |
| Results | Macro-F1 **73.2** vs CR+Wiki 67.8, MMD-Agent 57.3, standard prompt 41.6 |
| Code | Not mentioned |
| Reproducible? | Conceptually yes with an open VLM. Cost is many GPT-4o calls |
| Gap for us | **Different meaning of "source-aware."** The notebook/"procedural memory" idea is reusable later (for example, learning source-selection heuristics) |

### 1.2 Other highly relevant work found

| Paper | What it does | Why it matters to us |
|---|---|---|
| **Warren et al., *Show Me the Work*** ([CHI 2025, arXiv 2502.09083](https://arxiv.org/abs/2502.09083)) | Interviews with fact-checkers | Direct evidence for our gap: *"The crucial aspect… was retrieval of **primary sources**… court documents, official statements, a person who appears to be the source of the claim…"* and *"automated fact-checking techniques tend to rely on **secondary sources**… automated tools use stance detection… considering each document on its own terms"* instead of comparing sources with each other. **This is our motivation paragraph.** |
| **Schlichtkrull, *Generating Media Background Checks*** ([EMNLP-F 2024](https://aclanthology.org/2024.findings-emnlp.283/), [code](https://github.com/MichSchli/MediaBackgroundChecks)) | 6,709 MBFC-derived background checks. LLM generates source profiles | The source-critical-reasoning line of work CONFACT builds on. Still generic per outlet |
| **MediaRef** ([arXiv 2607.02383](https://arxiv.org/abs/2607.02383), 2026) | Public knowledge store: 21,921 docs about 200 outlets, for reproducible background checks | Reusable resource. Explicitly **not claim-specific** |
| **AuthorityBench** ([arXiv 2603.25092](https://arxiv.org/abs/2603.25092), 2026) | Can LLMs judge authority? DomainAuth 10K domains (PageRank), EntityAuth 22K entities (popularity), RAGAuth 120 queries | Closest to "authority," but authority = PageRank/popularity. **Must cite and differentiate.** Their finding that adding page text *hurts* authority judgments is useful |
| **Contradiction to Consensus** ([arXiv 2602.18693](https://arxiv.org/abs/2602.18693), 2026) | Multi-source retrieval (Wikipedia, PubMed, Google), keeps source labels, measures per-source disagreement via log-probs | Keeps source identity, but **treats all sources equally**. No authority, no temporal handling (stated limitation) |
| **WKGFC — Multi-Sourced, Multi-Agent Evidence Retrieval** ([arXiv 2603.00267](https://arxiv.org/abs/2603.00267), 2026) | Agent chooses KG (Wikidata/DBpedia) vs web. KG is the high-precision anchor | Hard-coded source *type* priority (KG > web), not claim-conditioned authority. GPT-4o. No code |
| **CAG — Credibility-aware Generation** ([EMNLP 2024](https://aclanthology.org/2024.emnlp-main.1109/), [code](https://github.com/panruotong/CAG)) / **CrAM** ([AAAI 2025](https://arxiv.org/abs/2406.11497)) | Fine-tune (CAG) or edit attention (CrAM) so LLMs weight docs by a given credibility score | Solves "use a credibility score." Assumes the score is given |
| **RAMDocs / MADAM-RAG** ([COLM 2025](https://arxiv.org/abs/2504.13079), [code](https://github.com/HanNight/RAMDocs)) | Multi-agent debate, one agent per document, aggregator handles ambiguity, misinformation and noise | Strong conflict baseline. Uses Llama-3.3-70B (heavy) |
| **DRAGged into Conflicts / CONFLICTS** ([arXiv 2506.08500](https://arxiv.org/abs/2506.08500), [data](https://github.com/google-research-datasets/rag_conflicts)) | Taxonomy of RAG conflicts (incl. **freshness**/outdated info, conflicting opinions), 458 expert-annotated instances | Useful conflict-type vocabulary. Asking LLMs to reason about the conflict type helps |
| **Burdisso et al., *Birds of a Feather*** ([NAACL 2024](https://aclanthology.org/2024.naacl-long.383/), [code/data](https://github.com/idiap/News-Media-Reliability)) | Reliability degree from the hyperlink graph (~17K outlets). 5,332 labelled domains (MBFC + Wikipedia perennial + NewsGuard + fake-news lists) | Open credibility prior |
| **Lin et al., domain quality ratings** ([PNAS Nexus 2023](https://academic.oup.com/pnasnexus/article/2/9/pgad286/7258994), [data](https://github.com/hauselin/domain-quality-ratings)) | PCA aggregate of 6 expert rating sets, ~11.5K domains | **Best open drop-in generic credibility prior** (license not stated in the README, **verify**) |
| **Truth discovery with source dependence**: Dong, Berti-Equille, Srivastava, VLDB 2009 (*Integrating conflicting data: the role of source dependence*); [Knowledge-Based Trust, VLDB 2015](https://arxiv.org/abs/1502.03519); TruthFinder (Yin et al., KDD 2007) | Jointly estimate source trust and fact truth. Detect **copying between sources** | The **independence** idea we need. Largely missing from LLM fact-checking |
| **DEFAME** ([ICML 2025](https://arxiv.org/abs/2412.10510), [code](https://github.com/multimodal-ai-lab/DEFAME)) | Zero-shot multimodal fact-checking agent (web + image search, reverse image search). SOTA on VERITE, AVeriTeC, MOCHEG. New ClaimReview2024+ | Strongest open-code multimodal baseline. No source-authority modelling |
| **5Pils** ([EMNLP 2024](https://aclanthology.org/2024.emnlp-main.448/), [code](https://github.com/UKPLab/5pils)) | 1,676 fact-checked images with QA on **Provenance, Source, Date, Location, Motivation** | The only dataset that operationalises *image* provenance/source. Useful for the multimodal extension |
| **AVeriTeC shared tasks** ([2024](https://arxiv.org/abs/2410.23850), [2025](https://aclanthology.org/2025.fever-1.15/)); **HerO / HerO 2** ([arXiv 2507.11004](https://arxiv.org/abs/2507.11004)); **CTU AIC** ([arXiv 2508.04390](https://arxiv.org/abs/2508.04390)) | Open ≤10B systems, 1 GPU (~23 GB), <1 min/claim | **Our compute budget and our baselines.** 2025 winner AVeriTeC score 33.17% on the new test set |
| **Time-aware evidence ranking** ([Allein et al. 2021](https://arxiv.org/abs/2009.06402)); **Implicit temporal reasoning** ([Allein et al., EACL-F 2023](https://aclanthology.org/2023.findings-eacl.13/)); **ChronoFact** ([IJCAI 2025](https://arxiv.org/abs/2410.14964)) | Temporal verification on MultiFC / timeline claims | The temporal state of the art (Part 8) |
| **Contamination in dynamic MAFC benchmarks** ([arXiv 2607.23514](https://arxiv.org/abs/2607.23514), 2026) | 17–29% of "post-cutoff" claims are still contaminated. Inflates Macro-F1 by up to 11.3 points | Always report a no-retrieval (B0) baseline |
| **X-POSE / TRENT evidence triangulation** ([arXiv 2606.31367](https://arxiv.org/abs/2606.31367), 2026) | Multimodal "triangulation" across evidence streams | "Triangulation" here is entailment across streams, **not** source independence |
| **Trusted Source Alignment / FactCheckQA** ([arXiv 2311.06697](https://arxiv.org/abs/2311.06697)) | Do LLMs side with trusted publishers? | Claim source for CONFACT |

### 1.3 Comparison table

Legend: ✔ yes · ✖ no · ~ partial/implicit · ? unknown

| Work | Task | Modality | Data (size) | "Source" means | Cred. repr. | Claim-conditioned authority | Identity kept end-to-end | Provenance / role | Independence | Conflict handling | Temporal | Models | Trained | Code | Reproducible by us |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HeterMV '26 | Veracity | T | Check-COVID 1.5K, FEVEROUS-S 29.9K | evidence channel | ✖ | ✖ | ~ node type | ~ citation view | ✖ | contrastive noise suppression | ✖ | PLM (?) | ✔ | ? | ✖ (no code) |
| RAVE '25 | Verifiable-claim detection | T | CT22, PoliClaim | publisher domain | fixed table | ✖ | ✔ (prompt) | ✖ | ✖ | ✖ | ✖ | GPT-4o | ✖ | promised | ✔ easy |
| CrediRAG '24 | Fake/real post | T + graph | Reddit ~12K nodes; Fakeddit | outlet of similar news | Ad Fontes scalar | ✖ | ✖ (averaged) | ✖ | ✖ | ✖ | label matching only | MiniLM + GAT | ✔ | ? | ~ (paid APIs) |
| CONFACT '25 | Veracity (yes/no) under conflict | T | 611 / 287 claims | publisher | MBFC + LLM background | ✖ | ✔ (SBA) | ✖ (institution type only) | ✖ | SF / CW / SBA / MajV / debate-like ens. | ✖ | Llama-3.1-8B, Qwen2, Mistral-7B | ✖ | ✔ | ✔✔ |
| VNL '26 | 4-way distortion attribution | I+T | MMFakeBench 3K used | distortion modality | ✖ | ✖ | n/a | ✖ | ✖ | ✖ | ✖ | GPT-4o | ✖ (notebook) | ? | ~ |
| Media Background Checks '24 / MediaRef '26 | Source profiling | T | 6,709 MBCs / 21.9K docs | publisher | text profile | ✖ | n/a | ✖ | ✖ | ✖ | ✖ | LLMs | ✖ | ✔ | ✔ |
| AuthorityBench '26 | Authority perception | T | 10K dom., 22K ent., 120 q | domain/entity | PageRank / popularity | ~ (per query, not per claim role) | ✖ | ✖ | ✖ | filtering | ✖ | 5 LLMs | ✖ | ✔ (stated) | ✔ |
| Contradiction→Consensus '26 | Veracity | T | SciFact, AVeriTeC, LIAR, PubHealth | knowledge base | ✖ (equal) | ✖ | ✔ | ✖ | ✖ | disagreement as uncertainty | ✖ | 70–405B | ✖ | ✔ (anon.) | ~ (large models) |
| WKGFC '26 | Veracity | T | FEVER, HOVER, AVeriTeC 465… | KG vs web | fixed priority | ✖ | ~ | ✖ | ✖ | ✖ | ✖ | GPT-4o | ✖ | ✖ | ✖ |
| CAG / CrAM '24 | RAG QA | T | CAGB | doc credibility | given score | ✖ | ✔ | ✖ | ✖ | weighting | ~ (CAG has time scenario) | 7–13B | ✔ / ✖ | ✔ | ✔ |
| MADAM-RAG '25 | RAG QA | T | RAMDocs, FaithEval, AmbigDocs | document | ✖ | ✖ | ✔ (agent per doc) | ✖ | ✖ | multi-agent debate | ✖ | Llama-3.3-70B, Qwen | ✖ | ✔ | ~ (swap to 8B) |
| CONFLICTS '25 | RAG conflict typing | T | 458 | document | ✖ | ✖ | ✔ | ✖ | ✖ | conflict-type reasoning | freshness type | LLMs | ✖ | ✔ data | ✔ |
| DEFAME '25 | Veracity | I+T | VERITE, AVeriTeC, MOCHEG, CR2024+ | tool/evidence | ✖ | ✖ | ✔ (report) | ~ (reverse image search) | ✖ | LLM judgement | ~ (post-cutoff set) | GPT-4o / open | ✖ | ✔ | ✔ (heavy) |
| Allein '21/'23, ChronoFact '25 | Temporal veracity | T | MultiFC; ChronoFact set | – | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✔ | RNN/Transformer/LLM | ✔ | ~ | ~ |
| Dong '09 / KBT '15 | Truth discovery | structured | web extractions | web source | learned trust | ✖ | ✔ | ✔ copy detection | ✔ | Bayesian | ~ | probabilistic | ✔ | ✖ | idea only |

**Bottom line of the table.** No column combines "claim-conditioned authority" ✔ + "role" ✔ + "independence" ✔. Those three together are where our contribution can go.

---

## PART 2 — The actual research gap (critical)

### 2.1 What "source-aware" means in existing research
1. **Publisher credibility prior**: one scalar or profile per domain/outlet (RAVE, CrediRAG, CONFACT, CAG/CrAM, Burdisso, Lin, AuthorityBench). *Claim-independent.*
2. **Textual source background**: an LLM-written profile of an outlet's bias, ownership and fact-check record (Schlichtkrull 2024, MediaRef, CONFACT SBA). *Richer, still claim-independent.*
3. **Evidence channel/type**: core vs. context vs. reference (HeterMV), KG vs. web (WKGFC), Wikipedia vs. PubMed vs. Google (Contradiction→Consensus).
4. **Source of distortion**: text vs. image vs. mismatch (MMFakeBench, VNL). *Unrelated to publishers.*
5. **Speaker/claimant credibility**: e.g., LIAR "credit history". A known shortcut that leaks label priors.
6. **Image provenance**: 5Pils (who took the image, when, where, prior uses).

### 2.2 Direct answers

| Question | Answer from the literature |
|---|---|
| Just a generic credibility score? | **Mostly yes.** Every retrieval-side system I found uses a claim-independent score or profile. CONFACT's finding that generic scores *in ranking* often hurt suggests they're the wrong abstraction |
| Anyone asking "which source is authoritative for THIS claim?" | **Not as a modelled, evaluated component** in the work reviewed. AuthorityBench is per-query but defines authority as PageRank/popularity. The AVeriTeC knowledge-store builders generated "provenance" queries (e.g., is the claim source a satire site), but only to *build* the store. Fact-checkers do it by hand (Warren et al.). **Caveat:** this review was targeted, not systematic. Before claiming novelty, run a systematic search (ACL Anthology, Semantic Scholar) for "primary source retrieval," "authoritative source identification," "source selection fact-checking," and "evidence source role" |
| Distinguish primary / secondary / corroborating / derived / unreliable? | **No system does.** CONFACT annotates *institution type* (Gov, News, Academic…), which is not the same thing: a government page can be secondary for a claim about a company. Warren et al. identify the primary-vs-secondary gap explicitly |
| Preserve source identity throughout? | Partly. RAVE and CONFACT-SBA keep domain/profile in the prompt. Contradiction→Consensus tracks the source KB. Most chunked RAG pipelines lose it after ranking, and **no evaluation checks whether the verdict's cited sources are the right ones** (AVeriTeC scores the QA *text*, not source choice) |
| Multiple primary/authoritative sources? | Not handled explicitly. Aggregation is majority vote, credibility weighting, debate (MADAM-RAG), or LLM judgement |
| Conflicting authoritative sources? | CONFACT and CONFLICTS study conflicts, but between sources of *different* credibility. When two credible sources disagree, the only tools are LLM judgement or the AVeriTeC label "Conflicting Evidence/Cherry-picking." No explicit scope, jurisdiction or supersession reasoning |
| Provenance? | Not in LLM fact-checking. Classical truth discovery models copying. 5Pils models image provenance. Wire-story duplication and "according to X" chains are ignored, so **majority vote counts copies as independent votes** |
| Recency? | Allein et al. (time-aware ranking), CONFLICTS (freshness type), AVeriTeC (pre-claim-date restriction for leakage). Rarely combined with source identity |
| Source + temporal combined? | **Very little.** CrediRAG uses time only for label matching. Supersession (a newer release from the *same* authority replaces an older one) isn't modelled anywhere I found |
| Is temporal reasoning necessary for us? | **Only for a subset of claims** (statistics, evolving events, updated guidance). Temporal *hygiene* is necessary for all claims |

### 2.3 Is our original idea already solved?
- **"Retrieve evidence + keep source + weight by credibility + LLM verdict"**: **substantially done** (RAVE, CONFACT, CAG/CrAM, DEFAME-style agents). Building it again is not a contribution. It becomes our **Baseline 2**.
- **"Handle conflicting sources"**: **actively studied** (CONFACT, MADAM-RAG, CONFLICTS). We add something only if we bring a new signal (role, independence, scope) that these don't use.
- **"Temporal context"**: **studied separately** (Allein, ChronoFact). Combining it with source role is open but secondary.

### 2.4 A defensible, narrower research problem

> **Claim-Conditioned Source Resolution and Role-Aware Evidence Aggregation for Fact Verification.**
> Given a claim with its metadata (speaker, reporting source, date, location): (i) predict *which sources would be authoritative for this claim* (the originator/speaker's own record, the entity with custody of or jurisdiction over the fact, the original study or dataset); (ii) retrieve evidence with those sources as targets; (iii) label each piece of evidence with its **role relative to the claim** (primary / independent secondary / derived-copy / commentary / unreliable) and collapse dependent evidence; (iv) aggregate by role, independence and scope instead of by vote count or generic credibility.

**Testable hypotheses** (any of them could come out negative, and a negative result is still publishable if the evaluation is solid):
- **H1 (retrieval).** Claim-conditioned source resolution raises **Gold-Source Recall@k** (retrieving the domains fact-checkers used) over (a) claim-only retrieval and (b) generic credibility re-ranking, *at a matched number of queries*.
- **H2 (verdict).** Better source coverage + role-aware aggregation improves verdict macro-F1 / AVeriTeC score, especially on Refuted and Conflicting claims.
- **H3 (conflict).** Collapsing dependent evidence + role precedence beats majority vote, credibility weighting and SBA on CONFACT-HumC.
- **H4 (diagnostic).** Generic credibility is a weak proxy for claim-specific authority. Measure how often the gold primary source has a *lower* generic score than a retrieved secondary source.

**Candidate contributions (student-scale):**
1. **Task formulation + small annotated resource:** a *source-role layer* on ~200–300 AVeriTeC dev claims (role of each gold and top-retrieved source relative to the claim). It's new, cheap, and useful to others.
2. **Method:** a lightweight, zero-shot source-resolution module (LLM + Wikidata) plus role- and independence-aware aggregation, with no fine-tuning in the first version.
3. **Evaluation protocol:** source-level metrics (Gold-Source Recall@k, Primary-Source Recall@k, citation correctness) on top of verdict metrics, with **oracle** and **query-matched** controls.

**Go/no-go check (Step 1 of the plan).** If the audit shows that (a) few gold evidence documents are primary sources, or (b) plain BM25/dense retrieval over the knowledge store already ranks gold-source documents in the top-10 most of the time, H1 has little headroom. In that case, shift the emphasis to H3 (role/independence-aware conflict resolution on CONFACT + AVeriTeC "Conflicting" claims).

---

## PART 3 — Feasibility: reusable components

Assumed hardware: 1 consumer GPU (12–24 GB) or free Colab/Kaggle (T4 16 GB), plus CPU. Rules of thumb for VRAM: ~2 GB per 1B params in bf16, ~0.6–0.7 GB per 1B at 4-bit, plus KV-cache.

### 3.1 LLM / VLM for reasoning and verification

| Model | Purpose | Size | License | GPU / VRAM | Local? | Notes |
|---|---|---|---|---|---|---|
| [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) | **Primary verifier** (text + image natively) | 9B | Apache-2.0 | bf16 ~20 GB. 4-bit ~7 GB | ✔ | 262K context. One model for text and multimodal. Also [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) for fast ablations |
| [Qwen3-VL-8B-Instruct](https://github.com/QwenLM/Qwen3-VL) (2B/4B also) | VLM alternative, strong OCR | 8B | Apache-2.0 | ~17 GB bf16. ~6 GB 4-bit | ✔ | Mature ecosystem (vLLM, transformers) |
| [Qwen2.5-VL-7B](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) | Older VLM baseline | 7B | Apache-2.0 (3B and 72B use Qwen licenses) | ~16 GB | ✔ | Widely used in 2025 papers, good for comparisons |
| [InternVL3.5](https://github.com/OpenGVLab/InternVL) (1B–8B) | VLM alternative | 1–8B | check per checkpoint **(verify)** | 4–17 GB | ✔ | Competitive, but mind license variation |
| [LLaVA-OneVision-7B](https://huggingface.co/lmms-lab/llava-onevision-qwen2-7b-ov) | Legacy VLM baseline | 7B | Apache-2.0 | ~16 GB | ✔ | Weaker. Only if reviewers ask |
| [Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) | Text verifier (**direct comparability with CONFACT**) | 8B | Llama 3.1 Community License (AUP, gated) | ~16 GB | ✔ | Use to reproduce CONFACT numbers |
| [Gemma 3 4B/12B](https://huggingface.co/google/gemma-3-12b-it) | Second model family for robustness | 4/12B | Gemma Terms of Use (use restrictions) | 8 / 24 GB | ✔ | Optional |
| API: GPT-4o / Claude / Gemini | Upper-bound reference only | – | commercial ToS | – | ✖ | Optional. Keeps the main claims about open models |

**Serving:** [vLLM](https://github.com/vllm-project/vllm) (Linux/WSL2, batched, fast) or [Ollama](https://ollama.com) / llama.cpp (Windows-friendly, GGUF 4-bit). All LLM calls go through one wrapper with a **disk cache** keyed on (model, prompt, params) for reproducibility and cost.

### 3.2 NLI / stance (cheap, deterministic)
| Model | Size | License | Use |
|---|---|---|---|
| [MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli](https://huggingface.co/MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli) | 435M | MIT | Per-evidence stance (support / refute / neutral) with calibrated probabilities. CPU is OK for small sets |
| LLM stance prompt (Qwen3.5-4B) | 4B | Apache-2.0 | Fallback for long or complex passages |

### 3.3 OCR (only needed for multimodal; **defer**)
| Tool | License | GPU | Notes |
|---|---|---|---|
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) (PP-OCRv5) | Apache-2.0 | optional | Best accuracy/speed of the classical options |
| [EasyOCR](https://github.com/JaidedAI/EasyOCR) | Apache-2.0 | optional | Easiest pip install (PyTorch) |
| [Tesseract](https://github.com/tesseract-ocr/tesseract) | Apache-2.0 | CPU | Weak on memes/screenshots |
| Qwen3-VL / Qwen3.5 built-in OCR | Apache-2.0 | ✔ | Often better than classical OCR on social images. **AVerImaTeC already provides transcriptions of in-image text**, so OCR can be skipped at first |

### 3.4 Entity extraction and linking
| Tool | Size | License | Use |
|---|---|---|---|
| [spaCy](https://spacy.io) `en_core_web_trf` / `_sm` | ~450M / 12M | MIT | Standard NER, fast |
| [GLiNER](https://github.com/urchade/GLiNER) (`urchade/gliner_multi-v2.1`) | ~200–300M | Apache-2.0 (**check per checkpoint**; some are NC) | **Zero-shot custom types**: "government agency", "statistical indicator", "court", "scientific study", "company", "public official" |
| [ReFinED](https://github.com/amazon-science/ReFinED) | ~0.3B | Apache-2.0 | Fast entity linking to Wikidata |
| [Wikidata](https://www.wikidata.org) API (`wbsearchentities`) + [SPARQL](https://query.wikidata.org) | – | CC0 data | **Source resolution backbone**: official website (P856), country (P17), applies to jurisdiction (P1001), instance of (P31), parent org (P749), "operator"/"publisher" |

### 3.5 Retrieval, embeddings and reranking
| Component | Option | License | Notes |
|---|---|---|---|
| Sparse | [bm25s](https://github.com/xhluca/bm25s) or [rank_bm25](https://github.com/dorianbrown/rank_bm25); [Pyserini](https://github.com/castorini/pyserini) for large indexes | MIT / Apache-2.0 | Per-claim indexes over ~955 docs are tiny, so pure Python is fine |
| Dense | [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) (568M, MIT, multilingual, 8K ctx); [bge-base-en-v1.5](https://huggingface.co/BAAI/bge-base-en-v1.5) (110M, MIT); [intfloat/e5-base-v2](https://huggingface.co/intfloat/e5-base-v2) (MIT); [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) (Apache-2.0) | – | Small models run on a T4, or on CPU for small sets |
| Hybrid | Reciprocal Rank Fusion of BM25 + dense | – | Standard. No training needed |
| Rerank | [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) (568M, Apache-2.0); [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) (Apache-2.0); `cross-encoder/ms-marco-MiniLM-L-6-v2` (22M) | – | Rerank the top ~100 chunks |
| Vector store | [FAISS](https://github.com/facebookresearch/faiss) | MIT | Only needed for large indexes |
| Web search (only if needed) | [Brave Search API](https://brave.com/search/api/), Serper, Tavily | commercial | **Google Custom Search JSON API is closed to new customers and shuts down 2027-01-01** ([Google](https://developers.google.com/custom-search/v1/overview)). Bing Search API was retired in 2025. **Use the offline AVeriTeC knowledge store for all main experiments** |
| Scraping and dates | [trafilatura](https://github.com/adbar/trafilatura), [htmldate](https://github.com/adbar/htmldate) (both Apache-2.0 in recent versions, **verify**), [Wayback CDX API](https://archive.org/developers/wayback-cdx-server.html), `tldextract` | – | Provenance and timestamps |

### 3.6 Generic credibility priors (for Baseline 2 and as one feature)
| Resource | Coverage | Access |
|---|---|---|
| [Lin et al. domain-quality ratings](https://github.com/hauselin/domain-quality-ratings) | ~11.5K domains, PCA of 6 rating sets | Public GitHub (license unclear, **verify**) |
| [Burdisso et al. reliability dataset](https://github.com/idiap/News-Media-Reliability) | 5,332 labelled domains + graph scores for ~17K | Public |
| MBFC | Thousands of outlets | Website ToS limit scraping. CONFACT ships what it used |
| Wikipedia [Perennial sources](https://en.wikipedia.org/wiki/Wikipedia:Reliable_sources/Perennial_sources) | ~500 outlets | CC BY-SA |
| RAVE Table 1 heuristic (domain-type scores) | Any domain | Trivial to reimplement |

**Feasibility verdict.** Everything in the first implementation runs on **one ≤24 GB GPU** (or Colab T4 with 4-bit models), with **no training**, **no paid APIs**, and **offline data**.

---

## PART 4 — Datasets

| Dataset | Task | Modality | Size | Labels | Evidence? | Source metadata | Temporal metadata | Splits | License | Link | Good for source-aware eval? | Limitations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **AVeriTeC** | Real-world claim verification | Text (+some image/PDF/table evidence) | 4,568 (+1,215 extra hidden test; 2025 new test) | S / R / NEE / Conflicting-Cherrypicking | ✔ QA pairs + justification; **knowledge store ~955 docs/claim incl. gold docs, pre-claim-date** | ✔✔ **speaker, reporting_source, original_claim_url**, per-QA **source_url, source_medium**, fact-check article | ✔ claim_date. Knowledge store restricted to before the claim date | train 3,068 / dev 500 / test hidden | CC BY-NC 4.0 | [fever.ai](https://fever.ai/dataset/averitec.html), [HF](https://huggingface.co/chenxwh/AVeriTeC) | **Best available.** Gold URLs let us compute Gold-Source Recall | Gold evidence is *one* valid path. Knowledge-store scraping is noisy (Papelo: 297/500 dev claims had ≥1 gold doc badly scraped). Label imbalance (Refuted dominates) |
| **AVerImaTeC** | Image-text claim verification | I+T | 1,297 | same 4 labels | ✔ QA pairs (text/image) + justification | ✔ speaker, reporting source, per-QA source URL/medium, answer method | ✔ claim date | train/dev public, test hidden (FEVER-9 shared task) | CC BY-NC 4.0 | [fever.ai](https://fever.ai/dataset/averimatec.html), [arXiv](https://arxiv.org/abs/2505.17978) | **Best multimodal option** for a later extension | Small. Image-evidence retrieval is hard. Includes in-image text transcriptions |
| **CONFACT** | Veracity (yes/no) under conflicting evidence | Text | ModC 611 / HumC 287 claims (~4 docs each) | Yes/No (very imbalanced) | ✔ fixed archived docs + stance labels | ✔ per-doc URL. Credibility 1–5 + institution type in the paper (confirm in release) | ✔ claim_date, review_date | eval only | not stated (**verify**) | [GitHub](https://github.com/zoeyyes/CONFACT) | **Yes, for the conflict/aggregation module alone** | Small, imbalanced, binary. Majority vote gets high accuracy |
| **CONFLICTS** | RAG conflict-type identification | Text | 458 | conflict types (incl. freshness) | ✔ passages | ~ URLs | ~ | eval | see repo | [GitHub](https://github.com/google-research-datasets/rag_conflicts) | Secondary: conflict-type prompting | QA, not fact-checking |
| **MultiFC** | Veracity (26 fact-check sites) | Text | 34,918 | 2–40 labels per site | ✔ top-10 Google snippets with URLs | ✔ speaker, site | ✔ claim & evidence dates | train/dev/test | CC BY 4.0 (**verify**) | [site](https://competitions.codalab.org/competitions/21163) (**verify link**) | ~ Temporal-ranking research; snippets only | Heterogeneous labels, snippet-level evidence, possible leakage from fact-check sites |
| **LIAR / LIAR-PLUS** | 6-way veracity | Text | 12,836 | 6 labels | ~ (PLUS adds justification) | ✔ speaker, party, job, "credit history" | ✔ partial | train/val/test | research use (**verify**) | [LIAR](https://www.cs.ucsb.edu/~william/data/liar_dataset.zip) | ✖ Speaker priors are a shortcut, no evidence sources | Label leakage via credit history |
| **FEVER** | Verification vs Wikipedia | Text | 185,445 | S / R / NEI | ✔ Wikipedia sentences | ✖ (single source) | ✖ | 145K/20K/20K | CC BY-SA 3.0 (Wikipedia) | [fever.ai](https://fever.ai/dataset/fever.html) | ✖ Only sanity checks | Synthetic claims, single source |
| **FEVEROUS** | Verification vs Wikipedia text + tables | Text + tables | 87,026 | S / R / NEI | ✔ sentences + cells | ✖ | ✖ | 71,291 / 7,890 / 7,845 | CC BY-SA 3.0 | [fever.ai](https://fever.ai/dataset/feverous.html) | ✖ ("multi-source" = text vs table) | Same as FEVER |
| **Check-COVID** | News claims vs scientific papers | Text | 1,504 | Support / Refute / NEI | ✔ sentences from journal articles | ~ news-article origin (**verify**) | ✖ / ~ | see repo | see repo | [GitHub](https://github.com/posuer/Check-COVID) | ~ One "authoritative source type" (science), which fits a domain-specific case study | Single domain, one evidence type |
| **Fakeddit** | Fake/real (2/3/6-way) | I+T | ~1M posts (~680K with images) | distant labels from subreddit | ✖ | ~ domain, author, subreddit | ✔ created_utc | train/val/test | research (**verify**) | [GitHub](https://github.com/entitize/Fakeddit) | ✖ Labels come from subreddit, not source reasoning | Label = subreddit. Shortcut-prone (CrediRAG notes this) |
| **NewsCLIPpings** | Out-of-context image-caption detection | I+T | ~85K (merged-balanced: 71K / 7K / 7.3K) | pristine / falsified | ✖ (web-evidence extensions exist, e.g., CCN) | ~ outlet (BBC, Guardian, USA Today, WaPo via VisualNews) | ~ | ✔ | VisualNews agreement required | [GitHub](https://github.com/g-luo/news_clippings) | ✖ Synthetic mismatches | No real claims or sources |
| **VERITE** | True / miscaptioned / OOC | I+T | 1,000 (338 / 338 / 324) | 3 classes | ✖ (DEFAME retrieves evidence) | ~ from Snopes/Reuters | ~ | test only | see repo | [GitHub](https://github.com/stevejpapad/image-text-verification) | ✖ for source reasoning | Benchmark only |
| **MMFakeBench** | Distortion-source attribution | I+T | 11,000 (1K val / 10K test) | 4 top-level, 12 sub-types | ✖ | ✖ (source = distortion type) | ✖ | val/test | CC BY-NC-SA 4.0 / CC-BY 4.0 (conflicting), gated | [GitHub](https://github.com/liuxuannan/MMFakeBench) | ✖ Different meaning of "source" | Largely synthetic |
| **5Pils** | Image meta-context (provenance, source, date, location, motivation) | Image | 1,676 | QA | ✔ | ✔ image source/provenance | ✔ date | ✔ | see repo | [GitHub](https://github.com/UKPLab/5pils) | ✔ For image provenance in the multimodal extension | Image-only. Contextualisation, not veracity |
| **QuanTemp** | Numerical/temporal claim verification | Text | ~15.5K (**verify**) | T / F / Conflicting | ✔ | ~ | ✔ | ✔ | see repo | [arXiv](https://arxiv.org/abs/2403.17169) | ~ Statistics claims, where the "authoritative agency" framing fits naturally | Domain-specific |
| **Community Notes (X)** | Crowd-written context notes | Text + links | millions, updated daily | helpful / not-helpful ratings | ✔ URLs in notes | ✔ cited domains | ✔ | – | X data terms | [download](https://communitynotes.x.com/guide/en/under-the-hood/download-data) | ~ Rich corpus of which sources people cite | Noisy, ToS constraints |

**Which dataset actually has enough source information for SOURCE-AWARE verification?**
- **AVeriTeC** is the only one that combines real claims, claimant/speaker identity, per-evidence source URLs picked by annotators following professional fact-checks, claim dates, and a leakage-controlled offline corpus that includes those gold sources. **Use it as the primary benchmark.**
- **CONFACT** is the only one with per-source credibility and stance under conflict. Use it for the aggregation module alone (retrieval held fixed).
- **AVerImaTeC** (+ **5Pils**) is the multimodal counterpart, for later.
- **Neither has *source-role* labels (primary/secondary/derived).** We have to add a small annotation layer ourselves, and it's part of our contribution.
- Fakeddit, NewsCLIPpings, VERITE, MMFakeBench, FEVER and FEVEROUS **cannot evaluate** the source-aware component. Don't use them for the core claims.

---

## PART 5 — Minimal research pipeline (v1, text-only)

Changes from your sketch, based on the literature:
- "Claim extraction" becomes **claim normalisation**. AVeriTeC claims are already extracted and decontextualised. RAVE-style verifiability detection isn't needed.
- "Source discovery" is split into **(a) claim-conditioned source resolution** (the novel part) and **(b) source-targeted retrieval**.
- A **role-tagging + dependence-collapsing** stage is added before verification. CONFACT shows that weighting at ranking time hurts, so source information should shape *what is retrieved* and *how evidence is aggregated*, not only the ranking score.
- Temporal handling is a **filter** in v1.

```
Claim + metadata (speaker, reporting_source, claim_date, location)
  │
  ├─[1] Claim normalisation & decomposition ──► sub-questions, claim type
  ├─[2] Entity identification & linking ─────► Wikidata QIDs
  ├─[3] Source resolution  (NOVEL) ─────────► ranked list of expected authoritative sources + roles + domains
  ├─[4] Evidence retrieval (hybrid; + source-targeted queries) over AVeriTeC knowledge store
  ├─[5] Provenance / role tagging + dependence clustering (NOVEL) ─► EvidenceUnit records
  ├─[6] Stance per unit (NLI + LLM)
  ├─[7] Role/independence-aware aggregation (rule-based v1) ─► verdict + conflict flag
  └─[8] Explanation generation (LLM, constrained to the structured evidence table) ─► verdict, cited sources + roles
```

| # | Stage | Tool / model | Input → Output | Approach | Training? |
|---|---|---|---|---|---|
| 1 | Claim normalisation | Qwen3.5-4B/9B prompt | claim + metadata → {normalised claim, claim_type (numerical / quote / event / causal / position), 2–5 sub-questions, time expression} | Few-shot prompt, JSON output. AVeriTeC train QA pairs as examples | No |
| 2 | Entities | spaCy + GLiNER (custom types) → ReFinED or Wikidata `wbsearchentities` + LLM disambiguation | claim + speaker → list of {mention, type, QID} | Pipeline. Cache Wikidata calls | No |
| 3 | **Source resolution** | LLM prompt + Wikidata facts (P856 official website, P17 country, P31 type, P749 parent org) | claim_type, entities, speaker, location → ranked `ExpectedSource{name, QID, domain(s), role: originator / custodian-authority / original-research / independent-verifier, rationale}` | Zero-shot. The prompt asks: *"Who originally said or published this? Which organisation holds the ground truth for this fact in this jurisdiction? Where is the primary record?"* Domains come from Wikidata P856 when available, otherwise from the LLM, validated against domains present in the knowledge store | No (v2: distil on AVeriTeC train, using gold domains as weak labels) |
| 4 | Retrieval | bm25s + bge-m3 (or bge-base) → RRF → bge-reranker-v2-m3 | claim + sub-questions (+ source-targeted queries "⟨source name⟩ ⟨sub-question⟩") → top-k chunks **with URL/domain/date attached** | Per-claim index over the knowledge store. Proposed system: additional query set + optional domain boost for resolved sources | No |
| 5 | **Provenance / role** | Rules + LLM | chunk + ExpectedSources + claim → `EvidenceUnit{source_domain, source_entity, role_wrt_claim ∈ {primary, independent-secondary, derived, commentary, unreliable, unknown}, cites[], dup_cluster_id}` | (a) domain matches a resolved source → primary candidate; (b) regex/LLM for attribution ("according to X", "X said", links) → `cites`; (c) MinHash/embedding near-duplicate clustering → collapse wire-copies; (d) generic credibility prior as a feature, not a filter | No |
| 6 | Stance | DeBERTa-v3 NLI (+ LLM fallback) | (claim or sub-question, unit) → {support, refute, neutral}, prob | Standard | No |
| 7 | Aggregation | Python rules (Part 7) | units → label ∈ {S, R, NEE, Conflicting} + per-unit weights | Transparent, deterministic | No (v2: logistic regression) |
| 8 | Explanation | Qwen3.5-9B | structured table → justification citing unit IDs + roles | Constrained generation. Verify that every citation exists | No |

**Engineering rules.** One typed schema (`Claim`, `SourceRecord`, `EvidenceUnit`, `Verdict`) passed through every stage means source identity can't be lost. Every stage is a pure function `(inputs, config) → outputs` with JSONL caching. Every experiment is one YAML config plus a seed. No services, no frontend.

---

## PART 6 — Baselines vs our system (experimental design)

All systems use the **same verifier LLM, the same k, the same token budget, and the same knowledge store**. Only the listed components differ.

| System | Retrieval | Source info | Aggregation | What it isolates |
|---|---|---|---|---|
| **B0** No-retrieval | none | none | LLM | Parametric knowledge / contamination floor |
| **B1** Standard RAG | hybrid over claim + sub-questions | **URLs stripped** | LLM over top-k | Plain RAG |
| **B1-meta** | same as B1 | domain + title shown | LLM | Effect of *just showing* source names |
| **B2** Credibility RAG | B1 + `α·rel + (1−α)·cred` rerank (RAVE/CONFACT-CW), and a variant with SBA backgrounds in the prompt | generic prior (Lin et al.) | LLM | Reproduces prior work on our data |
| **B2-MAD** | B1 | per-doc agents | MADAM-RAG-style debate (8B) | Strong conflict baseline (optional) |
| **P** (ours) | B1 **+ source-targeted queries + resolved-domain boost** | resolved ExpectedSources + roles + dependence clusters | Role/independence-aware rules → LLM explanation | Our full contribution |
| **P-T** (extended) | P + temporal alignment (Part 8) | + dates / supersession | + recency within same source | Temporal module |

**Ablations and controls (essential):**
1. **P − resolution** (role tagging + aggregation only) vs **P − aggregation** (resolution-guided retrieval, B1's LLM aggregation) shows which half helps.
2. **Query-count-matched control:** B1 with the same *number* of extra queries, paraphrases without source names. Without this, "more queries" is a confound.
3. **Oracle resolution:** use the gold evidence domains of each claim as the "resolved sources" to get an upper bound. **Random/shuffled resolution** (another claim's sources) as a lower-bound control.
4. **Generic prior swap:** Lin et al. vs RAVE heuristic vs none, to test H4.
5. **Model scale:** 4B vs 9B, to see whether the gains survive a stronger model.

**Metrics:**
- Verdict: accuracy, **macro-F1** (4-way and collapsed S/R), per-class F1 (especially Refuted and Conflicting).
- AVeriTeC score (official scorer; Ev2R if adopted by the 2025 scorer **(verify)**).
- **Source metrics (ours):** Gold-Source Recall@k (does a top-k chunk come from a gold evidence domain/URL?), **Primary-Source Recall@k** (on the annotated subset), source-resolution precision/recall vs gold domains, citation validity (does every cited unit exist and have the claimed stance?).
- Conflict: CONFACT-HumC accuracy + macro-F1 (always compare to majority vote and SBA).
- Statistics: paired bootstrap (10k) / McNemar on per-claim correctness; report mean ± sd over 3 seeds or prompt paraphrases.

**Data protocol.** Tune on AVeriTeC **train** subsets, report on **dev** (the test set is hidden). Hold out the annotated subset from any tuning. B0 is always reported (contamination).

---

## PART 7 — Multiple authoritative sources & conflicts

Example: A (supports), B (supports), C (contradicts). **Not majority vote.**

### 7.1 Signals (per EvidenceUnit)
| Signal | How to get it in v1 | Why |
|---|---|---|
| Authority for *this* claim | Match to ExpectedSources (stage 3): originator / custodian / original research | Core hypothesis |
| Role | primary / independent-secondary / derived / commentary / unreliable | Warren et al. |
| **Independence** | Near-duplicate clusters (MinHash, cos > 0.9), explicit citation ("according to C") → attach to the cited source | A+B may be one wire story, or both may cite C |
| Relevance | reranker score | Standard |
| Scope match | LLM yes/no: same entity, same jurisdiction, same time period, same metric definition? | Most "conflicts" between credible sources are scope mismatches (different year, region or definition) |
| Recency / supersession | pub/update dates. Same source + newer version supersedes older | Revised statistics, updated guidance |
| Generic credibility | Lin et al. prior | Tie-breaker only (CONFACT: hurts as a filter) |
| Stance confidence | NLI probability | – |

### 7.2 Simple first implementation (deterministic, explainable)
1. **Collapse dependence:** merge units into *independent evidence groups*. A group inherits the authority of its **underlying** source: "B reports that C said X" is C's evidence, not B's.
2. **Scope filter:** mark groups with a scope mismatch as `context-only`. They're kept for the explanation and excluded from the vote.
3. **Tiered precedence:** Tier 1 = primary/custodian for this claim; Tier 2 = independent secondary with high generic credibility; Tier 3 = everything else.
4. **Decide at the highest tier with stance-bearing evidence:**
   - Tier-1 agreement → that stance.
   - Tier-1 disagreement → check supersession (same authority, newer date wins) and scope. If still unresolved → **`Conflicting`** with both sides cited (AVeriTeC label).
   - No Tier-1 → Tier-2 weighted sum `Σ w_cred · p_stance` over *independent groups*, with an abstention margin → `NEE` if below the margin.
5. **LLM writes the explanation** from the structured table. In one ablation the LLM also decides, to compare rule and LLM decisions.

### 7.3 How it grows into a learned model
- **v2:** logistic regression / gradient boosting over group-level features (tier, role, cred, scope, recency, group size, stance prob), trained on AVeriTeC train with gold labels (and gold-domain weak labels for authority).
- **v3:** truth discovery with source dependence (Dong 2009 / KBT-style EM), jointly estimating source trust and claim truth across claims.
- **v4:** a graph model (HeterMV-style typed nodes: claim, source, evidence, citation edges), once the rule-based and linear versions show where the signal is.

---

## PART 8 — Temporal context (optional secondary module)

**What the literature says:**
- Temporal verification is studied as a separate problem: [Allein et al. 2021](https://arxiv.org/abs/2009.06402) (time-aware evidence ranking on MultiFC, up to +9 micro-F1 / +15 macro-F1), [Allein et al. 2023](https://aclanthology.org/2023.findings-eacl.13/), [ChronoFact 2025](https://arxiv.org/abs/2410.14964) (event timelines), CONFLICTS "freshness" conflicts, QuanTemp. AVeriTeC enforces "evidence published before the claim" for leakage control.
- **Datasets with usable timestamps:** MultiFC (claim and evidence dates), AVeriTeC and AVerImaTeC (claim date + pre-date knowledge store), ChronoFact data, QuanTemp.
- **Does it improve source-aware verification?** **Not shown.** No paper I found combines source role with temporal alignment. That makes it a potential second contribution, but there's no evidence yet that it matters for enough claims.

**Decision.** v1 = temporal *hygiene* only: (1) keep `t_pub ≤ t_post` (already true in the knowledge store; enforce it in any web retrieval); (2) store the timestamps below in the schema. v2 = supersession + event-time alignment for numerical and event claims, evaluated on that subset.

**Definitions (fields in the schema from day 1):**
| Field | Meaning | Source in v1 |
|---|---|---|
| `t_post` | When the claim was made/posted | AVeriTeC `claim_date` |
| `t_event` | Time period the claim is *about* ("unemployment in 2019") | LLM extraction in stage 1 (nullable) |
| `t_pub` | Evidence publication time | htmldate on the stored HTML / URL date patterns / Wayback first capture (nullable) |
| `t_update` | Last-modified / revision time of the evidence | htmldate (`original_date=False`) / Wayback (nullable) |
| `temporal_relation` | {before_post, after_post (leak), covers_event, outdated_for_event, superseded_by: unit_id} | Computed in v2 |

---

## PART 9 — Proposed repository structure

```
sourceawaremisinformation/
├── README.md                 # goal, setup, how to reproduce each table
├── pyproject.toml            # single package, pinned deps (uv or pip-tools)
├── configs/
│   ├── models/               # qwen3.5-9b.yaml, qwen3.5-4b.yaml, llama3.1-8b.yaml
│   ├── retrieval/            # bm25.yaml, hybrid.yaml, rerank.yaml
│   └── experiments/          # b0.yaml, b1.yaml, b1_meta.yaml, b2.yaml, p.yaml, p_oracle.yaml, ...
├── data/                     # (git-ignored) raw/ interim/ processed/ + data/README.md with sources & licenses
├── annotations/
│   ├── guidelines_source_roles.md
│   └── averitec_dev_roles.jsonl
├── src/samv/                 # "source-aware misinformation verification"
│   ├── schema.py             # Claim, Entity, ExpectedSource, EvidenceUnit, Verdict (pydantic/dataclasses)
│   ├── datasets/             # averitec.py, confact.py, averimatec.py (loaders -> schema)
│   ├── llm/                  # backend wrappers (vLLM / Ollama / HF) + on-disk cache
│   ├── claim/                # normalisation, decomposition, claim typing
│   ├── entities/             # NER (spaCy/GLiNER), linking (ReFinED/Wikidata)
│   ├── sources/              # source resolution (NOVEL), credibility priors, domain<->entity maps
│   ├── retrieval/            # bm25, dense, hybrid (RRF), rerank, source-targeted query gen
│   ├── provenance/           # role tagging, citation extraction, near-dup / dependence clustering (NOVEL)
│   ├── verification/         # stance (NLI/LLM), aggregation rules, verdict/explanation prompts
│   ├── temporal/             # date extraction & filters (v1: filter only)
│   ├── pipelines/            # b0.py, b1.py, b2.py, proposed.py: compose stages from config
│   └── evaluation/           # verdict metrics, AVeriTeC scorer wrapper, source metrics, significance
├── scripts/                  # download_averitec.py, build_indexes.py, run_experiment.py, audit_sources.py
├── experiments/              # (git-ignored) runs/<run_id>/{config.yaml, preds.jsonl, metrics.json, log}
├── notebooks/                # analysis & figures only (no pipeline logic)
├── tests/                    # schema round-trips, metric unit tests, tiny fixture claims
└── docs/                     # this review, decision log, annotation reports
```

Why this layout: stages map one-to-one onto the research questions (so ablations are config switches); the **novel parts are isolated** in `sources/` and `provenance/`; the shared `schema.py` makes source identity structurally impossible to drop; `llm/` caching makes runs reproducible and cheap.

---

## PART 10 — What we know, what we reuse, what we build

### ✅ ALREADY SOLVED BY EXISTING WORK
- Retrieval-augmented LLM fact-checking pipelines with open ≤10B models (AVeriTeC 2024/2025 systems, HerO, CTU AIC, DEFAME).
- Injecting *generic* source credibility into RAG through filtering, weighting or prompt backgrounds, and knowing that the ranking/filtering variants often hurt (CONFACT, RAVE, CAG, CrAM).
- Generic outlet credibility estimation and background generation (Baly 2018, Burdisso 2024, Lin 2023, Schlichtkrull 2024, MediaRef 2026).
- Studying conflicting evidence in RAG (CONFACT, MADAM-RAG, CONFLICTS).
- Multimodal "source of distortion" attribution (MMFakeBench, VNL) and image meta-context (5Pils).
- Time-aware evidence ranking and timeline verification (Allein, ChronoFact).

### 🧰 AVAILABLE TOOLS WE CAN REUSE
Qwen3.5-4B/9B, Qwen3-VL, Llama-3.1-8B (for CONFACT comparability) · vLLM / Ollama · DeBERTa-v3 NLI · spaCy, GLiNER, ReFinED, Wikidata SPARQL · bm25s, bge-m3 / bge-base, bge-reranker-v2-m3 / Qwen3-Reranker, FAISS · trafilatura, htmldate, Wayback CDX · Lin et al. / Burdisso credibility priors · AVeriTeC knowledge store + official scorer · CONFACT data + code.

### 🛠 COMPONENTS WE NEED TO IMPLEMENT
1. Shared schema + dataset loaders + cached LLM wrapper.
2. Baselines B0 / B1 / B1-meta / B2 on AVeriTeC dev.
3. **Source-audit script** (gold-domain typing, retrieval rank of gold sources).
4. **Source-role annotation guideline + ~200–300 annotated dev claims.**
5. **Claim-conditioned source resolution** (LLM + Wikidata).
6. **Source-targeted retrieval** (query generation + domain boost).
7. **Role tagging + dependence clustering.**
8. **Role/independence-aware aggregation** + constrained explanation.
9. Source-level metrics + significance testing.

### 💡 POTENTIAL RESEARCH CONTRIBUTION
*Framing: "Fact-checkers go to primary sources; automated systems don't. We formalise claim-conditioned source resolution and role-aware aggregation, and measure whether it closes that gap."*
- Task + metric: **Primary-/Gold-Source Recall** as a first-class evaluation target.
- Resource: **source-role annotations** on AVeriTeC dev.
- Method: zero-shot source resolution + independence-aware aggregation with ≤10B open models.
- Findings: whether claim-specific authority beats generic credibility (H1–H4), including negative results.

### 🔭 OPTIONAL FUTURE EXTENSIONS
- Temporal alignment + supersession (P-T).
- Multimodal: AVerImaTeC + 5Pils (image provenance as a source-resolution problem; reverse image search).
- Learned aggregation (v2 → truth discovery → graph).
- Distilling source resolution into a small model using AVeriTeC train gold domains.
- Live web retrieval (Brave/Serper) with Wayback archiving for reproducibility.
- "Verification notebook" (VNL-style) for learned source-selection heuristics.

---

## RECOMMENDED FIRST IMPLEMENTATION (steps 1–8)

1. **Data audit (go/no-go, ~1 week, no models beyond BM25).** Download AVeriTeC train/dev + the dev knowledge store. Report: metadata coverage (speaker, reporting_source, claim_date); distribution of **gold evidence domains** by type (gov / intergovernmental / court / academic / company-official / the speaker's own channels / news / fact-checker / social / other; rules + Wikidata); share of claims whose gold evidence includes a **primary** source; **rank of gold-source documents under plain BM25** over the knowledge store; share of gold docs that are empty or badly scraped. Write up in `docs/01_data_audit.md` and **decide whether H1 has headroom.**
2. **Skeleton.** `schema.py`, AVeriTeC and CONFACT loaders, LLM wrapper with disk cache (Ollama or vLLM, Qwen3.5-4B first), config-driven `run_experiment.py`, metric unit tests. No pipeline logic in notebooks.
3. **Baselines B0 + B1 + B1-meta** on AVeriTeC dev (500 claims): per-claim BM25 + bge + RRF + bge-reranker, k=10 chunks, Qwen3.5-9B 4-way verdict. Report macro-F1, per-class F1, AVeriTeC score, Gold-Source Recall@k. Sanity-check the numbers against published shared-task baselines.
4. **B2 (reproduce prior work):** Lin et al. prior with RAVE-style `α·rel+(1−α)·cred` rerank and a CONFACT-style SBA prompt. Also run B1/B2 on **CONFACT-HumC** with Llama-3.1-8B to reproduce roughly their Table 2 (this validates our setup).
5. **Annotation:** write `guidelines_source_roles.md` (role of each source *relative to the claim*), and have two people annotate ~200 dev claims (gold sources + top-5 retrieved). Report Cohen's κ. Freeze it as the test-only subset.
6. **Source resolution v1 + source-targeted retrieval:** LLM + Wikidata → ExpectedSources. Measure **resolution precision/recall vs gold domains** first (a cheap intrinsic eval), then plug into retrieval. Run the **query-matched control** and the **oracle/random** variants.
7. **Role tagging + dependence clustering + rule-based aggregation (Part 7)** → full system **P**. Evaluate on AVeriTeC dev (full + annotated subset + Conflicting/Refuted slices) and CONFACT-HumC.
8. **Ablations, significance, error analysis:** paired bootstrap across all systems, 4B vs 9B, a qualitative study of 50 errors (where did the role or authority reasoning fail?). Only then decide on the temporal or multimodal extension.

*Don't* in this phase: frontend, browser extension, fine-tuning, live web crawling for the main results, downloading Fakeddit/NewsCLIPpings, or reporting any number that didn't come from a logged run.
