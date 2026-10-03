"""Step 3: research annotation of the ROLE of each gold evidence source.

These labels are OUR judgement, not something AVeriTeC provides. They were made
by one annotator (Claude, reviewing each URL together with the claim, the
annotator's question and answer) and have NOT been validated by a second
annotator. Treat them as a pilot annotation. Definitions: docs/dataset_audit.md.

Role (relative to the claim, judged by the PUBLISHER of the page):
  A_primary   official gov / intergovernmental body, the organisation or company
              itself, original research/data producer, court/legislative record,
              or a direct statement / the original post of the relevant entity
  B_secondary news, magazines, fact-checkers, explainers, law-firm/advocacy
              explainers, blogs: reporting ABOUT something
  C_derived   encyclopedias/aggregators/mirrors, directories, trackers compiling
              others' data, third-party re-hosted copies of a primary document
  D_unclear   cannot tell who published it / tools / dead ends

entity_relevant = yes if the publisher is the claim's speaker/subject, or the
body with custody of / jurisdiction over the fact being checked.
Web archives (web.archive.org, archive.ph) are transparent: we label the
archived page's original publisher.
"""
import csv

from common import ANNOTATIONS, full_host, load_sample, registered_domain

# ---- default label per registered domain: (source_type, role, confidence) ----
GOV, IGO, ORG, COMP, ACAD, NEWS, FC, ENC, SOC, BLOG, TOOL, LAW, ADV = (
    "government", "intergovernmental", "organisation", "company", "academic/research",
    "news", "fact-checker", "encyclopedia/aggregator", "social_media", "blog/low-quality",
    "tool", "legal-explainer", "advocacy/think-tank")

A, B, C, D = "A_primary", "B_secondary", "C_derived", "D_unclear"

DOMAIN = {
    # government / legislative / regulators
    **{d: (GOV, A, "high") for d in [
        "ny.gov", "legislation.govt.nz", "treasury.govt.nz", "dol.gov", "www.gov.uk", "service.gov.uk",
        "cfa.gov", "house.gov", "dcboe.org", "wa.gov", "upsc.gov.in", "socialjustice.nic.in", "fbi.gov",
        "nasa.gov", "fda.gov", "hhs.gov", "federalregister.gov", "malegislature.gov", "nisra.gov.uk",
        "flgov.com", "ipid.gov.za", "westerncape.gov.za", "saps.gov.za", "crtc.gc.ca", "justice.gc.ca",
        "officialgazette.gov.ph", "congress.gov.ph", "senate.gov.ph", "ca.gov", "archives.gov",
        "justice.gov", "cdc.gov", "nigerianstat.gov.ng", "rbi.org.in", "gnb.ca", "usa.gov",
        "advocacy.org.nz"]},
    **{d: (IGO, A, "high") for d in ["who.int", "un.org", "worldbank.org", "oecd-ilibrary.org"]},
    # organisations / companies speaking for themselves, original research producers
    **{d: (ORG, A, "high") for d in ["amu.ac.in", "iowafarmbureau.com", "blacklivesmatter.com",
                                      "joebiden.com", "fopcovid19.org"]},
    **{d: (COMP, A, "high") for d in ["nnpcgroup.com", "regeneron.com", "kkr.com", "foxnews.com"]},
    **{d: (ACAD, A, "high") for d in ["nih.gov", "thelancet.com", "ias.ac.in"]},
    **{d: (ACAD, A, "medium") for d in ["cochrane.org", "guttmacher.org", "ucsf.edu"]},
    **{d: (ADV, A, "medium") for d in ["ti-defence.org", "yourbudgit.com", "lung.org"]},
    # secondary: news & magazines
    **{d: (NEWS, B, "high") for d in [
        "nypost.com", "theguardian.com", "nytimes.com", "cnbc.com", "buzzfeednews.com", "cbsnews.com",
        "dawn.com", "cnn.com", "nbcphiladelphia.com", "pennlive.com", "qctimes.com", "inquirer.com",
        "telegraphindia.com", "newindianexpress.com", "dailyo.in", "time.com", "abc.net.au",
        "washingtonpost.com", "npr.org", "nbcnews.com", "dailytrust.com", "thecable.ng", "dw.com",
        "reuters.com", "theatlantic.com", "detroitnews.com", "financialexpress.com", "indianexpress.com",
        "indiatimes.com", "indiatoday.in", "theprint.in", "thehindu.com", "globalnews.ca",
        "wildfiretoday.com", "vice.com", "fastcompany.com", "inc.com", "theverge.com", "politico.com",
        "axios.com", "cbc.ca", "thetimes.co.uk", "edweek.org", "fredericksburg.com", "gvnews.com",
        "vanguardngr.com", "militarytimes.com", "indianretailer.com", "alabamanewscenter.com",
        "intelligenttransport.com", "9to5google.com", "webmd.com", "science.org",
        "journalistsresource.org", "news21.com", "techlicious.com", "ajmc.com", "gonewsindia.com",
        "newsmobile.in", "healthline.com", "medicalnewstoday.com", "health-desk.org", "addictioncenter.com"]},
    **{d: (FC, B, "high") for d in ["factcheck.org", "altnews.in", "aap.com.au"]},
    **{d: (LAW, B, "medium") for d in ["sabilaw.org", "bhwlawfirm.com", "legalmatch.com", "clearias.com",
                                        "careerindia.com", "esa.org"]},
    **{d: (ADV, B, "medium") for d in ["brennancenter.org", "edchoice.org", "bothlivesmatter.org.nz"]},
    **{d: (ACAD, B, "medium") for d in ["jstor.org", "usp.br", "intechopen.com", "berkeley.edu",
                                         "globalscientificjournal.com"]},
    **{d: (BLOG, B, "medium") for d in ["peguru.com", "wonderdome.co.uk", "hotinsocialmedia.com",
                                         "theunionjournal.com"]},
    # derived / aggregated
    **{d: (ENC, C, "high") for d in ["wikipedia.org", "wikiwand.com", "britannica.com", "thoughtco.com",
                                      "google.com", "tradingeconomics.com", "justdial.com", "salary.com",
                                      "heritage.org", "propublica.org"]},
    # tools / unknown
    **{d: (TOOL, D, "high") for d in ["calculator-1.com", "calculator.net"]},
    **{d: (BLOG, D, "low") for d in ["fyrefox.com", "greatrockcapital.com"]},
}

# ---- per (claim_id, url-substring) overrides: role, source_type, confidence, entity_relevant, note ----
OVR = {
    # social-media posts: role depends on WHO posted
    (18, "facebook.com/GilbertLiz"): (A, SOC, "high", "yes", "speaker's own post (claim artifact)"),
    (72, "twitter.com/tesseract___"): (A, SOC, "medium", "yes", "post that spread the claim (claim artifact), not evidence about the fact"),
    (85, "twitter.com/thewire_in"): (B, SOC, "high", "no", "news outlet's tweet"),
    (85, "linkedin.com"): (A, COMP, "low", "no", "company profile on third-party platform"),
    (90, "youtube.com"): (D, SOC, "low", "yes", "video of the subject speaking; uploader unknown"),
    (90, "timesofindia"): (B, NEWS, "high", "no", "news video"),
    (90, "navbharattimes"): (B, NEWS, "high", "no", "news article on the fake page"),
    (116, "youtube.com"): (D, SOC, "low", "yes", "full-context footage of the speaker; uploader unknown"),
    (126, "wordpress.com"): (C, BLOG, "medium", "yes", "blog re-hosting an image of the primary historical document"),
    (187, "twitter.com/PressSec45"): (A, SOC, "high", "yes", "White House press secretary account"),
    (207, "africacheck.org"): (C, FC, "high", "no", "fact-checker re-hosting a UN WUP data file (copy of primary data)"),
    (277, "youtube.com"): (B, NEWS, "medium", "yes", "NBC News video of the subject's press remarks"),
    (320, "twitter.com/donmoyn"): (A, SOC, "high", "yes", "speaker's own tweet (claim artifact)"),
    (388, "archive.ph"): (A, SOC, "low", "yes", "archived copy of the post under dispute (claim artifact)"),
    (395, "archive.ph"): (A, SOC, "medium", "yes", "archived statement by the person the quote is attributed to"),
    (396, "twitter.com/ByAshishKumar"): (D, SOC, "low", "no", "third-party tweet identifying people"),
    (399, "lawyard.ng"): (C, LAW, "medium", "yes", "law blog re-hosting the primary court judgment PDF"),
    (405, "twitter.com"): (A, SOC, "high", "yes", "the subject's own account / search of it"),
    (412, "twitter.com/MoNDefense"): (A, SOC, "high", "yes", "Taiwan Ministry of National Defense account"),
    (441, "twitter.com/WBPolice"): (A, SOC, "high", "yes", "West Bengal Police account"),
    (466, "facebook.com/AMBERalert"): (A, SOC, "high", "yes", "official AMBER Alert page"),
    (467, "twitter.com/ChennaiIPL"): (A, SOC, "high", "yes", "team's official account"),
    (382, "twitter.com/search"): (A, SOC, "medium", "yes", "search over the subject's own account"),
    (382, "propublica.org"): (C, ENC, "medium", "yes", "archive of the subject's deleted tweets (derived record)"),
    (440, "thetimes.co.uk"): (A, NEWS, "high", "yes", "the article that made the claim (claim artifact)"),
    (345, "wikipedia.org"): (C, ENC, "high", "yes", None),
    (50, "blog.twitter.com"): (A, COMP, "high", "yes", "Twitter's own policy announcement; claim is about Twitter's behaviour"),
    (315, "fas.org"): (C, GOV, "medium", "partial", "third-party re-host of a Congressional Research Service report"),
    (473, "rev.com"): (C, TOOL, "medium", "yes", "third-party transcript of the speaker's speech"),
    # scope / jurisdiction mismatches: official but not the relevant authority
    (226, "wa.gov"): (A, GOV, "high", "no", "Washington STATE guidance, claim is about Washington DC (jurisdiction mismatch)"),
    (450, "flgov.com"): (A, GOV, "high", "no", "Florida governor order; claim is about a federal (Trump) declaration"),
    (374, "nasa.gov"): (A, GOV, "high", "no", "official, but not the authority on the fire causes (FBI/police are)"),
    (187, "cfa.gov"): (A, GOV, "medium", "no", "official, but tangential to the claim"),
    (298, "service.gov.uk"): (A, GOV, "medium", "partial", "workplace guidance; Parliament's own rules would be the direct authority"),
    (323, "usa.gov"): (A, GOV, "high", "partial", "background definition only"),
    (26, "thelancet.com"): (A, ACAD, "medium", "partial", "paper about ivermectin generally, not COVID"),
    (243, "who.int"): (A, IGO, "high", "partial", "general diet guidance, not about millets"),
    (374, "fbi.gov"): (A, GOV, "high", "yes", None),
    (143, "oecd-ilibrary.org"): (A, IGO, "high", "yes", "comparative pension data"),
    (222, "un.org"): (A, IGO, "medium", "yes", "UN News story about UN population report"),
}


def main():
    rows_out = []
    for r in load_sample():
        seen = set()
        for g in r["gold_evidence"]:
            if not g["is_web_source"] or g["source_url"] in seen:
                continue
            seen.add(g["source_url"])
            url, dom, host = g["source_url"], g["source_domain"], full_host(g["source_url"])
            hit = next((v for (cid, sub), v in OVR.items() if cid == r["claim_id"] and sub in url), None)
            if hit:
                role, stype, conf, ent, note = hit
            elif dom in DOMAIN:
                stype, role, conf = DOMAIN[dom]
                ent = "yes" if role == A else "no"
                note = None
            else:
                stype, role, conf, ent, note = "unknown", D, "low", "unclear", "domain not in annotation table"
            rows_out.append({
                "claim_id": r["claim_id"],
                "evidence_url": url,
                "source_domain": registered_domain(url),
                "source_host": host,
                "source_type": stype,
                "source_role": role,
                "entity_relevant": ent,
                "confidence": conf,
                "annotator": "claude-pilot",
                "notes": note or "",
            })
    ANNOTATIONS.mkdir(parents=True, exist_ok=True)
    with open(ANNOTATIONS / "source_roles.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0]))
        w.writeheader()
        w.writerows(rows_out)
    unk = [x["evidence_url"] for x in rows_out if x["notes"] == "domain not in annotation table"]
    print(f"{len(rows_out)} rows; {len(unk)} unlabelled:", *unk, sep="\n  ")


if __name__ == "__main__":
    main()
