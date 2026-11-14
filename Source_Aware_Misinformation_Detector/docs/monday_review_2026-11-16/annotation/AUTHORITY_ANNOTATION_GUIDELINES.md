# Annotation Guidelines: Claim-Specific Relevance and Authority of Web Documents

**Project:** IR_03 Source-Aware Misinformation Detection · **Version:** 1.0-draft (2026-11-14) · **Status:** PROTOCOL READY. **NO ANNOTATIONS COLLECTED YET.**

This version extends the earlier claim-level primary-source guide (`data/annotations/heldout_primary_package/ANNOTATION_GUIDE.md`) to the unit we need for training: **one claim + one candidate document**.

---

## 1. Unit of annotation

Each row is a **claim–document pair**. You see:

- the claim text, speaker, claim date and country;
- the document URL, its publisher key and a text excerpt (open the URL if it still works).

You assign two **independent** labels.

| Label | Question | Values |
|---|---|---|
| **RELEVANCE** | Does this document contain information about the specific fact the claim makes? | `relevant` · `partially_relevant` · `not_relevant` · `cannot_determine` |
| **AUTHORITY** | Is this source the one that issued, recorded, measured or holds *this claim's fact*? | `primary` · `authoritative_secondary` · `secondary_derivative` · `not_authoritative` · `cannot_determine` |

Judge authority **for this claim's fact, regardless of whether the page is relevant**. Then judge relevance separately. The system combines the two labels later. Do not let one label decide the other.

## 2. Relevance labels

| Value | Use when |
|---|---|
| `relevant` | The document directly addresses the claim's central fact (the figure, event, statement, law or finding). It would help a fact-checker confirm or refute it. |
| `partially_relevant` | It covers the same topic or one sub-part of the claim, or gives useful context, but does not address the central fact. |
| `not_relevant` | It is about something else. This includes pages that share keywords but concern a different event, person, period or place. |
| `cannot_determine` | The excerpt is empty, cut off, paywalled, in a language you cannot read, or otherwise too incomplete to judge (see §7). |

**Relevance is not agreement.** A document that *refutes* the claim is just as relevant as one that supports it. You never judge whether the claim is true.

## 3. Authority labels

| Value | Definition | Typical examples |
|---|---|---|
| `primary` | **First-hand for the fact at issue:** the body or person that issued, recorded, measured or holds the fact, publishing it in its own channel. | The ministry's own press release · the statistics office table · the court judgment · the law or executive order text · the company's own announcement · the person's own post or transcript · the journal article reporting the study |
| `authoritative_secondary` | **Not first-hand, but a domain-expert institution whose job is to report or synthesise this kind of fact,** and which cites or reproduces the primary record faithfully. | A national public-health agency summarising a peer-reviewed study · an official parliamentary research service brief on a bill · an intergovernmental body's compilation of national statistics · a systematic review covering the claimed finding |
| `secondary_derivative` | Reports on, explains, aggregates, re-hosts or checks someone else's information. | News articles (including highly credible outlets) · fact-check articles · Wikipedia · blogs · think-tank commentary · a third-party copy of a government PDF |
| `not_authoritative` | The source is **not** in a position to hold or report this fact first-hand or expertly, or the page is about something else entirely. | An unrelated government department · a university page from an unrelated field · an opinion piece · a spam or SEO site |
| `cannot_determine` | You cannot tell who published the page or what it is, or the document is inaccessible (§7). | An empty scrape · an unclear mirror |

### 3.1 The test to apply

> *If a careful fact-checker wanted the record itself, would they cite **this document's publisher** as the origin of the fact — or would they cite whoever this document is citing?*

- **They cite this publisher** → `primary`.
- **They cite whoever it cites, but this publisher is an expert body that reproduces the record faithfully** → `authoritative_secondary`.
- **They cite whoever it cites** → `secondary_derivative`.

## 4. Publisher credibility ≠ claim-specific authority

**Credibility belongs to a publisher** and is the same for every claim. **Authority belongs to a (claim, document) pair.**

| Claim | Credible but NOT the authority | The authority |
|---|---|---|
| "India's unemployment rate was 7.8% in December" | Reuters article quoting the figure | The statistics office (PLFS / MoSPI release) that produced it |
| "The WHO declared mpox a global emergency" | BBC report | WHO's own statement |
| "Study shows masks caused 1918 flu deaths" | A `.gov` health page about a different disease | The journal article / NIH researchers' paper |
| "Senator X voted against bill Y" | A respected newspaper | The legislature's roll-call record |

**Do not** label a page `primary` just because its domain is `.gov`, `.edu` or a famous outlet. A US government page is not the authority for a UK law. A university's press office is not the authority for another university's study.

## 5. Relevance vs authority: the four combinations

| | Authoritative (primary / auth.-secondary) | Not authoritative |
|---|---|---|
| **Relevant** | ✅ **Target evidence.** Counts as an *authority hit*. | Useful but second-hand, e.g. a news report of the figure |
| **Not relevant** | The right publisher but the wrong page, e.g. the statistics office's page on a different survey | Discard |

The training target for the authority head is the full 5-way label. The evaluation metric **Authority Recall@K** counts a document as a hit only if it is (`relevant` or `partially_relevant` — pending mentor decision, see §11) **AND** (`primary` or `authoritative_secondary`).

## 6. Hard cases

1. **Primary documents** (laws, orders, judgments, filings, official transcripts, the person's own post): `primary` for claims about their own content. A verbatim re-host on a third-party site is `secondary_derivative`, *unless* it is an official archive of the issuer (e.g. `trumpwhitehouse.archives.gov` for a 2020 White House order, `congress.gov` for bill text).
2. **Official statistics.** The producer of the figure is `primary`. An intergovernmental compilation of national statistics (World Bank, OECD) is `authoritative_secondary`, unless it publishes its own estimate, in which case it is `primary` for that estimate. A news chart of the figure is `secondary_derivative`.
3. **Scientific publications.** The paper that reports the finding is `primary`, whether it is a journal, a PubMed record or a preprint (note "preprint" in `notes`). A systematic review or agency guidance summarising it is `authoritative_secondary`. A university press release about its own researchers' study is `authoritative_secondary`. Science journalism is `secondary_derivative`.
4. **"X said Y."** If the claim is about *what X said*, X's own statement or channel is `primary`, and a news report of the quote is `secondary_derivative`. If the claim asserts Y as fact, the authority on Y is also primary for that part; label the document by what it is.
5. **Secondary reporting of a primary source.** A news article that embeds or links the primary document is still `secondary_derivative`, even if it quotes the document verbatim.
6. **Fact-check articles** are always `secondary_derivative`, however good they are. Do not open fact-check sites for the claim while annotating (leakage, §9).
7. **Conflicting sources.** Two documents may disagree. You do **not** resolve who is right. Label each document's authority by *its position relative to the fact*. Two `primary` sources can conflict, for example two governments in a bilateral dispute. Note the conflict in `notes`.
8. **Multiple legitimate authorities.** More than one publisher can be `primary`, for example the health ministry and the statistics office. Do not force a single winner.
9. **No identifiable authority.** For rumours or opinions, no document may qualify as `primary`. That is a valid outcome.
10. **Time.** Judge authority as of the claim date. An organisation that was the issuer then remains the authority, even if it was later renamed.

## 7. Inaccessible or incomplete documents

- **Empty or very short excerpt (< ~100 characters of content), broken link, paywall or unreadable language:** relevance = `cannot_determine`. Judge authority from the URL and publisher only if you are confident (e.g. `bls.gov/news.release/...`); otherwise use `cannot_determine`. Set `accessible = no` or `partial`.
- **Excerpt is cut off but the URL works:** read the page, then set `accessible = yes_via_url`.
- **Never guess relevance from the URL alone.**

## 8. Columns you fill in

| Column | Values |
|---|---|
| `relevance` | see §2 |
| `authority` | see §3 |
| `authority_basis` | `issuer` · `data_producer` · `own_statement` · `official_archive` · `expert_body` · `reporting` · `aggregation` · `unrelated` · `unknown` |
| `doc_type` | `official_doc` · `statistics` · `research_paper` · `press_release` · `social_post` · `news` · `fact_check` · `encyclopedia` · `blog_opinion` · `other` |
| `accessible` | `yes` · `yes_via_url` · `partial` · `no` |
| `confidence_1to3` | 1 = unsure, 2 = fairly sure, 3 = certain |
| `time_spent_min` | approximate minutes |
| `notes` | required for every `cannot_determine`, every conflict, and every case you found hard |

## 9. Leakage rules (strict)

- **Annotators must NOT look up, or be shown:** the AVeriTeC verdict, justification, question–answer pairs, the original fact-check article, any "gold/evidence" indicator, retrieval rank or score, or any model or LLM prediction. The sheets deliberately omit them, and documents are shuffled within each claim.
- **Do not search** for the claim on fact-checking sites. You may open the given document URL and the publisher's own "About" page to identify the publisher.
- **Automatically collected metadata** (URL, publisher key, excerpt, retrieval rank, evidence indicator) is stored in separate columns or files from **human labels**. The evidence indicator and rank live only in `_KEY_DO_NOT_GIVE_TO_ANNOTATORS/`.
- **Model inputs** may use only prediction-time information: claim text, speaker, date, country, document URL/text/metadata. Never the AVeriTeC verdict, justification, Q/A, fact-check article or evidence indicator.

## 10. Workflow

1. Read this guide and the one-page instruction sheet. Do the 3 worked examples with the lead.
2. Annotate independently. **Do not discuss items with the other annotator until both sheets are submitted.**
3. Submit the CSV. The lead computes agreement (`experiments/esa_nov2026/annotation/agreement.py`).
4. Adjudication: the two annotators and an adjudicator resolve disagreements in `adjudication_template.csv`, citing the guideline section. If a disagreement reveals a guideline gap, the guide is versioned (v1.1, …) and the change is logged.

## 11. Decisions requiring mentor approval

- whether `partially_relevant` counts toward an authority hit (default proposal: yes for training, report both for evaluation);
- whether `authoritative_secondary` counts as an authority hit (default proposal: yes, with `primary`-only reported as well);
- pool depth to annotate per claim (top-10 hybrid for the pilot; top-20 or top-30 for the main set; see the model design);
- annotator recruitment (team members vs. external) and the time budget.
