# Annotator Instruction Sheet (one page)

**For each row (one claim + one document), give TWO separate labels.** Full rules: `AUTHORITY_ANNOTATION_GUIDELINES.md`.

### RELEVANCE: *does this page address the claim's specific fact?*
`relevant` (directly addresses it, for OR against) · `partially_relevant` (same topic or one sub-part) · `not_relevant` · `cannot_determine` (empty, paywalled or unreadable)

### AUTHORITY: *is this publisher the origin of THIS claim's fact?*
| | |
|---|---|
| `primary` | issued, recorded, measured or holds the fact; its own channel (law text, statistics table, court ruling, own statement or post, the study itself) |
| `authoritative_secondary` | not the origin, but an expert body faithfully reporting the record (health agency summarising a study, parliamentary research brief) |
| `secondary_derivative` | news (even the best outlets), fact-checks, Wikipedia, blogs, re-hosted copies |
| `not_authoritative` | not in a position to know this fact (unrelated agency, opinion, spam) |
| `cannot_determine` | cannot tell who published it, or inaccessible |

### Five rules
1. **Credible ≠ authoritative.** `.gov`, `.edu` or a famous newspaper does not make a page `primary`. Ask: *would a careful fact-checker cite this publisher as the origin?*
2. **Judge the two labels independently.** The right publisher on the wrong topic = `not_relevant` + `primary`/`authoritative_secondary`.
3. **Never judge whether the claim is true.** A page that refutes the claim is relevant.
4. **Do not search fact-check sites, and do not discuss items** with the other annotator until both of you have submitted.
5. **Write a note** for every `cannot_determine`, every conflict between sources, and every hard case.

### Illustrative guideline examples
*These were written by the protocol author to explain the rules. They are **not** annotation data and will not be used for training or evaluation.*

Claim (AVeriTeC dev 268): *"Donald Trump's 24 Sept 2020 executive order legally ensures health coverage protections for people with pre-existing conditions."*

| Document | Relevance | Authority | Why |
|---|---|---|---|
| `trumpwhitehouse.archives.gov/presidential-actions/executive-order-america-first-healthcare-plan` (text of the order) | relevant | primary | the issuer's official archive of the order itself |
| `cnbc.com/2020/09/24/trump-to-sign-executive-orders-on-preexisting-conditions...` | relevant | secondary_derivative | credible news *reporting* the order |
| `finance.senate.gov/ranking-members-news/wyden-blasts-...` (senator's press release criticising it) | relevant | not_authoritative *or* secondary_derivative (decide with the guide §6.4) | a `.gov` page, but partisan commentary; it does not issue or hold the order |

**Time:** about 1–2 minutes per pair. Take breaks every 45 minutes.
