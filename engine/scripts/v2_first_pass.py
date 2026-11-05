"""First-pass numbers for the new outline (14 Oct 2026). Hacks by year, DeFi hack losses as % of DeFi TVL,
recovery coverage, and 1-day 99% VaR before three stablecoin collapses vs the loss that followed."""
import glob, json
import numpy as np, pandas as pd
from pathlib import Path
RAW = Path(__file__).resolve().parents[1] / "data/raw/v2"
h = pd.DataFrame(json.load(open(sorted(RAW.glob("hacks_*.json"))[-1]))); h["yr"] = pd.to_datetime(h.date, unit="s").dt.year
t = pd.DataFrame(json.load(open(sorted(RAW.glob("defi_tvl_*.json"))[-1]))); t["yr"] = pd.to_datetime(t.date.astype(int), unit="s").dt.year
print("all hacks", len(h), "| since 2020:", (h.yr >= 2020).sum(), f"${h[h.yr >= 2020].amount.sum()/1e9:.2f}bn")
print(h[h.yr >= 2020].groupby("yr").amount.agg(["size", "sum"]).assign(sum=lambda d: (d["sum"] / 1e9).round(2)))
d = h[(h.targetType == "DeFi Protocol") & (h.yr >= 2020)]
g = d.groupby("yr").amount.agg(n="size", lost_bn=lambda x: x.sum() / 1e9)
g["avg_tvl_bn"] = t.groupby("yr").tvl.mean() / 1e9; g["loss_pct_tvl"] = g.lost_bn / g.avg_tvl_bn * 100
print(g.round(3)); print("median DeFi hack $mn", round(d.amount.median() / 1e6, 2))
print("events with returnedFunds recorded:", h.returnedFunds.notna().sum(), "of", len(h))
EVENTS = {"resolv-usr": "2026-03-22", "staked-stream-usd": "2025-11-03", "elixir-deusd": "2025-11-05"}
for c, e in EVENTS.items():
    p = []
    for f in glob.glob(str(RAW / f"var_{c}_*.json")):
        p += next(iter(json.load(open(f)).get("coins", {}).values()), {}).get("prices", [])
    s = pd.DataFrame(p).drop_duplicates("timestamp"); s["d"] = pd.to_datetime(s.timestamp, unit="s").dt.normalize()
    s = s.groupby("d").price.last(); e = pd.Timestamp(e)
    pre = s[(s.index < e - pd.Timedelta(days=7)) & (s.index >= e - pd.Timedelta(days=97))]
    var99 = -np.percentile(pre.pct_change().dropna(), 1) * 100
    post = s[(s.index >= e - pd.Timedelta(days=7)) & (s.index <= e + pd.Timedelta(days=30))]
    print(f"{c}: VaR99 1d {var99:.2f}% ({len(pre)-1} days of history) | loss within 30 days {(1 - post.min()/pre.iloc[-1])*100:.1f}%")
