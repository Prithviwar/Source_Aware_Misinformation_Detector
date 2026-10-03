# Annotation guide: who is the primary source for this claim?

**Your task.** For each of the **192 claims** in `heldout_primary_annotation.csv` (or the `.xlsx` copy), name the publisher or publishers that would be a **first-hand (primary) source for the fact the claim is about**.

- You judge **from the claim alone**. You are not shown any evidence, search results or model output, and you should not look for them.
- **Allow about 1–2 minutes per claim (4–6 hours total).** You can split it over several sessions.

---

## 1. The question to ask

> If someone wanted to check this claim at the source, **which institution, organisation or person issued, recorded or holds the fact itself**, and where do they publish it?

Judge **who originates the fact**, not who is trustworthy. A reputable newspaper that *reports* what a ministry said is **not** the primary source; the ministry is.

## 2. Source roles (definitions)

Only **primary** sources go into the `authority_*` columns. The other roles are defined so you know what to leave out.

| Role | Definition | Examples |
|---|---|---|
| **Primary / authoritative** | First-hand for the fact at issue. See the list below. | A ministry's press release; the national statistics office's table; a court judgment; a company's own announcement; a politician's own tweet or speech transcript; the journal that published the study. |
| **Secondary** | Reports on, explains or checks someone else's information. | News agencies and newspapers, TV sites, magazines, fact-checkers, explainers, advocacy or law-firm commentary, blogs. |
| **Derived / syndicated** | Compiles, mirrors, re-hosts or syndicates others' content. | Wikipedia and other encyclopedias; aggregators and trackers; syndicated copies of wire stories; a third-party site re-hosting a government PDF; LegiScan's copy of a bill. |
| **Unclear** | You cannot tell who, if anyone, is first-hand. | Very vague claims; claims whose subject cannot be identified. |

A source is **primary** when it is one of these:

- the government body, intergovernmental body, court, legislature, regulator or election body that issued, records or holds the fact, data, law or decision;
- the organisation or company itself, when the claim is about its own actions, products, policies or statements;
- the original research or data producer;
- for claims about **what someone said, did or posted**: that person's or account's own statement, post or official channel.

## 3. Claim-level situations (column `authority_situation`)

| Value | Use when |
|---|---|
| `single_primary` | One publisher is clearly the first-hand source. List it as authority 1. You may still list up to two more *possible* primaries in order of likelihood. |
| `multiple_legitimate_authorities` | **Two or more** publishers are each genuinely first-hand, e.g. the health ministry *and* the national statistics office, or both governments in a bilateral event. List them (2–3), most central first. **This is allowed and expected; do not force a single answer.** |
| `no_identifiable_primary` | The fact has no first-hand publisher you could point to. Examples: pure opinion, a rumour with no originating record, or a claim whose only record is secondary reporting. Leave the authority columns empty. |
| `unclear` | You cannot decide, e.g. the claim is too vague or you do not know the domain. Fill authorities if you have a best guess, and explain in `notes`. |

### 3a. Hard cases (how to apply §2–§3; the definitions themselves are unchanged)

- **Claims with several factual parts** (two figures; an event plus its cause; a decision plus an alleged motive, link or intention).
  - For each part that could be checked against a record, ask who issued or holds that record. List those publishers, the most central part first, **up to 3 in total**. If more than 3 would apply, keep the most central and name the others in `notes`.
  - If different parts have different first-hand publishers, use `multiple_legitimate_authorities`.
  - An alleged motive, intention or hidden link usually has no first-hand publisher of its own. List the publishers of the checkable parts around it: the relationship, the vote, the decision, the document.
  - Use `no_identifiable_primary` only when **no** part has a first-hand publisher. Use `unclear` when you cannot tell which part the claim is really about.
- **"X said Y" claims** (X is a named person or organisation; "X says …", "according to X …").
  - The claim is about **what X said**, so X's own statement or channel is authority 1.
  - If the claim *also* presents Y as a fact in its own voice, or you cannot tell whether it is about the statement or the fact, also list the authority on Y and use `multiple_legitimate_authorities`.
- **"X did Y" at an event** (a speech, ceremony, match, inspection, public appearance). List X's own channel and, if one exists, the body that organised the event or officially recorded it.
- **Observed or visual events** (what was seen, shown, displayed or happened in public).
  - List a body only if it would plausibly hold **its own record of this particular event**. That means the organiser's own channel, or an agency whose job is to monitor and report that kind of event in that place.
  - A body that is an expert on the topic in general is **not** enough.
  - If the only first-hand record you can think of is third-party footage, photos or eyewitness posts, use `unclear` and say so in `notes`.
- **Statistics, estimates, rankings and indices.**
  - The body that **produces and publishes** a figure, estimate, ranking or index is first-hand for that figure. This includes an international body that publishes its own official estimates or data series.
  - A site that only re-hosts, quotes or summarises someone else's figure is derived (§2).
  - **Historical figures about a country** (e.g. a rate or total from decades ago): list the country's statistics office and, if you know one, an international body that publishes its own historical series for that figure. Use `multiple_legitimate_authorities`.
  - **Evaluative claims** ("performed poorly", "worst in the world", "third most …"): list the producer(s) of the data or index that such a judgement would rest on. If there are several standard sources, use `multiple_legitimate_authorities`.
- **More than one possible authority.** Do not force a single answer. If a second publisher is also first-hand, list it after the main one. If you are unsure whether it is first-hand, you may still list it and explain why in `notes`. Do not list publishers that are not first-hand just to be safe; news outlets, fact-checkers and encyclopedias are never listed.
- **You know who, but not their domain or account.** First try a lookup (§6). If you still cannot find one:
  - do not list that authority. Leave its name, domain and type columns empty;
  - write `missing key: <name>` in `notes`;
  - if no authority on the row has a domain or account, use `unclear`.
- **Two authorities on the same website** (e.g. two agencies on one government portal). List both; that is fine.

## 4. Columns you fill (leave `row`, `claim_id`, `claim_text`, `claim_speaker`, `claim_date`, `claim_country` unchanged)

| Column | What to enter |
|---|---|
| `annotator_id` | Your initials, the same on every row. |
| `authority_situation` | One value from §3. |
| `authority_N_name` (N = 1, 2, 3) | The publisher's name, e.g. "Nigeria Centre for Disease Control". Leave unused authorities empty. |
| `authority_N_domain_or_account` | Its web domain (`ncdc.gov.ng`) and/or its official social account as **platform/handle** (`twitter.com/ncdcgov`). Separate several with `;`. **List every official domain or account you know for this publisher**, including separate sites it runs for particular reports, data portals or campaigns. A domain is enough; a full web address or a subdomain is also fine. Do **not** write a bare `@handle`. This column is what gets matched, so it must be a real domain or account. If you cannot find one, leave this authority's name, domain and type empty and follow §3a ("missing key"). |
| `authority_N_type` | One of the types in §5. |
| `authority_rationale` | One line: why these publishers are first-hand for *this* fact. |
| `confidence` | `high` / `medium` / `low`: how sure you are about the whole row. |
| `research_used` | `none` if you answered from knowledge. `institution_lookup_only` if you looked up an institution's website or account (§6). |
| `notes` | Optional: ambiguity, alternatives you rejected, anything the reviewer should know. |

**Rules.**

- **Order matters.** List authorities from most to least central.
- **Record uncertainty explicitly.**
  - Use `confidence` on every row.
  - Use `unclear` rather than guessing silently.
  - Say in `notes` which part you are unsure of: the publisher, or its domain.

## 5. Authority types (`authority_N_type`)

| Type | Examples |
|---|---|
| `government_executive` | Presidency, ministries, departments, state/provincial governments, police services, police oversight/complaints bodies, police-run fraud-reporting centres |
| `legislature` | Parliament, Congress, legislative record sites |
| `court_or_prosecutor` | Courts, attorneys general, prosecutors |
| `regulator_or_election_body` | Central bank, FDA, election commission |
| `statistics_or_data_agency` | National statistics office, census bureau |
| `intergovernmental_org` | WHO, UN, World Bank, IMF |
| `health_or_science_agency` | CDC, NCDC, national science academies, NASA |
| `academic_or_research_producer` | The university, journal or institute that produced the study or data |
| `organisation_about_itself` | A company, NGO, party or club, when the claim is about its own actions or statements |
| `person_own_statement_or_account` | The person's own speech, post or official channel, for "X said/did Y" claims |
| `other` | Anything else. Explain in `notes`. |

## 6. What you may and may not look up

**Allowed:** finding the official website or social account of an **institution, organisation or named person that you have already identified**, either because the claim names it or from your own knowledge. Example: searching "Kenya Ministry of Health official website".

- Search by the **name only**, plus "official website" or "official account".
- If the claim itself **names** a report, index or dataset, you may search for that name plus "official website".
- Stop at the official site or account. Do not open any result that is about the claim.
- Mark `research_used = institution_lookup_only`.

**Not allowed:**

- searching to find out **who** produces, publishes or holds a figure, ranking, index, record or event that the claim mentions without naming its source (e.g. "who publishes the [topic] ranking", "which agency records [topic]"). That identification must come from the claim or from your own knowledge. If you know the name but not the domain, use the missing-key rule (§3a). If you cannot name any publisher, use `unclear`;
- searching the claim itself, its keywords or its fact-check;
- opening fact-checking sites or AVeriTeC material;
- using an AI assistant or chatbot for this task;
- opening any project file other than this package, especially anything under `results/`, `docs/`, the other files in `data/annotations/`, or `data/processed/`.

These restrictions keep the annotation **independent of the evaluation**.

## 7. Worked examples (invented claims, not from the sheet)

All names and domains in the examples marked `.example` are invented. In the sheet, always enter real domains or accounts.

| Claim | Situation | Authorities | Why |
|---|---|---|---|
| "Kenya's unemployment rate hit 40% in 2020." | `single_primary` | Kenya National Bureau of Statistics, `knbs.or.ke`, `statistics_or_data_agency` | The statistics office produces the official rate. News reports are secondary. |
| "Germany and Poland signed a new border agreement this week." | `multiple_legitimate_authorities` | German Federal Government, `bundesregierung.de`, `government_executive`; Government of Poland, `gov.pl`, `government_executive` | Both signatories publish the agreement first-hand. |
| "Senator X tweeted that vaccines contain microchips." | `single_primary` | Senator X, `twitter.com/senatorx`, `person_own_statement_or_account` | Whether X said it is settled by X's own account. The science question is not what the claim asserts. |
| "Nike stopped selling in China." | `single_primary` | Nike, `nike.com; twitter.com/nike`, `organisation_about_itself` | The claim is about the company's own action. |
| "Everyone knows the moon landing was staged." | `no_identifiable_primary` | – | An opinion with no originating record. (NASA could be argued; if you think so, use `unclear` and note it.) |
| "Valdoria's exports fell 12% last year, and its central bank cut interest rates twice." | `multiple_legitimate_authorities` | Valdoria Statistics Office, `stats.valdoria.example`, `statistics_or_data_agency`; Central Bank of Valdoria, `centralbank.valdoria.example`, `regulator_or_election_body` | Two checkable parts with different first-hand publishers: the trade figure and the rate decisions. |
| "According to the Norland Football Association, the national stadium holds 90,000 people." | `single_primary` | Norland Football Association, `norlandfa.example; twitter.com/norlandfa`, `organisation_about_itself` | The claim reports what the association said, so its own channel is authority 1. If the claim had stated the capacity as a fact in its own voice, the stadium's operator would be added (`multiple_legitimate_authorities`). |
| "Footballer Jon Arro wore a T-shirt with a political slogan during the Valdoria cup final." | `multiple_legitimate_authorities` | Jon Arro, `instagram.com/jonarro`, `person_own_statement_or_account`; Valdoria Premier League (organiser), `vpl.example`, `organisation_about_itself` | "X did Y" at an event: X's own channel plus the organiser's own record of the match. |
| "A large crowd gathered outside Eastvale station on Tuesday night to watch a street performer." | `unclear` | – (notes: "no body would hold its own record of this; only eyewitness posts or footage") | An observed event with no organiser or monitoring agency. A general expert body would not count. |
| "Norland's adult literacy rate was 30% in 1960." | `multiple_legitimate_authorities` | Norland Statistics Office, `stats.norland.example`, `statistics_or_data_agency`; International Education Data Institute (publishes its own historical series), `iedi.example`, `intergovernmental_org` | A historical national figure: the national producer plus an international body that publishes its own series. |
| "Norland's universities dropped out of the top 100 of the Global University Table." | `single_primary` | Higher Education Review (producer of the table), `hereview.example; universitytable.example`, `academic_or_research_producer` | The producer of the named ranking is first-hand. Both of its official sites are listed (§4). |
| "Composer Lio Marsh donated his entire prize money to Eastvale Children's Hospital." | `multiple_legitimate_authorities` | Eastvale Children's Hospital, `eastvalechildrens.example`, `organisation_about_itself` (notes: "missing key: Lio Marsh, no official site or account found by name lookup") | Both the composer and the hospital are first-hand. Only the hospital has a findable domain, so the composer goes in `notes`, not in the authority columns (§3a). |

For "X said Y" and "X did Y" claims, follow §3a: X's own statement or channel comes first; add the authority on the fact itself when the claim also asserts it, or when you are unsure.

## 8. When you finish

1. Save the CSV (or the xlsx, but only one of the two) with your initials in the filename, e.g. `heldout_primary_annotation_AB.csv`.
2. Do not re-sort, add or delete rows.
3. Return it to the project owner.
