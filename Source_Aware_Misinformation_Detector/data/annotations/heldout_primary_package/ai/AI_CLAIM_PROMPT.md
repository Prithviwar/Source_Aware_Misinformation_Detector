<!-- SYSTEM -->
You are annotating one claim for a fact-checking research dataset, following the annotation guide below exactly.
You have no tools and no web access: answer from your own knowledge only. Ignore guide §6 (lookups) and §8 (saving files); set "research_used" to "none".
Output ONLY one JSON object, no prose, no code fences.

===== ANNOTATION GUIDE (verbatim) =====
{guide}
===== END OF GUIDE =====
<!-- USER -->
CLAIM
- Claim: {claim_text}
- Speaker: {claim_speaker}
- Claim date (day-month-year): {claim_date}
- Country: {claim_country}

Annotate this claim as the guide describes. If you cannot give a real domain or account for an authority, apply the guide's "missing key" rule.

OUTPUT: one JSON object with exactly these keys (use "" for unused fields)
{"authority_situation": "single_primary" | "multiple_legitimate_authorities" | "no_identifiable_primary" | "unclear",
 "authority_1_name": "", "authority_1_domain_or_account": "", "authority_1_type": "",
 "authority_2_name": "", "authority_2_domain_or_account": "", "authority_2_type": "",
 "authority_3_name": "", "authority_3_domain_or_account": "", "authority_3_type": "",
 "authority_rationale": "<one line>",
 "confidence": "high" | "medium" | "low",
 "research_used": "none",
 "notes": ""}
