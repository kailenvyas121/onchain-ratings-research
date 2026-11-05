"""
Market-regime checks: could a crash or a rally have shaped the results?

G1 Event conditions: Bitcoin's trailing 30-day return on day -1 and its move over each event window.
G2 Regime-matched placebo: re-rank each Credora downgrade only against ordinary days in the same regime
   (Bitcoin's trailing 30-day return the same sign), and re-run the permutation test.
G3 Do grade flips cluster in falling markets? Crossings and vault-years split by regime.
G4 Positive control vs the 10 Oct 2025 crash: how much did each Stream-era series move in the crash week (no warning)
   compared with the warning week?
G5 Bond benchmark level: were 2026 spreads unusually tight? (FRED now serves only the last 3 years of ICE data.)
Writes data/processed/regime_*.csv
"""
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import CONTROL_ADDRESS, CONTROLS, POOLS, PROC, RAW, is_investment_grade, load_fred, load_grades, load_pool, load_protocol_tvl, notch  # noqa: E402

rng = np.random.default_rng(20261013)
pts = json.load(open(RAW / "llama_price_btc.json"))["coins"]["coingecko:bitcoin"]["prices"]
btc = pd.Series({pd.Timestamp(dt.datetime.fromtimestamp(p["timestamp"], dt.UTC).date()): p["price"] for p in pts})
btc = btc[~btc.index.duplicated(keep="last")].sort_index()
btc = btc.reindex(pd.date_range(btc.index.min(), btc.index.max(), freq="D")).ffill()
trail30 = 100 * (btc / btc.shift(30) - 1)


def win(d0, h):
    a, b = d0 - pd.Timedelta(days=1), d0 + pd.Timedelta(days=h)
    return 100 * (btc.get(b, np.nan) / btc.get(a, np.nan) - 1)


# ---------------------------------------------------------------- G1 conditions at each event
ev = pd.read_csv(PROC / "grade_events.csv", parse_dates=["date"])
tested = ev[ev.status == "tested"]
EXTRA = [("S&P cuts USDT to 5", "2025-11-26"), ("S&P rates Sky B-", "2025-08-08"), ("Moody's rates Sky B3", "2026-10-07"),
         ("Stream warning", "2025-10-28"), ("10 Oct 2025 crash (no warning)", "2025-10-10")]
g1 = [dict(event=f"Credora {r.vault} {r.from_grade}->{r.to_grade}", date=r.date.date(),
           btc_trailing_30d=trail30.get(r.date - pd.Timedelta(days=1)), btc_event_week=win(r.date, 7)) for _, r in tested.iterrows()]
g1 += [dict(event=e, date=pd.Timestamp(d).date(), btc_trailing_30d=trail30.get(pd.Timestamp(d) - pd.Timedelta(days=1)),
            btc_event_week=win(pd.Timestamp(d), 7)) for e, d in EXTRA]
g1 = pd.DataFrame(g1)
g1.to_csv(PROC / "regime_event_conditions.csv", index=False)

# ---------------------------------------------------------------- G2 regime-matched placebo (main spec: h=7, base -1, $10M, control)
grades = load_grades()


def daily(s):
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))


oc = pd.read_csv(RAW / "onchain_spark_tvl.csv", parse_dates=["day"])


def vault_tvl(addr, pool):
    s = load_pool(pool).tvl
    o = oc[oc.address == addr]
    return daily(s.combine_first(pd.Series(o.onchain_musd.values * 1e6, index=o.day)).sort_index())


CTRL = {"SPARK": vault_tvl(CONTROL_ADDRESS, CONTROLS["SPARK"][1]), "LISTA": daily(load_protocol_tvl("lista-lending"))}
flow = lambda s: 100 * (s.shift(-7) / s.shift(1) - 1)  # noqa: E731  day -1 -> day +7
evs, nulls = [], {}
for addr, (name, pool, conf, how, dollar) in POOLS.items():
    if not pool or addr == CONTROL_ADDRESS:
        continue
    gv = grades[grades.address == addr].reset_index(drop=True)
    ch = [(gv.date[i], gv.rating[i - 1], gv.rating[i]) for i in range(1, len(gv)) if gv.rating[i] != gv.rating[i - 1]]
    tvl = vault_tvl(addr, pool)
    f = flow(tvl) - flow(CTRL[gv.protocol.iloc[0]]).reindex(tvl.index)
    lvl = tvl.shift(1)
    near = {d + pd.Timedelta(days=k) for d, _, _ in ch for k in range(-10, 11)}
    days = [d for d in f.index if gv.date.min() <= d <= gv.date.max() and d not in near and lvl.get(d, 0) >= 10e6 and np.isfinite(f[d])]
    nulls[name] = pd.DataFrame({"x": [f[d] for d in days], "up": [trail30.get(d - pd.Timedelta(days=1), np.nan) > 0 for d in days]})
    for d, a, b in ch:
        if lvl.get(d, 0) >= 10e6 and np.isfinite(f.get(d, np.nan)) and notch(b) > notch(a):
            evs.append(dict(vault=name, date=d, x=f[d], up=trail30.get(d - pd.Timedelta(days=1)) > 0))
down = pd.DataFrame(evs)
down["pct_all_days"] = [100 * (nulls[v].x <= x).mean() for v, x in zip(down.vault, down.x)]
down["pct_same_regime"] = [100 * (nulls[v][nulls[v].up == u].x <= x).mean() for v, x, u in zip(down.vault, down.x, down.up)]
draws = np.column_stack([rng.choice(nulls[v][nulls[v].up == u].x.values, 5000) for v, u in zip(down.vault, down.up)]).mean(axis=1)
p_matched = (np.sum(draws <= down.x.mean()) + 1) / 5001
down.to_csv(PROC / "regime_matched_downgrades.csv", index=False)

# ---------------------------------------------------------------- G3 do flips cluster in falling markets?
rows = []
for addr, gv in grades.groupby("address"):
    gv = gv.sort_values("date").reset_index(drop=True)
    for i in range(1, len(gv)):
        if is_investment_grade(gv.rating[i - 1]):
            up = trail30.get(gv.date[i] - pd.Timedelta(days=1)) > 0
            rows.append(dict(up=up, years=(gv.date[i] - gv.date[i - 1]).days / 365.25,
                             cross=not is_investment_grade(gv.rating[i])))
g3 = pd.DataFrame(rows).groupby("up").agg(crossings=("cross", "sum"), vault_years=("years", "sum")).reset_index()
g3["prob_within_1y_pct"] = 100 * (1 - np.exp(-g3.crossings / g3.vault_years))
g3["regime"] = np.where(g3.up, "Bitcoin up over prior 30 days", "Bitcoin down over prior 30 days")
g3.to_csv(PROC / "regime_flip_rate.csv", index=False)
cw = (btc.get(pd.Timestamp("2026-10-12")) / btc.get(pd.Timestamp("2026-02-03")) - 1) * 100
seg = btc.loc["2026-02-03":"2026-10-12"]
mdd = 100 * (seg / seg.cummax() - 1).min()

# ---------------------------------------------------------------- G4 crash week vs warning week
xd = json.load(open(RAW / "xusd_arb_daily.json"))["data"]["marketById"]["historicalState"]["supplyAssetsUsd"]
xusd = daily(pd.Series({pd.Timestamp(dt.datetime.fromtimestamp(p["x"], dt.UTC).date()): p["y"] for p in xd}).sort_index())
g4 = []
for name, s in (("Morpho xUSD market", xusd), ("Stream Finance", daily(load_protocol_tvl("stream-finance"))),
                ("Elixir", daily(load_protocol_tvl("elixir")))):
    ch6 = lambda d: 100 * (s.get(pd.Timestamp(d) + pd.Timedelta(days=6)) / s.get(pd.Timestamp(d)) - 1)  # noqa: E731
    g4.append(dict(series=name, crash_week_10oct=ch6("2025-10-10"), warning_week_28oct=ch6("2025-10-28")))
g4 = pd.DataFrame(g4)
g4.to_csv(PROC / "regime_crash_vs_warning.csv", index=False)

# ---------------------------------------------------------------- G5 bond spreads: 2026 window vs the 3 years FRED serves
g5 = []
for lab, sid in (("BBB", "BAMLC0A4CBBB"), ("BB", "BAMLH0A1HYBB"), ("B", "BAMLH0A2HYB")):
    s = load_fred(sid)
    w = s.loc["2026-02-01":"2026-10-13"]
    g5.append(dict(rating=lab, window_mean=w.mean(), three_year_mean=s.mean(), three_year_max=s.max(),
                   window_percentile_vs_3y=100 * (s <= w.mean()).mean(), first=s.index.min().date()))
g5 = pd.DataFrame(g5)
g5.to_csv(PROC / "regime_bond_levels.csv", index=False)

pd.set_option("display.width", 200)
print("G1 conditions at each event (Bitcoin, %)")
print(g1.round(1).to_string(index=False))
print(f"\nG2 downgrades re-ranked only against same-regime days: mean percentile {down.pct_same_regime.mean():.0f} "
      f"(all days {down.pct_all_days.mean():.0f}); permutation p = {p_matched:.2f}; "
      f"{int(down.up.sum())} of {len(down)} downgrades came in rising markets")
print(f"\nG3 flip rate by regime (Credora window: Bitcoin {cw:+.0f}%, worst drawdown {mdd:.0f}%)")
print(g3[["regime", "crossings", "vault_years", "prob_within_1y_pct"]].round(2).to_string(index=False))
print("\nG4 six-day change: 10 Oct 2025 crash week (no warning) vs Stream warning week")
print(g4.round(1).to_string(index=False))
print("\nG5 bond spreads in our window vs the last 3 years")
print(g5.round(2).to_string(index=False))
