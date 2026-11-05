"""
Robustness suite: is the "grades don't move money" result an artefact of our choices?

Offline. Re-implements the event test with every analysis choice exposed as a parameter, then runs:

  R1 Specification curve. Every combination of: horizon (3, 7, 14, 30 days), start of window (day -1, -3, -7:
     Credora's API can update up to 24h before the PDF we date by), minimum deposits ($1M, $5M, $10M, $25M),
     control (same-platform control, or none), placebo exclusion (5, 10, 20 days). 288 specs.
     Per spec: mean abnormal flow of the downgrades, and a permutation p-value (one-sided, outflow).
  R2 Calibration. Fake "downgrades" drawn from ordinary days, run through the same test: how often p < 0.05?
     A fair test says ~5%.
  R3 Power. Inject a known outflow (1-20%) into ordinary days and ask how often the test catches it.
     Gives the smallest effect we could have seen. A null result only counts above that size.
  R4 Leave-one-out. Drop each downgrade in turn.
  R5 Pre-trend. Flow from day -8 to day -1 (before the report): did money move first, or did the grade follow money?
  R6 Positive control. The same placebo rank applied to the Stream warning (28 Oct 2025), for the Morpho
     xUSD market, Stream and Elixir: the test must be able to flag a real run.
  R7 Yield test. Split sample (Feb-Jun vs Jul-Oct), the grade read one notch more generously, and medians.
  R8 Investment-grade share. Count-, vault- and deposit-weighted; first vs second half.

Writes data/processed/robustness_*.csv and prints a summary.
"""
import datetime as dt
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import (BOND_BUCKET, CONTROL_ADDRESS, CONTROLS, ORDER, POOLS, PROC, RAW, SCALE, asof,  # noqa: E402
                        is_investment_grade, load_fred, load_grades, load_pool, load_protocol_tvl, notch)

rng = np.random.default_rng(20261013)  # fixed seed: rerun gives identical numbers
N_PERM = 5000
grades = load_grades()
oc = pd.read_csv(RAW / "onchain_spark_tvl.csv", parse_dates=["day"]) if (RAW / "onchain_spark_tvl.csv").exists() else None


def daily(s: pd.Series) -> pd.Series:
    """Calendar-daily index; missing days stay NaN (never interpolated)."""
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))


def vault_tvl(addr, pool):
    s = load_pool(pool).tvl
    if oc is not None and (o := oc[oc.address == addr]).size:
        s = s.combine_first(pd.Series(o.onchain_musd.values * 1e6, index=o.day))
    return daily(s.sort_index())


CTRL = {"SPARK": vault_tvl(CONTROL_ADDRESS, CONTROLS["SPARK"][1]), "LISTA": daily(load_protocol_tvl(CONTROLS["LISTA"][1]))}
VAULTS = {}
for addr, (name, pool, conf, how, dollar) in POOLS.items():
    if not pool or addr == CONTROL_ADDRESS:
        continue
    gv = grades[grades.address == addr].reset_index(drop=True)
    ch = [(gv.date[i], gv.rating[i - 1], gv.rating[i]) for i in range(1, len(gv)) if gv.rating[i] != gv.rating[i - 1]]
    VAULTS[name] = dict(tvl=vault_tvl(addr, pool), proto=gv.protocol.iloc[0], changes=ch,
                        start=gv.date.min(), end=gv.date.max())


def flows(s, base, h):
    """% change from day `base` to day +h, indexed by day 0."""
    return 100 * (s.shift(-h) / s.shift(-base) - 1)


def run_spec(h=7, base=-1, min_tvl=10e6, control=True, excl=10):
    """Returns event rows and per-vault placebo arrays for one specification."""
    ev, null = [], {}
    for name, v in VAULTS.items():
        f = flows(v["tvl"], base, h)
        if control:
            f = f - flows(CTRL[v["proto"]], base, h).reindex(f.index)
        lvl = v["tvl"].shift(-base)  # deposits on the window's first day
        near = {d + pd.Timedelta(days=k) for d, _, _ in v["changes"] for k in range(-excl, excl + 1)}
        days = f.index[(f.index >= v["start"]) & (f.index <= v["end"])]
        null[name] = np.array([f[d] for d in days if d not in near and lvl.get(d, 0) >= min_tvl and np.isfinite(f[d])])
        for d, a, b in v["changes"]:
            x = f.get(d, np.nan)
            if lvl.get(d, 0) >= min_tvl and np.isfinite(x):
                ev.append(dict(vault=name, date=d, from_grade=a, to_grade=b, abnormal=x,
                               down=notch(b) > notch(a), cross=is_investment_grade(a) != is_investment_grade(b)))
    return pd.DataFrame(ev), null


def perm_p(events, null, n=N_PERM):
    """One-sided p: share of random same-vault draws whose mean is as low as the events' mean."""
    if events.empty or any(len(null[v]) < 20 for v in events.vault):
        return np.nan
    obs = events.abnormal.mean()
    draws = np.column_stack([rng.choice(null[v], n) for v in events.vault]).mean(axis=1)
    return (np.sum(draws <= obs) + 1) / (n + 1)


# ---------------------------------------------------------------- R1 specification curve
rows = []
for h, base, mt, ctl, ex in itertools.product((3, 7, 14, 30), (-1, -3, -7), (1e6, 5e6, 10e6, 25e6), (True, False), (5, 10, 20)):
    ev, null = run_spec(h, base, mt, ctl, ex)
    for grp, sel in (("all downgrades", ev.down if len(ev) else []), ("IG-line downgrades", (ev.down & ev.cross) if len(ev) else [])):
        e = ev[sel] if len(ev) else ev
        rows.append(dict(h=h, base=base, min_tvl_m=mt / 1e6, control=ctl, excl=ex, group=grp, n=len(e),
                         mean_abnormal=e.abnormal.mean() if len(e) else np.nan, p=perm_p(e, null)))
spec = pd.DataFrame(rows)
spec.to_csv(PROC / "robustness_spec_curve.csv", index=False)

# ---------------------------------------------------------------- main spec (the one in the article)
ev, null = run_spec()
down = ev[ev.down].reset_index(drop=True)

# ---------------------------------------------------------------- R2 calibration and R3 power (same vault mix as real downgrades)
null_means = np.column_stack([rng.choice(null[v], N_PERM) for v in down.vault]).mean(axis=1)


def p_of(mean):
    return (np.sum(null_means <= mean) + 1) / (N_PERM + 1)


sims = 2000
fake = np.column_stack([rng.choice(null[v], sims) for v in down.vault])
calib = np.mean([p_of(m) < 0.05 for m in fake.mean(axis=1)])
power = []
for shock in (1, 2, 3, 5, 10, 20):
    power.append(dict(injected_outflow_pct=shock, detection_rate=np.mean([p_of(m) < 0.05 for m in fake.mean(axis=1) - shock])))
power = pd.DataFrame(power)
power.to_csv(PROC / "robustness_power.csv", index=False)
single = pd.DataFrame([dict(vault=v, n_null_days=len(a), p5=np.percentile(a, 5), p50=np.percentile(a, 50), p95=np.percentile(a, 95))
                       for v, a in null.items() if len(a)])

# ---------------------------------------------------------------- R4 leave-one-out
loo = pd.DataFrame([dict(dropped=f"{r.vault} {r.date:%d %b}", mean_abnormal=down.drop(i).abnormal.mean(), p=perm_p(down.drop(i), null))
                    for i, r in down.iterrows()])

# ---------------------------------------------------------------- R5 pre-trend (day -8 to day -1, before any report)
pre_ev, pre_null = run_spec(h=-1, base=-8)
pre_down = pre_ev[pre_ev.down]
pre_p_out = perm_p(pre_down, pre_null)
pre_p_in = 1 - perm_p(pre_down, pre_null) if not np.isnan(pre_p_out) else np.nan

# ---------------------------------------------------------------- R6 positive control: Stream warning, 28 Oct 2025
WARN = pd.Timestamp("2025-10-28")
xd = json.load(open(RAW / "xusd_arb_daily.json"))["data"]["marketById"]["historicalState"]["supplyAssetsUsd"]
xusd = daily(pd.Series({pd.Timestamp(dt.datetime.fromtimestamp(p["x"], dt.UTC).date()): p["y"] for p in xd}).sort_index())
pos = []
for name, s, first in (("Morpho xUSD market (curated-vault lenders)", xusd, pd.Timestamp("2025-09-22")),
                       ("Stream Finance deposits", daily(load_protocol_tvl("stream-finance")), pd.Timestamp("2024-01-01")),
                       ("Elixir deposits", daily(load_protocol_tvl("elixir")), pd.Timestamp("2024-01-01"))):
    f = flows(s, 0, 6)  # 28 Oct 00:00 -> 3 Nov 00:00, the window used in the article (withdrawals halted 4 Nov)
    hist = f.loc[first:WARN - pd.Timedelta(days=7)].dropna()  # only days fully before the warning
    pos.append(dict(series=name, flow_6d_pct=f[WARN], null_days=len(hist), null_p1=np.percentile(hist, 1),
                    percentile=100 * (hist <= f[WARN]).mean(), worst_prior_6d=hist.min()))
pos = pd.DataFrame(pos)
pos.to_csv(PROC / "robustness_positive_control.csv", index=False)

# ---------------------------------------------------------------- R7 yield test robustness
tbill = load_fred("DTB3")
SERIES = {"AAA": "BAMLC0A1CAAA", "AA": "BAMLC0A2CAA", "A": "BAMLC0A3CA", "BBB": "BAMLC0A4CBBB", "BB": "BAMLH0A1HYBB",
          "B": "BAMLH0A2HYB", "CCC": "BAMLH0A3HYC"}
bond = {k: load_fred(v) for k, v in SERIES.items()}
LADDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]
yrows = []
for addr, (name, pool, conf, how, dollar) in POOLS.items():
    if not pool or not dollar:
        continue
    p = load_pool(pool).loc["2026-02-01":"2026-10-13"].dropna(subset=["apy"])
    p = p[p.tvl >= 10e6]
    if len(p) < 30:
        continue
    gv = grades[grades.address == addr]
    live = pd.Series(gv.rating.values, index=gv.date).reindex(p.index.union(gv.date)).ffill().reindex(p.index)
    for d, g in live.dropna().items():
        t = asof(tbill, d)
        if t is None:
            continue
        b0 = BOND_BUCKET[g]
        b1 = LADDER[max(0, LADDER.index(b0) - 1)]  # one bucket more generous to Credora
        m0, m1 = asof(bond[b0], d), asof(bond[b1], d)
        yrows.append(dict(vault=name, rate_set_by=how, day=d, spread=p.apy[d] - t, gap=p.apy[d] - t - m0, gap_generous=p.apy[d] - t - m1))
yd = pd.DataFrame(yrows)
yd["half"] = np.where(yd.day < pd.Timestamp("2026-07-01"), "Feb-Jun", "Jul-Oct")
yr = yd.groupby(["vault", "rate_set_by"]).agg(gap_mean=("gap", "mean"), gap_median=("gap", "median"),
                                             gap_generous=("gap_generous", "mean"), days=("gap", "size"),
                                             share_days_below_bond=("gap", lambda s: (s < 0).mean())).reset_index()
yr = yr.merge(yd.pivot_table(index="vault", columns="half", values="gap", aggfunc="mean").reset_index(), on="vault", how="left")
yr.to_csv(PROC / "robustness_yield.csv", index=False)

# ---------------------------------------------------------------- R8 investment-grade share, several weightings
g = grades.copy()
tvl_on = []
for _, r in g.iterrows():
    pool = POOLS.get(r.address, (None, None))[1]
    tvl_on.append(load_pool(pool).tvl.get(r.date, np.nan) if pool else np.nan)
g["tvl"] = tvl_on
mid = g.date.min() + (g.date.max() - g.date.min()) / 2
ig = dict(count_weighted=g.investment_grade.mean(),
          vault_weighted=g.groupby("address").investment_grade.mean().mean(),
          deposit_weighted=(g.investment_grade * g.tvl).sum() / g.tvl[g.tvl.notna()].sum(),
          deposit_weighted_coverage=g.tvl.notna().mean(),
          first_half=g[g.date <= mid].investment_grade.mean(), second_half=g[g.date > mid].investment_grade.mean())

pd.DataFrame([dict(calibration_false_positive_pct=100 * calib, pretrend_mean_pct=pre_down.abnormal.mean(), pretrend_p=pre_p_out,
                   main_n_down=len(down), main_mean=down.abnormal.mean(), main_p=perm_p(down, null),
                   specs_with_data=int(spec.dropna(subset=["p"]).groupby("group").size().min()),
                   specs_significant=int((spec.p < 0.05).sum()))]).to_csv(PROC / "robustness_summary.csv", index=False)

# ---------------------------------------------------------------- summary
pd.set_option("display.width", 200)
print("R1 specification curve (288 specs per group)")
for grp, s in spec.groupby("group"):
    s = s.dropna(subset=["p"])
    print(f"   {grp:20} specs with data {len(s):3}; mean abnormal flow median {s.mean_abnormal.median():+.1f}% "
          f"[range {s.mean_abnormal.min():+.1f} to {s.mean_abnormal.max():+.1f}]; p < 0.05 in {(s.p < .05).sum()} specs "
          f"({100 * (s.p < .05).mean():.0f}%); p < 0.10 in {(s.p < .10).sum()}")
print(f"\nMain spec: {len(down)} downgrades, mean abnormal 7d {down.abnormal.mean():+.2f}%, p = {perm_p(down, null):.2f}")
print(f"R2 calibration: fake downgrades flagged at p < 0.05 in {100 * calib:.1f}% of {sims} runs (fair test ~5%)")
print("R3 power: chance the test catches an injected outflow of this size (same 7 vaults/days mix)")
print(power.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
print("   single-event yardstick, 7d abnormal flow on ordinary days (5th / 50th / 95th pct):")
print(single.to_string(index=False, float_format=lambda v: f"{v:.1f}"))
print("R4 leave-one-out (downgrades):")
print(loo.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
print(f"R5 pre-trend, day -8 to -1: mean {pre_down.abnormal.mean():+.2f}% (n={len(pre_down)}), p(outflow first) = {pre_p_out:.2f}")
print("R6 positive control (Stream warning, 28 Oct -> 3 Nov 2025):")
print(pos.to_string(index=False, float_format=lambda v: f"{v:.1f}"))
print("R7 yield gap vs same-grade bond (pts):")
print(yr.round(2).to_string(index=False))
print("R8 investment-grade share:", {k: round(100 * v, 1) for k, v in ig.items()})
