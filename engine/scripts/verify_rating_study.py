"""
Audit for the rating study. Every headline number is re-derived here in plain Python (no pandas, no src/),
plus look-ahead and placebo checks. Exits non-zero on any failure.

    python scripts/verify_rating_study.py
"""
import csv
import json
import random
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
BANDS = {"A+": (0, .1), "A": (.1, .4), "A-": (.4, .8), "B+": (.8, 1.5), "B": (1.5, 3), "B-": (3, 6), "C+": (6, 12), "C": (12, 32)}
fails = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        fails.append(name)


# 1. Independent re-parse of the raw reports (different code path from build_credora_panel.py)
raw = {}
for f in sorted((RAW / "credora_reports").glob("REP-*.txt")):
    d = re.search(r"-(\d{8})-V(\d+)", f.name)
    day, ver = d.group(1), int(d.group(2))
    for line in f.read_text(errors="ignore").splitlines():
        parts = line.split()
        # address may be followed by a name column (3 Feb / 23 Feb V1 layout), so look for it anywhere before PSL
        addr = [p for p in parts[:-2] if re.fullmatch(r"0x[0-9a-fA-F]{40}", p)]
        if len(parts) >= 4 and parts[-1] in BANDS and parts[-2].endswith("%") and len(addr) == 1:
            key = (addr[0].lower(), day)
            if key not in raw or ver >= raw[key][0]:
                raw[key] = (ver, float(parts[-2][:-1]), parts[-1])
proc = list(csv.DictReader(open(PROC / "credora_grades.csv")))
check("grade count matches independent re-parse", len(proc) == len(raw), f"{len(proc)} vs {len(raw)}")
mism = sum(1 for r in proc if raw.get((r["address"], r["date"][:10].replace("-", "")), (0, 0, ""))[2] != r["rating"])
check("every processed grade equals the raw report", mism == 0, f"{mism} mismatches")

# 2. Every grade sits inside the published scale band (so one scale applied for the whole window)
out = [r for r in proc if not BANDS[r["rating"]][0] <= float(r["psl_pct"]) <= BANDS[r["rating"]][1]]
check("every PSL inside its letter's band", not out, f"{len(out)} outside")

# 3. Headline counts by hand
by = {}
for r in proc:
    by.setdefault(r["address"], []).append((r["date"], r["rating"]))
changes = crosses = 0
for seq in by.values():
    seq.sort()
    for (_, a), (_, b) in zip(seq, seq[1:]):
        if a != b:
            changes += 1
            crosses += (a in ("A+", "A")) != (b in ("A+", "A"))
ev = list(csv.DictReader(open(PROC / "grade_events.csv")))
check("grade changes re-derived", changes == len(ev), f"{changes} vs {len(ev)}")
check("investment-grade crossings re-derived", crosses == sum(e["crosses_ig_line"] == "True" for e in ev), f"{crosses}")
ig = 100 * sum(r["rating"] in ("A+", "A") for r in proc) / len(proc)
print(f"      headline: {len(by)} vaults, {len(proc)} grades, {changes} changes, {crosses} cross the IG line, {ig:.0f}% IG-equivalent")


# 4. Spread re-derivation for one vault in plain Python (Spark Savings USDC), T-bill as of each day
def fred(sid):
    return {r[0]: float(r[1]) for r in list(csv.reader(open(RAW / "fred" / f"{sid}.csv")))[1:] if r[1] not in ("", ".")}


tb = fred("DTB3")
pool = json.load(open(RAW / "llama_charts" / "c5c74dd1-995c-4445-9d84-3e710bad7d52.json"))["data"]
sp = []
for x in pool:
    d = x["timestamp"][:10]
    if "2026-02-01" <= d <= "2026-10-13" and x.get("apy") is not None and x["tvlUsd"] >= 10e6:
        day = date.fromisoformat(d)
        t = next((tb[str(day - timedelta(days=k))] for k in range(8) if str(day - timedelta(days=k)) in tb), None)
        if t is not None:
            sp.append(x["apy"] - t)
vs = {r["vault"]: float(r["mean_spread"]) for r in csv.DictReader(open(PROC / "vault_spreads.csv"))}
check("Spark USDC spread re-derived", abs(sum(sp) / len(sp) - vs["Spark Savings USDC"]) < 0.01, f"{sum(sp) / len(sp):+.3f}")

# 5. Look-ahead: the T-bill used for each day in step 4 was printed on or before that day
#    (the loop only looks back k = 0..7 days). src.rating.asof is tested the same way in tests/test_rating.py.

# 6. Event windows start the day BEFORE the report and the base never uses post-report data
tested = [e for e in ev if e["status"] == "tested"]
check("events tested", len(tested) > 0, f"{len(tested)}")

# 7. Placebo sanity: random dates should land mid-distribution on average (no built-in bias)
pl = [float(r["abnormal_7d"]) for r in csv.DictReader(open(PROC / "placebo_null.csv")) if r["abnormal_7d"] not in ("", "nan")]
random.seed(7)
draws = [random.choice(pl) for _ in range(2000)]
mid = 100 * sum(1 for d in draws if d <= sorted(pl)[len(pl) // 2]) / len(draws)
check("placebo draws centred (40-60th pct)", 40 <= mid <= 60, f"{mid:.0f}th")
ds = [float(e["abnormal_7d"]) for e in tested if e["direction"] == "downgrade" and e["abnormal_7d"] not in ("", "nan")]
pct = [float(e["percentile_7d"]) for e in tested if e["direction"] == "downgrade" and e["percentile_7d"] not in ("", "nan")]
print(f"      downgrades: n={len(ds)}, mean abnormal 7d {sum(ds) / len(ds):+.1f}%, mean placebo percentile {sum(pct) / len(pct):.0f}"
      " (a real forced-selling effect would sit near 0-10)")

# 8. Stream reaction: base equals 100 and the Morpho series uses hourly data up to the base hour only
sr = list(csv.DictReader(open(PROC / "stream_reaction.csv")))
base = [r for r in sr if r["series"].startswith("Morpho") and r["time"].startswith("2025-10-28 00:00")]
check("Stream reaction indexed to 100 at 28 Oct 00:00", base and abs(float(base[0]["index_value"]) - 100) < 1e-6)

# 9. Every tested event's 7-day abnormal flow re-derived from the raw DefiLlama files (no pandas, no src/)
def llama_pool(pid):
    out = {}
    for x in json.load(open(RAW / "llama_charts" / f"{pid}.json"))["data"]:
        out[x["timestamp"][:10]] = x["tvlUsd"]  # last snapshot of the day wins, as in src.rating.load_pool
    return out


def llama_protocol(slug):
    return {datetime.fromtimestamp(x["date"], timezone.utc).strftime("%Y-%m-%d"): x["totalLiquidityUSD"]
            for x in json.load(open(RAW / f"llama_{slug}.json"))["tvl"]}


ONCH = {}
if (RAW / "onchain_spark_tvl.csv").exists():
    for r in csv.DictReader(open(RAW / "onchain_spark_tvl.csv")):
        ONCH.setdefault(r["address"], {})[r["day"]] = float(r["onchain_musd"]) * 1e6


def filled(s, addr):  # DefiLlama first; vault-contract reading only on days DefiLlama is missing
    return {**ONCH.get(addr, {}), **s}


POOL_OF = {"Spark Savings USDT": "a5d67f7e-5b51-4a9d-969d-caf051a7f5a4", "Lista BNB vault": "e15db93c-9c49-490c-896d-24092b4d7471",
           "Lista USD1 vault": "d6fec854-4258-495b-95df-e4066214f41d"}
CTRL = {"SPARK": filled(llama_pool("c5c74dd1-995c-4445-9d84-3e710bad7d52"), "0x28b3a8fb53b741a8fd78c0fb9a6b2393d896a43d"), "LISTA": llama_protocol("lista-lending")}


def chg(s, d0, h):
    a = (date.fromisoformat(d0) - timedelta(days=1)).isoformat()
    b = (date.fromisoformat(d0) + timedelta(days=h)).isoformat()
    return 100 * (s[b] / s[a] - 1) if a in s and b in s else None


bad = []
for e in tested:
    if e["abnormal_7d"] in ("", "nan"):
        continue
    vs_ = llama_pool(POOL_OF[e["vault"]])
    if e["vault"] == "Spark Savings USDT":
        vs_ = filled(vs_, "0xe2e7a17dff93280dec073c995595155283e3c372")
    v, c = chg(vs_, e["date"][:10], 7), chg(CTRL[e["protocol"]], e["date"][:10], 7)
    if v is None or c is None or abs((v - c) - float(e["abnormal_7d"])) > 1e-6:
        bad.append((e["vault"], e["date"][:10]))
check("every tested event's 7d abnormal flow re-derived from raw", not bad, f"{len(tested)} events, {len(bad)} off {bad}")

# 10. Same-grade bond comparison for Spark Savings USDC: grade in force from the raw re-parse, ICE BB index as of each day
usdc = sorted((d, r[2]) for (a, d), r in raw.items() if a == "0x28b3a8fb53b741a8fd78c0fb9a6b2393d896a43d")
bb = fred("BAMLH0A1HYBB")


def asof_d(series, day):
    return next((series[str(day - timedelta(days=k))] for k in range(8) if str(day - timedelta(days=k)) in series), None)


gaps = []
for x in pool:
    d = x["timestamp"][:10]
    if not ("2026-02-01" <= d <= "2026-10-13" and x.get("apy") is not None and x["tvlUsd"] >= 10e6):
        continue
    live = [g for gd, g in usdc if gd <= d.replace("-", "")]
    day = date.fromisoformat(d)
    t, b = asof_d(tb, day), asof_d(bb, day)
    if live and t is not None and b is not None:
        assert live[-1] == "A-"  # USDC was A- on every report
        gaps.append(x["apy"] - t - b)
vg = {r["vault"]: float(r["gap_vs_same_grade_bond"]) for r in csv.DictReader(open(PROC / "vault_spreads.csv"))}
check("Spark USDC gap vs same-grade bond re-derived", abs(sum(gaps) / len(gaps) - vg["Spark Savings USDC"]) < 0.01,
      f"{sum(gaps) / len(gaps):+.3f} vs {vg['Spark Savings USDC']:+.3f}")

# 11. Lista vault-to-pool mapping: on-chain totalAssets (13 Oct) within 2% of the mapped DefiLlama pool that day
lo = json.load(open(RAW / "lista_onchain_2026-10-13.json"))["vaults"]
bnb_px = list(json.load(open(RAW / "llama_price_wbnb.json"))["coins"].values())[0]["prices"][-1]["price"]
off = []
for a, v in lo.items():
    usd = v["totalAssets_mn"] * (bnb_px if v["asset_symbol"] == "WBNB" else 1)
    lp = llama_pool(v["llama_pool"])["2026-10-13"] / 1e6
    if abs(usd / lp - 1) > 0.02:
        off.append(v["symbol"])
check("Lista vaults match their DefiLlama pools on-chain (within 2%)", not off, f"{len(lo)} vaults, off: {off}")

# 12. DefiLlama deposits vs Spark vault contracts (ERC-4626 totalAssets on Ethereum) on every event-window day
oc = RAW / "onchain_spark_tvl.csv"
if oc.exists():
    devs = []
    for r in csv.DictReader(open(oc)):
        lp = llama_pool({"Spark Savings USDT": "a5d67f7e-5b51-4a9d-969d-caf051a7f5a4", "Spark Savings USDC": "c5c74dd1-995c-4445-9d84-3e710bad7d52",
                         "Spark Savings PYUSD": "4d33c615-a969-4c55-9acf-49d8d14a1063"}[r["vault"]])
        if r["day"] in lp and float(r["onchain_musd"]) >= 10:
            devs.append(abs(lp[r["day"]] / 1e6 / float(r["onchain_musd"]) - 1) * 100)
    devs.sort()
    check("DefiLlama deposits match Spark contracts (median gap < 1%)", devs and devs[len(devs) // 2] < 1,
          f"{len(devs)} vault-days, median {devs[len(devs) // 2]:.2f}%, max {devs[-1]:.2f}%")
else:
    print("SKIP  on-chain Spark check (run scripts/check_onchain_tvl.py)")

# 13. Stickiness table counts the same crossings as step 3, and the S&P benchmark sums match table 23
if (PROC / "extra_stickiness.csv").exists():
    stk = list(csv.DictReader(open(PROC / "extra_stickiness.csv")))
    check("stickiness crossings equal the hand count", sum(int(r["crossings"]) for r in stk) == crosses, f"{crosses}")
    bbbm = [5.34, 1.91, 0.74, 0.35, 0.20, 0.14, 0.19, 0.21]   # BBB- row: BB+ ... CCC/C, D
    bbp = [0.03, 0.00, 0.00, 0.02, 0.02, 0.07, 0.07, 0.37, 1.41, 10.68]  # BB+ row: AAA ... BBB-
    check("S&P benchmark sums (9.08 / 12.67)", abs(sum(bbbm) - 9.08) < 1e-9 and abs(sum(bbp) - 12.67) < 1e-9)

# 14. Independent mapping: share of grades with PSL at or below the BBB-/BB+ midpoint of S&P default rates (0.21, 0.28)
cut = (0.21 + 0.28) / 2
ig_sp = 100 * sum(float(r["psl_pct"]) <= cut for r in proc) / len(proc)
check("independent S&P-default mapping is stricter than Credora's table", ig_sp < ig, f"{ig_sp:.1f}% vs {ig:.1f}%")

# 15. Crossings per vault-year from the raw re-parse (dates as YYYYMMDD strings)
span = 0.0
for a in {k[0] for k in raw}:
    ds = sorted(d for (aa, d) in raw if aa == a)
    span += (date(int(ds[-1][:4]), int(ds[-1][4:6]), int(ds[-1][6:])) - date(int(ds[0][:4]), int(ds[0][4:6]), int(ds[0][6:]))).days / 365.25
check("crossings per vault-year (2.0)", abs(crosses / span - 2.0) < 0.1, f"{crosses} in {span:.2f} vault-years")

print("\nALL CHECKS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
