"""Drive the RUNNING demo app in a real (headless Chromium) browser and save genuine screenshots for the fallback.

  1) start the app:  run_demo.bat           (must be serving http://localhost:8501)
  2) python experiments/esa_nov2026/capture_screenshots.py

Clicks exactly what the presenter clicks (claim 268, stored mode, Run pipeline; then the evaluation and PU tabs) and
writes results/esa_nov2026/demo/screenshots/*.png plus capture_log.json. Nothing on the page is edited.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "esa_nov2026" / "demo" / "screenshots"
URL = "http://localhost:8501"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log = {"started": datetime.now().isoformat(timespec="seconds"), "url": URL, "steps": []}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        t0 = time.time()
        pg.goto(URL, timeout=120_000)
        pg.get_by_text("Run pipeline").wait_for(timeout=600_000)
        pg.get_by_text("Pick a claim in the sidebar").wait_for(timeout=600_000)
        log["steps"].append({"app_ready_s": round(time.time() - t0, 1)})
        pg.screenshot(path=str(OUT / "01_start.png"))
        t1 = time.time()
        pg.get_by_role("button", name="Run pipeline").click()
        pg.get_by_text("Step 5 · Final ranked sources").wait_for(timeout=600_000)
        time.sleep(3)
        log["steps"].append({"claim_268_run_s": round(time.time() - t1, 1)})
        pg.screenshot(path=str(OUT / "02_claim268_full.png"), full_page=True)
        for name, anchor in (("03_step3_retrieval.png", "Step 3 · Retrieval"), ("04_step4_authority.png", "Step 4 · Authority"),
                             ("05_step5_final.png", "Step 5 · Final ranked sources")):
            pg.get_by_text(anchor).first.scroll_into_view_if_needed()
            time.sleep(1)
            pg.screenshot(path=str(OUT / name))
        # authority tab D
        pg.get_by_role("tab", name="D  LLM authority prior").click()
        time.sleep(1.5)
        pg.get_by_text("Step 4 · Authority").first.scroll_into_view_if_needed()
        pg.screenshot(path=str(OUT / "06_authority_D_tab.png"))
        pg.get_by_role("tab", name="Evaluation: frozen held-out").click()
        pg.get_by_text("Primary: D vs A, R@10").wait_for(timeout=60_000)
        time.sleep(2)
        pg.screenshot(path=str(OUT / "07_evaluation_tab.png"), full_page=True)
        pg.get_by_role("tab", name="PU relevance baseline").click()
        pg.get_by_text("NOT an authority model").first.wait_for(timeout=60_000)
        time.sleep(2)
        pg.screenshot(path=str(OUT / "08_pu_tab.png"), full_page=True)
        b.close()
    log["finished"] = datetime.now().isoformat(timespec="seconds")
    log["files"] = sorted(x.name for x in OUT.glob("*.png"))
    json.dump(log, open(OUT / "capture_log.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
