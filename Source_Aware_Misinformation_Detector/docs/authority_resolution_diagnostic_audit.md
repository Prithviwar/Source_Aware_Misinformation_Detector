# Audit of the Authority-Resolution Bottleneck Diagnostic

*2026-10-28. Read-only audit of `docs/authority_resolution_bottleneck_analysis.md` (the "report") and
`experiments/authority_bottleneck_diagnostics.py` (the "diagnostic").*

**What this audit did not do:**

- run retrieval;
- make LLM, API or network calls;
- create, edit or score AI labels;
- modify frozen artifacts.

**The original report and its outputs are unchanged.** Errata are listed here (§7), not applied
there.

**Status labels used below:**

| Label | Meaning |
|---|---|
| **[Verified]** | Recomputed from frozen artifacts and checked |
| **[Oracle]** | A gold-using ceiling, never system performance |
| **[Heuristic]** | Depends on hand-written classification rules |
| **[AI-generated]** | Existing MODEL_GENERATED labels, counted descriptively; circular |
| **[Untested]** | A hypothesis |

## 0. Audit artifacts and files changed

| Path | Status | SHA-256 (prefix) |
|---|---|---|
| `experiments/authority_diagnostic_audit.py` | **new** (audit script) | `6e2f4753` (raw file) |
| `results/authority_bottleneck_diagnostics_audit/audit_summary.json` | **new** | `c39b4836` |
| `results/authority_bottleneck_diagnostics_audit/category_rule_audit.csv` | **new** (T4/T5/T7/T8 rows for manual review) | `636e3cfb` |
| `results/authority_bottleneck_diagnostics_audit/rerun/{summary.json, per_claim.csv, gold_urls.csv}` | **new** (re-run of the diagnostic) | `f9615d9a`, `c823f693`, `7d79d968` |
| `docs/authority_resolution_diagnostic_audit.md` | **new** (this file) | – |
| `experiments/__pycache__/` | bytecode refreshed by running Python; git-ignored | – |

**Unchanged.**

- `docs/authority_resolution_bottleneck_analysis.md`;
- `experiments/authority_bottleneck_diagnostics.py` (raw `66a962c0`);
- `results/authority_bottleneck_diagnostics/`: `summary.json` `4188fcf6`, `per_claim.csv` `c9b93e64`,
  `gold_urls.csv` `7d79d968`.

These hashes are identical before and after the audit.

**About the audit directory.** It was generated three times during this session: two fixes to the
audit script's own checks, and one added section. Each time it was deleted and rebuilt. Only the
final version is kept. It never overwrote a pre-existing output.

**How to reproduce.** Run `python experiments/authority_diagnostic_audit.py` (it refuses if the
audit directory exists).

---

## 1. Did the diagnostic run cleanly and read-only? [Verified]

- **Guards.** The audit script imports the diagnostic and runs `main()` with a redirected output
  directory (`…_audit/rerun/`). Before any import it patches:
  - `socket.socket.connect`, `socket.socket.connect_ex`, `socket.create_connection` and
    `socket.getaddrinfo` to raise;
  - `subprocess.Popen.__init__` to raise, which also covers `run`, `call` and `check_output`.

  The run **completed**, so no network connection, DNS lookup or subprocess (including the
  `claude` CLI) was attempted. `os.system` was not patched, but neither script uses it.
- **Static check.** The diagnostic imports `authority_resolution`, which *defines* the LLM `call()`,
  but it never invokes it. `tldextract` runs with `suffix_list_urls=()` (offline). No dense model or
  BM25 index is built; all rankings are read from the frozen `.jsonl.gz` files.
- **The reproduction gate passed again (all 52 checks).** It covers:
  - the 167 / 305 / 422 counts;
  - every stored GoldR@{1,3,5,10,20} of A–H;
  - the exact stored D top-100 order;
  - the exact stored targeted top-10 lists;
  - O R@10 = 0.659.
- **The re-run output is identical.**
  - Every `summary.json` section is identical except the `created` timestamp, and the
    provenance hashes are identical.
  - `gold_urls.csv` is byte-identical.
  - `per_claim.csv` differs **only in the display column `near_miss` in 13 rows.** The text lists
    the first 3 elements of a Python set, so it varies with hash randomisation. Categories and all
    counts are identical. **This is a minor reproducibility defect** (§7, E6).

## 2. Reconciliation of headline numbers [Verified]

All 70 numeric statements checked against `summary.json` match
(`audit_summary.json → 2_headline_checks`: 70/70). The ones you asked about:

| Quantity | Value | Note |
|---|---|---|
| Held-out claims | **200** | Your task text says "192 total claims"; that is not right. **192 is the number of claims with ≥ 1 web gold URL**; 8 have none |
| Claims with reachable gold | **167** | 25 claims have only unreachable web gold |
| Gold URLs | 422 (305 reachable, 117 unreachable) | Unique per claim |
| Corpus-reachability ceiling (hit-based, any k) | 1.0 over 167; **0.870** over 192 (Wilson [0.815, 0.910]); 0.835 over 200 | [Oracle/ceiling] |
| Doc-level ceiling, n = 167 | @1 0.682, @3 0.986, @5+ 1.0 | [Oracle/ceiling] |
| Baseline A R@10 / D R@10 | 0.251 / 0.293 | [Verified], equal to the frozen `results_heldout.json` |
| Candidate-pool coverage (hybrid top-100) | 0.671 (112/167) | [Verified]; F union pool 0.701, equal to frozen `Gold_claim_coverage` |
| Coverage at depth 200 / 300 / 500 | 0.850 / 0.922 / 0.964 | [Verified] |
| D @10: hit / ranking loss / pool loss | 49 / 63 / 55 | [Verified] |
| Authority top-3 match vs **all** gold publishers | 0.391 (75/192) | Frozen figure, quoted only |
| Authority match vs **reachable non-secondary** gold publishers | top-3 **53/105**, top-1 39/105 | [Verified]; class filter is [Heuristic]; "top-1" means the first entry *with a usable key* (see §4.2) |
| T1 claims (predicted key = publisher of a reachable gold doc) | 56 | [Verified] |
| Oracle publisher, pool 100 / full corpus | R@10 0.659 / 0.832 | [Oracle] |
| Oracle non-secondary publisher, pool 100 / full corpus | R@10 0.467 / 0.611 | [Oracle] + [Heuristic]; interpretation corrected in §4.6 |
| Stored H (targeted oracle) | R@10 0.868 | [Oracle], frozen |

**Definition discrepancies inside the report.** They are internally consistent but easy to misread.

1. **"Non-secondary" has two denominators.**
   - The oracle ladder uses the publisher keys of **all** gold URLs, including unreachable ones:
     124 claims have such a key.
   - The accuracy figure uses keys of **reachable** gold docs: 105 claims.
   - Both numbers are correct for their definitions.
2. **Gold publisher keys come from two functions.**
   - `gold_keys` (used by the oracles and T2) uses `target_keys(raw source_url)`.
   - T1 matching uses `cand_key(url_norm)`.
   - They disagree on 2 of 422 URLs:
     - #77 `archive.ph/EKPAJ`: `target_keys` returns ∅, `cand_key` returns `archive.ph`;
     - #108 a twitter search for `from:CNN`: `target_keys` returns `twitter.com/cnn`, `cand_key`
       returns bare `twitter.com`.
   - This has no effect on any headline count, but the two definitions should be unified.
3. **Report §3.2, "D hits@10 on 20 of 23".** Confirmed for the stricter reading as well: the
   authority's own gold doc is in D's top 10 in 20 of the 23 claims where it is in the pool.
4. **Medians** in the diagnostic are upper medians (`sorted(x)[n // 2]`). Values are unaffected
   where n is odd.

## 3. Gold-information use [Verified]

| Check | Result |
|---|---|
| Frozen retrieval modules read only `{url_norm, text}` | Yes. `ks_type` appears in `baseline_retrieval.claim_docs` only under `audit=True`, which the retrieval path never sets. `source_roles.csv` is read only in `authority_retrieval.oracle_primary_domains` (dev oracle) and `authority_resolution.load_targets` (dev evaluation; it also selects *which dev claim IDs* entered the dev authority study, as already documented there). |
| Frozen `source_targeted_eval.py` | Gold enters only through `gold_truth()` (scoring) and the separately labelled `ORACLE:targeted+prior` path |
| Predictor prompts (200 held-out L+Wctx prompts scanned) | **0** contain a full gold URL; **0** contain the fact-checking article URL. **14** mention a gold publisher's domain, all through Wikidata official-website context (claims 46, 52, 89, 108, 163, 200, 249, 262, 278, 312, 386, 444, 453, 496). Wikidata is a documented inference-time input, so this is legitimate, but it is a possible advantage worth reporting. |
| The diagnostic's deployable reconstructions (D re-rank, targeted list) | Use only the predictions and frozen rankings. Gold is used only in `hit()`, oracle rows, the taxonomy and the ceilings |
| **Risk found:** `DOMAIN_OVERRIDES` (143 domains) | Classified by an analysing session that had seen the gold URLs. It is diagnostic-only, but **must not be reused** in a deployable system, e.g. as the list for fixing the government rule. A gold-blind source (public-suffix list, an external registry of government domains) is required. |

## 4. Implementation audit: matching and category rules

### 4.1 Publisher keys (`cand_key`, `org_domain`, `target_keys`) [Verified counts]

| Issue | Evidence | Count |
|---|---|---|
| Malformed key | #495 `web.archihttps://joebiden.com/...` gives key `archihttps` (`strip_wayback` does not repair a truncated "archi" prefix) | 1 gold URL; the page is absent from the corpus, so no recall effect |
| Non-publisher gold keys (platform, redirect, hosting) | `google.com` 6, `amazonaws.com` 2, `perma.cc` 2, `govdelivery.com` 2, bare `twitter.com` 2; and 1 each of `google.com.ph`, `gannett-cdn.com`, `archive.ph`, `scribd.com`, `cloudfront.net`, `fb.com`, `blogspot.com`, `bit.ly`, `t.co`, `youtu.be`, `medium.com` | 26 gold URLs; the publisher identity is hidden |
| Over-merging keys | `go.com` merges ABC News, ABC local and ESPN. `archives.gov` merges NARA with the Trump and Obama White House archives. `gov.uk` merges every UK department. `medium.com` and `blogspot.com` merge all authors | `go.com` 2, `archives.gov` 2, `gov.uk` 2 gold URLs |
| Not normalised | `fb.com/...` is not mapped to `facebook.com/<handle>` | 1 gold URL, 1 predicted key |

### 4.2 Predicted keys (`pred_keys`) [Verified]

- **Unusable entries.** 13 of 600 predicted entries (in 11 claims: 61, 101, 180, 184, 234, 254,
  269, 293, 358, 444, 452) have no usable key and are silently dropped. For claim 180 the rank-1
  entry is dropped, so "top-1" uses rank 2.
- **Non-publisher predicted keys (7):** bare `twitter.com` (claims 312, 407), `youtube.com`
  (189, 312), `linkedin.com` (310), `fb.com` (163), `archive.org` (386). A bare platform key matches
  every handle-less page on that platform, so it is a potential false positive.
- **Broad predicted keys:** `archives.gov` 20×, `gov.uk` 9×, `un.org` 7×, `gob.mx` 3×,
  `europa.eu` 2×. A broad key boosts every document of that umbrella domain.

### 4.3 Authority matching (T1) [Verified, manually inspected]

The 56 T1 matches break down as follows:

- **49** match a specific publisher.
- **3** match a news outlet that is itself the subject of the claim (#10 Axios, #32 NY Post,
  #108 CNN). These are legitimate first-hand sources, but they are not "institutional authority".
- **4** match only through a broad key:
  - #168 `gov.uk` (DHSC predicted; gold on `gov.uk` and `legislation.gov.uk`);
  - #268 `archives.gov` (the Trump White House archive);
  - #360 `gov.uk` (DHSC; gold is a DHSC consultation);
  - #490 `europa.eu` (Commission; gold on `ec.europa.eu`).

  On inspection all 4 are substantively correct. **No false-positive T1 match was found**, but 4/56
  rest on merged keys, so the method's precision there is untested.

### 4.4 Generic-prior rules (`authority_retrieval.is_gov` / `generic_prior`; affects frozen B and C only) [Verified]

| Bug | Mechanism | Corpus docs affected (held-out) |
|---|---|---|
| **Commercial domain scored as government (false positive)** | `"go"` is in `GOV_LABELS` (meant for `go.jp`, `go.kr`), so `abcnews.go.com` and `dig.abclocal.go.com` score **1.0** | **913 docs** |
| Official site scored as unknown (false negative): bare government suffix hosts | `generic_prior` uses `full_host`, which strips `www.`, so the host `gov.uk` / `gov.za` / `gov.ie` / … has the government label first and is missed | 301 docs (`gov.uk` 241, `gov.za` 15, `gov.ie` 11, `gov.je` 8, `gov.mb.ca` 8, …). The audit rule itself has at least one false hit, `govt.chinadaily.com.cn` (1 doc) |
| Official site scored as unknown (false negative): no government label | `canada.ca`, `hse.ie`, `ohchr.org`, `opcw.org`, `undocs.org` | 379 docs (from the report's 620, minus `gov.uk`) |

**Effect on the report's "non-gold government docs in top-10" (§3.6).** These counts include ABC
News pages:

| System | Reported | of which `*.go.com` | Excluding `go.com` |
|---|---:|---:|---:|
| A | 130 | 20 | 110 |
| B generic | 762 | **118** | **644** |
| C heuristic | 673 | 116 | 557 |
| D LLM | 477 | 14 | 463 |

The direction of the finding stands: B and C push many more non-gold official pages into the top
10 than A. The B and C counts are about 15–17% overstated.

**Effect on the report's §1.5 count.** The report's "official docs scored unknown" count (620 docs,
113 claims) is incomplete. About 60 further docs sit on other bare government-suffix hosts.

### 4.5 Error-category rules (diagnostic `main()`, section 5) [Heuristic]

| Category | Rule problem found | Evidence | Effect |
|---|---|---|---|
| T3 claimant / subject account | Can only fire on *reachable* social gold, and only 6 reachable social gold docs exist; 22 social gold URLs are unreachable | 0 claims | "0" means the case is **unmeasurable**, not that it is rare. The report's T3 = 0 should not be read as rare |
| T4 identity near-miss | Low precision and recall. String-overlap rules | Of 5 hits, 2 genuine (#4 VITAS→Chemed; #475 multi-entity name emitting only `upenn.edu`), 3 spurious (#171 `india.com`~`india.gov.in`, #172 and #445 "health" overlaps). 2 genuine aliases are filed under T7 (#14 `un.org`/`undocs.org`, #248 `blog.gov.uk`) | The report's "≈ 4 identity failures" comes from manual review, not from the rule; the rule alone gives precision 2/5 and recall 2/4 on what was found |
| T5 all-secondary gold | Uses publisher **class**, not evidence **role** | Class labels look right on inspection of all 54. But a news page is first-hand when the claim is about news coverage or the outlet (#263 "No news coverage was given…", #110 the claim is a USA Today headline). [AI-generated] 4 of 54 T5 claims (#47, #263, #270, #338) have a reachable gold doc labelled primary | 54 is an **upper estimate**; ≈ 50 have no first-hand gold by the AI labels (circular) |
| T6 jurisdiction mismatch | Same `is_gov` false negative applied to bare keys (`gob.mx`, `gov.uk`) | With the corrected test (audit-only): #44 (UK pred vs US gold) and #183 (MX pred vs US gold) move T7 → T6 | Report's T6 = 0 and T7 = 25 should read T6 = 2, T7 = 23 |
| T7 / T8 | Inherit the class table; T8 is a residual | `category_rule_audit.csv` lists all rows | Approximate |
| Rule order | T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8, first match wins | – | Counts depend on the order. For example, a claim with both an alias and secondary-only gold is T4 |

**Regex news classification.** The `NEWS_FC_HINT`-only keys were all inspected:
`afp.com`, `brisbanetimes.com.au`, `buzzfeednews.com`, `dailymail.co.uk`, `detroitnews.com`,
`globalnews.ca`, `guardian.ng`, `newsobserver.com`, `newsroom.co.nz`, `newsweek.com`, `nypost.com`,
`seattletimes.com`, `startribune.com`, `thenassauguardian.com`. All are news outlets, so no false
positive was found.

### 4.6 Oracle definitions [Oracle]

- **ORACLE "non-secondary"** removes only news, fact-check and reference publishers. [AI-generated]
  Of 155 reachable gold docs from the remaining publishers, only 79 are labelled primary; 47 are
  secondary and 21 derived.
- **ORACLE-NS (0.611 / 0.467) is therefore a "non-news publisher" oracle, not a "first-hand
  authority" oracle.** The report's wording ("approximating what a claim-specific authority
  resolver is supposed to name") overstates it. The true first-hand bound is unknown, and probably
  lower.
- `ORACLE_pub_all_gold_full_lambda1` equals the site-filter variant **by construction**. Min-max
  scores lie in [0, 1], so λ = 1 with a binary prior is a hard filter. It is not an independent
  confirmation.
- **All publisher oracles use the publishers of the scored gold documents.** They are partly
  circular; 13/167 claims degenerate to a URL oracle.

---

## 5. Frozen artifacts unchanged [Verified]

| File (recorded hash source) | Match | Form that matches |
|---|---|---|
| `results/source_targeted/rankings_heldout.jsonl.gz` (Addendum 2) | ✔ | raw bytes |
| `experiments/validation_heldout.py` (validation prereg) | ✔ | LF-normalised |
| `experiments/source_targeted.py`, `source_targeted_eval.py` (Addendum 1) | ✔ | LF |
| `experiments/score_heldout_primary.py` (scorer, Addendum 2) | ✔ | LF |
| `experiments/authority_resolution.py`, `authority_retrieval.py` (prefix…suffix only) | ✔ | raw bytes |
| `experiments/baseline_retrieval.py` (prefix…suffix only) | ✔ | LF |
| `heldout_primary_annotation.csv` (blank sheet, prefix only) | ✔ | raw bytes |
| `AI_EVIDENCE_PROMPT.md`, `AI_CLAIM_PROMPT.md`, `ANNOTATION_GUIDE.md`, `ai_annotate.py`, `score_ai_primary.py` (`FROZEN_HASHES.json`) | ✔ | LF |
| `results/authority_quality_ablation_phase2/x1_assignment.csv` (`.sha256` file) | ✔ | – |

- **15/15 match exactly.** The freeze recorded some files as LF and some as raw CRLF bytes; each
  file matches exactly one form. Record this when re-verifying on another OS.
- **`git status --porcelain`** lists only new untracked paths: the two reports, two scripts and two
  result directories. `git status --ignored` adds only `experiments/__pycache__/`. No tracked file
  differs from `HEAD`.
- **Not done:** no preregistration, canonical annotation, ranking, prediction or scoring file was
  edited, and the 192-claim AI-primary labels were neither generated nor scored.

---

## 6. Separation of findings by evidential status

| Status | Findings |
|---|---|
| **Directly verified measurements** | 200 / 192 / 167 claims; 422 / 305 / 117 gold URLs; reachability by medium and archive flag; pool coverage curve (0.671 @100 … 0.964 @500); A–G R@k and the hit / ranking / pool decomposition; T1 = 56 (key-level); 33 of 56 T1 authority-gold docs outside the pool, with targeted positions ≤ 10: 11, ≤ 20: 19, ≤ 50: 31; 20/23 in-pool T1 hits; displacement (D 19, G 68 claims with ≥ 5 non-gold predicted-publisher docs in the top 10); 0 loose-canonical rescues; the `go.com` and bare-suffix prior bugs; 13 keyless predicted entries; 0 gold URLs in predictor prompts |
| **Oracle / ceiling estimates** | 1.0 / 0.870 / 0.835 claim ceilings; doc-level ceilings; URL oracle 0.671 (pool); publisher oracle 0.659 / 0.832; non-secondary oracle 0.467 / 0.611; stored H 0.868 |
| **Heuristic classifications** | Publisher classes; "non-secondary"; reachability by class; T3–T8 counts (T5 = 54, T7 = 25 → 23 after the T6 fix, T8 = 18); top-3 accuracy 53/105 (the denominator is heuristic); about 4 alias failures (manual) |
| **AI-generated (descriptive, circular)** | Primary 61% vs secondary 79% reachable; primary 41% vs secondary 61% in pool; 4/54 T5 claims with AI-primary gold; 79/155 non-secondary-class docs labelled primary |
| **Untested hypotheses** | Institution-specific queries would recover out-of-pool authority docs; pool-grounded LLM authority beats memory-based; caps and graded priors remove displacement; disappearance of official pages explains part of the unreachable gov gold; syndication effects on held-out; every expected gain in report §5 |

## 7. Errata and unresolved discrepancies

| ID | Item | Severity | Status |
|---|---|---|---|
| E1 | Task statement "192 total claims": the held-out set has **200**; 192 is the web-gold subset | Wording | Resolved here; the report uses 200/192/167 correctly |
| E2 | Report §3.6 non-gold "gov" counts include 118 (B) / 116 (C) / 14 (D) / 20 (A) ABC News pages | Moderate | Corrected values in §4.4; the original report is not edited |
| E3 | Report §1.5 "620 docs scored unknown" omits about 60 docs on other bare government-suffix hosts, and omits the `go.com` false positive (913 docs) entirely | Moderate | Unresolved in the report; quantified here |
| E4 | T6 = 0 is an artifact of the bare-key `is_gov` test; corrected T6 = 2, T7 = 23 | Minor | Unresolved in the diagnostic's outputs |
| E5 | ORACLE-NS described as approximating claim-specific authority; it is a non-news oracle (about half of its docs are AI-labelled non-primary) | Moderate for planning | Unresolved; the true first-hand bound is unknown |
| E6 | `per_claim.csv` `near_miss` text is nondeterministic (set order) | Minor | Unresolved; fix with `sorted()` in a future version |
| E7 | Two gold-key functions (`target_keys` vs `cand_key`) disagree on 2 URLs | Minor | Unresolved |
| E8 | T4 rule precision 2/5; 2 genuine aliases are filed under T7 | Minor | The report's "≈ 4" relies on manual review |
| E9 | T3 = 0 reflects unreachable social gold, not rarity | Minor | Interpretation note |
| E10 | "Absent from KS" vs "empty text" cannot be separated (`data/raw/` missing) | Limitation | Unresolved; needs the KS extracts |
| E11 | `DOMAIN_OVERRIDES` was built with gold exposure | Leakage risk for future work | Must not enter deployable code |

## 8. Decision table

| Finding | Evidence | Confidence | Limitation | Safe for experiment planning? |
|---|---|---|---|---|
| 200 claims; 192 with web gold; 167 with reachable gold; ceiling 0.870 over 192 | Gate plus exact reproduction of frozen counts | High | Absent vs empty KS docs are not separable | **Yes** |
| Hybrid top-100 pool covers 0.671; deeper pools reach 0.85 / 0.92 / 0.96 at 200 / 300 / 500 | Frozen full rankings | High | Single held-out set | **Yes** |
| D @10 loses 55 claims before ranking and 63 in ranking | Frozen rankings; reproduces frozen R@k | High | – | **Yes** |
| Correct authority, evidence outside pool: 33/56 T1; ≤ 50-deep targeting would include 31 | Exact replay of the frozen targeting | High (mechanism); oracle-type for "would include" | Uses gold to locate the doc; recovery into the top 10 is untested | **Yes, as motivation**; the effect size must be tested on fresh claims |
| When the authority's gold is in the pool, D ranks it top-10 (20/23) | Frozen D ranking | High | n = 23 | **Yes** |
| Binary prior and targeting displace gold (D 19, G 68 claims) | Frozen rankings | High | Counts non-gold, not irrelevant, docs | **Yes** |
| Predictor top-3 matches 53/105 non-secondary gold publishers | Frozen predictions | Medium | Class filter is heuristic; first-usable-key "top-1" | **Yes, as an approximate figure** |
| 54/167 claims have only secondary-class gold | Heuristic classes; 4 contradicted by AI labels | Medium | Class ≠ role; AI labels are circular | **With caution**: use ~50–54 and plan a human audit |
| Non-secondary publisher oracle 0.611 (full) / 0.467 (pool) | Oracle | Medium | Non-news, not first-hand; circular | **Only as a loose upper bound**, not as "authority headroom" |
| Publisher oracle 0.659 / 0.832; H 0.868 | Oracle | High (as computed) | Includes news publishers; circular | **Only as ceilings, never as performance** |
| URL canonicalization loses no gold; aliases ≈ 4 claims | Loose-match check; manual review | Medium-High | Loose rule set is finite; manual alias review by one session | **Yes**: deprioritise canonicalization |
| Generic-prior bugs (`go.com` → gov; bare-suffix gov → unknown) | Code and corpus counts | High | Affects B/C only, not D/G | **Yes**: any new credibility baseline must fix them **declared and gold-blind**, without editing the frozen B/C |
| §3.6 over-boosting volume (B 762, C 673) | Corrected 644 / 557 excluding `go.com` | High | – | **Yes, with the corrected numbers** |
| T6/T7 split, T4 counts | Heuristic rules with known errors | Low-Medium | See §4.5 | **No** for sizing; use only as illustrations |
| T3 = 0 | Rule cannot see unreachable social gold | Low | – | **No** |
| No gold in deployable queries, sources or ranking | Code read, prompt scan, runtime guards | High | 14 prompts carry gold domains via Wikidata (legitimate input) | **Yes** |
| Frozen artifacts unchanged | 15/15 hashes; git status | High | Mixed LF/CRLF recording at freeze | **Yes** |
