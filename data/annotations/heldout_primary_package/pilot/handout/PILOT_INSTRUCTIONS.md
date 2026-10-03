# Pilot: 15 claims

This is a short trial run of the full task (192 claims). It checks whether the guide is clear before you do the rest. Your answers are **not** used as results.

## Files in this folder

- `heldout_primary_pilot15.csv` or `heldout_primary_pilot15.xlsx` is your sheet. Fill **one** of them, not both.
- `ANNOTATION_GUIDE.md` is the full guide. Read §1–§6 once before you start; it takes about 10 minutes.
- `PILOT_FEEDBACK.md` is a short form to fill at the end.

## The one rule that matters

For each claim, name who **actually issued, recorded or holds the fact**. Do **not** name who is merely credible.

- A newspaper, TV site, fact-checker, Wikipedia page, aggregator or mirror that *reports* the fact is **not** the answer. The ministry, agency, court, company, research producer, or the person's own account that the fact comes from **is**.

## What to fill for each of the 15 rows

Leave `row`, `claim_id`, `claim_text`, `claim_speaker`, `claim_date` and `claim_country` unchanged. The date is in day-month-year format.

1. **`annotator_id`**: your initials.
2. **`authority_situation`**: choose one.
   - `single_primary`: one publisher clearly issued or holds the fact.
   - `multiple_legitimate_authorities`: two or three publishers are each genuinely first-hand. List 2–3. This is allowed; don't force one.
   - `no_identifiable_primary`: nothing first-hand exists, e.g. opinion or a rumour with no originating record. Leave the authorities empty.
   - `unclear`: you cannot decide. Give a best guess if you have one, and explain in `notes`.
3. **Up to 3 authorities**, most central first. For each one:
   - **`authority_N_name`**: e.g. "Kenya National Bureau of Statistics".
   - **`authority_N_domain_or_account`**: a web domain (`knbs.or.ke`) and/or an official account written as platform/handle (`twitter.com/knbs_kenya`). Separate several with `;`. List **every** official domain or account you know for that publisher. A domain is enough; a full web address is also fine. **Never a bare `@handle`.**
   - **No domain or account found?** Leave that authority's name, domain and type empty, and write `missing key: <name>` in `notes`. If no authority on the row has a domain or account, choose `unclear`.
   - **`authority_N_type`**: one value from the dropdown (guide §5).
4. **`authority_rationale`**: one line on why these publishers are first-hand for *this* fact.
5. **`confidence`**: `high`, `medium` or `low`, for the whole row. Low is fine; record it honestly.
6. **`research_used`**: `none`, or `institution_lookup_only` if you looked up an institution's website or account.
7. **`notes`**: optional. Say what you are unsure about (the publisher, or its domain) and any alternatives you rejected.

Source roles, for reference (guide §2):

- **Primary** is first-hand. Only primary sources go in the authority columns.
- **Secondary** reports on the fact.
- **Derived/syndicated** compiles, mirrors or re-hosts others' content.
- **Unclear** means you cannot tell.

For "X said Y" and "X did Y" claims (guide §3a):

- X's own statement or channel is authority 1.
- If the claim also presents Y as a fact in its own voice, or you cannot tell, also list the authority on Y and use `multiple_legitimate_authorities`.
- For something X did at an event, also list the organiser or official recorder of the event, if one exists.

## Allowed and not allowed

- **Allowed:** looking up the official website or account of an **institution, organisation or named person you have already identified** (named in the claim, or known to you), only to find its domain or account. Search by name only, and don't open results about the claim. If the claim names a report or index, you may search that name plus "official website".
- **Hard cases** are covered in guide §3a: claims with several parts, "X said Y" and "X did Y", observed events, statistics and indices, more than one possible authority, a missing domain, and two authorities on one site.
- **Not allowed:**
  - searching to find out **who** produces or holds a figure, ranking, index or record that the claim mentions without naming its source;
  - searching the claim or its keywords;
  - looking up fact-checks of it or anything about AVeriTeC;
  - using any AI assistant or chatbot;
  - opening any file outside this folder.

## When you finish

1. Note how long the 15 claims took in total.
2. Fill `PILOT_FEEDBACK.md`.
3. Rename your sheet `heldout_primary_pilot15_<INITIALS>.csv`, or `.xlsx` if you used Excel.
4. Send both files back. Don't edit the sheet after sending it.

Expected time: about 30–45 minutes, including reading the guide.
