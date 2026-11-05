"""
One command: rebuild the rating study, audit it, and redraw every final chart. Stops at the first failure.

    python run_all.py --online   # first run: download raw data, then rebuild everything
    python run_all.py            # later runs: offline, uses the cached raw data
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
STEPS = [
    ("offline tests",                         ["-m", "pytest", "tests", "-q"]),
    ("build Credora grade panel",             ["scripts/build_credora_panel.py"]),
    ("test 1: yield vs grade",                ["scripts/build_yield_spreads.py"]),
    ("test 2: grade changes vs deposits",     ["scripts/build_grade_events.py"]),
    ("test 2b: BNB vault in BNB units",       ["scripts/build_bnb_robustness.py"]),
    ("test 3: Stream reaction",               ["scripts/build_stream_reaction.py"]),
    ("test 3b: who left the xUSD market",     ["scripts/build_xusd_lenders.py"]),
    ("curator concentration (Morpho, 13 Oct 2026)", ["scripts/build_curator_concentration.py"]),
    ("market-regime checks",                  ["scripts/build_regime_checks.py"]),
    ("extra evidence (stickiness, yield vs risk, other raters)", ["scripts/build_extra_evidence.py"]),
    ("ratings vs warnings, head to head",     ["scripts/build_ratings_vs_warnings.py"]),
    ("adversarial pass on core claims",       ["scripts/attack_core_claims.py"]),
    ("audit (re-derive by hand, no lookahead)", ["scripts/verify_rating_study.py"]),
    ("robustness (spec curve, power, placebo, controls)", ["scripts/robustness.py"]),
    ("Coinbase-style article charts",        ["scripts/chart_cb.py"]),
    ("chart freshness",                       ["scripts/check_freshness.py"]),
    ("v2: stablecoin breaks",                 ["scripts/v2_depegs.py"]),
    ("v2: VaR before every break",            ["scripts/v2_var_all_breaks.py"]),
    ("v2 charts",                             ["scripts/v2_charts.py"]),
    ("X-thread charts",                       ["scripts/x_post_charts.py"]),
]
ONLINE = [("refresh raw data (rating study)", ["scripts/update_data.py"]), ("refresh raw data (v2 and X thread)", ["scripts/fetch_v2_raw.py"])]

for name, args in (ONLINE if "--online" in sys.argv else []) + STEPS:
    print(f"\n=== {name}")
    res = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True)
    tail = (res.stdout + res.stderr).strip().splitlines()
    print("\n".join(tail[-4:]))
    if res.returncode != 0:
        print(f"\nSTOPPED: {' '.join(args)} failed (exit {res.returncode})\n" + "\n".join(tail[-25:]))
        sys.exit(res.returncode)
print("\nall steps passed")
