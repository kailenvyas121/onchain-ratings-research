"""Systematic version of the VaR test: for every stablecoin break in the primary list (below $0.95 for 3+ days,
>= $10mn supply), 1-day 99% historical VaR from the 90 days ending 7 days before the first day below $0.95,
vs the drop to the lowest price within 30 days after. Removes the cherry-picking critique of the 3-coin chart."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; RAW = ROOT / "data/raw/v2"; PROC = ROOT / "data/processed"
# Same break rule as the robustness grid's primary spec: first day the coin has been below $0.95 for 3+ days
# with >= $10mn supply 3 days earlier.
rows = []
for f in sorted((RAW / "stable_prices").glob("*.json")):
    m = json.loads(f.read_text()); sf = RAW / "stable_supply" / f.name
    if not m["prices"] or not sf.exists(): continue
    p = pd.DataFrame(m["prices"]); p["d"] = pd.to_datetime(p.timestamp, unit="s").dt.normalize(); s = p.groupby("d").price.last()
    sp = pd.DataFrame(json.loads(sf.read_text()), columns=["t", "supply"]); sp["d"] = pd.to_datetime(sp.t, unit="s").dt.normalize()
    df = pd.concat([s, sp.groupby("d").supply.last()], axis=1, sort=True); df["supply"] = df.supply.ffill(); df = df.dropna(subset=["price"])
    if not (df.supply >= 10e6).any(): continue
    below = df.price < 0.95; run = below.groupby((~below).cumsum()).cumsum()
    hit = df.index[(run >= 3) & (df.supply.shift(3) >= 10e6)]
    if not len(hit): continue
    b = hit[0] - pd.Timedelta(days=2)                     # first of the 3 days below $0.95
    s = df.price
    mech = (m["mech"] or "").replace("crytpo", "crypto")
    pre = s[(s.index < b - pd.Timedelta(days=7)) & (s.index >= b - pd.Timedelta(days=97))]
    ret = pre.pct_change().dropna()
    if len(ret) < 30: rows.append(dict(coin=m["name"], mech=mech, first_below=b.date(), obs=len(ret))); continue
    post = s[(s.index >= b - pd.Timedelta(days=7)) & (s.index <= b + pd.Timedelta(days=30))]
    v1 = -np.percentile(ret, 1) * 100
    rows.append(dict(coin=m["name"], mech=mech, first_below=b.date(), obs=len(ret), var99=v1, var99_30d=v1 * np.sqrt(30),
                     loss=(1 - post.min() / pre.iloc[-1]) * 100))
d = pd.DataFrame(rows); d.to_csv(PROC / "v2_var_all_breaks.csv", index=False)
ok = d.dropna(subset=["var99"])
print(ok.round(2).to_string(index=False))
print(f"\nbreaks with 30+ days of prior history: {len(ok)} of {len(d)}")
print(f"median VaR {ok.var99.median():.2f}% | 30-day scaled {ok.var99_30d.median():.2f}% | median loss {ok.loss.median():.1f}%"
      f" | loss > 30-day VaR in {(ok.loss > ok.var99_30d).sum()} of {len(ok)} | loss > 10x 1-day VaR in {(ok.loss > 10 * ok.var99).sum()}")
