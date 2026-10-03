> **Note (2026-10-02).**
> - The per-URL label scheme below (`primary / secondary / derived / unclear`, with its "Further rules") is reused **verbatim** in the prompt of the **AI** evidence-level annotator (`heldout_primary_package/ai/AI_EVIDENCE_PROMPT.md`; Addendum 3).
> - In that prompt, "open the URL" is dropped because the annotator has no web access, and the `multiple_primary_sources` / `other_primary_sources` fields are not asked for.
> - No human second annotation was obtained, for either development or held-out claims. Any comparison of AI labels with the development pilot labels is **AI–AI agreement**, not inter-annotator reliability.

> **Held-out claims (2026-09-30):** held-out primary-source annotation now uses the blind package in `heldout_primary_package/` (see its README and ANNOTATION_GUIDE). Do not give held-out annotators `heldout_annotator_template.*` or `heldout_annotator_claim_authority_template.*`.

# Second-annotator guidelines: source role of evidence URLs

**Who:** a human annotator who has **not** seen `source_roles.csv`, `top1_blind_roles.csv` or any of the project's results/docs. Please do not open those files until you have finished.

**Files** (each CSV has an identical `.xlsx` copy with dropdowns; fill whichever you prefer, but only one of the two):

1. `second_annotator_claim_authority_template` (119 development claims) and `heldout_annotator_claim_authority_template` (192 held-out claims; claims with at least one web gold URL). These are **claim-level** sheets. **Fill them first, before you see any evidence rows of a claim.** For each claim, name the publisher(s) that would be first-hand authoritative for the fact at issue: up to 3 names + domain or social account. Then fill `multiple_legitimate_authorities` (`yes` if more than one is genuinely first-hand, e.g. a ministry *and* the statistics office), `authority_rationale` (one line), and `confidence`. Use only the claim, speaker, date and country, plus your own knowledge or a web search for the *institution* (not for fact-checks of the claim). This is the project's manual "oracle authority" and is used only as an upper bound.
2. `second_annotator_template` (226 rows, development claims). This measures agreement with the pilot annotation (Cohen's κ).
3. `heldout_annotator_template` (422 rows, held-out validation claims; no earlier labels exist). This enables primary-source recall on the held-out set.

**Columns to fill in the evidence sheets** (leave every other column unchanged):

| Column | Values | Meaning |
|---|---|---|
| `annotator_id` | your initials | the same on every row |
| `annotator_label` | `primary` / `secondary` / `derived` / `unclear` | see the table below |
| `publisher_name` | free text | who published this page, e.g. "Nigeria Centre for Disease Control" |
| `multiple_primary_sources` | `yes` / `no` / `unsure` | could more than one publisher be first-hand for this claim? |
| `other_primary_sources` | free text, `;`-separated | if yes: which others (name + domain) |
| `authority_rationale` | one line | why this publisher is / is not first-hand for the fact at issue |
| `confidence` | `high` / `medium` / `low` | |
| `notes` | optional | anything ambiguous |

**Context you have for each row:**

- the claim, its speaker, date and country
- the evidence URL, with a title and snippet from the AVeriTeC knowledge store
- the fact-checker's question and answer that this URL was cited for

Open the URL (or its web.archive.org copy) whenever the snippet is not enough.

## The question to ask

> Relative to **this claim**, is the **publisher of this page** a first-hand source for the fact being checked, or does it report on / repackage someone else's information?

Judge the **publisher**, not the page's quality or trustworthiness. A highly credible newspaper is still `secondary` when it reports what an agency said.

## Labels

| Label | Use when the publisher is… | Examples |
|---|---|---|
| `primary` | the government body, intergovernmental body, court, legislature or regulator that issued / records / holds the fact. Also the organisation or company itself, when the claim is about its own actions or statements; the original research or data producer; or, for "X said/posted Y" claims, X's own statement, post or official channel. | a ministry's press release; the official statistics office's table; a court judgment; a company's own announcement; the politician's own tweet; the journal article reporting the study |
| `secondary` | news, magazines, fact-checkers, explainers, law-firm or advocacy explainers, blogs: reporting **about** something | a Reuters story about the ministry's release; a PolitiFact article |
| `derived` | encyclopedias, aggregators, mirrors, directories, trackers compiling others' data, or third-party **re-hosted copies** of a primary document | Wikipedia; a statistics-aggregator site; a PDF of a government report hosted on someone else's site; LegiScan's copy of a bill |
| `unclear` | you cannot tell who published it, or it is a tool, search page or dead end | a search-results page; an empty or broken page |

Further rules:

- **Web archives are transparent.** For `web.archive.org/...` or `archive.ph/...` links, judge the original publisher of the archived page.
- **Social media.** Judge the account owner: an agency's own account is `primary`; a random user re-posting something is `secondary` or `derived`.
- **Genuinely borderline cases.** Pick the best label and explain in `notes`, e.g. "think-tank's own survey = primary for its data, but it is interpreting government data".

The development evidence file has 226 rows (about 2–3 hours), the held-out file 422 rows. Please work in the given order, which is shuffled.

**Independence.** Do not look at `source_roles.csv`, `top1_blind_roles.csv`, any `results/` file, any model prediction or the project docs until you have finished. The existing labels were produced by an AI model (pilot) and are **not** a human annotation; your labels are the first human ones.
