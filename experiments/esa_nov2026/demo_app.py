"""Source-Aware Misinformation Detection (IR_03) - Phase-I review demo (local web app).

Launch (from the project folder):   run_demo.bat
or:   set HF_HUB_OFFLINE=1 && streamlit run experiments/esa_nov2026/demo_app.py --browser.gatherUsageStats false

Offline. No LLM/API call is made. Only the 120 dev-sample + 200 held-out AVeriTeC claims can be loaded.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

ROOT = HERE.parent.parent
RES = ROOT / "results"
ESA_OUT = RES / "esa_nov2026"

st.set_page_config(page_title="IR_03 Source-Aware Misinformation Detection - demo", layout="wide",
                   initial_sidebar_state="expanded")


# ------------------------------------------------------------------ loading

@st.cache_resource(show_spinner=False)
def load_backend():
    import demo_pipeline as P
    P.claim_choices()
    for s in ("heldout200", "dev120"):
        P.frozen_rankings(s)
        P.frozen_predictions(s)
    from authority_retrieval import claim_entities  # loads spaCy model
    claim_entities({"claim": "warm up", "speaker_or_entity": None})
    return P


def ks_stats():
    p = ESA_OUT / "demo" / "knowledge_store_stats.json"
    return json.load(open(p, encoding="utf-8")) if p.exists() else None


@st.cache_data(show_spinner=False)
def run_cached(cid, mode, query, k, show_gold):
    P = load_backend()
    return P.run(cid, mode=mode, query=query, k=k, show_gold=show_gold)


def link(u):
    return "https://" + u if u and not u.startswith("http") else u


def mark(v):
    return "" if v is None else ("✔ evidence" if v else "")


# ------------------------------------------------------------------ header

st.title("Source-Aware Misinformation Detection")
st.caption("IR_03 · PES University · Capstone Phase-I · Authority Resolution Module demo · "
           "offline: no LLM/API call, no download, AVeriTeC dev claims only (no reserved or test labels)")

with st.spinner("Starting: loading the knowledge-store index, frozen rankings, stored LLM predictions and spaCy "
                "(first start takes about 1-2 minutes on this laptop)..."):
    try:
        P = load_backend()
    except Exception as e:  # noqa: BLE001
        st.error(f"The demo backend could not start: {e!r}. Check that you started it from the project folder "
                 "with run_demo.bat. Fallback: open results/esa_nov2026/demo/fallback/INDEX.html in a browser.")
        st.stop()

choices = P.claim_choices()
by_id = {c["claim_id"]: c for c in choices}

# ------------------------------------------------------------------ sidebar

with st.sidebar:
    st.header("1 · Claim input")
    sugg = [cid for cid in P.SUGGESTED]
    labels = {cid: f"{cid} · {P.SUGGESTED[cid][0]} · {by_id[cid]['claim'][:60]}" for cid in sugg}
    pick_from = st.radio("Choose from", ["Suggested demo claims", "All 320 allowed claims"], horizontal=False)
    if pick_from == "Suggested demo claims":
        cid = st.selectbox("Claim", sugg, format_func=lambda c: labels[c])
    else:
        allc = [c["claim_id"] for c in choices]
        cid = st.selectbox("Claim (type to search)", allc,
                           format_func=lambda c: f"{c} [{by_id[c]['split']}] {by_id[c]['claim'][:70]}")
    mode_label = st.radio(
        "Retrieval mode",
        ["Stored rankings (fast, exact)", "Recompute live now (2-8 min)", "Custom claim text (live)"],
        help="Stored = the frozen Sept-2026 BM25/MiniLM/Hybrid rankings (re-verified identical to a live re-run). "
             "Live = recompute BM25 + MiniLM + RRF now on this CPU. Custom = your own text, retrieved live over the "
             "selected claim's knowledge store.")
    mode = {"Stored": "frozen", "Recompute": "live", "Custom": "query"}[mode_label.split()[0]]
    query = None
    if mode == "query":
        query = st.text_area("Claim text", value=by_id[cid]["claim"], height=110,
                             help="Searched only inside the selected claim's AVeriTeC knowledge store "
                                  "(the project has no open-web index).")
    k = st.slider("Documents shown per list (top-K)", 5, 20, 10)
    show_gold = st.toggle("Show AVeriTeC evidence markers", value=True,
                          help="Marks documents the AVeriTeC annotators cited as evidence. Used only to evaluate; "
                               "never an input to ranking. Evidence is relevance, NOT authority.")
    go = st.button("Run pipeline", type="primary", use_container_width=True)
    st.divider()
    s = ks_stats()
    if s:
        st.caption(f"Knowledge store loaded: {s['n_claims']} claim stores · {s['n_docs_raw']:,} documents "
                   f"({s['n_docs_retrievable']:,} non-empty, URL-deduplicated) · {s['size_gb']:.2f} GB on disk")

if go:
    st.session_state["req"] = (cid, mode, query, k, show_gold)

tab_demo, tab_eval, tab_pu, tab_about = st.tabs(
    ["Pipeline demo", "Evaluation: frozen held-out", "PU relevance baseline", "Provenance & limits"])

# ------------------------------------------------------------------ demo tab

with tab_demo:
    req = st.session_state.get("req")
    if not req:
        st.info("Pick a claim in the sidebar and press **Run pipeline**. Suggested start: claim **268** "
                "(government/health policy).")
    else:
        cid_r, mode_r, query_r, k_r, gold_r = req
        o = None
        try:
            if mode_r == "frozen":
                with st.spinner("Running BM25 / MiniLM / Hybrid (stored) and the authority priors..."):
                    o = run_cached(cid_r, mode_r, query_r, k_r, gold_r)
            else:
                with st.status("Live retrieval running on CPU...", expanded=True) as stt:
                    msgs = []
                    o = P.run(cid_r, mode=mode_r, query=query_r, k=k_r, show_gold=gold_r,
                              progress=lambda m: (msgs.append(m), stt.write(m)))
                    stt.update(label="Live retrieval finished", state="complete", expanded=False)
        except PermissionError as e:
            st.error(f"Refused for research-integrity reasons: {e}")
        except ValueError as e:
            st.warning(str(e))
        except FileNotFoundError as e:
            st.error(f"A required project file is missing: {e}. Use the stored fallback pages in "
                     "results/esa_nov2026/demo/fallback/.")
        except Exception as e:  # noqa: BLE001
            st.error(f"Unexpected error: {e!r}. Try 'Stored rankings' mode, or open the fallback pages in "
                     "results/esa_nov2026/demo/fallback/.")

        if o:
            c = o["claim"]
            st.subheader(f"Step 1 · Claim {o['claim_id']}")
            st.markdown(f"> **{c['claim']}**")
            cols = st.columns(4)
            cols[0].metric("Speaker / entity", (c["speaker_or_entity"] or "-")[:28])
            cols[1].metric("Claim date", c["claim_date"] or "-")
            cols[2].metric("Country", c["location_ISO_code"] or "-")
            cols[3].metric("Candidate documents", f"{o['n_candidates']:,}")
            st.caption(f"Sample: {o['split']} · mode: {o['mode']}"
                       + (f" · live run computed {o['live_meta'].get('computed_at')}"
                          f"{' (loaded from this app’s on-disk cache)' if o['live_meta'].get('from_cache') else ''}"
                          f" · timing {o['live_meta'].get('timing_s')}" if o.get("live_meta") and not o['live_meta'].get('stub') else ""))

            st.subheader("Step 2 · Claim processing (as implemented)")
            pr = o["processing"]
            a, b = st.columns(2)
            with a:
                st.markdown(f"**Retrieval query** (whitespace-normalised claim text; no rewriting):  \n`{pr['normalized_query']}`")
                st.markdown("**BM25 query terms** (English stop words removed, no stemming):  \n"
                            + " ".join(f"`{t}`" for t in pr["bm25_tokens"]))
                st.markdown("**MiniLM input:** the same query text (first 128 word pieces).")
            with b:
                ents = ", ".join(f"{e['mention']} ({e['label']})" for e in pr["entities"]) or "none"
                st.markdown(f"**Entities for the heuristic prior** (spaCy + speaker field): {ents}")
                st.markdown("**Entity keys matched against domains / handles:** "
                            + (" ".join(f"`{x}`" for x in pr["entity_keys"]) or "none"))
                st.markdown(f"**Claim country (jurisdiction rule):** `{pr['country_iso']}`")

            st.subheader("Step 3 · Retrieval: BM25 vs MiniLM vs Hybrid RRF")
            ov = o["overlap"]
            m = st.columns(5)
            for i, (kk, v) in enumerate(ov.items()):
                m[i].metric(f"Top-{o['k']} overlap: {kk}", f"{v}/{o['k']}")
            if o["best_evidence_rank"]:
                ber = o["best_evidence_rank"]
                m[4].metric("Best evidence rank B / D / H", f"{ber['bm25']} / {ber['dense']} / {ber['hybrid']}")
            rt = st.tabs([o["retrieval"][x]["label"] for x in ("bm25", "dense", "hybrid")] + ["Side by side"])
            for i, meth in enumerate(("bm25", "dense", "hybrid")):
                with rt[i]:
                    df = pd.DataFrame(o["retrieval"][meth]["top"])
                    df["link"] = df["url"].map(link)
                    df["ranks B/M/H"] = df.apply(lambda r: f"{r.rank_bm25} / {r.rank_dense} / {r.rank_hybrid}", axis=1)
                    df["query terms"] = df["matched_terms"].map(lambda x: ", ".join(x[:8]))
                    df["evidence"] = df["evidence_marker"].map(mark)
                    st.dataframe(df[["rank", "publisher", "title_guess", "link", "score", "ranks B/M/H",
                                     "query terms", "evidence", "snippet"]],
                                 hide_index=True, use_container_width=True,
                                 column_config={"link": st.column_config.LinkColumn("URL", display_text=r"https?://(.{0,60}).*"),
                                                "title_guess": st.column_config.TextColumn("Title (first sentence)*"),
                                                "snippet": st.column_config.TextColumn("Text snippet", width="large")})
            with rt[3]:
                side = pd.DataFrame({x: [f"{d['publisher']}{'  ✔' if d['evidence_marker'] else ''}"
                                         for d in o["retrieval"][x]["top"]] for x in ("bm25", "dense", "hybrid")})
                side.index = range(1, len(side) + 1)
                side.columns = ["BM25", "MiniLM", "Hybrid RRF"]
                st.dataframe(side, use_container_width=True)
            st.caption("*The AVeriTeC knowledge store has no title field; the first sentence of the page text is shown. "
                       "Score = BM25 score / cosine similarity / RRF score. Ranks B/M/H = the document's rank under each "
                       "method over all candidates.")

            st.subheader("Step 4 · Authority Resolution Module")
            p = o["llm_prediction"]
            if p:
                with st.container(border=True):
                    st.markdown("**Stored LLM authority prediction** · "
                                ":orange[generated Sept 2026 by Claude Opus 5.5 (no web), NOT generated live here]")
                    st.caption(p["provenance"])
                    st.markdown(f"**Fact at issue:** {p['fact_at_issue']}  \n**Claim kind:** `{p['claim_kind']}` · "
                                f"**Authority situation:** `{p['authority_situation']}` · **Confidence:** {p['confidence']}")
                    st.dataframe(pd.DataFrame(p["top3"]).rename(columns={"type": "publisher type"}),
                                 hide_index=True, use_container_width=True)
                    st.caption("Predicted publisher keys → documents in the hybrid top-100 pool: "
                               + ", ".join(f"`{kk}`: {v}" for kk, v in p["keys_docs_in_pool"].items()))
            if o["llm_note"]:
                st.warning(o["llm_note"])
            at = st.tabs([o["authority"][s]["label"] for s in o["authority"]])
            for i, sid in enumerate(o["authority"]):
                with at[i]:
                    A = o["authority"][sid]
                    st.caption(f"{A['desc']}. Re-ranks the hybrid top-100: final = minmax(relevance) + 1.0 × prior. "
                               f"Promoted into top-{o['k']} from below rank {o['k']}: {A['n_from_below_k']}; "
                               f"from below rank 50: {A['n_from_below_50']}"
                               + (f"; best evidence rank: {A['best_evidence_rank_in_pool']}" if show_gold else ""))
                    df = pd.DataFrame(A["top"])
                    df["link"] = df["url"].map(link)
                    df["evidence"] = df["evidence_marker"].map(mark)
                    st.dataframe(df[["rank", "hybrid_rank", "moved", "publisher", "domain_type", "relevance", "prior",
                                     "final", "why", "evidence", "link"]],
                                 hide_index=True, use_container_width=True,
                                 column_config={"link": st.column_config.LinkColumn("URL", display_text=r"https?://(.{0,50}).*"),
                                                "hybrid_rank": "was (hybrid)",
                                                "why": st.column_config.TextColumn("authority factors", width="large")})

            st.subheader("Step 5 · Final ranked sources")
            F = o["authority"][o["final_system"]]
            st.markdown(f"Final system shown: **{F['label']}**"
                        + ("" if o["final_system"] == "D" else " (the LLM prior is unavailable for this input, "
                                                               "so the heuristic prior is used)"))
            fdf = pd.DataFrame(F["top"])
            chart = fdf[["relevance", "prior"]].copy()
            chart.columns = ["relevance (minmax)", "authority (λ×prior)"]
            chart.index = [f"{int(r):02d} · {pbl[:22]}" for r, pbl in zip(fdf["rank"], fdf["publisher"])]
            st.caption("Each bar = final score of a top-ranked document, split into its relevance part and its authority part.")
            st.bar_chart(chart, horizontal=True, stack=True, height=34 * len(chart) + 60)
            st.info("**Relevance ≠ authority.** Relevance asks *does this page talk about the claim?* (BM25 / MiniLM). "
                    "Authority asks *is this source the one that issued, measured or holds the fact at issue?* "
                    "A relevant news report can be non-authoritative; an authoritative agency page on another topic is "
                    "irrelevant. The final score adds the two parts. Because the prior is 0/1 and relevance is in [0,1], a "
                    "boosted publisher outranks every non-boosted page — the main weakness the supervised model should fix.")
            st.caption(o["evidence_note"])
            st.markdown("**Step 6 · Evaluation:** open the *Evaluation* and *PU relevance baseline* tabs above.")

# ------------------------------------------------------------------ evaluation tab

with tab_eval:
    st.subheader("Frozen, preregistered held-out evaluation (AVeriTeC dev, 200 claims)")
    st.caption("Source files (read-only): results/source_targeted/results_heldout.json, "
               "results/heldout/validation_heldout.json. Re-scored from frozen rankings and identical (2026-11-08, re-run "
               "2026-11-14). Metric = evidence Recall@K: share of the 167 claims with ≥1 reachable AVeriTeC evidence "
               "document in the top K. This is a RELEVANCE/evidence metric, not authority recall.")
    try:
        R = json.load(open(RES / "source_targeted" / "results_heldout.json", encoding="utf-8"))
        V = json.load(open(RES / "heldout" / "validation_heldout.json", encoding="utf-8"))
        names = {"bm25": "BM25", "dense": "MiniLM dense", "hybrid": "A · Hybrid RRF", "hybrid+generic": "B · + generic prior",
                 "hybrid+heuristic": "C · + heuristic prior", "hybrid+llm_authority": "D · + LLM authority prior"}
        rows = []
        for kk, nm in names.items():
            t = R["table"][kk]
            rows.append({"system": nm, **{f"R@{K}": t[f"GoldR@{K}"] for K in (1, 5, 10, 20, 50, 100)},
                         "MRR@100": t["GoldMRR@100"], "pool coverage": t["Gold_claim_coverage"]})
        tdf = pd.DataFrame(rows).set_index("system")
        st.dataframe(tdf, use_container_width=True)
        pe = V["primary_endpoint"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Primary: D vs A, R@10", f"{tdf.loc['D · + LLM authority prior', 'R@10']:.3f} vs "
                  f"{tdf.loc['A · Hybrid RRF', 'R@10']:.3f}", f"+{pe['diff_R@10']:.3f}")
        c2.metric("Exact McNemar (wins / losses)", f"p = {pe['p']:.3f}", f"+{pe['wins']} / −{pe['losses']}",
                  delta_color="off")
        c3.metric("Bootstrap 95% CI of difference", f"[{pe['bootstrap95CI'][0]:.3f}, {pe['bootstrap95CI'][1]:.3f}]")
        st.warning("Not statistically significant (p = 0.167; CI includes 0). A directional, not a demonstrated, gain.")
        long = tdf[[f"R@{K}" for K in (1, 5, 10, 20, 50, 100)]].T
        long.index = [1, 5, 10, 20, 50, 100]
        st.markdown("**Recall@K curves**")
        fig2 = ESA_OUT / "figures" / "fig2_heldout_recall_curves.png"
        if fig2.exists():
            st.image(str(fig2), width=820)
        else:
            st.line_chart(long, height=320)
        cap = V["candidate_pool_coverage"]
        st.markdown("**Candidate-pool coverage and the recall ceiling.** A source that is never retrieved cannot be "
                    "selected by the Authority Resolution Module. Any reranker of the hybrid top-100 is capped at "
                    f"**{R['table']['hybrid']['Gold_claim_coverage']:.3f}** (112/167 claims).")
        rc_p = ESA_OUT / "recall_ceiling" / "recall_ceiling.json"
        if rc_p.exists():
            rc = json.load(open(rc_p, encoding="utf-8"))
            try:
                hy = rc["splits"]["heldout200"]["stage2_retrieval"]["hybrid"]
                row = {kk.replace("@", "top-"): f"{v['claim_recall']:.3f} ({v['claim_hits']})" for kk, v in hy.items()}
                st.markdown("**Hybrid recall by retrieval depth (claims with evidence in top-K):**")
                st.dataframe(pd.DataFrame([row]), hide_index=True, use_container_width=True)
            except Exception:  # noqa: BLE001
                st.json(rc.get("splits", rc), expanded=False)
            st.caption("Recomputed 2026-11-14 by experiments/esa_nov2026/recall_ceiling.py from frozen full rankings "
                       "(exploratory, descriptive).")
        st.markdown(f"Claims whose predicted-authority evidence document is inside the pool: top-100 "
                    f"{cap['top100']['claims_whose_predicted_publisher_gold_doc_is_in_pool']}, top-200 "
                    f"{cap['top200']['claims_whose_predicted_publisher_gold_doc_is_in_pool']}, all candidates "
                    f"{cap['all_candidates']['claims_whose_predicted_publisher_gold_doc_is_in_pool']}.")
        with st.expander("Three different metrics — do not mix them"):
            st.markdown(
                "1. **Retrieval (evidence) Recall@K** — is an AVeriTeC evidence document in the top K? Measured here.\n"
                "2. **Authority Recall@K** — is a document *human-labelled as authoritative for this claim* in the top K? "
                "**Cannot be measured yet**: no human claim-document authority labels exist. This is the Phase-II target.\n"
                "3. **Relevance-ranking evaluation** (PU baseline tab) — weak citation labels on a separate AVeriTeC "
                "*train* sample; a different dataset and denominator.")
    except FileNotFoundError as e:
        st.error(f"Frozen result file missing: {e}")

# ------------------------------------------------------------------ PU tab

with tab_pu:
    st.subheader("PU relevance-ranking baseline (AVeriTeC TRAIN sample) — recorded result")
    st.error("This is NOT an authority model. Labels = weak-positive relevance proxies (AVeriTeC train evidence URLs "
             "with text); all other pages are unlabelled, not negatives. Different dataset from the held-out tab.")
    p = ESA_OUT / "relevance_baseline" / "run1_pu_RECORDED_OUTPUT_FROM_TRANSCRIPT" / "run1_pu_console_output.txt"
    if not p.exists():
        st.warning("Recorded output file not found.")
    else:
        txt = p.read_text(encoding="utf-8")
        st.caption("Source: verbatim console output of the original 8 Nov 2026 run, preserved in the session transcript. "
                   "The run's model files and per-claim outputs were lost on 13 Nov 2026 and are NOT shown or claimed.")
        section, data = None, {}
        for line in txt.splitlines():
            ms = re.match(r"^===== (\w+)", line)
            if ms:
                section = ms.group(1)
                continue
            mm = re.match(r"^(hybrid_rrf_baseline|M1_logreg|M2_hist_gbdt|M3_logreg_minilm|pool_coverage_upper_bound|fit_data) (\{.*\})$", line)
            if mm:
                data.setdefault(section or "_", {})[mm.group(1)] = json.loads(mm.group(2))
        nm = {"hybrid_rrf_baseline": "Hybrid RRF", "M1_logreg": "M1 Logistic Regression",
              "M2_hist_gbdt": "M2 HistGradientBoosting (selected on validation)", "M3_logreg_minilm": "M3 LogReg + MiniLM"}
        if "_" in data and "fit_data" in data["_"]:
            fd = data["_"]["fit_data"]
            st.markdown(f"Fit data: {fd['fit_claims_with_docs']} fit claims · {fd['n_fit_pairs']:,} pairs = "
                        f"{fd['n_labelled_s1']} weak positives + {fd['n_unlabelled_sampled_s0']:,} unlabelled. "
                        "Split: 179 fit / 60 validation / 61 test claims (claim-disjoint, seed 2051).")
        for sec, title in (("test", "Test (42 eligible claims; scored once)"), ("validation", "Validation (37; model selection)")):
            if sec in data:
                rows = []
                for kk, lab in nm.items():
                    d = data[sec].get(kk)
                    if d:
                        r = {"system": lab, **{x: d[x] for x in ("claim_R@1", "claim_R@5", "claim_R@10", "claim_R@20", "MRR@100")}}
                        if "vs_hybrid_hit@10_mcnemar" in d:
                            mc = d["vs_hybrid_hit@10_mcnemar"]
                            r["hit@10 vs hybrid"] = f"+{mc['wins']}/−{mc['losses']}, p={mc['p_exact']}"
                        else:
                            r["hit@10 vs hybrid"] = "—"
                        rows.append(r)
                st.markdown(f"**{title}**")
                st.dataframe(pd.DataFrame(rows).set_index("system"), use_container_width=True)
                if sec in data and "pool_coverage_upper_bound" in data[sec]:
                    st.caption("Pool ceiling (any reranker of hybrid top-100): "
                               + data[sec]["pool_coverage_upper_bound"]["pool_coverage_claim_level_(max_claim_R@100)"])
        st.warning("Result: no learned model improved over Hybrid RRF on the primary test metric (Recall@10: selected "
                   "HistGBDT 12/42 vs hybrid 13/42, p = 1.0). HistGBDT overfits (reaches the pool ceiling on its own "
                   "training claims). A valid negative result: citation proxies are not enough; human labels are needed.")
        with st.expander("Show the raw recorded console output"):
            st.code(txt, language="text")

# ------------------------------------------------------------------ about tab

with tab_about:
    st.markdown("""
**What is live in this app**
- BM25, MiniLM (all-MiniLM-L6-v2, cached locally) and Hybrid RRF are the project's own frozen functions.
  *Stored* mode loads the Sept-2026 rankings; *Live* mode recomputes them now (verified identical top-100 order).
- Generic (B) and heuristic (C) authority priors are computed live from the URL, claim entities and country.
- The final re-ranking (minmax relevance + λ·prior) is computed live.

**What is a stored output (not generated live)**
- The LLM authority predictions (D) were generated in Sept 2026 by Claude Opus 5.5 with no web access. This app never calls an LLM.
- Frozen held-out evaluation tables and the PU baseline's recorded console output.

**Not available / not claimed**
- The reserved-180 retrieval outputs and LLM predictions (authority-v2 Steps 10–11) were executed historically but the files were **lost**; they are not used here.
- No human claim-document authority labels exist yet → no supervised authority model, no Authority Recall@K.
- The PU relevance model files were lost on 13 Nov 2026; only the recorded metrics are shown.
- Retrieval runs inside AVeriTeC's per-claim knowledge stores (built partly from gold-derived queries); no open-web search.

**Integrity safeguards**: only 120 dev + 200 held-out claim ids load (others are refused); no sealed or test labels;
evidence markers never feed any ranking; HF_HUB_OFFLINE=1 and Streamlit telemetry off.
""")
