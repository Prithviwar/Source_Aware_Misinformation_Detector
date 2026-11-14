"""Build an UPDATED COPY of the Review-2 deck for the 16 Nov 2026 review. The original is never modified.

  python experiments/esa_nov2026/build_updated_ppt.py

Input  (read-only): C:/Users/Lenovo/Downloads/CapstoneProject_IR_03.pptx  (sha256 checked before and after)
Output: C:/Users/Lenovo/Downloads/CapstoneProject_IR_03_UPDATED_2026-11-16.pptx
        + copy in docs/monday_review_2026-11-16/
Changes: corrects stale reserved-180 / ~139,397-doc statements on slides 4, 5, 7, 8, 9, 10 (run-level text edits keep the
original formatting) and inserts 5 new slides after slide 9 that reuse the deck's own frame (header, title, rule, footer).
All numbers are read from project result files.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RES = ROOT / "results"
SRC = Path(r"C:/Users/Lenovo/Downloads/CapstoneProject_IR_03.pptx")
SRC_SHA = "f6932d163c7d3874ac6d8d123ada3f610112e17f8b78d5728ea912fe24e3a369"
OUT = SRC.with_name("CapstoneProject_IR_03_UPDATED_2026-11-16.pptx")
OUT2 = ROOT / "docs" / "monday_review_2026-11-16" / OUT.name
FIG = RES / "esa_nov2026" / "figures"

CARD, HEAD, BODY, ACC, GREEN, GREY = "F7F4F0", "BD582C", "404040", "E48312", "5B7A3A", "7F7F7F"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ data (read from files)

R = json.load(open(RES / "source_targeted" / "results_heldout.json", encoding="utf-8"))["table"]
V = json.load(open(RES / "heldout" / "validation_heldout.json", encoding="utf-8"))
PE = V["primary_endpoint"]
KS = json.load(open(RES / "esa_nov2026" / "demo" / "knowledge_store_stats.json", encoding="utf-8"))
RC = json.load(open(RES / "esa_nov2026" / "recall_ceiling" / "recall_ceiling.json", encoding="utf-8"))
RCH = RC["splits"]["heldout200"]["stage2_retrieval"]["hybrid"]


def rcv(k):
    return float(RCH[f"@{k}"]["claim_recall"])


NDOCS = f"{KS['n_docs_retrievable']:,}"


# ------------------------------------------------------------------ helpers

def set_para_text(p, new):
    runs = p.runs
    if not runs:
        p.add_run().text = new
        return
    runs[0].text = new
    for r in runs[1:]:
        r._r.getparent().remove(r._r)


def replace_in_slide(slide, old, new, count_expected=1):
    """Replace the text of every paragraph containing `old` (text spread across runs is handled)."""
    n = 0
    frames = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            frames.append(sh.text_frame)
        if sh.has_table:
            for row in sh.table.rows:
                for c in row.cells:
                    frames.append(c.text_frame)
    for tf in frames:
        for p in tf.paragraphs:
            txt = "".join(r.text for r in p.runs)
            if old in txt:
                if len(p.runs) > 1 and any(old in r.text for r in p.runs):
                    for r in p.runs:
                        if old in r.text:
                            r.text = r.text.replace(old, new)
                else:
                    set_para_text(p, txt.replace(old, new))
                n += 1
    if n != count_expected:
        raise RuntimeError(f"expected {count_expected} match(es) for {old!r}, found {n}")


def table_row(slide, first_cell_startswith):
    for sh in slide.shapes:
        if sh.has_table:
            for row in sh.table.rows:
                if row.cells[0].text_frame.text.strip().startswith(first_cell_startswith):
                    return row
    raise RuntimeError(f"row {first_cell_startswith!r} not found")


def set_cell(cell, text, color=None, bold=None):
    p = cell.text_frame.paragraphs[0]
    for extra in cell.text_frame.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)
    set_para_text(p, text)
    if color or bold is not None:
        r = p.runs[0]
        if color:
            r.font.color.rgb = RGBColor.from_string(color)
        if bold is not None:
            r.font.bold = bold


def new_slide_like(prs, template_slide, title):
    """New slide on the template's layout with the template's frame shapes (rule, title, header, footer)."""
    s = prs.slides.add_slide(template_slide.slide_layout)
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    for sh in template_slide.shapes:
        if sh.name.startswith("Google Shape"):
            s.shapes._spTree.append(copy.deepcopy(sh._element))
    for sh in s.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip() == template_slide_title(template_slide):
            set_para_text(sh.text_frame.paragraphs[0], title)
    return s


def template_slide_title(s):
    for sh in s.shapes:
        if sh.name.startswith("Google Shape") and sh.has_text_frame and Emu(sh.top).inches > 1.0 and Emu(sh.top).inches < 1.5:
            return sh.text_frame.text.strip()
    return None


def textbox(s, x, y, w, h, paras, fill=None, anchor=MSO_ANCHOR.TOP, name=None, inset=0.12):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, Inches(inset))
    if fill:
        tb.fill.solid()
        tb.fill.fore_color.rgb = RGBColor.from_string(fill)
    first = True
    for item in paras:
        text, size, color, bold = item[:4]
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.LEFT
        if len(item) > 4 and item[4]:
            p.space_before = Pt(item[4])
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.name = "Calibri"
        r.font.color.rgb = RGBColor.from_string(color)
    return tb


def card(s, x, y, w, h, head, lines, name, head_size=16, body_size=14):
    paras = [(head, head_size, HEAD, True)] + [(ln, body_size, BODY, False, 4) for ln in lines]
    return textbox(s, x, y, w, h, paras, fill=CARD, name=name, inset=0.16)


def move_slide(prs, old_index, new_index):
    lst = prs.slides._sldIdLst
    el = list(lst)[old_index]
    lst.remove(el)
    lst.insert(new_index, el)


# ------------------------------------------------------------------ build

def main():
    assert sha(SRC) == SRC_SHA, "original deck changed since it was inspected; stop"
    for f in ("fig1_heldout_recall_at_10.png", "fig3_recall_ceiling_by_depth.png", "fig4_pu_baseline_test_recall10.png"):
        assert (FIG / f).exists(), f"missing figure {f}; run make_figures.py"
    prs = Presentation(str(SRC))
    S = prs.slides

    # ---- slide 4: Review-1 suggestions table
    s4 = S[3]
    r = table_row(s4, "Check whether we can approach maximum recall")
    set_cell(r.cells[1], f"BM25, MiniLM, Hybrid RRF evaluated on 200 frozen held-out AVeriTeC claims (167 with evidence): "
                         f"R@10 {R['bm25']['GoldR@10']:.3f} / {R['dense']['GoldR@10']:.3f} / {R['hybrid']['GoldR@10']:.3f}; "
                         f"pool ceiling {rcv(100):.3f} at top-100, {rcv(300):.3f} at top-300")
    set_cell(r.cells[2], "Done (evidence recall)", GREEN)
    r = table_row(s4, "Train an ML model")
    set_cell(r.cells[1], f"LLM authority prior R@10 {R['hybrid+llm_authority']['GoldR@10']:.3f} vs {R['hybrid']['GoldR@10']:.3f} "
                         f"(p = {PE['p']:.3f}, not significant); learned PU relevance ranker: no gain over hybrid; "
                         "supervised authority model needs human labels")
    set_cell(r.cells[2], "Baselines done; model pending", ACC)
    r = table_row(s4, "Investigate existing datasets")
    set_cell(r.cells[1], "AVeriTeC, NELA-GT-2020, Wikidata, AuFIN/AuRED examined: none labels claim-specific document authority")
    set_cell(r.cells[2], "Completed", GREEN)
    r = table_row(s4, "Create a real-world")
    set_cell(r.cells[1], "Annotation guidelines, templates and agreement plan ready; 200-pair pilot packet built (not yet annotated)")
    set_cell(r.cells[2], "Protocol ready", ACC)

    # ---- slide 5, 7, 8: stale knowledge-store / reserved statements
    replace_in_slide(S[4], "For an input claim, from a ~139,397-document knowledge store",
                     f"For an input claim, from AVeriTeC per-claim knowledge stores (320 claims, {NDOCS} docs)")
    replace_in_slide(S[6], "search ~139K documents now", f"{NDOCS} documents in 320 claim stores now")
    replace_in_slide(S[7], "~139,397 docs, URL-", "320 AVeriTeC claim stores, URL-")
    replace_in_slide(S[7], "initial predictions, 180 claims", "stored predictions, 320 dev claims")

    # ---- slide 9: demo box
    s9 = S[8]
    replace_in_slide(s9, "Load the ~139,397-document knowledge store", "Load the AVeriTeC knowledge stores (320 claims)")
    replace_in_slide(s9, "Run a reserved claim through BM25, MiniLM and Hybrid RRF",
                     "Run a held-out claim through BM25, MiniLM and Hybrid RRF")
    replace_in_slide(s9, "Show the LLM-based authority prediction for the claim",
                     "Show heuristic and stored LLM authority priors re-ranking it")
    replace_in_slide(s9, "Walk through freeze manifests and experiment logs",
                     "Show frozen evaluation, recall ceiling and PU baseline results")
    replace_in_slide(s9, "Uses reserved claims only; no sealed gold labels.",
                     "Uses dev / held-out claims only; reserved-180 outputs were lost and are not used.")

    # ---- slide 10: timeline statuses
    s10 = S[9]
    done_run = table_row(s10, "BM25 retrieval").cells[1].text_frame.paragraphs[0].runs[0]
    done_col = str(done_run.font.color.rgb) if done_run.font.color and done_run.font.color.type else ACC
    for label, status, col in (("Initial LLM authority predictions", "Completed", done_col),
                               ("Recall@K evaluation", "Completed", done_col),
                               ("Dataset investigation", "Completed", done_col),
                               ("Annotation methodology", "Protocol ready", HEAD),
                               ("Supervised authority model", "Awaiting labels", GREY)):
        row = table_row(s10, label)
        set_cell(row.cells[1], status, col)

    tmpl = S[10]  # "Any Other Information" frame
    new = []

    # ---- N1 status
    s = new_slide_like(prs, tmpl, "Phase-I Status Since Review-2")
    rows = [("Item", "Status", "Evidence"),
            ("BM25 / MiniLM / Hybrid RRF pipeline + live demo app", "Completed", "demo_app.py; 10/10 tests pass"),
            ("Frozen held-out evaluation (200 claims, n = 167)", "Completed earlier; re-verified 14 Nov",
             "hash gate PASS; all values identical"),
            ("Recall ceiling by retrieval depth", "Completed", f"top-100 {rcv(100):.3f} → top-300 {rcv(300):.3f}"),
            ("PU relevance-ranking baseline (AVeriTeC train)", "Completed earlier (8 Nov)",
             "negative result; model files lost, metrics recorded"),
            ("Dataset investigation", "Completed", "no claim-document authority labels exist"),
            ("Annotation guidelines, templates, pilot packet", "Partially completed", "protocol ready; no labels yet"),
            ("Supervised claim-specific authority model", "Proposed", "design + metrics fixed; needs labels"),
            ("Three-domain validation", "Pending", "illustrated on real claims, not validated")]
    tbl = s.shapes.add_table(len(rows), 3, Inches(0.56), Inches(1.94), Inches(12.22), Inches(4.6)).table
    tbl.columns[0].width, tbl.columns[1].width, tbl.columns[2].width = Inches(5.3), Inches(3.1), Inches(3.82)
    colors = {"Completed": GREEN, "Partially": ACC, "Proposed": ACC, "Pending": GREY}
    for i, rw in enumerate(rows):
        for j, val in enumerate(rw):
            c = tbl.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = RGBColor.from_string("FFFFFF" if i else CARD)
            tf = c.text_frame
            set_para_text(tf.paragraphs[0], val)
            run = tf.paragraphs[0].runs[0]
            run.font.size = Pt(13 if i else 14)
            run.font.bold = (i == 0) or j == 1
            run.font.name = "Calibri"
            col = BODY
            if i and j == 1:
                col = next((v for k, v in colors.items() if val.startswith(k)), BODY)
            run.font.color.rgb = RGBColor.from_string(col)
            c.margin_top = c.margin_bottom = Inches(0.05)
    s.notes_slide.notes_text_frame.text = ("Distinguish completed, completed earlier, partial, proposed and pending. The reserved-180 "
                                           "outputs from Review 2 were lost and are not part of these results.")
    new.append(s)

    # ---- N2 held-out evaluation
    s = new_slide_like(prs, tmpl, "Retrieval Evaluation: Frozen Held-out Set")
    s.shapes.add_picture(str(FIG / "fig1_heldout_recall_at_10.png"), Inches(0.56), Inches(1.95), width=Inches(7.9))
    card(s, 8.75, 1.95, 4.03, 4.55, "Key results (n = 167 of 200 claims)", [
        f"Hybrid RRF R@10 {R['hybrid']['GoldR@10']:.3f}; + LLM authority prior {R['hybrid+llm_authority']['GoldR@10']:.3f}",
        f"D vs A: +{PE['wins']} / -{PE['losses']} claims, exact McNemar p = {PE['p']:.3f}, "
        f"95% CI [{PE['bootstrap95CI'][0]:.3f}, {PE['bootstrap95CI'][1]:.3f}]: not significant",
        f"Best-evidence rank, D vs hybrid: won {V['rank_win_loss_tie']['authority_vs_hybrid']['win']}, "
        f"lost {V['rank_win_loss_tie']['authority_vs_hybrid']['loss']}",
        "Metric = evidence Recall@K vs AVeriTeC citations, not authority recall",
        "Preregistered; frozen rankings re-scored 14 Nov: identical"], "Eval card", body_size=15)
    s.notes_slide.notes_text_frame.text = "Source: results/source_targeted/results_heldout.json, results/heldout/validation_heldout.json."
    new.append(s)

    # ---- N3 ceiling + PU
    s = new_slide_like(prs, tmpl, "Recall Ceiling and Learned Relevance Baseline")
    s.shapes.add_picture(str(FIG / "fig3_recall_ceiling_by_depth.png"), Inches(0.56), Inches(1.95), width=Inches(6.0))
    s.shapes.add_picture(str(FIG / "fig4_pu_baseline_test_recall10.png"), Inches(6.78), Inches(1.95), width=Inches(6.0))
    textbox(s, 0.56, 5.15, 6.0, 1.5, [
        ("A source that is never retrieved cannot be selected", 14, HEAD, True),
        (f"Any re-ranker of the hybrid top-100 is capped at {rcv(100):.3f}; depth 300 lifts the ceiling to {rcv(300):.3f}.",
         12, BODY, False, 4)], name="Ceiling note")
    textbox(s, 6.78, 5.15, 6.0, 1.5, [
        ("PU relevance ranker (not an authority model)", 14, HEAD, True),
        ("300 AVeriTeC train claims, 217 weak positives + 5,370 unlabelled. No model beat Hybrid RRF on test "
         "Recall@10; HistGBDT overfit. Valid negative result: citation proxies are not enough.", 12, BODY, False, 4)],
            name="PU note")
    s.notes_slide.notes_text_frame.text = ("Ceiling recomputed 14 Nov from frozen rankings (exploratory). PU metrics from the original "
                                           "8 Nov console output; model files were lost on 13 Nov.")
    new.append(s)

    # ---- N4 dataset + model
    s = new_slide_like(prs, tmpl, "Authority Dataset and Model Design (Proposed)")
    card(s, 0.56, 1.94, 5.97, 2.25, "Human-annotated claim-document dataset", [
        "Unit: (claim, candidate document) from the hybrid pool",
        "Two separate labels: relevance (4-way) and authority (primary / auth. secondary / secondary / not / cannot determine)",
        "2+ annotators; all test pairs double-annotated, 20% of train; adjudication; Cohen's kappa / Krippendorff's alpha"],
         "Dataset card")
    card(s, 6.81, 1.94, 5.97, 2.25, "Leakage controls", [
        "Annotators and model never see verdict, justification, Q/A, fact-check article, evidence indicator or rank",
        "Documents shuffled within claim; key file kept separately",
        "Pilot: 20 dev-sample claims x 10 docs = 200 pairs, built and blank"], "Leakage card")
    card(s, 0.56, 4.35, 5.97, 2.25, "Supervised authority model", [
        "Features: retrieval scores, claim-doc similarity, document type, primary-source cues, domain and jurisdiction, provenance",
        "Models: LogReg → Gradient Boosting → MiniLM features (cross-encoder later)",
        "Score = P(relevant) x (1 + beta x P(authoritative)): graded, document-level"], "Model card")
    card(s, 6.81, 4.35, 5.97, 2.25, "Evaluation protocol", [
        "Claim-disjoint split of AVeriTeC train claims; common candidate pool for every system",
        "Primary: Authority Recall@10; also P@10, MRR, F1, calibration",
        "Baselines: hybrid, generic, heuristic, LLM prior; McNemar + bootstrap"], "Eval protocol card")
    s.notes_slide.notes_text_frame.text = "Not trained. No human labels exist yet. PU relevance labels are never used as authority labels."
    new.append(s)

    # ---- N5 three domains
    s = new_slide_like(prs, tmpl, "Applicability Across Three Domains")
    doms = [("Health and medical", "Claim 89: 1918 flu deaths blamed on masks",
             "Authorities: the study itself, WHO / CDC / ICMR, regulators, trial registries",
             "A credible newspaper reporting a study is secondary and often mis-states it",
             "Illustration: evidence rank 21 → 10 with the LLM prior"),
            ("Government and civic", "Claim 268: executive order on pre-existing conditions",
             "Authorities: the issuing body's text, statistics offices, election commissions, courts",
             "A .gov senator's press release is credible but partisan commentary, not the issuer",
             "Illustration: executive order rank 28 → 1; claim 328 NCES 43 → 3"),
            ("Science and technology", "Claim 464: bison reduced to 27 animals",
             "Authorities: the paper or dataset, responsible agency (NPS, FWS, NASA), standards bodies",
             "Contested claims often have many legitimate authorities",
             "Illustration: 18 → 1; failure case claim 326: 24 → 28")]
    for i, (h, ex, a, why, ill) in enumerate(doms):
        card(s, 0.56 + i * 4.15, 1.94, 3.92, 3.95, h, [ex, a, why, ill], f"Domain {i + 1}", body_size=15)
    textbox(s, 0.56, 6.0, 12.22, 0.6, [("Illustrated on real AVeriTeC claims; single-claim observations, not a per-domain "
                                        "validation. Domain-stratified evaluation is Phase-II work.", 12, GREY, False)],
            name="Domain caveat")
    new.append(s)

    # move new slides to sit after slide 9 (index 8)
    n_total = len(prs.slides._sldIdLst)
    for k in range(len(new)):
        move_slide(prs, n_total - len(new) + k, 9 + k)

    prs.save(str(OUT))
    OUT2.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT, OUT2)
    assert sha(SRC) == SRC_SHA, "original deck was modified!"
    print(f"original unchanged (sha {SRC_SHA[:12]}...)\n-> {OUT}\n-> {OUT2}\nslides: {len(prs.slides._sldIdLst)}")


if __name__ == "__main__":
    main()
