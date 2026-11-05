"""
Extra evidence, added 13 Oct 2026 after the robustness suite (logged in README as post-results additions).

X1 Stickiness: how often Credora grades cross the investment-grade line, against S&P's long-run bond record
   (2023 Annual Global Corporate Default and Rating Transition Study, table 23, 1981-2023 averages:
   BBB- -> BB+ or lower within one year 9.08%; BB+ -> BBB- or better 12.67%; withdrawn ratings excluded).
X2 Does yield respond to the risk number? On each pair of consecutive reports, change in PSL vs change in APY
   (mean of the 7 days after the later report minus the 7 days before it). Plus cross-section: rank correlation
   of PSL and yield across Spark dollar vaults on each report date.
X3-X5 Out-of-sample rating events from other raters (not used to form the thesis):
   X3 S&P cuts USDT's stablecoin stability assessment to 5 'weak' (26 Nov 2025)   -> USDT supply
   X4 S&P assigns Sky B- and USDS a 4 'constrained' (7 Aug 2025, 23:31 EDT = 8 Aug UTC) -> USDS supply, sUSDS deposits
   X5 Moody's assigns Sky B3 (7 Oct 2026)                                         -> USDS supply, sUSDS deposits
   Flow from day -1 to day +h minus USDC's supply change (control), ranked against every other day
   (±10 days around these events excluded).
Writes data/processed/extra_*.csv
"""
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import POOLS, PROC, RAW, is_investment_grade, load_grades, load_pool  # noqa: E402

rng = np.random.default_rng(20261013)
grades = load_grades()

# ------------------------------------------------------------------ X1 stickiness
SP_BBBm_TO_SPEC, SP_BBp_TO_IG = 9.08, 12.67  # % per year, S&P table 23 (sum of BB+..D; sum of AAA..BBB-)
rows = []
for addr, g in grades.groupby("address"):
    g = g.sort_values("date").reset_index(drop=True)
    for i in range(1, len(g)):
        rows.append(dict(vault=POOLS[addr][0], start=g.date[i - 1], end=g.date[i], frm=g.rating[i - 1], to=g.rating[i],
                         years=(g.date[i] - g.date[i - 1]).days / 365.25))
sp = pd.DataFrame(rows)
st = []
for side, frm_ig in (("investment grade (A+/A) -> junk-equivalent", True), ("junk-equivalent -> investment grade", False)):
    s = sp[sp.frm.map(is_investment_grade) == frm_ig]
    n = int((s.to.map(is_investment_grade) != frm_ig).sum())
    yrs = s.years.sum()
    st.append(dict(direction=side, crossings=n, vault_years_at_risk=yrs, per_year=n / yrs,
                   prob_within_1y_pct=100 * (1 - np.exp(-n / yrs)),
                   sp_bond_benchmark_pct=SP_BBBm_TO_SPEC if frm_ig else SP_BBp_TO_IG))
stick = pd.DataFrame(st)
stick.to_csv(PROC / "extra_stickiness.csv", index=False)
flips = sp[sp.frm.map(is_investment_grade) != sp.to.map(is_investment_grade)].groupby("vault").size()
# Like-for-like check (S&P counts start vs end of period, so round trips inside the period don't count):
# share of investment-grade grades that are junk-equivalent h days later, against S&P BBB-/BBB scaled to h days.
coh = []
for h in (30, 60, 90, 120, 180):
    n = k = 0
    for addr, gg in grades.groupby("address"):
        s_ = pd.Series(gg.sort_values("date").rating.values, index=gg.sort_values("date").date)
        for t, r in s_.items():
            if is_investment_grade(r) and t + pd.Timedelta(days=h) <= grades.date.max():
                n += 1
                k += not is_investment_grade(s_.loc[:t + pd.Timedelta(days=h)].iloc[-1])
    coh.append(dict(horizon_d=h, ig_starts=n, junk_after_pct=100 * k / n if n else np.nan,
                    sp_bbbminus_scaled_pct=100 * (1 - (1 - SP_BBBm_TO_SPEC / 100) ** (h / 365.25))))
coh = pd.DataFrame(coh)
coh.to_csv(PROC / "extra_stickiness_cohort.csv", index=False)
vault_years = sum((gg.date.max() - gg.date.min()).days / 365.25 for _, gg in grades.groupby("address"))
first_last = grades.groupby("vault").date.agg(["min", "max"])

# ------------------------------------------------------------------ X2 yield vs risk number
xr = []
for addr, g in grades.groupby("address"):
    name, pool, conf, how, dollar = POOLS[addr]
    if not pool or not dollar:
        continue
    p = load_pool(pool)
    p = p[p.tvl >= 10e6].apy.dropna()
    g = g.sort_values("date").reset_index(drop=True)
    for i in range(1, len(g)):
        d = g.date[i]
        before, after = p.loc[d - pd.Timedelta(days=7):d - pd.Timedelta(days=1)], p.loc[d:d + pd.Timedelta(days=6)]
        if len(before) >= 4 and len(after) >= 4:
            xr.append(dict(vault=name, rate_set_by=how, date=d, d_psl=g.psl_pct[i] - g.psl_pct[i - 1],
                           d_apy=after.mean() - before.mean()))
xr = pd.DataFrame(xr)


def perm_corr(x, y, n=5000):
    obs = np.corrcoef(x, y)[0, 1]
    null = np.array([np.corrcoef(x, rng.permutation(y))[0, 1] for _ in range(n)])
    return obs, (np.sum(np.abs(null) >= abs(obs)) + 1) / (n + 1)


mv = xr[xr.d_psl.abs() > 0]
r_all, p_all = perm_corr(mv.d_psl.values, mv.d_apy.values)
xr.to_csv(PROC / "extra_psl_vs_apy.csv", index=False)

cs = []
spark_dollar = [a for a, v in POOLS.items() if v[1] and v[4] and a.startswith("0x") and v[0].startswith(("Spark", "Staked"))]
for d, g in grades[grades.address.isin(spark_dollar)].groupby("date"):
    pts = []
    for _, r in g.iterrows():
        p = load_pool(POOLS[r.address][1])
        w = p.loc[d:d + pd.Timedelta(days=6)]
        w = w[w.tvl >= 10e6].apy.dropna()
        if len(w) >= 4:
            pts.append((r.psl_pct, w.mean()))
    if len(pts) >= 4:
        a = pd.DataFrame(pts, columns=["psl", "apy"])
        cs.append(dict(date=d, vaults=len(a), spearman=a.psl.rank().corr(a.apy.rank())))
cs = pd.DataFrame(cs)
cs.to_csv(PROC / "extra_cross_section.csv", index=False)


# ------------------------------------------------------------------ X3-X5 out-of-sample events
def stable_supply(i):
    t = json.load(open(RAW / f"llama_stablecoin_{i}.json"))["tokens"]
    s = pd.Series({pd.Timestamp(dt.datetime.fromtimestamp(x["date"], dt.UTC).date()): x["circulating"].get("peggedUSD", np.nan) for x in t})
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))


usdt, usdc = stable_supply(1), stable_supply(2)
# Sky issues two interchangeable dollars (DAI and USDS, 1:1 convertible), so holders switching between them is not
# an exit: Sky's supply is USDS + DAI. (USDS alone fell 11% in the week after S&P's rating while DAI rose 7%.)
usds = stable_supply(209) + stable_supply(5).reindex(stable_supply(209).index)
susds = load_pool(POOLS["0xa3931d71877c0e7a3148cb7eb4463524fec27fbd"][1]).tvl
susds = susds.reindex(pd.date_range(susds.index.min(), susds.index.max(), freq="D"))
EVENTS = [("S&P cuts USDT to 5 'weak'", pd.Timestamp("2025-11-26"), {"USDT supply": usdt}),
          ("S&P rates Sky B- / USDS 4", pd.Timestamp("2025-08-08"), {"Sky supply (USDS+DAI)": usds, "sUSDS deposits": susds}),
          ("Moody's rates Sky B3", pd.Timestamp("2026-10-07"), {"Sky supply (USDS+DAI)": usds, "sUSDS deposits": susds})]
ev_days = {d + pd.Timedelta(days=k) for _, d, _ in EVENTS for k in range(-10, 11)}


def chg(s, h):
    return 100 * (s.shift(-h) / s.shift(1) - 1)  # day -1 -> day +h, indexed by day 0


out = []
for label, d0, series in EVENTS:
    for sname, s in series.items():
        for h in (3, 7, 14, 30):
            ab = chg(s, h) - chg(usdc, h).reindex(s.index)
            x = ab.get(d0, np.nan)
            if not np.isfinite(x):
                continue
            hist = ab.loc["2024-01-01":].drop([d for d in ev_days if d in ab.index]).dropna()
            out.append(dict(event=label, date=d0.date(), series=sname, horizon_d=h, raw_flow_pct=chg(s, h).get(d0),
                            usdc_flow_pct=chg(usdc, h).get(d0), abnormal_pct=x, percentile=100 * (hist <= x).mean(),
                            null_days=len(hist), level_day_minus1_bn=s.get(d0 - pd.Timedelta(days=1)) / 1e9))
oos = pd.DataFrame(out)
oos.to_csv(PROC / "extra_out_of_sample.csv", index=False)

# ------------------------------------------------------------------ X2b slope: extra yield for one grade step
# Same report dates, Spark governance vaults graded A (= BBB/BBB-) vs A- (= BB+/BB), 7-day mean APY after the report,
# against the ICE BBB -> BB step over the same window (bond_spreads.csv).
st_rows = []
for d, g in grades[grades.protocol == "SPARK"].groupby("date"):
    for _, r in g.iterrows():
        name, pool, conf, how, dollar = POOLS[r.address]
        if not dollar or how != "governance":
            continue
        w = load_pool(pool).loc[d:d + pd.Timedelta(days=6)]
        w = w[w.tvl >= 10e6].apy.dropna()
        if len(w) >= 4:
            st_rows.append(dict(date=d, rating=r.rating, apy=w.mean()))
stp = pd.DataFrame(st_rows).groupby(["date", "rating"]).apy.mean().unstack()
stp = (stp["A-"] - stp["A"]).dropna()
bs = pd.read_csv(PROC / "bond_spreads.csv").set_index("rating").mean_spread
step = dict(spark_A_to_Aminus_mean=stp.mean(), spark_min=stp.min(), spark_max=stp.max(), report_dates=len(stp),
            bond_BBB_to_BB=bs["BB"] - bs["BBB"])
pd.DataFrame([step]).to_csv(PROC / "extra_grade_step.csv", index=False)

# ------------------------------------------------------------------ X6 independent mapping from S&P default rates
# S&P 2023 study, table 23, one-year default rate (column D) by rating, 1981-2023 averages (%).
SP_DEFAULT = {"AAA": 0.00, "AA+": 0.00, "AA": 0.02, "AA-": 0.02, "A+": 0.04, "A": 0.05, "A-": 0.05, "BBB+": 0.09, "BBB": 0.14,
              "BBB-": 0.21, "BB+": 0.28, "BB": 0.45, "BB-": 0.88, "B+": 1.86, "B": 2.73, "B-": 5.33}
IG_CUT = (SP_DEFAULT["BBB-"] + SP_DEFAULT["BB+"]) / 2  # halfway between the last IG and first junk default rate


def nearest_sp(psl):
    return min(SP_DEFAULT, key=lambda r: abs(np.log((SP_DEFAULT[r] or 0.005) / max(psl, 0.005))))


ind = grades.assign(sp_nearest=grades.psl_pct.map(nearest_sp), ig_by_sp_default=grades.psl_pct <= IG_CUT)
ind.to_csv(PROC / "extra_independent_mapping.csv", index=False)
band_map = {L: [r for r, d in SP_DEFAULT.items() if lo < d <= hi or (lo == 0 and d <= hi)] for L, (lo, hi) in
            {"A+": (0, .1), "A": (.1, .4), "A-": (.4, .8), "B+": (.8, 1.5), "B": (1.5, 3), "B-": (3, 6)}.items()}

# ------------------------------------------------------------------ X7 short-maturity benchmark (duration check)
from src.rating import load_fred as _lf  # noqa: E402
short_ig = _lf("BAMLC1A0C13Y").loc["2026-02-01":"2026-10-13"].mean()  # ICE BofA 1-3 Year US Corporate (all IG) OAS

# ------------------------------------------------------------------ summary
pd.set_option("display.width", 220)
print("X1 how often grades cross the investment-grade line")
print(stick.round(2).to_string(index=False))
print("   crossings per vault:", flips.to_dict())
print(f"   {len(flips)} of {grades.address.nunique()} vaults crossed; {int(flips.sum())} crossings in {vault_years:.1f} vault-years "
      f"= {flips.sum() / vault_years:.1f} per vault-year")
print("   like-for-like (start vs end of period; S&P counts this way):")
print(coh.round(1).to_string(index=False))
print("   -> don't present 93% vs 9% as a ratio: the first counts every crossing, S&P's counts year-end status")
print(f"\nX2 change in PSL vs change in yield: n={len(mv)} report pairs where PSL moved, r = {r_all:+.2f}, p = {p_all:.2f}")
print(xr.groupby("rate_set_by").apply(lambda g: pd.Series(dict(n=len(g[g.d_psl != 0]),
      r=np.corrcoef(g[g.d_psl != 0].d_psl, g[g.d_psl != 0].d_apy)[0, 1] if len(g[g.d_psl != 0]) > 2 else np.nan)),
      include_groups=False).round(2).to_string())
print(f"   cross-section (Spark dollar vaults, {len(cs)} report dates): median Spearman(PSL, yield) = {cs.spearman.median():+.2f}, "
      f"positive on {100 * (cs.spearman > 0).mean():.0f}% of dates (bond market: +1 by construction)")
print(f"   one grade step (BBB -> BB equivalent): Spark pays {step['spark_A_to_Aminus_mean']:+.2f} pts more "
      f"[{step['spark_min']:+.2f} to {step['spark_max']:+.2f}, {step['report_dates']} dates]; bonds pay {step['bond_BBB_to_BB']:+.2f}")
print(f"\nX7 1-3 year investment-grade corporate spread, Feb-Oct 2026: +{short_ig:.2f} pts (Spark vaults vs T-bill: see vault_spreads.csv)")
print(f"\nX6 independent mapping (S&P default rates): bands -> {band_map}")
print(f"   investment grade if PSL <= {IG_CUT:.3f}% (between BBB- and BB+ default rates): "
      f"{100 * ind.ig_by_sp_default.mean():.1f}% of grades (Credora's table: {100 * grades.investment_grade.mean():.1f}%)")
print("\nX3-X5 out-of-sample rating events (abnormal = flow minus USDC supply flow; percentile vs all days since 2024)")
print(oos.round(2).to_string(index=False))
