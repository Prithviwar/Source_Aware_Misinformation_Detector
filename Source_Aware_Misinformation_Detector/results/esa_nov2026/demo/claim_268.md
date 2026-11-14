```text
=== Claim 268 (heldout200, mode=frozen) ===
Claim   : US President Donald Trump's executive order on September 24, 2020 legally ensures health coverage protections for those with pre existing medical conditions.
Speaker : Jon McConnell | date 25-9-2020 | country US
Candidates in this claim's knowledge store (non-empty, deduplicated): 1070
Query terms used by BM25: us, president, donald, trump, executive, order, september, 24, 2020, legally, ensures, health, coverage, protections, those, pre, existing, medical, conditions

--- BM25 top-10 ---
 #  BM25  Dns  Hyb  gold  url  [matched query terms]
 1     1    7    1        cnbc.com/2020/09/24/trump-to-sign-executive-orders-on-preexisting-conditions-sur  [us, president, donald, trump, executive, order, legally, health]
 2     2   42   10        cnn.com/2020/09/21/politics/supreme-court-obamacare-affordable-care-act/index.ht  [us, president, donald, trump, executive, order, september, 2020]
 3     3   25    3        americanprogress.org/press/statement-caps-topher-spiro-says-executive-order-crea  [us, president, donald, trump, executive, order, september, 24]
 4     4   10    2        upi.com/Top_News/US/2020/09/24/Trump-outlines-healthcare-plan-ensures-coverage-f  [president, donald, trump, executive, order, 24, 2020, health]
 5     5   33    9        advisory.com/daily-briefing/2020/09/25/executive-orders  [us, president, trump, executive, order, 24, health, coverage]
 6     6   41   11        pnhp.org/news/trumps-america-first-healthcare-plan  [us, president, trump, executive, order, september, 24, 2020]
 7     7  808   47        americanprogress.org/article/religious-liberty-no-harm  [us, president, donald, trump, executive, order, 24, legally]
 8     8  235   34        kff.org/report-section/president-trumps-record-on-health-care-issue-brief  [us, president, trump, executive, order, september, 2020, health]
 9     9  113   22        factcheck.org/2020/09/biden-misleads-on-preexisting-conditions  [us, president, donald, trump, order, 24, health, coverage]
10    10  157   30        en.wikipedia.org/wiki/Pre-existing_condition  [president, trump, executive, order, september, 24, 2020, health]

--- MiniLM dense top-10 ---
 #  BM25  Dns  Hyb  gold  url  [matched query terms]
 1   222    1   25        aamc.org/advocacy-policy/washington-highlights/president-trump-signs-executive-o  [president, donald, trump, executive, order, 24, health, coverage]
 2   242    2   27        aha.org/news/headline/2020-09-25-trump-signs-executive-order-variety-health-care  [president, trump, executive, order, health, pre, existing, medical]
 3    35    3    6        nbcnews.com/politics/white-house/trump-signs-eos-health-care-does-little-change-  [president, donald, trump, executive, order, health, protections, those]
 4   382    4   36        kff.org/hivaids/issue-brief/short-term-limited-duration-plans-and-hiv/view/footn  [president, donald, trump, executive, order, health, coverage, conditions]
 5    30    5    5        abc7chicago.com/donald-trump-executive-order-president-preexisting-conditions/65  [us, president, donald, trump, executive, order, 2020, health]
 6    31    6    8        abc7ny.com/donald-trump-executive-order-president-preexisting-conditions/6543235  [us, president, donald, trump, executive, order, 2020, health]
 7     1    7    1        cnbc.com/2020/09/24/trump-to-sign-executive-orders-on-preexisting-conditions-sur  [us, president, donald, trump, executive, order, legally, health]
 8    51    8   12        ebglaw.com/insights/publications/assessing-president-trumps-executive-order-prom  [president, donald, trump, executive, order, legally, health, coverage]
 9    69    9   17        cbpp.org/research/health-care-executive-order-would-destabilize-insurance-market  [president, trump, executive, order, health, coverage, protections, those]
10     4   10    2        upi.com/Top_News/US/2020/09/24/Trump-outlines-healthcare-plan-ensures-coverage-f  [president, donald, trump, executive, order, 24, 2020, health]

--- Hybrid RRF (k=60) top-10 ---
 #  BM25  Dns  Hyb  gold  url  [matched query terms]
 1     1    7    1        cnbc.com/2020/09/24/trump-to-sign-executive-orders-on-preexisting-conditions-sur  [us, president, donald, trump, executive, order, legally, health]
 2     4   10    2        upi.com/Top_News/US/2020/09/24/Trump-outlines-healthcare-plan-ensures-coverage-f  [president, donald, trump, executive, order, 24, 2020, health]
 3     3   25    3        americanprogress.org/press/statement-caps-topher-spiro-says-executive-order-crea  [us, president, donald, trump, executive, order, september, 24]
 4    15   13    4        bbc.com/news/world-us-canada-41599532  [us, president, donald, trump, executive, order, health, coverage]
 5    30    5    5        abc7chicago.com/donald-trump-executive-order-president-preexisting-conditions/65  [us, president, donald, trump, executive, order, 2020, health]
 6    35    3    6        nbcnews.com/politics/white-house/trump-signs-eos-health-care-does-little-change-  [president, donald, trump, executive, order, health, protections, those]
 7    11   22    7        kffhealthnews.org/morning-breakout/trump-affirms-preexisting-condition-protectio  [president, donald, trump, executive, order, health, coverage, protections]
 8    31    6    8        abc7ny.com/donald-trump-executive-order-president-preexisting-conditions/6543235  [us, president, donald, trump, executive, order, 2020, health]
 9     5   33    9        advisory.com/daily-briefing/2020/09/25/executive-orders  [us, president, trump, executive, order, 24, health, coverage]
10     2   42   10        cnn.com/2020/09/21/politics/supreme-court-obamacare-affordable-care-act/index.ht  [us, president, donald, trump, executive, order, september, 2020]

Top-10 overlap: BM25&Dense 2, BM25&Hybrid 5, Dense&Hybrid 5, all three 2
Best rank of a reachable gold document: bm25 45, dense 44, hybrid 28   (3 reachable of 4 web gold URLs)

--- Existing LLM authority prediction (frozen file; NOT re-generated) ---
fact_at_issue: Whether the executive order Donald Trump signed on September 24, 2020 (the 'America First Healthcare Plan' order) creates legally binding health coverage protections for people with pre-existing conditions.
claim_kind: law_or_legal_decision | authority_situation: multiple_legitimate_authorities | confidence: 0.6
  1. Federal Register (Office of the Federal Register, National Archives) | domain=federalregister.gov | social=None | government
  2. The White House (Trump administration archive) | domain=trumpwhitehouse.archives.gov | social=twitter.com/WhiteHouse45 | government
  3. Congressional Research Service / U.S. Congress | domain=congress.gov | social=None | court_or_legislature
Predicted publisher keys -> documents in hybrid top-100: {'archives.gov': 1, 'congress.gov': 0, 'federalregister.gov': 0, 'twitter.com/whitehouse45': 0}

--- B_generic: Generic credibility prior (claim-independent domain type) ---
 #  was  moved prior gold  publisher | url
 1    1     +0   0.6       cnbc.com | cnbc.com/2020/09/24/trump-to-sign-executive-orders-on-preexisting-cond
 2   23    +21   1.0       senate.gov | finance.senate.gov/ranking-members-news/wyden-blasts-latest-trump-scam
 3    4     +1   0.6       bbc.com | bbc.com/news/world-us-canada-41599532
 4   28    +24   1.0 GOLD  archives.gov | trumpwhitehouse.archives.gov/presidential-actions/executive-order-amer
 5    6     +1   0.6       nbcnews.com | nbcnews.com/politics/white-house/trump-signs-eos-health-care-does-litt
 6   10     +4   0.6       cnn.com | cnn.com/2020/09/21/politics/supreme-court-obamacare-affordable-care-ac
 7   37    +30   1.0       house.gov | waters.house.gov/media-center/press-releases/waters-trump-s-decision-s
 8   41    +33   1.0       senate.gov | tillis.senate.gov/2019/4/senators-introduce-the-protect-act-to-ensure-
 9   42    +33   1.0       house.gov | waysandmeans.house.gov/president-trump-u-s-policy-is-to-protect-patien
10    2     -8   0.3       upi.com | upi.com/Top_News/US/2020/09/24/Trump-outlines-healthcare-plan-ensures-
Promoted into top-10 from below rank 10: 5; from below rank 50: 0 (0 of them non-gold); best gold rank in pool: 4

--- C_heuristic: Heuristic claim prior (generic + claim-entity / claim-country rules) ---
 #  was  moved prior gold  publisher | url
 1    1     +0   0.6       cnbc.com | cnbc.com/2020/09/24/trump-to-sign-executive-orders-on-preexisting-cond
 2   23    +21   1.0       senate.gov | finance.senate.gov/ranking-members-news/wyden-blasts-latest-trump-scam
 3    4     +1   0.6       bbc.com | bbc.com/news/world-us-canada-41599532
 4   28    +24   1.0 GOLD  archives.gov | trumpwhitehouse.archives.gov/presidential-actions/executive-order-amer
 5    6     +1   0.6       nbcnews.com | nbcnews.com/politics/white-house/trump-signs-eos-health-care-does-litt
 6   10     +4   0.6       cnn.com | cnn.com/2020/09/21/politics/supreme-court-obamacare-affordable-care-ac
 7   37    +30   1.0       house.gov | waters.house.gov/media-center/press-releases/waters-trump-s-decision-s
 8   41    +33   1.0       senate.gov | tillis.senate.gov/2019/4/senators-introduce-the-protect-act-to-ensure-
 9   42    +33   1.0       house.gov | waysandmeans.house.gov/president-trump-u-s-policy-is-to-protect-patien
10    2     -8   0.3       upi.com | upi.com/Top_News/US/2020/09/24/Trump-outlines-healthcare-plan-ensures-
Promoted into top-10 from below rank 10: 5; from below rank 50: 0 (0 of them non-gold); best gold rank in pool: 4

--- D_llm: LLM authority prior (frozen Claude Opus 5.5 top-3 publishers, binary) ---
 #  was  moved prior gold  publisher | url
 1   28    +27   1.0 GOLD  archives.gov | trumpwhitehouse.archives.gov/presidential-actions/executive-order-amer
 2    1     -1   0.0       cnbc.com | cnbc.com/2020/09/24/trump-to-sign-executive-orders-on-preexisting-cond
 3    2     -1   0.0       upi.com | upi.com/Top_News/US/2020/09/24/Trump-outlines-healthcare-plan-ensures-
 4    3     -1   0.0       americanprogress.org | americanprogress.org/press/statement-caps-topher-spiro-says-executive-
 5    4     -1   0.0       bbc.com | bbc.com/news/world-us-canada-41599532
 6    5     -1   0.0       abc7chicago.com | abc7chicago.com/donald-trump-executive-order-president-preexisting-con
 7    6     -1   0.0       nbcnews.com | nbcnews.com/politics/white-house/trump-signs-eos-health-care-does-litt
 8    7     -1   0.0       kffhealthnews.org | kffhealthnews.org/morning-breakout/trump-affirms-preexisting-condition
 9    8     -1   0.0       abc7ny.com | abc7ny.com/donald-trump-executive-order-president-preexisting-conditio
10    9     -1   0.0       advisory.com | advisory.com/daily-briefing/2020/09/25/executive-orders
Promoted into top-10 from below rank 10: 1; from below rank 50: 0 (0 of them non-gold); best gold rank in pool: 1

gold = AVeriTeC annotator evidence URL that is present and non-empty in this claim's knowledge store. It is relevance/evidence information, NOT a claim-specific authority label.
```
