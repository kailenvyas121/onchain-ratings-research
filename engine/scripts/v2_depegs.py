"""How often USD stablecoins break. A depeg = daily price below $0.97 on 2+ consecutive days while the coin had
>= $10mn in circulation. Coin-years count each calendar year a coin had >= $10mn supply on any day."""
import json
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]; RAW = ROOT / "data/raw/v2"; OUT = ROOT / "data/processed"
MIN_SUPPLY, TH, RUN = 10e6, 0.97, 2
rows, events = [], []
for f in sorted((RAW / "stable_prices").glob("*.json")):
    m = json.loads(f.read_text()); sf = RAW / "stable_supply" / f.name
    if not m["prices"] or not sf.exists(): continue
    p = pd.DataFrame(m["prices"]); p["d"] = pd.to_datetime(p.timestamp, unit="s").dt.normalize()
    p = p.groupby("d").price.last()
    s = pd.DataFrame(json.loads(sf.read_text()), columns=["t", "supply"]); s["d"] = pd.to_datetime(s.t, unit="s").dt.normalize()
    s = s.groupby("d").supply.last()
    df = pd.concat([p, s], axis=1, sort=True); df["supply"] = df.supply.ffill(); df = df.dropna(subset=["price"])
    big = df.supply >= MIN_SUPPLY
    if not big.any(): continue
    mech = (m["mech"] or "").replace("crytpo", "crypto")
    below = (df.price < TH)
    run = below.groupby((~below).cumsum()).cumsum()            # consecutive days below
    start = (run == RUN)                                         # second consecutive day = event confirmed
    prev_supply = df.supply.shift(RUN)                           # supply before the run began
    ev = df[start & (prev_supply >= MIN_SUPPLY)]
    # one event per 90 days per coin
    last = None
    for d, r in ev.iterrows():
        if last is None or (d - last).days > 90:
            after = df.loc[d:d + pd.Timedelta(days=180), "price"]
            events.append(dict(coin=m["name"], symbol=m["symbol"], mech=mech, date=d.date(), supply_mn=round(prev_supply[d] / 1e6, 1),
                               low_180d=round(after.min(), 4), back_above_099=bool((after > 0.99).any()), price_now=round(df.price.iloc[-1], 4)))
            last = d
    yrs = sorted(set(df.index[big].year))
    for y in yrs:
        rows.append(dict(coin=m["name"], mech=mech, year=y))
cy = pd.DataFrame(rows); ev = pd.DataFrame(events)
ev["year"] = pd.to_datetime(ev.date).dt.year
OUT.joinpath("v2_depeg_events.csv").write_text(ev.to_csv(index=False))
summ = cy.groupby("mech").agg(coins=("coin", "nunique"), coin_years=("coin", "size"))
summ["events"] = ev.groupby("mech").size(); summ["coins_ever_depegged"] = ev.groupby("mech").coin.nunique()
summ = summ.fillna(0); summ["events_per_100_coin_years"] = (summ.events / summ.coin_years * 100).round(1)
summ["share_coins_ever_depegged_pct"] = (summ.coins_ever_depegged / summ.coins * 100).round(1)
tot = summ[["coins", "coin_years", "events", "coins_ever_depegged"]].sum()
print(summ); print("ALL", dict(tot), "per100cy", round(tot.events / tot.coin_years * 100, 1), "share ever", round(tot.coins_ever_depegged / tot.coins * 100, 1))
OUT.joinpath("v2_depeg_summary.csv").write_text(summ.to_csv())
print(ev.sort_values("supply_mn", ascending=False).head(25).to_string())
print("never back above 0.99 within 180d:", (~ev.back_above_099).sum(), "of", len(ev))

# ---- robustness grid: share of coins that ever broke, by design, across thresholds / run lengths / size floors
series = {}
for f in sorted((RAW / "stable_prices").glob("*.json")):
    m = json.loads(f.read_text()); sf = RAW / "stable_supply" / f.name
    if not m["prices"] or not sf.exists(): continue
    p = pd.DataFrame(m["prices"]); p["d"] = pd.to_datetime(p.timestamp, unit="s").dt.normalize(); p = p.groupby("d").price.last()
    s = pd.DataFrame(json.loads(sf.read_text()), columns=["t", "supply"]); s["d"] = pd.to_datetime(s.t, unit="s").dt.normalize()
    s = s.groupby("d").supply.last()
    df = pd.concat([p, s], axis=1, sort=True); df["supply"] = df.supply.ffill(); df = df.dropna(subset=["price"])
    series[m["name"]] = ((m["mech"] or "").replace("crytpo", "crypto"), df)
grid = []
for th in (0.97, 0.95, 0.90):
    for run in (2, 3, 7):
        for ms in (10e6, 50e6):
            for name, (mech, df) in series.items():
                if not (df.supply >= ms).any(): continue
                b = df.price < th; r = b.groupby((~b).cumsum()).cumsum()
                grid.append(dict(th=th, run=run, min_supply_mn=int(ms / 1e6), coin=name, mech=mech,
                                 broke=bool(((r >= run) & (df.supply.shift(run) >= ms)).any())))
g = pd.DataFrame(grid)
out = g.groupby(["th", "run", "min_supply_mn", "mech"]).broke.agg(["sum", "size"]).reset_index()
out["pct"] = out["sum"] / out["size"] * 100
OUT.joinpath("v2_depeg_grid.csv").write_text(out.to_csv(index=False))
print(out.groupby("mech").pct.agg(["min", "max"]).round(1))
