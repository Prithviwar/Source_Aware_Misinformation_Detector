# Applicability Across Three Domains

**No domain-specific validation has been conducted.** The examples are real AVeriTeC dev claims from the frozen study. "Evidence rank" moves are **single-claim observations** from the stored rankings, used as illustrations, not results. The evaluation was not stratified by domain, and no per-domain metric is claimed.

All examples below can be shown live in the demo app (claim IDs given).

---

## 1. Health and medical misinformation

| | |
|---|---|
| **Example claim types** | Treatment efficacy ("X cures COVID"); study findings ("masks caused 1918 flu deaths", **claim 89**); vaccine safety; outbreak figures; drug approvals |
| **Authoritative source categories** | The original study (journal article, PubMed record, preprint); the health agency that issued guidance (WHO, CDC, NHS, ICMR, MoHFW); regulator decisions (FDA, EMA, CDSCO); trial registries (ClinicalTrials.gov, CTRI); official case statistics |
| **Why a credible publisher is not the best authority** | A respected newspaper reporting a study is secondary and often simplifies or mis-states its findings. A `.gov` health page about a different disease is credible but not authoritative for this claim. A university press office overstates its own researchers' results |
| **How claim-specific authority helps** | It identifies *which* study or agency holds the fact and prefers that document. For claim 89, the stored LLM prediction named NIAID/NIH and the *Journal of Infectious Diseases*. The best evidence document moved from hybrid rank 21 to 10 |
| **Domain risk** | Earlier project analysis found science and health claims had the weakest LLM authority accuracy (top-1 0.25, n = 71, AI-labelled target; `docs/authority_resolution_study.md`). This motivates a document-level learned model |

## 2. Government, civic and public-policy information

| | |
|---|---|
| **Example claim types** | What a law or order does (**claim 268**, Trump executive order on pre-existing conditions); official statistics (**claim 328**, "24 of every 100 US school kids speak Spanish"); election results; budget figures; what an official said |
| **Authoritative source categories** | The issuing body's own text (Federal Register / Gazette of India, legislature bill text, court judgment); statistics producers (Census, BLS, NCES, MoSPI); election commissions; the official's own transcript or channel |
| **Why a credible publisher is not the best authority** | Many government sites are credible, but only the **issuing** body is authoritative. For claim 268 the generic and heuristic priors lift a `finance.senate.gov` press release to rank 2 because it is `.gov`, even though it is partisan commentary. Jurisdiction also matters: a UK government page is not the authority for a US law |
| **How claim-specific authority helps** | It maps the claim's entity and jurisdiction to the issuer. For claim 268 the LLM prior lifts the executive order itself (`trumpwhitehouse.archives.gov`) from hybrid rank **28 to 1**. For claim 328 it lifts the NCES document from **43 to 3** |
| **Domain risk** | A government publisher has thousands of pages. Binary publisher boosting promotes off-topic pages from the same domain, which is why the model design is document-level |

## 3. Science, research and technology claims

| | |
|---|---|
| **Example claim types** | Environmental and biological facts (**claim 464**, North American bison reduced to 27 animals); origin claims (**claim 326**, "COVID-19 was developed as a bioweapon"); technology safety (5G); space and mission claims |
| **Authoritative source categories** | The peer-reviewed paper or dataset; the agency responsible (NPS, FWS, NASA, ISRO); standards bodies (ITU, IEEE, ICNIRP for 5G); a company's own technical documentation for claims about its products |
| **Why a credible publisher is not the best authority** | A university domain is credible but may host an unrelated department's page. Contested claims often have **no single authority**: the LLM labelled 169 of 200 held-out claims as having "multiple legitimate authorities" |
| **How claim-specific authority helps** | For claim 464 the predicted authorities (US National Park Service, Fish and Wildlife Service) lift the evidence document from **18 to 1** |
| **Failure case (show honestly)** | For claim 326 the predicted authority (the US intelligence community) was boosted, but the evidence moved **24 to 28**, because off-topic pages from boosted publishers were promoted. A document-level relevance × authority model is designed to fix exactly this |

---

## What would be needed to *validate* three-domain applicability (Phase II)

1. Tag each annotated claim with a domain, either by rule or by the annotator.
2. Ensure at least about 40 test claims per domain in the human-annotated set.
3. Report Authority Recall@10 per domain, with confidence intervals, for every baseline and the learned model.
4. Report per-domain agreement (κ). The authority task may be harder in science than in government claims.

Until then, the correct statement is: **"the method is domain-general by design, and is illustrated on real health, government and science claims, but it has not been validated per domain."**
