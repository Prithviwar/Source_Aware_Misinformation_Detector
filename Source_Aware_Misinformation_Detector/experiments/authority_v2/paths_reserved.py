"""Reserved-set paths and the path redirection of the frozen modules (preregistration §4.1 Mechanism).

Only module-level path constants are reassigned: validation_heldout.HO, HO_SAMPLE, PRED_RAW,
PROBE_RAW, KS_DIR; common.KS_DIR; wikidata_authority.CACHE. No function body is changed.
"""
from v2common import RES, ROOT

import common
import validation_heldout as V
import wikidata_authority

DEV_JSON = ROOT / "data/raw/averitec/dev.json"
KS_RESERVED = ROOT / "data/raw/averitec/ks_reserved180"
INPUTS = ROOT / "data/processed/averitec_reserved180_inputs.jsonl"
SEALED = ROOT / "data/processed/averitec_reserved180_gold.jsonl"
HO_RES = RES / "reserved"
WD_DIR = RES / "wikidata"
WD_COPY = WD_DIR / "wikidata_resolution.json"
WD_FROZEN = ROOT / "results/wikidata_resolution.json"

ORIGINAL = {"V.HO": V.HO, "V.HO_SAMPLE": V.HO_SAMPLE, "V.PRED_RAW": V.PRED_RAW, "V.PROBE_RAW": V.PROBE_RAW,
            "V.KS_DIR": V.KS_DIR, "common.KS_DIR": common.KS_DIR, "wikidata_authority.CACHE": wikidata_authority.CACHE}


def redirect():
    V.HO = HO_RES
    V.HO_SAMPLE = INPUTS  # inputs only before scoring
    V.PRED_RAW = HO_RES / "authority_raw.jsonl"
    V.PROBE_RAW = HO_RES / "memorisation_probe_raw.jsonl"
    V.KS_DIR = KS_RESERVED
    common.KS_DIR = KS_RESERVED
    wikidata_authority.CACHE = WD_COPY
    HO_RES.mkdir(parents=True, exist_ok=True)
    return {"V.HO": V.HO, "V.HO_SAMPLE": V.HO_SAMPLE, "V.PRED_RAW": V.PRED_RAW, "V.PROBE_RAW": V.PROBE_RAW,
            "V.KS_DIR": V.KS_DIR, "common.KS_DIR": common.KS_DIR, "wikidata_authority.CACHE": wikidata_authority.CACHE}
