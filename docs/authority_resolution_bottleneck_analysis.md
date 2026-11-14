# Authority-Resolution Bottleneck Analysis

*2026-10-28. Diagnostic report and proposal: nothing in the pipeline was changed and no experiment was re-run.*

**Status of everything in this document: exploratory / diagnostic. Not preregistered.** Every number
labelled *oracle* or *ceiling* uses gold by design and is **not** a retrieval result. Deployable
systems are only the frozen A–G; no new deployable system was scored on the held-out set.

| Label used below | Meaning |
|---|---|
| **[Measured]** | Computed from frozen artifacts by `experiments/authority_bottleneck_diagnostics.py` (or quoted from a frozen result file, cited) |
| **[Oracle]** | Uses gold publishers or gold URLs; an upper bound, never a system |
| **[Heuristic]** | Depends on a hand-written domain classification (see §3.1); counts are approximate |
| **[AI-generated]** | Uses the existing MODEL_GENERATED role labels (Claude Opus 5.5, same family as the predictor); descriptive only, circular |
| **[Hypothesis]** | Not testable with existing data |
| **[Not verified]** | Could not be checked from the repository |

## Provenance of the new analysis

- **Script:** `experiments/authority_bottleneck_diagnostics.py`. It is read-only, makes 0 LLM calls,
  re-runs no retrieval, and refuses to overwrite its output directory.
- **Outputs:** `results/authority_bottleneck_diagnostics/`, with these SHA-256 hashes:
  - `summary.json`: `4188fcf6…`
  - `per_claim.csv`: `c9b93e64…`
  - `gold_urls.csv`: `7d79d968…`
- **What `summary.json` records:** the SHA-256 of the script (`66a962c0…`, raw CRLF file), of every
  imported module, and of every input artifact.
- **Reproduction gate (all checks passed).** Before any analysis, the script reproduces:
  - the stored reachable-gold counts (167 claims, 305 docs, 422 URLs) and every per-claim
    `n_gold_reachable`;
  - every stored GoldR@{1,3,5,10,20} of systems A–H;
  - the exact stored top-100 order of system D for all 200 claims;
  - the exact stored targeted top-10 list of all 200 claims (so source targeting can be replayed
    offline from the frozen BM25 and dense rankings);
  - the Phase-1 oracle-publisher R@10 (0.659).
- **Data availability.** `data/raw/` (the knowledge-store extracts) is **not present** in this
  checkout. All analysis is reconstructed from the frozen *full* hybrid/BM25/dense rankings. These
  list every non-empty document of each claim's corpus, so gold ∩ ranking = reachable gold; the
  gate confirms this exactly.
- **Frozen files untouched.**
  - `git status` shows only the new script and its output directory.
  - The frozen held-out rankings hash matches the preregistration (`9105a5da…`).
  - `validation_heldout.py`, `source_targeted.py`, `source_targeted_eval.py`,
    `score_heldout_primary.py`, `score_ai_primary.py` and `ai_annotate.py` match their
    preregistered SHA-256 **after CRLF→LF normalisation**. The Windows checkout converted line
    endings, so raw-byte hashes differ. Note that `ai_annotate.py`'s hash gate would refuse to run
    on this checkout, which is harmless because nothing should be annotated.
- **Not touched:** the frozen rankings, predictions, AI annotations, preregistrations and scorer.
  No AI-primary recall was computed. The existing MODEL_GENERATED evidence-role labels were only
  counted descriptively (§3.9).

---

## 1. Verified description of the existing pipeline

I verified this by reading the code, not the notes. Where the notes and the code differ, I say so.

### 1.1 Corpus and candidate generation

- **Corpus.** Each claim's AVeriTeC dev knowledge store (KS) is deduplicated by `normalize_url` and
  shuffled with a per-claim seed. Empty-text documents are dropped (`baseline_retrieval.retrieval_corpus`).
  - Corpus size: median 782 docs per claim (range 417–1,639) [Measured].
  - The retriever sees only `{url_norm, text}`.
- **BM25:** `bm25s`, English stop words, query = claim text.
- **Dense:** `all-MiniLM-L6-v2` over the first 1,000 characters, 128 tokens.
- **Hybrid:** RRF (k = 60) over the *full* BM25 and dense lists.
- **Candidate pool for reranking:** hybrid top-100 (`validation_heldout.POOL`). **This is the only
  candidate-generation step besides source targeting.**

### 1.2 How authority is assigned to a source

Authority is assigned **per publisher key, not per document**. The key is computed by
`cand_key(url) = social_key(url) or org_domain(url)`:

- the registered domain (eTLD+1);
- `gov.uk` subdomains are collapsed to `gov.uk` unless they are their own registrable domain;
- `x.com` maps to `twitter.com`;
- for twitter/facebook/instagram/youtube/linkedin, the key is `platform/handle`.

Four authority signals exist. They are **separate systems that are never combined**.

| Signal | Code | Inputs | Output | Used in |
|---|---|---|---|---|
| Generic credibility prior | `authority_retrieval.generic_prior` | URL only | gov/intergov 1.0, academic 0.8, major news 0.6, reference 0.5, unknown 0.3, platform 0.2 | B |
| Heuristic claim prior | `authority_retrieval.full_prior` | URL, spaCy entities of the claim plus the speaker, `location_ISO_code` | max(generic with a 0.6 foreign-jurisdiction penalty, 1.0 if the domain/handle matches a claim entity or is a gov domain of the claim's country) | C |
| LLM authority predictor (L+Wctx) | `authority_resolution.USER/SYSTEM`, `call` | claim, speaker, date, ISO, Wikidata facts for spaCy entities; Claude Opus 5.5, no tools | top-3 publishers with domain and social account | D, E, F, G |
| Wikidata-only and name-grounding (W, L+Wgnd) | `wikidata_authority.py`, `authority_resolution.ground_names` | entity mentions / predicted names | official sites (P856) and handles | dev study only; **not** used in any held-out system |

**How the heuristic and the LLM interact [Measured, code]:**

- The only shared component is spaCy entity extraction (`claim_entities`). It feeds both the
  heuristic entity keys and the Wikidata context given to the LLM.
- No system combines the heuristic prior with the LLM prior.
- The LLM's prediction becomes a **binary** prior: 1 if `cand_key(url)` is in the union of the
  top-3 predicted keys (`pred_keys`), else 0.
- The LLM's `confidence`, `authority_situation`, `claim_kind`, rank order and `publisher_type` are
  **not used** by D (rank order *is* used by E/F/G, which apply authority-first ordering).

### 1.3 Source targeting (E, F, G)

`source_targeted.targeted_rank` runs offline.

1. **Site filter:** keep corpus docs whose `cand_key` is one of the predicted keys.
2. **Order:** by authority rank (candidate 1's docs, then 2's, then 3's). Within one authority,
   order by RRF of BM25 and dense ranks.
3. **Truncation:** M = 10 (`FROZEN`).
4. **Fusion:** F = RRF(hybrid top-100, targeted top-10).
5. **Rerank:** G = F reranked with the binary LLM prior at λ = 1.

With `text_mode = claim` the "targeted query" text equals the claim, so the BM25 scores equal the
frozen BM25 ranking. This is why the gate can reproduce it exactly. **The "query" therefore does
not target an institution at all; only the site filter does.** The preregistration addendum also
notes that query wording barely mattered on dev.

### 1.4 Evidence ranking and top-k

- **B, C, D:** `minmax(hybrid score in top-100) + λ·prior`, λ = 1, stable sort. Because the
  min-max score lies in [0, 1], with a binary prior and λ = 1 **every prior-1 document outranks
  every prior-0 document.** D is therefore a hard publisher filter on the top-100 pool, with
  relevance order inside each group.
- **G:** the same rerank applied to the fused pool.
- **Top-k:** the first k URLs.
- **Metric:** hit-based R@k, i.e. whether at least one reachable gold doc is in the top k, over
  the 167 claims with reachable gold.

### 1.5 Implemented vs only proposed

| Implemented (verified in code and frozen results) | Only proposed or not run |
|---|---|
| BM25 / dense / hybrid; generic prior; heuristic entity+country prior; Wikidata context; L+Wctx predictor; binary key-match prior; offline site-filter targeting; RRF fusion; size-matched control; oracle H; memorisation probe; Phase 1/2 authority-quality ablations | graded or claim-conditioned authority *scores*; publisher alias / parent-organisation resolution; learned ranker; cross-encoder reranking; provenance-aware *ranking* |
| Shingle-based duplication heuristics and a verdict-level provenance aggregation probe (**dev only**) | Provenance on held-out; temporal module; open-web retrieval |
| AI-generated evidence-role labels (422 held-out URLs) | Human primary annotation (template unfilled); second annotator (pending); cross-family check (not run) |

**Discrepancies found between notes and code.**

1. **The generic prior has a rule gap [Measured].**
   - `is_gov("gov.uk")` is False: host `www.gov.uk` scores 0.3 while
     `assets.publishing.service.gov.uk` scores 1.0.
   - `canada.ca`, `hse.ie`, `ohchr.org`, `opcw.org` and `undocs.org` also score 0.3.
   - This affects **620 held-out corpus docs in 113 claims**, 7 of them reachable gold.
   - Frozen B and C are affected; D is not. The notes describe B as "gov/intergov 1.0", so this is
     an implementation deviation. It must not be fixed silently in the frozen code; it is recorded here.
2. **One gold URL is malformed [Measured].**
   - Claim 495's gold URL `https://web.archihttps://joebiden.com/clean-energy/` is not repaired by
     `strip_wayback`, so its publisher key becomes `archihttps`.
   - The page is absent from the corpus, so recall is unaffected, but oracle H receives a junk key.
3. The `authority_retrieval.py` docstring says λ = 0.25 is the headline. That was the dev
   pre-specification; the held-out freeze uses λ = 1. This is consistent with the preregistration,
   but the docstring is stale.

---

## 2. Recall ceiling and bottleneck decomposition

### 2.1 What the corpus allows [Measured]

| Quantity | Value |
|---|---|
| Held-out claims | 200 |
| … with ≥ 1 web gold URL | 192 (8 have none) |
| … whose web gold is all unreachable (absent from KS or empty text) | 25 |
| … with ≥ 1 reachable gold doc (**evaluation denominator**) | **167** |
| Gold URLs (unique per claim) | 422; 305 reachable, 117 unreachable |
| Unreachable gold that a looser canonicaliser would match to a corpus URL (case, m./amp., query, trailing index, tweet-handle-insensitive status ids) | **0** |

- **"Absent from the KS" vs "present but empty" [Not verified].** These cannot be separated
  without `data/raw/`.
- **Canonicalization is not where gold is lost.** No unreachable gold URL is rescued by looser URL
  matching, and only the one malformed URL above was found.

**Unrepresentable gold, by kind [Measured; publisher class Heuristic]:**

| Publisher class of the gold URL | Reachable |
|---|---|
| Social-media account posts | **6/28 (21%)** |
| Government / intergovernmental | **71/106 (67%)** |
| News-like | 122/146 (84%) |
| Reference | 18/18 |
| PDF (by extension or medium) | 25/38 (66%) |
| Gold URL archive-wrapped in AVeriTeC (link-rot proxy) | 97/151 (64%) |
| Not archive-wrapped | 208/271 (77%) |
| [AI-generated] labelled *primary* | **86/140 (61%)** |
| [AI-generated] labelled *secondary* | 170/215 (79%) |

The corpus systematically under-represents exactly the evidence an authority resolver is meant to
find: official pages, PDFs, and the claimant's own posts.

### 2.2 Three different ceilings (do not mix)

All values are at k = 1, 3, 5, 10, 20.

| Ceiling | Definition | R@1 | R@3 | R@5 | R@10 | R@20 |
|---|---|---|---|---|---|---|
| **Theoretical, evaluation definition** | any perfect ranker over the full corpus, n = 167 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Theoretical, over 192 web-gold claims | same, counting the 25 unrepresentable claims as misses | 0.870 | 0.870 | 0.870 | 0.870 | 0.870 |
| Theoretical, over all 200 claims | | 0.835 | 0.835 | 0.835 | 0.835 | 0.835 |
| Doc-level recall ceiling (share of a claim's gold docs findable in top-k), n = 167 | | 0.682 | 0.986 | 1.000 | 1.000 | 1.000 |
| Doc-level, over all 192 claims' gold incl. unreachable | | 0.482 | 0.720 | 0.731 | 0.731 | 0.731 |
| **Rerank-only ceiling (hybrid top-100 pool)** [Oracle] | perfect reordering of the frozen pool | 0.671 | 0.671 | 0.671 | 0.671 | 0.671 |

- Wilson 95% CI for 167/192: [0.815, 0.910].
- Wilson 95% CI for the pool ceiling of 112/167: [0.596, 0.737].
- **The hit-based ceiling is flat in k because one gold doc suffices.** At n = 167, the
  "maximum achievable recall" is 1.0 for every k. The binding limits are the corpus (25 + 8
  claims) and candidate generation, not k.

### 2.3 Oracle recall when gold-source identity is known [Oracle]

The same frozen hybrid scores are used throughout; only the publisher keys and the pool change.
"Non-secondary" removes news, fact-check and reference publishers from the gold keys [Heuristic].
This approximates what a *claim-specific authority* resolver is supposed to name.

| Condition | R@1 | R@3 | R@5 | R@10 | R@20 |
|---|---|---|---|---|---|
| A hybrid (actual) | 0.060 | 0.126 | 0.156 | 0.251 | 0.383 |
| D predicted top-3 prior, pool 100 (actual, best deployable) | 0.066 | 0.144 | 0.198 | 0.293 | 0.437 |
| ORACLE publisher, all gold keys, pool 100 (= Phase-1 O) | 0.431 | 0.587 | 0.641 | 0.659 | 0.665 |
| ORACLE publisher, non-secondary gold keys, pool 100 | 0.222 | 0.335 | 0.407 | 0.467 | 0.551 |
| ORACLE publisher, all gold keys, **full corpus** (site filter, hybrid order inside) | 0.479 | 0.683 | 0.772 | 0.832 | 0.940 |
| ORACLE publisher, non-secondary gold keys, **full corpus** | 0.281 | 0.437 | 0.521 | **0.611** | 0.719 |
| H ORACLE targeted + prior (stored) | 0.479 | 0.695 | 0.754 | 0.868 | 0.880 |
| ORACLE URL, pool 100 | 0.671 | 0.671 | 0.671 | 0.671 | 0.671 |
| ORACLE URL, full corpus | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

**The publisher oracle is not a URL oracle in disguise [Measured].**

- Claims have a median of 29 corpus docs from their gold publishers.
- Only 13/167 claims have no non-gold doc from those publishers.
- 98/167 claims have ≥ 20 docs from gold publishers.

It is still partly circular, because it uses the publishers of the scored documents.

### 2.4 Where recall is lost (deployable systems, n = 167) [Measured]

Each cell shows hits / lost in ranking (gold in pool, rank > k) / lost before ranking (gold not in
the pool). The 25 + 8 claims without reachable gold are outside this table.

| System | @1 | @3 | @5 | @10 | @20 |
|---|---|---|---|---|---|
| A | 10 / 102 / 55 | 21 / 91 / 55 | 26 / 86 / 55 | 42 / 70 / 55 | 64 / 48 / 55 |
| D | 11 / 101 / 55 | 24 / 88 / 55 | 33 / 79 / 55 | 49 / 63 / 55 | 73 / 39 / 55 |
| F | 10 / 107 / 50 | 25 / 92 / 50 | 34 / 83 / 50 | 48 / 69 / 50 | 68 / 49 / 50 |
| G | 10 / 107 / 50 | 22 / 95 / 50 | 29 / 88 / 50 | 41 / 76 / 50 | 67 / 50 / 50 |

**Candidate-generation curve (hybrid coverage at depth N) [Measured]:**

| Depth | Coverage |
|---|---|
| top-100 | 0.671 |
| top-200 | 0.850 |
| top-300 | 0.922 |
| top-500 | 0.964 |
| top-1000 | 0.994 |
| dense top-200 alone | 0.904 |
| BM25 ∪ dense top-100 | 0.784 |

Of the 55 claims whose gold is outside the hybrid top-100, the best gold rank is 101–200 for 30,
201–300 for 12, 301–500 for 7, and > 500 for 6.

**Decomposition at R@10, D as the reference:**

```
200 claims ─┬─ 33  no reachable gold (8 no web gold, 25 all-unreachable)        corpus / dataset
            └─ 167 ─┬─ 55 gold outside hybrid top-100                           candidate generation
                    └─ 112 ─┬─ 63 gold in pool, ranked > 10                     ranking
                            └─ 49 hit@10 (D)
```

- **Over 192 web-gold claims, D's R@10 is 0.255.** About 0.13 of recall is lost to the corpus,
  0.29 before ranking, and 0.33 in ranking.
- **Within-pool ranking loss is almost entirely an authority-identification loss *if* "authority"
  includes news outlets.** Perfect publisher identity in the same pool recovers 110 of 112
  in-pool claims at R@10 (0.659).
- **With only non-secondary publishers (the ones an authority resolver should name), it recovers
  78 (0.467).** The remaining in-pool loss lies on claims whose only gold is secondary.

---

## 3. Error analysis

### 3.1 Taxonomy [Measured counts; T3–T8 Heuristic]

Each of the 167 claims is assigned the **first** matching rule. Publisher classes come from
`generic_prior` plus a manual domain table in the script (`DOMAIN_OVERRIDES`, 143 domains,
classified from the domain name alone by the analysing session). The table is not validated.

| Category | Rule | n | A hit@10 | D hit@10 | gold in hybrid top-100 |
|---|---|---:|---:|---:|---:|
| T1 predictor names a publisher of reachable gold | exact key match | **56** | 11 | 23 | 35 |
| T2 predictor names a gold publisher, but only of unreachable gold | | 9 | 1 | 0 | 4 |
| T3 gold is the claimant's or subject's own account | handle ↔ speaker/claim text | 0 | – | – | – |
| T4 identity near-miss (alias, parent, channel) | label overlap ≥ 5 chars or predicted name contains gold label | 5 | 4 | 4 | 5 |
| T5 all reachable gold is news / fact-check / reference | | **54** | 17 | 16 | 41 |
| T6 jurisdiction mismatch (gov vs gov) | | 0 | – | – | – |
| T7 an institutional (gov/intergov/academic) gold publisher was missed | | 25 | 4 | 3 | 15 |
| T8 other (NGO, company, transcript, hosting sites) | | 18 | 5 | 3 | 12 |

**Authority accuracy against the target the resolver is meant to hit [Measured].**

- On the 105 claims with a reachable *non-secondary* gold publisher, the predictor's top-3 matches
  in **53/105 (0.50)** and its top-1 in **39/105 (0.37)**.
- The frozen figure (top-3 0.391 vs all gold publishers) is a lower bound. Against the target an
  authority resolver should hit, the miss rate is about one half, not about 60%.

### 3.2 Correct source discovered but treated as secondary, or ranked low

- **When the authority is correct and its gold doc is in the pool, ranking works [Measured].**
  For 23 T1 claims the authority's gold doc lies in the hybrid top-100; D hits@10 on 20 of them.
  A median of 2 non-gold docs from the same publisher rank above it.
- There is no per-document "secondary" classification in the pipeline: all docs of a predicted
  publisher get the same prior. So "correct source classified as secondary" does not occur as such.
- **Its analogue is generic credibility outranking the primary page.** [AI-generated, descriptive]
  Among reachable gold, AI-labelled *primary* docs are in the hybrid top-100 in 35/86 cases (41%);
  *secondary* docs are in 104/170 cases (61%). Relevance retrieval already favours secondary pages.
  This matches the dev pilot finding that primary docs rank lower (median 137 vs 43;
  `docs/experiment_results.md` §4.3).

### 3.3 Publisher identity: redirects, aliases, subdomains, syndication

- **URL canonicalization: no measurable loss [Measured].** 0 of 117 unreachable gold URLs match
  under looser canonicalization; there is 1 malformed URL (claim 495).
- **Publisher aliases: rare [Measured, manually reviewed].** Of the 5 T4 claims, two are genuine:
  - #4: VITAS Healthcare was predicted as `vitas.com`; the gold publisher is the parent
    `chemed.com`.
  - #475: the predicted name "Penn Wharton Budget Model / Tax Foundation" emitted only
    `upenn.edu`, while the gold is `taxfoundation.org`. This is a key-extraction failure on a
    multi-entity name.

  Two more genuine cases fall under T7:
  - #14: `un.org` predicted; the gold is `undocs.org`, the UN's own documents domain.
  - #248: the gold is on the shared `blog.gov.uk` platform, which hides the department.

  The other T4 hits (#171, #172, #445) are spurious string overlaps. **About 4/167 claims (2.4%)
  are identity failures.**
- **Syndication and copies [Not verified on held-out].** No document text is available. On dev,
  8/62 primary docs had ≥ 1 copy at containment ≥ 0.5, and 11 copies outranked the primary under
  BM25 (`docs/experiment_results.md` §5).

### 3.4 Official source missed because retrieval targets the topic, not the institution [Measured]

- For **33 of the 56 T1 claims**, the correct authority's gold doc is **outside the hybrid
  top-100**: its median full-hybrid rank is 265 and its maximum 1,624.
- The current "targeted query" is the claim text restricted to the authority's documents. Within
  the authority's documents (median 62 per claim), the gold doc's position is:

  | Position in the authority-first targeted list | Claims (of 33) |
  |---|---|
  | ≤ 10 | 11 |
  | ≤ 20 | 19 |
  | ≤ 50 | 31 |
  | any | 33 |

- Examples:
  - #108: CNN, 409 docs; gold at position 64.
  - #52: World Bank, 200 docs; position 65.
  - #15: CBP, 81 docs; position 29.
- **This is the largest authority-attributable loss: about 20% of claims.** Identification
  succeeded; delivery failed. The cause is low claim-text relevance of first-hand pages, which are
  short, tabular, PDF or boilerplate.
- [Hypothesis] Institution-specific queries (the document type the authority would publish,
  e.g. "press release", "statement", "data table") would reorder these lists. This is untestable
  without new runs.

### 3.5 Authoritative source found but ranked below less authoritative sources [Measured]

- In D, among the 63 claims whose gold is in the pool but missed @10, a mean of 3.4 of the top-10
  are non-gold docs from predicted publishers; 19 claims have ≥ 5.
- **In G, source targeting displaces gold.** Among 76 such claims the mean is 8.7, and 68 claims
  have ≥ 5. This reproduces the frozen G-vs-D finding (18 losses; targeted docs fill the top 10).
- The binary prior with λ = 1 is a hard filter, so **every** page of a predicted publisher outranks
  every other page.

### 3.6 Overly broad government / institutional rules [Measured]

| System | Non-gold gov/intergov docs in top-10 (167 claims) | … in a foreign jurisdiction | R@1 vs A | R@10 vs A |
|---|---:|---:|---|---|
| A | 130 | – | – | – |
| B generic | **762** | **150** | +2 / −8 | +15 / −13 |
| C heuristic | 673 | 26 | +3 / −8 | +15 / −11 |
| D LLM | 477 | 30 | +7 / −6 | +13 / −6 |

- When B loses a claim that A had at rank 1, B's new top-1 is a government page in 5 of 8 cases.
- C's entity-match rule fires on 179 pool docs, only **4 of them gold**.
- The broad gov rule costs precision at the top. The claim-country rule reduces the foreign-gov
  noise (150 → 26) but keeps the volume. The gov.uk / canada.ca gap (§1.5) means B and C are not
  even consistent official-source detectors.

### 3.7 Claim-specific authority not captured by domain reputation; wrong authority for the claim

These are the T7 cases [Measured counts, manually inspected]. Two patterns recur.

- **Canonical-agency default on science/health claims.** The model predicts WHO/CDC where the gold
  is the specific research producer:
  - #16: `ucsf.edu`
  - #77: `samrc.ac.za`
  - #134: `cmu.edu`
  - #443: `asm.org`
  - #44: `harvard.edu`

  T1 rate for `scientific_or_health_fact` claims is 8/20. The dev study found the same
  (top-1 0.25).
- **Right type, wrong institution or level.**
  - #183: Mexican kidnapping alert; three `gob.mx` accounts predicted; the gold is a US
    `state.gov` advisory.
  - #419: a CDC claim; the gold is the Mississippi state health department `ms.gov`.
  - #237: Cuba; the gold is `senate.gov`.
  - #192: Nigerian fuel prices; the gold is the statistics bureau `nigerianstat.gov.ng`, not the
    presidency or the regulator.

**T1 rate by predicted claim kind [Model output]:**

| Claim kind | T1 / n |
|---|---|
| statement_by_someone | 4 / 31 |
| event_occurrence | 5 / 27 |
| action_or_policy_of_org | 17 / 43 |
| official_statistic_or_data | 14 / 30 |
| law_or_legal_decision | 7 / 12 |

Statements and events are where institution-level authority is least defined.

### 3.8 Primary / derived / secondary confusion is mostly an *evaluation-target* problem [Measured, Heuristic]

- **For 54 of 167 claims (32%), all reachable human gold is news, fact-check or reference**
  (T5). A correct claim-specific authority resolver is *instructed not* to name these: only 7 of
  501 predicted-publisher entries (all ranks, 167 claims) have type `news`.
- On these claims authority resolution cannot help the human-gold endpoint and can only displace
  gold. A further 40 claims mix secondary and non-secondary gold.
- **The human-gold R@k endpoint therefore rewards finding *any* annotator-used page, not the
  first-hand source.** This explains much of the "authority bottleneck": it is partly a mismatch
  between the method's objective and the metric.

### 3.9 Sources authoritative at claim time that changed or disappeared [Measured proxies; mostly Not verified]

- The dataset has no evidence-date field (dev audit).
- Of the 81 gold URLs with a year in the path, none is dated after the claim year.
- Archive-wrapped gold is less often reachable: 64% vs 77%. Government gold is reachable at 67%.
- Examples of unreachable official gold:
  - `whitehouse.gov/briefings-statements/...` (Trump-era pages since removed);
  - `budgetoffice.gov.ng` (a login redirect);
  - `tableau.minneapolismn.gov` (a dynamic dashboard).
- Disappearance is a plausible cause of part of the 35 unreachable gov URLs, but scrape failure
  cannot be separated from it [Not verified].

### 3.10 What the predictor names that the corpus cannot serve [Measured]

- Of the 102 no-match claims, the predicted publishers are **absent from the whole corpus** for 6
  and **absent from the hybrid top-100** for 45.
- The predictor answers from memory, without seeing which publishers exist in the candidate set.
  Even a correct-in-principle authority with no page in the pool has zero effect on D.

### 3.11 Summary: which failure mode is the bottleneck?

| Failure mode (requested list) | Size (n = 167 unless stated) | Status |
|---|---|---|
| Correct authority, evidence outside pool (delivery) | 33 | Measured |
| All gold secondary: authority irrelevant to the endpoint | 54 | Measured / Heuristic |
| Wrong institution / level / research producer | 25 (T7) + part of 18 (T8) | Measured / Heuristic |
| Predicted authority only has unreachable gold | 9 | Measured |
| Corpus: no reachable gold | 25 of 192 (+ 8 no web gold) | Measured |
| Over-broad gov rules (B/C) | 762 / 673 non-gold gov top-10 docs | Measured |
| Publisher-wide displacement by the binary prior (D/G) | 19 (D) / 68 (G) claims with ≥ 5 | Measured |
| Publisher identity / alias | about 4 | Measured, manually reviewed |
| URL canonicalization | 0 (+1 malformed, no recall effect) | Measured |
| Correct authority in pool but ranked > 10 | 3 | Measured |
| Syndication outranking primary | dev only: 11 BM25 copies | Not verified on held-out |
| Temporal change / disappearance | ≤ 35 gov URLs (upper bound) | Not verified |

**Measured conclusion.** "Authority resolution" as identification (which publisher) explains less
of the gap than its two neighbours:

- **(i) delivery:** the correct authority's first-hand page is not surfaced by claim-text
  relevance, and binary publisher boosting floods the top-k;
- **(ii) the evaluation target:** a third of claims have no first-hand gold to find.

Identification is still half wrong (53/105 top-3), concentrated in science/health and in
institution-level ambiguity.

---

## 4. Literature and implementations

Depth of verification: unless marked, only abstracts and landing pages were checked in this
session (2026-10-28). Numbers not quoted from a paper are omitted.

| Work | Link | Core idea | Relevance to our bottleneck | What we can realistically adapt |
|---|---|---|---|---|
| AVeriTeC dataset (Schlichtkrull et al., NeurIPS 2023) | [arXiv 2305.13117](https://arxiv.org/abs/2305.13117) | Real-world claims with QA evidence and a per-claim knowledge store | Defines our corpus; the KS was built from gold-derived queries | Train-split claims as an untouched design/test pool (§5.6) |
| AVeriTeC shared task 2024 | [arXiv 2410.23850](https://arxiv.org/abs/2410.23850) | Overview; notes the KS scraper left many documents empty | Independent confirmation of the unreachable-gold ceiling | Report the ceiling alongside every result |
| AIC CTU at AVeriTeC 2024 / FEVER-8 2025 (winner 2025) | [2410.11446](https://arxiv.org/abs/2410.11446), [2508.04390](https://arxiv.org/abs/2508.04390) | Simple RAG: whole-document dense retrieval (mxbai), MMR, long-context LLM | The strongest systems use **no authority signal**; a stronger relevance baseline is the fair comparator | Add a strong relevance-only baseline (better embedder or cross-encoder) to every ablation |
| 2nd AVeriTeC shared task overview (FEVER 2025) | [ACL 2025.fever-1.15](https://aclanthology.org/2025.fever-1.15) | Open-weights, one-GPU, < 1 min per claim | Sets realistic compute constraints | Budget check for proposals |
| HiSS (Zhang & Gao, AACL 2023) | [arXiv 2310.00305](https://arxiv.org/abs/2310.00305) | Claim decomposition, then sub-question search | Query generation is the established alternative to claim-text queries | Generate institution-specific sub-queries (proposal C) |
| "Who said it, and why?" (Zhang, Ives, Roth, ACL 2020) | [2020.acl-main.406](https://aclanthology.org/2020.acl-main.406) | Provenance graph for a claim via extraction and entailment | Closest prior work on claim provenance | Attribution-edge extraction (proposal D) |
| Inferring fine-grained provenance (Zhang, Ives, Roth, ACL 2021) | [2021.acl-long.458](https://aclanthology.org/2021.acl-long.458) | Detect externally sourced sentences, generate queries for the source, ILP selection | Directly the "find the original source from a derived article" step | Use attributions in retrieved secondary docs to generate source queries |
| Source dependence (Dong, Berti-Equille, Srivastava, VLDB 2009) | [PDF](https://lunadong.com/publication/dependence_vldb.pdf) | Bayesian copy detection, discounting dependent votes | Source independence for ranking / aggregation | Collapse copy clusters before top-k (proposal D/F) |
| Knowledge-Based Trust (Dong et al., VLDB 2015) | [arXiv 1502.03519](https://arxiv.org/abs/1502.03519) | Source trust from factual correctness, not links | Claim-independent; an example of what we are *not* doing | Comparator framing only |
| Baly et al., EMNLP 2018 | [D18-1389](https://aclanthology.org/D18-1389/) | Outlet-level factuality/bias from Wikipedia, Twitter, URL and traffic features | Outlet credibility, not claim authority | Feature ideas for a publisher-type classifier |
| Lin, Lasser et al., PNAS Nexus 2023 | [PMC10500312](https://pmc.ncbi.nlm.nih.gov/articles/PMC10500312/), [data](https://github.com/hauselin/domain-quality-ratings) | Expert news-domain ratings agree; 11,520-domain aggregate | A better-founded generic prior than our hand list | Replace B's hand list with this aggregate as the **credibility** baseline |
| RA-RAG (Hwang et al., EMNLP 2025) | [arXiv 2410.22954](https://arxiv.org/abs/2410.22954) | Estimate source reliability by cross-checking; weighted voting | Reliability is learned per source, still claim-independent | Cross-checking idea for provenance-aware aggregation |
| AuthorityBench (Yao, Zhang, Bi, 2026) | [arXiv 2603.25092](https://arxiv.org/abs/2603.25092), [code](https://github.com/Trustworthy-Information-Access/AuthorityBench) | LLM authority judgement (domain/entity); list/pairwise judging is best; page text *hurts* | Most direct evidence that **listwise LLM judging over candidate publishers** is effective | Pool-grounded listwise authority judging (proposal A); don't feed page text to the authority judge |
| CrAM (Deng et al., AAAI 2025) / CAG (Pan et al., EMNLP 2024) | [2406.11497](https://arxiv.org/abs/2406.11497), [2404.06809](https://arxiv.org/abs/2404.06809) | Use credibility scores at generation time | Downstream of retrieval | Not needed for retrieval recall |
| CheckThat! 2025 Task 4b | [overview](https://ceur-ws.org/Vol-4038/paper_54.pdf), [2505.23250](https://arxiv.org/abs/2505.23250), [2507.06563](https://arxiv.org/abs/2507.06563) | Retrieve the specific paper a post implicitly refers to; BM25 + dense + LLM reranker | A **claim-specific original-source retrieval** benchmark (science only) | The fix for our science/health T7 failures: retrieve the producer, not the agency |
| WKGFC (Gong et al., 2026) | [arXiv 2603.00267](https://arxiv.org/abs/2603.00267) | Agentic KG (Wikidata) evidence plus web | KG for entity/institution resolution | Wikidata relations for publisher identity (proposal B) |
| Contradiction to Consensus (Biswas & Uzuner, 2026) | [arXiv 2602.18693](https://arxiv.org/abs/2602.18693) | Claim and negation queries over several sources; source-level disagreement | Multi-source candidate generation | Negated-claim queries as a cheap expansion control |
| ReFinED entity linking | [arXiv 2207.04108](https://arxiv.org/abs/2207.04108), [code](https://github.com/alexa/ReFinED) | Fast Wikidata entity linking | Better than spaCy NER plus Wikidata search for entity → organisation | Proposal B |
| Cross-encoder reranker (e.g. `BAAI/bge-reranker-v2-m3`) | [model](https://huggingface.co/BAAI/bge-reranker-v2-m3) | Query–document relevance scoring | Within-authority relevance (§3.4) | Proposals E/F; official model card **not verified** in this session |
| LambdaMART (LightGBM `lambdarank`), MinHash (`datasketch`) | [LightGBM](https://lightgbm.readthedocs.io), [datasketch](https://github.com/ekzhu/datasketch) | Standard learning-to-rank; near-duplicate detection | Proposals G and D | **Not fetched** in this session; standard tools |

**Research gap that our experiments could test (not a novelty claim).**

- **Covered:** claim-independent credibility (Baly, KBT, Lin et al., RA-RAG, AuthorityBench); claim
  provenance from a given article (Zhang et al.); original-source retrieval for one domain with a
  single target (CheckThat 4b). Combining these is not novel.
- **Untested:** whether *claim-conditioned, candidate-grounded* identification of the first-hand
  publisher improves retrieval of **first-hand evidence** on general real-world claims. The test
  needs:
  - controls for pool size and a mismatched authority;
  - a decomposition into identification, delivery and corpus losses;
  - **an endpoint that distinguishes first-hand from secondary evidence and is not labelled by the
    same model family.**
- The decomposition method in §2 and the delivery-vs-identification finding (§3.4) are the parts
  that existing work does not report.

---

## 5. Proposed interventions

**Common rules for every proposal.**

- Gold never enters retrieval.
- Tuning is done only on design claims (§5.6).
- The publisher list of a claim's corpus *is* inference-time input. It is available to any system
  over this KS, but in AVeriTeC it is shaped by gold-derived KS queries. That is a threat to
  external validity, not leakage within this benchmark; it must be stated.

### A. Claim-conditioned, pool-grounded authority resolution

- **Addresses:** T7 (wrong institution or level), §3.10 (predicted publishers absent from the pool
  in 45/102 no-match claims), and the binary prior.
- **Method.** Give the LLM the claim plus the list of *publishers present in the candidate pool*
  (keys, counts and one title each; no page text, per AuthorityBench). Ask for a graded
  authority score in [0, 1] per publisher and the fact at issue. This replaces "name from memory".
- **Why it may improve recall:** it can only pick reachable publishers, and graded scores reduce
  hard-filter displacement.
- **Stage:** authority classification and ranking.
- **Cost:** one call per claim, as now (about $0.022/claim, i.e. $4.38 per 200 claims [Measured]),
  with a longer prompt; no training.
- **Data:** none; λ is tuned on design claims.
- **Risks:**
  - the LLM may fall back on credibility (choosing the most "official" publisher in the list);
  - it can only reorder the existing pool, not add missing publishers (combine with C);
  - the same-model circularity with the AI labels remains.
- **Fair evaluation:**
  - against D (memory-based) with an identical λ, pool and scorer;
  - a mismatched-publisher control (X1 style);
  - a "list-without-claim" control, which tests whether it is just credibility.

### B. Entity and publisher resolution

- **Addresses:** about 4/167 alias cases, the multi-entity key-extraction bug (#475), shared
  platforms (`blog.gov.uk`, `medium.com`), and parent/subsidiary links (VITAS → Chemed).
- **Method.**
  - A publisher graph from Wikidata: P856 official website, P749/P355 parent/subsidiary,
    P2002/P2013 accounts.
  - Link social accounts to their organisations.
  - Use subdomain keys for shared government/blog platforms.
  - Emit one key per entity in a multi-entity name.
  - Fix the `strip_wayback` malformed prefix in new code only.
- **Expected gain:** small (at most about 4 claims, ≈ 0.02 R@10 on 167). **This alone would not be
  detectable** (§5.6).
- **Stage:** authority classification (key matching).
- **Cost:** offline Wikidata lookups; cached.
- **Risks:** over-merging (e.g. collapsing all of `gov.uk` already merges departments, which hurts
  precision).
- **Evaluate:** as an add-on to A or D; report how many claims change key-match status, with
  examples.

### C. Source targeting (institution-specific queries and deeper authority candidates)

- **Addresses:** §3.4, the largest bucket (33 claims where the authority is right but its page is
  out of the pool).
- **Method.**
  - **(i)** Within predicted-authority docs, rank by relevance to an *institution-specific
    query*: the fact at issue plus the expected document type, generated by the predictor
    (`fact_at_issue` already exists). Alternatively rank by a cross-encoder.
  - **(ii)** Take the top-M (M ∈ {20, 50}, chosen on design claims) instead of 10.
  - **(iii)** Fuse by *relevance-calibrated* scores, not authority-first order.
- **Diagnostic bound [Oracle, held-out]:** with M = 50, 31 of the 33 out-of-pool authority-gold
  docs would enter the pool; with M = 10, only 11.
- **Stage:** candidate generation, plus ranking.
- **Cost:** no new LLM calls if `fact_at_issue` is reused. A cross-encoder over about 50–150 docs
  per claim costs CPU time [Not verified locally].
- **Risks:** displacement (G's failure). A per-publisher cap in the top-k is needed (see F).
- **Evaluate:**
  - pool coverage vs a size-matched deeper-hybrid control;
  - a mismatched-authority expansion control (same number of docs, from a non-predicted
    publisher of similar size).

### D. Provenance and citation tracing

- **Addresses:** syndication / copies outranking the primary (dev evidence only); secondary pages
  that name the primary.
- **Method.**
  - MinHash near-duplicate clusters, keeping the earliest or most-original member.
  - Attribution extraction ("according to X", "said in a statement", links to X) inside top
    secondary docs. Each attributed X becomes an extra authority candidate or query (cf. Zhang et
    al. 2021).
- **Stage:** candidate generation (from attributions) and ranking (dedup).
- **Cost:** moderate; text processing over the top-50.
- **Data:** none for dedup; the attribution extractor can be a prompt or patterns.
- **Risks:**
  - attributions also point to non-authorities;
  - dedup can delete the gold copy when gold *is* the syndicated copy (the human gold often is).
- **Evaluate:**
  - on design claims first; it has not been measured on held-out at all;
  - report how often a dedup removes a gold doc.

### E. Multi-stage retrieval

- **Structure:**
  1. Candidate generation: hybrid plus authority-restricted plus attribution-derived.
  2. Publisher identity resolution (B).
  3. Claim-conditioned authority scoring (A).
  4. Relevance or "directness" scoring by a cross-encoder.
  5. Final selection with diversity/independence constraints.
- **Addresses:** it makes each stage's loss measurable. Stage-wise coverage is the experiment's
  instrumentation.
- **Cost / risk:** engineering, and more knobs to tune (more forking paths). Freeze them on design
  claims.

### F. Authority-aware ranking (multi-signal, not reputation-only)

- **Score:** `rel(q, d) + λ_a·auth(publisher | claim) + λ_dir·directness(d) − λ_dup·dependence(d)`,
  with a cap of c docs per publisher in the top-k.
- **Addresses:** §3.5 and §3.6 displacement (G: 68 claims with ≥ 5 non-gold predicted-publisher
  docs in the top 10) and B's 762 non-gold gov docs.
- **Temporal fit [Not feasible].** No evidence dates exist and only 28.8% of dev gold docs carry
  any date signal (dev audit), so temporal fit should be left out.
- **Risks:** weights tuned to the human-gold target re-learn "news is good".
- **Evaluate:** at a fixed pool so that ranking effects are isolated.

### G. Lightweight learned approaches

- **Data that already exists:** AVeriTeC **train** (3,068 claims) has human gold URLs, so
  *relevance* supervision needs no annotation. The KS can be range-extracted per claim, as was done
  for dev.
- **Feasible:** a LambdaMART ranker over about 15 features (BM25/dense/cross-encoder scores, ranks,
  graded authority from A, publisher class, publisher doc count in the pool, URL depth, PDF flag,
  duplication). Training on 300–500 train claims is cheap.
- **Not feasible without annotation:** a supervised "authority" classifier. The only per-URL role
  labels on held-out are AI-generated and circular. A human set of about 100 claims × 2 annotators
  (about 300 URLs, ≈ 15–20 h at 3–4 min per URL [estimate]) would allow a primary-evidence
  endpoint *and* a small authority classifier evaluation.
- **Risk:** the learned ranker optimises human-gold recall, i.e. it learns to find secondary pages.
  It is a strong *relevance* baseline, not an authority method. Report it as such.

### Trade-off summary

| | Failure mode | Stage | Effort | Cost per claim | Data | Expected benefit (n = 167 scale) | Clarity |
|---|---|---|---|---|---|---|---|
| C | delivery (33) | candidates + rank | low | ~0 LLM | none | **high** (bound 31 into pool) | high |
| F (cap + graded) | displacement | rank | low | 0 | none | medium | high |
| A | identification (T7, pool-absent) | authority | medium | ≈ 1 call | none | medium (≤ ~25–45 claims) | medium (circularity) |
| D | copies / attribution | both | medium | text processing | none | unknown (dev only) | low |
| B | identity (~4) | authority | low–medium | 0 | Wikidata | low (~0.02) | high but underpowered |
| E | instrumentation | all | medium | – | – | enables measurement | – |
| G | relevance | rank | medium | 0 | train split | medium (relevance) | confounded with authority |

---

## 6. Controlled ablation plan (requires a new preregistration; not started)

### 6.1 Splits (no reuse of the frozen held-out for selection)

- **Design set:** the 120 dev claims plus a new sample of about 300 AVeriTeC **train** claims.
  Train claims have never been used and have gold; the KS would be extracted with the existing
  range-request code.
- **Test set:** the **180 untouched dev claims** (≈ 150 with reachable gold, if the 167/200 rate
  holds). Optionally add about 400 further train claims, never used for design, to raise power
  (see 6.4).
- **Frozen held-out (200):** diagnostics only. It already served the exploratory Phase 1/2
  analyses and this report, so it must not select a method.

### 6.2 Systems

The pool and λ are fixed per row. Rows 1–6 are the requested set.

| # | System | What changes vs row 1 |
|---|---|---|
| 1 | Baseline = frozen D (and A, B for reference) | – |
| 1b | Strong relevance baseline: hybrid + cross-encoder, no authority | separates relevance gains from authority gains |
| 2 | 1 + publisher resolution (B) | key matching only |
| 3 | 1 + claim-conditioned, pool-grounded authority (A), graded | authority scores only |
| 4 | 1 + source targeting C (deeper M, relevance-calibrated fusion, per-publisher cap) | candidates + fusion |
| 5 | 1 + provenance (D: dedup + attribution queries) | candidates + dedup |
| 6 | Best combination, **chosen on the design set by a rule fixed in advance** | – |
| Ctrl-size | deeper hybrid, size-matched to 4 / 6 | pool size |
| Ctrl-mismatch | rows 3 / 4 with a pool-visible, non-predicted publisher of similar size and type (X1 protocol) | authority content |
| ORACLE-NS (diagnostic) | rows 4 / 6 with non-secondary gold publishers | identification upper bound |
| ORACLE-URL (diagnostic) | perfect reorder of each system's pool | pool ceiling |

### 6.3 Metrics (frozen scorer definitions, unchanged)

- **Per system:** R@1/3/5/10/20, MRR@100, and pool coverage before ranking.
- **Denominators:**
  - reachable claims (primary);
  - also reported over web-gold claims and over all claims, so that corpus loss stays visible.
- **Per-claim categories:** the T1–T8 rules of `authority_bottleneck_diagnostics.py`, frozen as
  written. The stage decomposition (corpus / candidate / ranking) is reported for every system.
- **Authority accuracy:**
  - vs reachable non-secondary gold publishers (top-1, top-3);
  - vs all gold publishers (lower bound, as before).
- **Cost:** wall-clock time per claim, number of LLM calls, USD (`total_cost_usd` from the CLI
  envelope, as now), and cross-encoder CPU seconds.
- **Secondary, if annotated:** a human primary-evidence endpoint (§5G). AI labels may be reported
  only descriptively and never as validation (Addendum 3 rule).

### 6.4 Statistics

- **Primary test:** one family only, exact McNemar on hit@10 with paired bootstrap 95% CI
  (10,000 resamples, seed 2026, existing `validation_heldout.boot_ci`).
- **Holm correction** over at most 4 tests: rows 4 vs 1, 3 vs 1, 6 vs 1b, and 4 vs Ctrl-size
  (coverage).
- **Power [estimate].**
  - With about 150 reachable claims and the observed discordance (D vs A: 19/167 discordant), only
    effects of roughly +0.08–0.10 R@10 are detectable.
  - B alone (≈ +0.02) cannot be tested. Either report it descriptively or enlarge the test set
    with train claims (about 550 reachable claims → about +0.05 detectable).

### 6.5 Leakage controls

- Gold URLs, gold publishers, labels, justifications and fact-check articles are read only by the
  scorer.
- The predictor never sees rankings.
- Oracle rows are generated in a separate code path labelled `ORACLE`, as now.
- All design choices (M, λ, cap c, cross-encoder model) are fixed on the design set and hashed
  before the test KS is scored.

### 6.6 Preregistration amendment required — awaiting approval

The plan needs a **new preregistration document** (proposed name:
`docs/authority_resolution_v2_preregistration.md`) that:

- (a) defines the new test population (180 dev claims, optionally plus train claims) and its KS
  extraction;
- (b) fixes systems 1–6, the controls and the selection rule for row 6;
- (c) fixes the primary family above;
- (d) states that the existing preregistrations, frozen results and scorer are unchanged.

**I have not written or started it.** It is described here for review.

---

## 7. Recommended first experiment and roadmap

### 7.1 Ranking of interventions

| Rank | Intervention | Benefit | Effort | Clarity |
|---|---|---|---|---|
| 1 | **C + F-cap: authority-restricted candidate expansion with relevance-calibrated fusion and a per-publisher cap** | Largest measured authority-attributable bucket (33 claims); also removes G's displacement | Low; reuses the frozen predictor | High: one mechanism, clear controls |
| 2 | A: pool-grounded, graded, claim-conditioned authority | Attacks the 50% identification miss and pool-absent predictions | Medium | Medium |
| 3 | 1b strong relevance baseline (cross-encoder / better embedder) | Needed as a comparator before claiming any authority gain | Low | High |
| 4 | Human primary-evidence annotation (≈ 100 claims) | Fixes the endpoint mismatch (54 secondary-only claims) | Medium (human time) | High |
| 5 | D provenance | Unknown on held-out | Medium | Low |
| 6 | B publisher resolution | ~2% of claims | Low | Underpowered |

### 7.2 First improvement to implement (after approval)

**Authority-conditioned candidate expansion (proposal C), delivered with relevance-calibrated
fusion and a per-publisher cap (part of F).** The predictor stays fixed. This tests whether a
*correct* authority can be turned into recall without displacing gold. That question has to be
answered before improving identification is worth anything: a better resolver run through the
current delivery is capped at 0.467 R@10 (oracle, pool-bound), and through full-corpus delivery
at 0.611.

### 7.3 Smallest useful experiment

**On the design set only (dev 120 plus train sample)**, a 2 × 2 design plus 2 controls, with no
new LLM calls on dev (frozen predictions exist):

| | Pool | Final ranking |
|---|---|---|
| D (frozen) | hybrid top-100 | binary prior, λ = 1 |
| D + cap | hybrid top-100 | binary prior, at most c docs per predicted publisher in the top-10 |
| C | hybrid top-100 ∪ authority top-M (claim + `fact_at_issue` query) | relevance-calibrated fusion |
| C + cap | same | + cap |
| Ctrl-size | hybrid top-(100 + added) | as C + cap |
| Ctrl-mismatch | hybrid top-100 ∪ top-M of a matched non-predicted publisher | as C + cap |

- **Outcomes:** pool coverage, R@1–20, and the T1 out-of-pool recovery rate. The latter is the
  mechanism check: of claims with correct authority and gold outside the hybrid top-100, how many
  reach the top 10.
- **Cost:** CPU only; minutes for 120 claims.

Only if this passes a pre-stated design-set criterion (for example, T1 recovery ≥ 30% *and* R@10 ≥
D + 0.04 *and* beating both controls) does it go into the preregistered test (§6).

### 7.4 Diagnostics needed before implementation

1. **Human audit of the taxonomy.** Two annotators label the publisher class and whether the gold
   is first-hand for the 54 T5, 25 T7 and 18 T8 claims (or a 60-claim sample). This validates
   that a third of the claims really have secondary-only gold.
2. **Re-run this diagnostic on the design set,** to check that the decomposition (≈ 20% delivery,
   ≈ 32% secondary-only) is not a held-out artifact. It needs the dev full rankings, which are
   gitignored and must be regenerated with the documented commands, plus the train extracts.
3. **Restore `data/raw/`** for the design claims, to separate "absent from KS" from "empty text".
4. **Fix the power target** (§6.4) and decide whether to add train claims to the test set.

### 7.5 When to stop improving authority resolution

Stop and redirect effort to the corpus or to candidate generation when any of the following holds
on the design set.

- **The identification headroom is exhausted.** R@10(ORACLE-NS publishers through the current best
  delivery) − R@10(best deployable) < 0.03, i.e. about 5 claims per 167, below what the test can
  detect.
- **Too few misses are authority-attributable.** Fewer than 25% of the remaining R@10 misses of the
  best system fall in T1/T4/T7. The rest would be T5 (secondary-only gold), unreachable gold, or
  out-of-pool claims without a predicted publisher.
- **Delivery is saturated.** The T1 out-of-pool recovery reaches ≥ 80%, so identification is the
  only authority lever left, and the identification headroom (first bullet) is small.
- **The human-gold endpoint is structurally capped.** If the human audit confirms ≥ 30%
  secondary-only claims, further authority work should be evaluated *only* on a first-hand
  endpoint. On human-gold R@k it can at best stay level on those claims.

---

## 8. Risks, limitations, and research implications

- **Single, already-used held-out set.** Every number here is post hoc on the 200 claims that
  already carried the preregistered test and two exploratory ablations. It can motivate but not
  validate a method.
- **Heuristic classes.** T3–T8 and "non-secondary" depend on a hand-written domain table (143
  domains classified from the name by the analysing session, which had seen gold URLs). The
  non-secondary oracle and the 54-claim T5 figure are approximate until audited.
- **Oracle circularity.** Publisher oracles use the publishers of the scored gold documents.
  ORACLE-NS removes news, but remains an upper bound, not an estimate of achievable recall.
- **AI-generated labels.** §2.1 and §3.2 use MODEL_GENERATED roles only as counts. The same model
  family produced the predictor, so these counts cannot validate anything.
- **Corpus construction.** The AVeriTeC KS was built partly from gold-derived queries, so
  pool-grounded methods (A) exploit a publisher list that the open web would not provide. Results
  are specific to this KS.
- **No document text** in this checkout. Provenance, syndication and temporal claims are either dev
  results or unverified.
- **Endpoint mismatch** is the main research implication. The question "can authority resolution
  bring recall close to the ceiling?" has two parts on the current endpoint:
  - about 0.13 of the denominator (over 192 claims) is unreachable;
  - about 0.33 is lost before ranking;
  - about a third of reachable claims have no first-hand gold.

  On human-gold R@k, perfect non-secondary authority identification with full-corpus delivery
  reaches **0.611 R@10** [Oracle], against **0.293** for D. That gap of about 0.32 is the
  realistic maximum authority-attributable gain on this endpoint, and only part of it is
  identification. Reaching the 1.0 ceiling would require relevance-side improvements that are not
  about authority. A claim about *authority* needs a first-hand evidence endpoint with independent
  (human or cross-family) labels.
