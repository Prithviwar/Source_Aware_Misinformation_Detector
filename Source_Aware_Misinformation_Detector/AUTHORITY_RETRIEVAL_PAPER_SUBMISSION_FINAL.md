# Claim-Specific Authority for Evidence Retrieval in Fact Verification

## A Frozen Held-Out Evaluation on AVeriTeC and an Analysis of Failure Modes

Rachit Mane  
Department of Artificial Intelligence and Machine Learning  
PES University, Bengaluru, India

## Abstract

Evidence retrieval for automated fact verification usually ranks
documents by their relevance to the claim, and some systems also
weight documents by the general credibility of their publisher. We
ask whether retrieval improves when a system first identifies the
source that is authoritative for the specific claim, that is, the
organisation or person that issued, recorded or holds the fact in
question.

We evaluate this idea on a frozen held-out set of 200 AVeriTeC claims,
of which 167 have at least one reachable gold evidence document. An
authority prior predicted by a large language model raised R@10 from
0.251 for hybrid retrieval to 0.293. In the paired comparison the
prior won on 13 claims and lost on 6, giving an exact McNemar p-value
of 0.167, a difference of +0.042 and a 95% confidence interval of
[-0.006, 0.096]. This difference is directional but not statistically
significant.

A pipeline that retrieves extra documents directly from the predicted
authorities did not carry over from the development data to the
held-out claims. Wrong authority prediction was a major failure mode:
for 102 of the 167 claims, none of the three predicted publishers
matched any gold publisher.

An exploratory analysis of AI-labelled primary-evidence recall is
conditional on 72 claims. On these claims, the full targeting pipeline
reached R@10 = 0.431, compared with 0.097 for hybrid retrieval. The
same model family produced both the authority predictions and the
evidence-role labels, so this result is supporting evidence and not
independent validation. All conclusions are limited to this frozen
evaluation inside the AVeriTeC knowledge store.

## 1 Introduction

A fact-checking system can only reach a sound verdict if it first
finds suitable evidence. Most systems treat this step as relevance
retrieval: they look for documents that discuss the same subject as
the claim and rank them by textual similarity. Some systems add a
credibility score for each publisher or web domain and use it to move
trustworthy outlets up the ranking.

Human fact-checkers describe their work differently. Fact-checkers
interviewed by Warren et al. (2025) say that they try to find "the
most primary, most original source" of a piece of information. The
same study observes that automated fact-checking tends to rely on
secondary sources, such as news articles and existing fact-checks.

This observation separates two ideas that are often treated as one.

- **General source credibility** asks whether a source or publisher
  is trustworthy in general. It is a property of the publisher and
  takes the same value for every claim.
- **Claim-specific authority** asks whether a source actually issued,
  recorded, measured, announced, observed or holds the fact at issue
  in the claim being checked.

The two ideas can point in different directions. A national
statistics office is the authority for a claim about the unemployment
figure it publishes, but not for a claim about the earnings of a
private company. A respected newspaper may be highly credible and
still be only a secondary source for both claims.

In this paper we test whether claim-specific authority is a useful
retrieval signal. A large language model predicts, for each claim,
the publishers that are most likely to be authoritative. The
predictions are used in two ways: as a ranking prior over a candidate
pool built by relevance retrieval, and as a guide for retrieving
additional documents directly from the predicted publishers.

The evaluation is a frozen held-out study on AVeriTeC. On the
preregistered human-gold endpoint, the outcome is mixed and mostly
negative. The authority prior gives a directional improvement that is
not statistically significant, and the targeting pipeline, which
looked promising during development, does not carry over to the
held-out claims.

We therefore present the work as an empirical study of when
claim-specific authority helps retrieval and when it fails. The most
useful part of the study is its account of failures. Authority
prediction is often wrong. A correct prediction does not ensure that
the authoritative document is retrieved, because the document is
often absent from the candidate pool. Aggressive targeting can also
displace relevant evidence from the top ranks.

We also report an exploratory analysis of first-hand evidence, based
on evidence-role labels produced by an AI model. Because the same
model family also predicts authority, we treat this analysis only as
supporting evidence.

This paper makes three contributions:

1. a frozen held-out evaluation of claim-specific authority-aware
   retrieval on 200 AVeriTeC claims, covering relevance retrieval, a
   generic credibility prior, a heuristic authority prior, an LLM
   authority prior and several source-targeting variants;
2. a failure analysis showing that wrong authority prediction is a
   major bottleneck, that a correct prediction does not ensure
   retrieval, that collection coverage limits what authority-aware
   ranking can reach, and that aggressive authority-first targeting
   can reduce recall;
3. an openly disclosed exploratory analysis of AI-labelled
   primary-evidence recall, together with its conditional denominator
   and its dependence on the model that predicts authority.

We do not claim that authority-aware retrieval is generally better
than relevance retrieval. We do not claim that language models
reliably identify authoritative sources. We do not claim that source
targeting generalises beyond this evaluation.

## 2 Related Work

### 2.1 Benchmarks for fact verification

Several widely used benchmarks for fact verification are based on
Wikipedia. FEVER (Thorne et al., 2018) contains 185,445 claims that
were produced by altering sentences from Wikipedia. FEVEROUS (Aly et
al., 2021) combines evidence from Wikipedia sentences with evidence
from Wikipedia tables. HoVer (Jiang et al., 2020) targets multi-hop
verification, in which a claim can require evidence from as many as
four Wikipedia articles. Since the evidence in these benchmarks comes
from a single kind of source, they cannot be used to study which
publisher is authoritative for a claim.

AVeriTeC (Schlichtkrull et al., 2023) is built from real-world claims.
It contains 4,568 claims drawn from fact-checks published by 50
organisations. Every claim has metadata describing its speaker, its
publisher, its date and its location. Evidence takes the form of
question-answer pairs, and every answer must be backed by a source
URL. Annotators followed the original fact-checking article while
writing the questions, but they were not allowed to use the article
itself as evidence. The first AVeriTeC shared task (Schlichtkrull et
al., 2024) released a knowledge store of candidate documents for each
claim, described in Section 4. The second shared task (Akhtar et al.,
2025) required systems to use open-weights models running on a single
23 GB GPU and to return each verdict within one minute.

### 2.2 Source signals in retrieval and verification

Several existing systems already make use of information about
sources.

- RAVE (Li and Zubiaga, 2025) combines evidence retrieval with
  relevance and source-credibility signals in order to detect
  verifiable claims.
- CrediRAG (Ram et al., 2024) assigns Reddit posts an initial
  misinformation score based on the source credibility of similar
  retrieved news articles.
- CONFACT (Ge et al., 2025) studies retrieval-augmented fact-checking
  when the retrieved evidence conflicts. It finds that adding media
  background information helps models resolve the conflict, whereas
  credibility strategies applied at the retrieval and ranking stages
  are less effective and can sometimes lower performance.
- CrAM (Deng et al., 2025) changes how strongly each retrieved
  document influences the model, according to a given credibility
  score.
- CAG (Pan et al., 2024) trains language models to treat retrieved
  content according to its credibility.
- AuthorityBench (Yao et al., 2026) measures how well language models
  judge authority. It defines the authority of a web domain by
  PageRank and the authority of an entity by popularity, and it
  reports that giving the models webpage text makes their judgments
  worse.

### 2.3 Multi-source and multimodal verification

Other recent systems collect evidence from several kinds of sources.

- WKGFC (Gong et al., 2026) treats an open knowledge graph as its main
  source of evidence and uses web retrieval to fill the gaps.
- Contradiction to Consensus (Biswas and Uzuner, 2026) retrieves
  evidence from Wikipedia, PubMed and Google, keeps a source label on
  every piece of evidence, and measures how much the sources disagree.
- RAMA (Yang et al., 2025) is a retrieval-augmented multi-agent
  framework for detecting multimodal misinformation. Its abstract
  describes cross-verification evidence aggregation from diverse,
  authoritative sources.
- REVEAL (Tariq and Kementchedjhieva, 2026) is a retrieval-enhanced
  system for checking image-text claims. It uses an iterative context
  loop that combines sparse and dense retrieval.
- Verification-Notebook Learning (Tan, 2026) uses the word
  "source-aware" for identifying which part of a multimodal post
  carries a misleading signal.

### 2.4 Source dependence

Research on truth discovery has examined how sources conflict and how
they depend on each other. Dong et al. (2009) studied the role of
source dependence when integrating conflicting data, and Dong et al.
(2015) estimated how trustworthy web sources are from the correctness
of the facts they state.

### 2.5 Research gap

Existing systems already retrieve, rank, aggregate or reason over
evidence from many sources. Several of them use source-level signals:
claim-independent credibility (RAVE, CrediRAG, CONFACT and CrAM),
source type (WKGFC) and aggregation across authoritative sources
(RAMA). AuthorityBench evaluates language-model judgments of
authority defined by PageRank and popularity. Within the work we
reviewed (a targeted, not systematic evaluation), we did not find an
evaluation that predicts, for each claim, the publisher that holds the
fact at issue, uses that prediction as a retrieval and ranking signal,
and measures where it fails. This study offers such an evaluation on
AVeriTeC, together with an analysis of the failures that come from
authority prediction, source targeting and evidence availability.

## 3 Research Question and Hypotheses

The study is built around one research question.

> Can explicitly identifying the source that is authoritative for a
> particular claim improve evidence retrieval compared with standard
> relevance- and credibility-based retrieval?

The preregistered comparisons on the human-gold endpoint correspond
to the null hypotheses below. Each was tested with a two-sided exact
McNemar test on per-claim outcomes.

- **H1 (primary).** Hybrid retrieval with the LLM authority prior (D)
  and plain hybrid retrieval (A) are equally likely to place gold
  evidence in the top 10.
- **H2.** The candidate pool of hybrid retrieval plus source targeting
  (F) and a size-matched hybrid pool are equally likely to contain
  gold evidence.
- **H3.** The full pipeline (G) and the authority reranker (D) are
  equally likely to place gold evidence in the top 10.
- **H4.** The full pipeline (G) and plain hybrid retrieval (A) are
  equally likely to place gold evidence in the top 10.

A secondary family of five tests compared D with A at R@5 and R@20,
and D with the generic credibility system B at R@5, R@10 and R@20.

The comparisons on AI-labelled primary evidence in Section 9 follow
the same test design. They were pre-specified but not preregistered,
as Section 4.5 explains.

## 4 Dataset and Frozen Held-Out Protocol

### 4.1 Knowledge store

Every retrieval step in this study runs inside the per-claim AVeriTeC
knowledge store released for the 2024 shared task. The study does not
perform any live or open-web retrieval.

The shared-task paper (Schlichtkrull et al., 2024) explains that the
organisers built the knowledge store with the Google Search API. Some
search queries were generated from the claim and others from the gold
questions and gold answers. Only documents that would have been
available before the claim was made were kept, and the evidence
documents chosen by the original annotators were added. On average,
each claim has about 955 documents. The store is therefore already
focused on each claim and rich in relevant pages.

### 4.2 Samples

Both samples in this project come from the official AVeriTeC
development split, which has 500 claims.

- The development sample has 120 claims, which were used to design and
  tune the methods.
- The held-out sample has 200 claims taken from the remaining 380. It
  is stratified by label, with 124 Refuted, 48 Supported, 15
  Conflicting/Cherrypicking and 13 Not Enough Evidence claims, and it
  was drawn with seed 2027. It shares no claims with the development
  sample.

### 4.3 Gold evidence

The counts below refer to this project's extraction of the knowledge
store for the held-out sample.

- 192 of the 200 held-out claims have at least one web gold URL.
- The held-out claims have 422 gold URLs in total.
- 117 of these URLs have empty text in the extracted knowledge store.
- 167 claims have at least one reachable gold document, that is, a
  gold document whose text is not empty. These 167 claims form the
  denominator of the main benchmark.
- 25 claims have web gold URLs whose text is entirely empty.
- 8 claims have no web gold URL.

### 4.4 Preprocessing and leakage controls

The steps below were introduced by this project and are not part of
AVeriTeC.

- In each knowledge-store file, gold documents are listed first. To
  keep this order out of the rankings, documents are sorted by URL and
  then shuffled with a fixed seed for each claim.
- Archive-wrapped URLs were far more common among gold documents than
  among other documents, so retrievers only see a normalised URL.
- Duplicate URLs are merged, and documents with empty text are
  dropped.

### 4.5 Preregistration and chronology

The human-gold retrieval endpoint and its tests were preregistered
before held-out evaluation. The plan for comparing D with A was
written on 2026-09-29, before the held-out sample was drawn. It fixed
the prior weight at lambda = 1, named D versus A at R@10 as the single
primary test, and defined the secondary family of five tests. The
source-targeting family (H2, H3 and H4) was preregistered on
2026-09-30, before any held-out targeted retrieval had been scored,
with Holm correction across its three tests. The configuration,
scripts and rankings were then frozen and run.

The blind human primary-source endpoint specified in Addendum 2 was
not executed. Addendum 2 was written after the gold-endpoint results
were known, and it defined four tests and a frozen scorer for an
endpoint based on human labels of primary evidence.

The AI-labelled primary-evidence endpoint was introduced as a
documented deviation in Addendum 3. It was specified before any
held-out AI label existed, together with a rule that it could not
alter the preregistered verdict on the human-gold endpoint. The
AI-primary tests were pre-specified in Addendum 2 and carried over
unchanged by Addendum 3; they are not described as preregistered. The
endpoint was scored only after the project owner gave explicit
approval.

Claim-level AI breakdowns are post-hoc and exploratory.

## 5 Retrieval and Authority-Aware Systems

### 5.1 Relevance retrieval

The relevance baselines are BM25 over the document text and dense
retrieval with the all-MiniLM-L6-v2 encoder. The hybrid system (A)
merges the two rankings by reciprocal rank fusion with k = 60. Every
reranking system starts from the top 100 documents of this hybrid
ranking.

### 5.2 Authority-aware reranking

A reranker gives each document its relevance score, min-max
normalised within the candidate pool, plus a weighted prior:

    score = minmax(relevance within pool) + lambda * prior(url)

For the held-out evaluation the weight lambda was fixed at 1.

### 5.3 Generic credibility (B)

The generic credibility prior depends only on the kind of domain, so
it is identical for every claim. Government and intergovernmental
domains receive 1.0, academic domains 0.8, major news outlets 0.6,
reference sites 0.5, unknown domains 0.3, and platforms and blogs
0.2.

### 5.4 Heuristic authority (C)

The heuristic authority prior takes the larger of two values. One is
the generic prior, with a penalty for government domains of other
countries. The other is a claim-specific rule, which fires when a
domain or social-media handle matches an entity named in the claim or
in the speaker field, or when the domain belongs to the government of
the claim's country.

### 5.5 LLM authority (D)

The LLM authority predictor, called L+Wctx, is Claude Opus 5.5 used
without tools and without web access. For every claim it receives the
claim text, the speaker, the claim date and the country, along with
Wikidata facts about the entities in the claim. These Wikidata facts
were collected in 2026. The predictor returns a ranked list of the
three publishers it judges most authoritative for the claim, each
with publisher keys such as a registered domain or a platform handle.
The prior is 1 for a document whose publisher key matches a predicted
key and 0 for any other document.

### 5.6 Source targeting (E)

Source targeting fetches documents directly from the predicted
publishers. For every predicted publisher, the system sends a
site-restricted query to the claim's knowledge store. It keeps only
documents whose publisher key matches and ranks them by BM25 and dense
scores computed on that subset. The output is ordered authority-first:
all documents of the first predicted publisher come before those of
the second, and those come before the documents of the third. Within
each publisher, the BM25 and dense rankings are merged by reciprocal
rank fusion. The system keeps the top M = 10 targeted documents.

### 5.7 Combined systems, control and oracle

- System F takes the union of the hybrid top 100 and the targeted top
  10 and merges them by reciprocal rank fusion.
- System G reranks the F pool with the LLM authority prior, again with
  lambda = 1.
- The size-matched control (Ctrl) takes the hybrid top 100 plus as
  many further hybrid documents as F adds through targeting. This
  separates the effect of targeting from the effect of simply going
  deeper in the hybrid ranking.
- The oracle (H) runs the same pipeline with publisher keys taken from
  all human gold URLs. It uses gold information by design and serves
  only as a diagnostic upper bound.

### 5.8 Selection of the targeting configuration

The targeting configuration was selected on the development sample
from 18 candidate settings, using a selection rule that was written in
code before the comparison was run. The selected setting uses the
claim text as the query, authority-first ordering and M = 10. The
selection rule averaged G's gold R@10 with G's primary-evidence R@10.
The primary-evidence labels used for this were AI-generated (Claude)
development pilot labels, so the targeting configuration was partly
tuned on Claude-generated labels.

**Table 0. System identifiers used in all tables.**

| ID | System |
|---|---|
| A | Hybrid |
| B | Hybrid + generic credibility |
| C | Hybrid + heuristic authority |
| D | Hybrid + LLM authority |
| E | Source-targeted |
| F | Hybrid + source-targeted |
| G | Hybrid + source-targeted + LLM authority |
| Ctrl | Size-matched hybrid control |
| H | Oracle (uses gold by design; diagnostic only) |

## 6 Evaluation

### 6.1 Metrics

R@K is the share of claims for which at least one reachable gold
document appears among the top K results. MRR@100 is the mean
reciprocal rank of the first reachable gold document within the top
100 results. Pool coverage is the share of claims whose candidate pool
contains at least one reachable gold document.

### 6.2 Statistical tests

Paired comparisons use the two-sided exact McNemar test on per-claim
outcomes. Confidence intervals for differences are paired bootstrap
95% intervals based on 10,000 resamples. Within each family of tests,
p-values are adjusted by the Holm method.

### 6.3 Endpoints

The human-gold endpoint counts all reachable gold documents of the 167
gold-reachable claims. It is the preregistered primary evaluation.

The AI-labelled primary-evidence endpoint counts only gold documents
from publishers that an AI model labelled as primary. It covers a
conditional subset of 72 claims and is reported in Section 9 as an
exploratory, supporting analysis.

## 7 Results

### 7.1 Human-gold retrieval

Tables 1a and 1b show how well each system retrieves human gold
evidence on the 167 held-out claims that have at least one reachable
gold document.

**Table 1a. Human-gold retrieval, held-out set (n = 167): R@1 to R@20.**

| ID | R@1 | R@5 | R@10 | R@20 |
|---|---:|---:|---:|---:|
| A | 0.060 | 0.156 | 0.251 | 0.383 |
| B | 0.024 | 0.174 | 0.263 | 0.383 |
| C | 0.030 | 0.186 | 0.275 | 0.407 |
| D | 0.066 | 0.198 | 0.293 | 0.437 |
| E | 0.060 | 0.138 | 0.180 | 0.180 |
| F | 0.060 | 0.204 | 0.287 | 0.407 |
| G | 0.060 | 0.174 | 0.246 | 0.401 |
| Ctrl | 0.060 | 0.156 | 0.251 | 0.383 |
| H | 0.479 | 0.754 | 0.868 | 0.880 |

**Table 1b. Human-gold retrieval, held-out set (n = 167): R@50,
R@100, MRR@100 and pool coverage.**

| ID | R@50 | R@100 | MRR@100 | Pool coverage |
|---|---:|---:|---:|---:|
| A | 0.563 | 0.671 | 0.125 | 0.671 |
| B | 0.569 | 0.671 | 0.099 | 0.671 |
| C | 0.569 | 0.671 | 0.109 | 0.671 |
| D | 0.581 | 0.671 | 0.138 | 0.671 |
| E | 0.180 | 0.180 | 0.091 | 0.180 |
| F | 0.617 | 0.695 | 0.141 | 0.701 |
| G | 0.611 | 0.695 | 0.128 | 0.701 |
| Ctrl | 0.563 | 0.671 | 0.125 | 0.677 |
| H | 0.886 | 0.886 | 0.602 | 0.886 |

Leaving the oracle aside, D has the highest R@10 (0.293) and the
highest R@20 (0.437). F, not D, has the highest R@5, with 0.204
compared with 0.198 for D. F also has the highest R@50 (0.617) and the
highest MRR@100 (0.141). F and G share the highest R@100 (0.695) and
the highest pool coverage (0.701).

The oracle is far ahead of every other system, which shows how much
room there would be if the authoritative publishers were known
exactly. Because the oracle relies on gold information, it is not an
achievable target.

### 7.2 Preregistered tests

**Table 2. Preregistered held-out tests on the human-gold endpoint.**

| Test | Wins / losses | Exact p | Holm p | Delta | 95% CI |
|---|---|---:|---:|---:|---|
| D vs A, R@10 (primary) | +13 / -6 | 0.167 | 0.167 | +0.042 | [-0.006, 0.096] |
| D vs A, R@5 | +11 / -4 | 0.118 | 0.373 | +0.042 | [-0.006, 0.090] |
| D vs A, R@20 | +12 / -3 | 0.035 | 0.176 | +0.054 | [0.012, 0.102] |
| D vs B, R@10 | +16 / -11 | 0.442 | 0.884 | +0.030 | [-0.030, 0.090] |
| F vs Ctrl, pool coverage | +5 / -1 | 0.219 | 0.555 | +0.024 | [0.000, 0.054] |
| G vs D, R@10 | +10 / -18 | 0.185 | 0.555 | -0.048 | [-0.108, 0.012] |
| G vs A, R@10 | +21 / -22 | 1.000 | 1.000 | -0.006 | [-0.084, 0.072] |

The comparison of D with A at R@10 was the single preregistered
primary test, so its Holm-adjusted p-value is the same as its exact
p-value.

No preregistered held-out comparison on the human-gold endpoint is
statistically significant.

In the primary comparison, D placed gold evidence in the top 10 for
13 claims on which A did not, while A did so for 6 claims on which D
did not. The difference of +0.042 is directional, and its confidence
interval includes zero. On the development sample, the same
comparison had given a difference of +0.101, with 15 wins and 5
losses. The observed difference therefore decreased from +0.101 on the
development data to +0.042 on the held-out set.

D has a higher observed R@10 than the generic credibility system B
(0.263) and the heuristic authority system C (0.275). The
preregistered comparison of D with B is not statistically significant,
and no preregistered statistical comparison of D with C was carried
out.

The full targeting pipeline G did not carry over from the development
data to the held-out set. On the development sample, G had reached
R@10 = 0.354, against 0.242 for hybrid retrieval. On the held-out set,
G does not improve on A at R@10 (0.246 against 0.251, with 21 wins and
22 losses), and it falls behind D (10 wins and 18 losses).

Targeting does widen the candidate pool. F and G reach a pool
coverage of 0.701, against 0.671 for the hybrid pool. The coverage
advantage of F over the size-matched control (5 wins and 1 loss) is
small and not statistically significant.

### 7.3 Accuracy of authority prediction

We also measured how often the predictor named the publisher of at
least one human gold URL. Over the 192 held-out claims that have web
gold, the top-ranked predicted publisher matched in 56 claims, a top-1
accuracy of 0.292. At least one of the three predicted publishers
matched in 75 claims, a top-3 accuracy of 0.391. The gold URLs also
include news articles and fact-checking pages, so these figures are a
lower bound on authority accuracy.

### 7.4 Memorisation probe

A probe checked whether the predictor's accuracy depends on
recognising particular claims. Top-3 accuracy hardly changed when the
claim was paraphrased (0.396) or when the metadata was removed
(0.401). It dropped to 0.307 when the names of people, places and
organisations were masked. The predictor therefore relies on named
entities, which the task legitimately requires. The probe does not
show that memorisation is absent.

## 8 Failure Analysis

This section describes the ways in which the systems fail. It is a
descriptive analysis of the frozen rankings and does not prove why any
individual failure occurred. All flags are defined with respect to
the full set of reachable gold documents for the 167 gold-reachable
claims.

### 8.1 Wrong authority

For 102 of the 167 claims, none of the three predicted publishers
matches any gold publisher. On these 102 claims, gold evidence reaches
the top 10 for 30 claims under hybrid retrieval (A), for 26 claims
under the authority reranker (D) and for 10 claims under the full
targeting pipeline (G). When the predicted authority is wrong, the
prior cannot help, and targeted retrieval fills the top ranks with
documents from the wrong publishers. Wrong authority prediction is
therefore a major bottleneck for every authority-aware system in this
study.

### 8.2 A correct authority is not enough

For 56 claims, at least one predicted publisher has a reachable gold
document. G places gold evidence in the top 10 for 31 of these claims
and misses it for the other 25. In 22 of these 25 misses, the
authority's gold document is outside the targeted candidate pool. In
the remaining 3 misses, the document is in the pool but ranked below
position 10.

The hybrid pool has a related problem. For 55 of the 167 claims, the
hybrid top 100 contains no gold document at all. Targeted retrieval
brings a gold document into G's top 100 for 5 of these claims, and
all 5 are also hits at rank 10 or better.

Identifying the authority and retrieving its specific document are
therefore separate problems. The second depends on how the targeted
queries are built and on whether the document exists in the
collection.

### 8.3 Failure of source targeting

G loses to D on 18 claims at gold R@10. In every one of these 18
claims, at least one targeted document appears in G's top 10, and on
average 8.89 of the 10 top positions are taken by targeted documents.
The predicted authority was correct for only 2 of the 18 claims. With
authority-first ordering and lambda = 1, targeted documents push
aside relevant evidence that hybrid retrieval had already ranked
highly. Because wrong predictions are common, aggressive targeting
turns many of them into lost recall.

### 8.4 Multiple legitimate authorities

The predictor labels 169 of the 200 held-out claims as having multiple
legitimate authorities, so the label barely separates one claim from
another. Among the 167 gold-reachable claims, 85 have reachable gold
documents from two or more publishers. Table 3 groups the
gold-reachable claims by the predictor's own label.

**Table 3. Gold hits at rank 10 by the predictor's authority label
(n = 167).**

| Predictor label | Claims | G hits | D hits |
|---|---:|---:|---:|
| Multiple legitimate authorities | 144 | 35 | 44 |
| Single clear authority | 20 | 6 | 5 |
| No clear authority | 3 | 0 | 0 |

These labels are model outputs that have not been validated. When
several publishers are legitimate, the gold evidence may come from a
publisher that the predictor did not place first.

### 8.5 Missing evidence

Of the 422 gold URLs, 117 have empty text in this project's extraction
of the knowledge store. Every recall figure in this paper therefore
depends on the evidence actually being present in the collection.

### 8.6 Provenance and duplication

The project's provenance analyses use word 5-gram containment to
detect heuristic apparent duplication/derivation between documents.
They are documented as heuristics and not as verified provenance. They
covered the 120 development claims only and cannot be linked to the
held-out claims. They therefore give no provenance conclusion for the
held-out evaluation, and we do not claim that any documents were
copied, syndicated, derived or independent.

## 9 AI-Primary Evidence Analysis

### 9.1 Purpose

Gold R@K treats any gold document as a hit, including news articles
and fact-checking pages that are secondary sources for the claim.
Because the methods in this study aim at first-hand evidence, a
measure that concentrates on primary evidence is also of interest.
The blind human primary-source endpoint specified in Addendum 2 was
not executed. As the documented deviation in Addendum 3, we report
AI-labelled primary-evidence recall instead. This endpoint is
exploratory and supporting. It does not replace the human-gold
endpoint and cannot change its preregistered conclusion.

### 9.2 AI-generated evidence-role labels

Claude Opus 5.5 gave each of the 422 held-out gold URLs one
evidence-role label: primary, secondary, derived or unclear.

- Every URL was labelled in a separate call, without tools and without
  web access.
- For each URL, the annotator saw the claim text, speaker, date and
  country; the URL, domain, page title and snippet; and the AVeriTeC
  gold question and answer for which the page had been cited. It did
  not see the full page.
- The annotator never saw rankings, predictions, results, the verdict
  or any other annotation.
- The labels comprised 140 primary, 215 secondary, 50 derived and 17
  unclear.

The AI-primary documents of a claim are those reachable gold documents
whose publisher matches the publisher of at least one gold URL
labelled primary. The frozen scorer and the frozen rankings were used
unchanged.

**AI-annotation consistency.** In a pilot on 34 URLs, the same model
and prompt were run twice. The two runs agreed on 94.1% of the
four-way labels (kappa = 0.906) and on 100% of the choices between
primary and the other labels (kappa = 1.000). These numbers measure
the self-consistency of a single model. They do not measure human
reliability.

### 9.3 Denominator

- 192 claims were annotated.
- 101 claims have at least one URL labelled primary.
- 100 claims have at least one AI-primary publisher key that the
  frozen scorer can use. For the remaining claim, the only URL
  labelled primary is malformed.
- 72 claims have at least one reachable AI-primary gold document.

The other 120 claims do not enter the conditional AI-primary
endpoint. For 92 of them there is no usable AI-primary publisher key:
91 have no URL labelled primary, and 1 has only the malformed URL. For
the remaining 28, some URLs were labelled primary, but every
corresponding document is empty. These 120 claims are not retrieval
failures. The endpoint is conditional on 72 of the 192 annotated
claims and does not represent the full held-out set.

### 9.4 Shared-model caveat

Claude Opus 5.5 produced both the authority predictions used by
systems D, E, F and G and the evidence-role labels used to score this
endpoint. A hit for an authority-aware system therefore partly
reflects reaching a publisher that the same model regards as
first-hand, and beliefs shared inside the model may contribute to any
association observed here.

The 72-claim subset is also enriched for claims on which the
predictor matched a gold publisher. It contains 53 of the 65
gold-reachable claims for which a predicted publisher matches a gold
publisher, but only 19 of the 102 claims for which no predicted
publisher matches.

For these reasons, the AI-labelled primary-evidence analysis is
exploratory and supporting evidence, not independent ground truth.
Addendum 3 also specified a circularity diagnostic and a cross-family
labelling check, and neither has been run.

### 9.5 Results

**Table 4a. AI-labelled primary-evidence recall (n = 72): R@1 to R@10.**

| ID | R@1 | R@3 | R@5 | R@10 |
|---|---:|---:|---:|---:|
| A | 0.028 | 0.042 | 0.056 | 0.097 |
| B | 0.028 | 0.069 | 0.167 | 0.181 |
| C | 0.028 | 0.069 | 0.153 | 0.181 |
| D | 0.097 | 0.167 | 0.236 | 0.278 |
| E | 0.139 | 0.236 | 0.306 | 0.403 |
| F | 0.083 | 0.222 | 0.278 | 0.375 |
| G | 0.125 | 0.250 | 0.319 | 0.431 |
| Ctrl | 0.028 | 0.042 | 0.056 | 0.097 |
| H | 0.250 | 0.375 | 0.528 | 0.694 |

**Table 4b. AI-labelled primary-evidence recall (n = 72): R@20,
MRR@100 and pool coverage.**

| ID | R@20 | MRR@100 | Pool coverage |
|---|---:|---:|---:|
| A | 0.139 | 0.051 | 0.458 |
| B | 0.278 | 0.081 | 0.458 |
| C | 0.292 | 0.081 | 0.458 |
| D | 0.306 | 0.151 | 0.458 |
| E | 0.403 | 0.208 | 0.403 |
| F | 0.444 | 0.180 | 0.597 |
| G | 0.458 | 0.215 | 0.597 |
| Ctrl | 0.139 | 0.051 | 0.458 |
| H | 0.722 | 0.360 | N/A |

The oracle's pool coverage is not available because its candidate
pool was not saved.

**Table 5. Tests on the AI-primary endpoint, pre-specified in
Addendum 2 and carried over unchanged by Addendum 3.**

| Test | Wins / losses | Exact p | Holm p |
|---|---|---:|---:|
| D vs A, R@10 | 14 / 1 | 0.00098 | 0.00294 |
| G vs A, R@10 | 25 / 1 | < 0.001 | < 0.001 |
| G vs D, R@10 | 13 / 2 | 0.00739 | 0.00739 |
| F vs Ctrl, pool coverage | 10 / 0 | 0.00195 | 0.0039 |

These tests describe an association within the conditional
AI-primary endpoint. Because the evidence-role labels were generated
by the same model family that predicts authority, they do not
constitute independent validation of authority-aware retrieval.

**Low-confidence sensitivity.** Dropping labels marked as low
confidence removes 2 claims. Both were already outside the 72-claim
subset, so all stored metrics and tests stay the same.

### 9.6 Post-hoc descriptive breakdown

This subsection is post-hoc and exploratory.

**Table 6. AI-primary hits at rank 10 for pairs of systems (n = 72).**

| Comparison | First system only | Second system only | Both | Neither |
|---|---:|---:|---:|---:|
| D vs A | 14 | 1 | 6 | 51 |
| G vs A | 25 | 1 | 6 | 40 |
| G vs D | 13 | 2 | 18 | 39 |

Every claim on which D or G placed an AI-primary document in the top
10 while A did not is a claim for which a reachable gold document came
from a predicted publisher. This is partly expected by construction,
since both the authority prior and targeted retrieval act only on
documents from predicted publishers. The breakdown shows where the
gains occurred. It does not establish that authority prediction is
responsible for better retrieval in general.

The subset contains 51 claims for which a predicted publisher has a
reachable gold document. On these claims, D ranked the AI-primary
document above A in 20 cases, below A in 2 cases and at the same
position in 29 cases. G ranked it above A in 31 cases, below A in 3
cases and at the same position in 17 cases.

G places an AI-primary document in the top 10 that D misses for 13
claims. For 10 of these claims, no AI-primary document was in the
hybrid top 100, so the document entered G's ranking only through
targeted retrieval. Since the targeted queries are built from the
predicted publishers, this design cannot separate the contribution of
authority prediction from that of targeting.

Targeting can also displace documents that D had already found. For
claims 268 and 485, D ranked the AI-primary document first and third
respectively, while G ranked it eleventh in both cases. In those two
claims, 10 and 7 of G's top 10 positions were occupied by targeted
documents.

The subset also contains 18 claims for which a predicted publisher
has a reachable gold document, G misses gold evidence at rank 10, and
the authority's document is outside the targeted pool. None of the
three systems places an AI-primary document in the top 10 for these
claims. Only one of them, claim 262, has an AI-primary document
anywhere in the top 100: at rank 79 under A, rank 79 under D and rank
89 under G.

### 9.7 AI-generated claim-level categories

A separate claim-level annotation by the same model assigned each
claim to an authority category. Table 7 groups the 72 claims by these
AI-generated categories.

**Table 7. AI-primary hits at rank 10 by AI-generated claim-level
category (n = 72).**

| Category | Claims | A hits | D hits | G hits |
|---|---:|---:|---:|---:|
| Multiple legitimate authorities | 54 | 7 | 16 | 25 |
| Single primary | 16 | 0 | 4 | 6 |
| Unclear | 2 | 0 | 0 | 0 |

These categories are AI-generated. A grouping based on the
evidence-level labels gives a different split, with 56 claims that
have a single AI-primary publisher and 16 that have several. Because
the two groupings disagree and the groups are small, we draw no
conclusion about differences between categories.

## 10 Discussion

### 10.1 Why is the authority prior only directionally better?

Only 19 claims change outcome between A and D, which gives the
primary comparison little statistical power. D can only reorder the
hybrid top 100, and that pool contains gold evidence for 67.1% of the
claims. The prior also relies on predicted publishers that match no
gold publisher for 102 of the 167 claims. Finally, the observed
difference fell from +0.101 on the development data to +0.042 on the
held-out set.

### 10.2 Why do the two endpoints order G and D differently?

G is below D on the human-gold endpoint but above D on the
AI-labelled endpoint. The two endpoints measure different things on
different sets of claims. Human-gold R@K also rewards secondary pages,
which hybrid retrieval finds well, whereas AI-labelled
primary-evidence recall rewards only documents from publishers that
the AI labelled as primary. All 10 of G's human-gold wins over D lie
inside the 72-claim subset, but only 5 of its 18 human-gold losses
do. The AI-labelled result does not overturn or replace the
preregistered conclusion on the human-gold endpoint.

### 10.3 What does source targeting add?

Targeting widens the candidate pool. Gold pool coverage rises from
0.671 to 0.701, and AI-primary pool coverage rises from 0.458 to
0.597. The system can therefore reach documents that relevance
retrieval misses. The price is lost recall at the top of the ranking
when the predicted authority is wrong, or when targeted pages crowd
out the most relevant document.

### 10.4 Why can a correct authority still fail?

The authority's specific document may be missing from the targeted
pool, which happened in 22 of the 25 relevant failures. The document
may be empty in the collection. It may also be outranked by other
pages from the same publisher.

### 10.5 Why are multiple legitimate authorities difficult?

The predictor marks most claims as having several legitimate
authorities, so the label carries little information. Authority-first
ordering commits to the first predicted publisher, while the gold
evidence may come from another legitimate publisher.

### 10.6 What does the 72-claim subset tell us?

The subset shows where gains occurred among claims that have a
reachable AI-labelled primary document, namely on claims whose gold
evidence includes a page from a predicted publisher. It says little
about the other 120 annotated claims.

### 10.7 Why does the shared model matter?

The annotator and the predictor share a single model's view of what
counts as first-hand evidence. Agreement between them is therefore
not independent evidence that the retrieved documents are truly
primary. The enrichment of matched-authority claims in the subset is
consistent with this concern, although it does not measure it.

### 10.8 What would an independent annotation test?

An independent human annotation of primary evidence would test
whether the association between authority-aware ranking and the
retrieval of first-hand evidence holds when first-hand status is
judged independently of the predictor. It could reuse the same frozen
rankings and the same frozen scorer.

## 11 Limitations

### 11.1 Main limitations

- No independent human annotation of primary evidence was completed.
  The human primary-source endpoint was specified but not executed.
- The AI-generated evidence-role labels come from the same model
  family as the authority predictor.
- The AI-primary endpoint has a conditional denominator of 72 out of
  192 annotated claims.
- Evidence is often missing. Of the 422 gold URLs, 117 are empty, and
  28 claims do not enter the AI-primary endpoint because their
  AI-primary documents are empty.
- Multiple legitimate authorities are common, and different labelling
  sources categorise them inconsistently.
- Source targeting did not carry over from the development data and
  can reduce recall.
- The evaluation is specific to AVeriTeC and runs inside its pre-built
  knowledge store.
- The held-out sample is fairly small, with 167 gold-reachable claims
  and 72 claims in the AI-primary analysis.
- The provenance analyses cover development claims only and cannot be
  linked to held-out claims.
- The study contains no open-web or live retrieval evaluation.

### 11.2 Threats to validity

**Internal validity.** Two known leaks in the knowledge store were
fixed before evaluation: gold documents listed first in each file, and
archive-wrapped gold URLs. The knowledge store was built partly from
queries derived from the gold questions and answers. The orchestrating
session had seen gold data, while the predictor and the AI annotator
ran in isolated contexts without it. The AI annotator did, however,
see the gold question and answer linked to each page.

**Construct validity.** Human-gold R@K counts secondary documents as
hits. AI-primary documents include any reachable gold document from an
AI-primary publisher. Authority accuracy measured against all gold
publishers is a lower bound. The hand-written domain lists of the
generic prior overlap some development gold domains.

**Temporal validity.** The Wikidata context given to the predictor was
collected in 2026 and is not limited to information that was
available on each claim's date.

**Statistical and procedural validity.** The targeting configuration
was partly tuned on AI-generated (Claude) development pilot labels.
The AI-primary endpoint is a documented deviation that replaced a
human endpoint specified after the gold-endpoint results. Several
endpoints are reported, and each family of tests is Holm-corrected
separately.

**External validity.** All conclusions apply to this frozen
AVeriTeC-based evaluation. Retrieval took place in the AVeriTeC
knowledge store, without live or open-web retrieval, so whether the
results generalise to other settings remains untested. The
memorisation probe relies on the model's self-reports and on a proxy
based on fact-checker domains, so it cannot rule out memorised
knowledge of which outlets covered a story.

## 12 Conclusion

This study asked whether identifying the source that is
authoritative for a particular claim improves evidence retrieval. In a
frozen AVeriTeC held-out evaluation with preregistered tests, an
authority prior predicted by a language model improved human-gold
recall only directionally, and an authority-first source-targeting
pipeline did not carry over from the development data.

The failure analysis accounts for much of this outcome. The predicted
authority is often wrong. A correct prediction does not ensure that
the authority's document is in the candidate pool. Aggressive
targeting can displace relevant evidence.

An exploratory analysis based on AI-generated evidence-role labels
found higher AI-labelled primary-evidence recall for the
authority-aware systems on a conditional subset of 72 claims. In a
post-hoc breakdown, these gains occurred on claims whose gold evidence
included a document from a predicted publisher. Because one model
family produced both the labels and the predictions, this is
supporting evidence and not independent validation.

The main open problems are better authority prediction, better
collection coverage and an independent judgement of what counts as
primary evidence. Whether these findings hold outside this frozen
AVeriTeC-based evaluation remains untested.

## References

Akhtar, M., Aly, R., Chen, Y., Deng, Z., Schlichtkrull, M.,
Whitehouse, C., and Vlachos, A. (2025). The 2nd Automated Verification
of Textual Claims (AVeriTeC) Shared Task: Open-weights, Reproducible
and Efficient Systems. In Proceedings of the Eighth Fact Extraction
and VERification Workshop (FEVER), pages 201-223, Vienna, Austria.

Aly, R., Guo, Z., Schlichtkrull, M., Thorne, J., Vlachos, A.,
Christodoulopoulos, C., Cocarascu, O., and Mittal, A. (2021).
FEVEROUS: Fact Extraction and VERification Over Unstructured and
Structured information. NeurIPS 2021 Datasets and Benchmarks Track.
arXiv:2106.05707.

Biswas, M. B., and Uzuner, O. (2026). Contradiction to Consensus: Dual
Perspective, Multi Source Retrieval Based Claim Verification with
Source Level Disagreement using LLM. arXiv:2602.18693.

Deng, B., Wang, W., Zhu, F., Wang, Q., and Feng, F. (2025). CrAM:
Credibility-Aware Attention Modification in LLMs for Combating
Misinformation in RAG. AAAI 2025. arXiv:2406.11497.

Dong, X. L., Berti-Equille, L., and Srivastava, D. (2009). Integrating
conflicting data: the role of source dependence. PVLDB 2(1):550-561.
https://doi.org/10.14778/1687627.1687690

Dong, X. L., Gabrilovich, E., Murphy, K., Dang, V., Horn, W.,
Lugaresi, C., Sun, S., and Zhang, W. (2015). Knowledge-Based Trust:
Estimating the Trustworthiness of Web Sources. arXiv:1502.03519.

Ge, Z., Wu, Y., Chin, D. W. K., Lee, R. K.-W., and Cao, R. (2025).
Resolving Conflicting Evidence in Automated Fact-Checking: A Study on
Retrieval-Augmented LLMs. IJCAI 2025 (AI and Social Good track).
arXiv:2505.17762.

Gong, S., Sinnott, R. O., Qi, J., Paris, C., Nakov, P., and Xie, Z.
(2026). Multi-Sourced, Multi-Agent Evidence Retrieval for
Fact-Checking. arXiv:2603.00267.

Jiang, Y., Bordia, S., Zhong, Z., Dognin, C., Singh, M., and Bansal, M.
(2020). HoVer: A Dataset for Many-Hop Fact Extraction And Claim
Verification. Findings of EMNLP 2020. arXiv:2011.03088.

Li, Y., and Zubiaga, A. (2025). RAVE: Retrieval and Scoring Aware
Verifiable Claim Detection. arXiv:2509.15793.

Pan, R., Cao, B., Lin, H., Han, X., Zheng, J., Wang, S., Cai, X., and
Sun, L. (2024). Not All Contexts Are Equal: Teaching LLMs
Credibility-aware Generation. EMNLP 2024.

Ram, A., Bayiz, Y. E., Amini, A., Munir, M., and Marculescu, R.
(2024). CrediRAG: Network-Augmented Credibility-Based Retrieval for
Misinformation Detection in Reddit. arXiv:2410.12061.

Schlichtkrull, M., Guo, Z., and Vlachos, A. (2023). AVeriTeC: A
Dataset for Real-world Claim Verification with Evidence from the Web.
NeurIPS 2023 Datasets and Benchmarks Track. arXiv:2305.13117.

Schlichtkrull, M., Chen, Y., Whitehouse, C., Deng, Z., Akhtar, M.,
Aly, R., Guo, Z., Christodoulopoulos, C., Cocarascu, O., Mittal, A.,
Thorne, J., and Vlachos, A. (2024). The Automated Verification of
Textual Claims (AVeriTeC) Shared Task. In Proceedings of the Seventh
Fact Extraction and VERification Workshop (FEVER). arXiv:2410.23850.

Tan, J. (2026). Verification-Notebook Learning for Source-Aware
Multimodal Misinformation Detection. arXiv:2607.23581.

Tariq, A., and Kementchedjhieva, Y. (2026). REVEAL:
Retrieval-Enhanced Verification for Multimodal Fact-Checking. In
Proceedings of the Ninth Fact Extraction and VERification Workshop
(FEVER), pages 108-113, Rabat, Morocco.

Thorne, J., Vlachos, A., Christodoulopoulos, C., and Mittal, A.
(2018). FEVER: a large-scale dataset for Fact Extraction and
VERification. NAACL 2018. arXiv:1803.05355.

Warren, G., Shklovski, I., and Augenstein, I. (2025). Show Me the
Work: Fact-Checkers' Requirements for Explainable Automated
Fact-Checking. CHI 2025. arXiv:2502.09083.

Yang, S., Yu, Z., Ying, Z., Dai, Y., Wang, G., Lan, J., Xu, J., Li,
J., and Ngai, E. C. H. (2025). RAMA: Retrieval-Augmented Multi-Agent
Framework for Misinformation Detection in Multimodal Fact-Checking.
arXiv:2507.09174.

Yao, Z., Zhang, H., and Bi, K. (2026). AuthorityBench: Benchmarking
LLM Authority Perception for Reliable Retrieval-Augmented Generation.
arXiv:2603.25092.
