"""
Is any final chart stale? Hashes each chart's declared inputs (its script, house_style.py and every data file it
reads) against a recorded manifest. mtimes are not used (a bulk touch makes everything look stale).

    python scripts/check_freshness.py           # verify
    python scripts/check_freshness.py --update  # re-record after re-rendering
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT.parent / "2_Charts" / "final"
MANIFEST = FINAL / ".freshness_manifest.json"
P, R = "data/processed/", "data/raw/"
COMMON = ["scripts/chart_cb.py", "scripts/house_style.py"]
CHARTS = {  # chart -> inputs it reads (the one manual step: add an input here when a chart gains one)
    "chart1_translation.png": [P + "credora_grades.csv", P + "extra_independent_mapping.csv", R + "llama_charts"],
    "chart2_crossings.png": [P + "credora_grades.csv", R + "llama_charts"],
    "chart3_yield.png": [P + "bond_spreads.csv", P + "vault_spreads.csv", R + "fred/BAMLC1A0C13Y.csv", P + "credora_grades.csv"],
    "chart4_ratings_vs_warning.png": [P + "grade_events.csv", P + "bnb_vault_token_flows.csv", P + "extra_out_of_sample.csv",
                                      P + "robustness_positive_control.csv"],
    "chart5_usdt.png": [R + "llama_stablecoin_1.json", R + "llama_stablecoin_2.json"],
    "chart6_xusd_market.png": [R + "xusd_arb_daily.json"],
    "chart7_curators.png": [P + "curator_concentration.csv"],
    "table1_grade_changes.png": [P + "grade_events.csv"],
}


def digest(rel):
    p = ROOT / rel
    files = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


current = {c: {i: digest(i) for i in COMMON + ins} for c, ins in CHARTS.items()}
missing = [c for c in CHARTS if not (FINAL / c).exists()]
if "--update" in sys.argv:
    MANIFEST.write_text(json.dumps(current, indent=1))
    print(f"recorded {len(current)} charts")
    sys.exit(0)
old = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
stale = [c for c in CHARTS if old.get(c) != current[c]]
for c in CHARTS:
    print(f"{'MISSING' if c in missing else 'STALE  ' if c in stale else 'fresh  '} {c}")
sys.exit(1 if stale or missing else 0)
