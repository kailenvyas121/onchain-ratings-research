"""
Test 2 -- does a grade change move money? Event study with a placebo null.

Event = a Credora letter change, dated to the report that published it (day 0).
Abnormal flow(h) = vault deposit change from day -1 to day +h, minus the control's change over the same days.
  Control: Spark Savings USDC (grade never changed) for Spark; Lista Lending protocol total for Lista.
Placebo null: the same statistic on every non-event day for the same vault (days within 10 of any grade
  change excluded). The event's percentile in that distribution is its p-value-like rank.
Flags: crosses the investment-grade line (A <-> A- or below); rate changed within 3 days (confound).
Vaults with < $10M deposits on day -1 are excluded (noise).

Writes data/processed/grade_events.csv and data/processed/placebo_null.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import CONTROL_ADDRESS, CONTROLS, POOLS, PROC, RAW, is_investment_grade, load_grades, load_pool, load_protocol_tvl, notch  # noqa: E402

HORIZONS = (3, 7, 14)
MIN_TVL = 10e6
EXCLUDE = 10  # days around any grade change removed from the placebo pool

grades = load_grades()

# Days DefiLlama is missing (e.g. 20-26 Jul 2026) are filled from the Spark vault contracts (totalAssets at 23:00 UTC,
# scripts/check_onchain_tvl.py). DefiLlama is used wherever it has the day; the two agree within 0.1% where both exist.
_oc = RAW / "onchain_spark_tvl.csv"
ONCHAIN = pd.read_csv(_oc, parse_dates=["day"]) if _oc.exists() else pd.DataFrame(columns=["address", "day", "onchain_musd"])


def with_onchain(tvl: pd.Series, addr: str) -> pd.Series:
    o = ONCHAIN[ONCHAIN.address == addr]
    return tvl.combine_first(pd.Series(o.onchain_musd.values * 1e6, index=o.day)).sort_index()


def control_series(proto: str) -> pd.Series:
    kind, ref = CONTROLS[proto]
    return with_onchain(load_pool(ref).tvl, CONTROL_ADDRESS) if kind == "pool" else load_protocol_tvl(ref)


def pct(s: pd.Series, d0: pd.Timestamp, h: int):
    a, b = d0 - pd.Timedelta(days=1), d0 + pd.Timedelta(days=h)
    if a not in s.index or b not in s.index or s[a] <= 0:
        return None
    return 100 * (s[b] / s[a] - 1)


events, placebo = [], []
for addr, (vault, pool, conf, how, dollar) in POOLS.items():
    gv = grades[grades.address == addr].reset_index(drop=True)
    proto = gv.protocol.iloc[0]
    changes = [(gv.date[i], gv.rating[i - 1], gv.rating[i]) for i in range(1, len(gv)) if gv.rating[i] != gv.rating[i - 1]]
    if not pool:
        for d, a, b in changes:
            events.append(dict(protocol=proto, vault=vault, date=d, from_grade=a, to_grade=b,
                               direction="downgrade" if notch(b) > notch(a) else "upgrade",
                               crosses_ig_line=is_investment_grade(a) != is_investment_grade(b),
                               status="not tested (vault-to-pool mapping unresolved)"))
        continue
    p = load_pool(pool)
    llama_days = set(p.index)
    p = p.reindex(p.index.union(ONCHAIN[ONCHAIN.address == addr].day))
    p["tvl"] = with_onchain(p.tvl.dropna(), addr)
    ctl = control_series(proto)
    is_control = addr == CONTROL_ADDRESS
    for d, a, b in changes:
        row = dict(protocol=proto, vault=vault, date=d, from_grade=a, to_grade=b, mapping=conf, rate_set_by=how,
                   direction="downgrade" if notch(b) > notch(a) else "upgrade",
                   crosses_ig_line=is_investment_grade(a) != is_investment_grade(b),
                   tvl_day_minus1_musd=p.tvl.get(d - pd.Timedelta(days=1), np.nan) / 1e6)
        win = p.apy.loc[d - pd.Timedelta(days=3): d + pd.Timedelta(days=3)].dropna()
        row["rate_change_within_3d"] = bool(len(win) and (win.max() - win.min()) > 0.1)
        if pd.isna(row["tvl_day_minus1_musd"]):
            row["status"] = "not tested (no deposit data on day -1)"
            events.append(row)
            continue
        if row["tvl_day_minus1_musd"] < MIN_TVL / 1e6:
            row["status"] = "not tested (< $10M deposits)"
            events.append(row)
            continue
        row["status"] = "tested"
        days = [d + pd.Timedelta(days=k) for k in (-1, *HORIZONS)]
        row["onchain_fill"] = any(x not in llama_days for x in days if x in p.index)
        for h in HORIZONS:
            v, c = pct(p.tvl, d, h), pct(ctl, d, h)
            row[f"flow_{h}d"] = v
            row[f"abnormal_{h}d"] = None if v is None or c is None or is_control else v - c
        events.append(row)
    # placebo pool for this vault
    near = set()
    for d, _, _ in changes:
        near |= {d + pd.Timedelta(days=k) for k in range(-EXCLUDE, EXCLUDE + 1)}
    if is_control:
        continue
    for d0 in p.index[(p.index >= grades.date.min()) & (p.index <= grades.date.max())]:
        if d0 in near or p.tvl.get(d0 - pd.Timedelta(days=1), 0) < MIN_TVL:
            continue
        r = dict(protocol=proto, vault=vault, date=d0)
        for h in HORIZONS:
            v, c = pct(p.tvl, d0, h), pct(ctl, d0, h)
            r[f"abnormal_{h}d"] = None if v is None or c is None else v - c
        placebo.append(r)

ev, pl = pd.DataFrame(events), pd.DataFrame(placebo)
for h in HORIZONS:
    col = f"abnormal_{h}d"
    ev[f"percentile_{h}d"] = [
        np.nan if pd.isna(x) or pl.empty else 100 * (pl[(pl.vault == vv)][col].dropna() <= x).mean()
        for x, vv in zip(ev.get(col, pd.Series(np.nan, index=ev.index)), ev.vault)]
ev.to_csv(PROC / "grade_events.csv", index=False)
pl.to_csv(PROC / "placebo_null.csv", index=False)

t = ev[ev.status == "tested"]
print(f"{len(ev)} grade changes, {int(ev.crosses_ig_line.sum())} cross the investment-grade line, {len(t)} testable")
print(t[["vault", "date", "from_grade", "to_grade", "abnormal_7d", "percentile_7d", "rate_change_within_3d"]]
      .to_string(index=False, float_format=lambda v: f"{v:.1f}"))
ig = t[t.crosses_ig_line & t.abnormal_7d.notna()]
for direction in ("downgrade", "upgrade"):
    x = ig[ig.direction == direction].abnormal_7d
    if len(x):
        print(f"IG-line {direction}s: n={len(x)}, mean abnormal 7d flow {x.mean():+.1f}%")
