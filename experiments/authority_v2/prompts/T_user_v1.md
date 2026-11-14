Claim: {claim}
Speaker/claimant field: {speaker}
Claim date: {date}
Country (ISO): {iso}
{wd}
Publishers of the candidate documents retrieved for this claim (publisher key, then the number of candidate documents from that publisher), in alphabetical order of key:
{pool}

Select at most 3 publishers FROM THIS LIST that are first-hand authorities for the claim's central fact, or abstain if none of them is.
Return JSON with exactly these keys:
{{"fact_at_issue": "<the specific checkable fact, one sentence>",
  "selections": [
    {{"key": "<a publisher key copied exactly from the list>", "publisher_type": "<government | intergovernmental | court_or_legislature | regulator_or_database | organisation | company | person | research | news | other>", "why": "<short>"}}
    ... 0 to 3 items, most likely first ...
  ],
  "abstain": <true if no listed publisher is a first-hand authority for the fact, else false>,
  "confidence": <0.0-1.0 that your first selection is right>}}
