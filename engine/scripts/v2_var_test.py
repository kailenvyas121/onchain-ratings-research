"""VaR before three stablecoin collapses vs the loss that followed. VaR from daily prices in the window ending
7 days before the collapse date (no look-ahead). Loss = drop from the last pre-window price to the trough within
30 days of the collapse date, and to the price 30 days after. Cross-check: CoinGecko daily prices (USR, xUSD)."""
import glob, json
import numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; RAW = ROOT / "data/raw/v2"
EVENTS = {"resolv-usr": ("Resolv USR", "2026-03-22"), "elixir-deusd": ("Elixir deUSD", "2025-11-05"),
          "staked-stream-usd": ("Stream xUSD", "2025-11-03")}
def llama(c):
    p = []
    for f in glob.glob(str(RAW / f"var_{c}_*.json")):
        p += next(iter(json.load(open(f)).get("coins", {}).values()), {}).get("prices", [])
    s = pd.DataFrame(p).drop_duplicates("timestamp"); s["d"] = pd.to_datetime(s.timestamp, unit="s").dt.normalize()
    return s.groupby("d").price.last()
def gecko(c):
    f = RAW / f"cg_{c}.json"
    if not f.exists(): return None
    d = json.load(open(f)).get("prices")
    if not d: return None
    s = pd.DataFrame(d, columns=["t", "price"]); s["d"] = pd.to_datetime(s.t, unit="ms").dt.normalize()
    return s.groupby("d").price.last()
rows = []
for c, (name, e) in EVENTS.items():
    e = pd.Timestamp(e)
    for src, s in (("DefiLlama", llama(c)), ("CoinGecko", gecko(c))):
        if s is None: continue
        for win in (30, 60, 90, 180):
            pre = s[(s.index < e - pd.Timedelta(days=7)) & (s.index >= e - pd.Timedelta(days=7 + win))]
            r = pre.pct_change().dropna()
            if len(r) < 20: continue
            post = s[(s.index >= e - pd.Timedelta(days=7)) & (s.index <= e + pd.Timedelta(days=30))]
            p0 = pre.iloc[-1]
            rows.append(dict(coin=name, source=src, window_days=win, obs=len(r),
                             var99_1d=-np.percentile(r, 1) * 100, var99_10d=-np.percentile(r, 1) * 100 * np.sqrt(10),
                             param_var99_1d=2.326 * r.std() * 100, worst_day_pre=-r.min() * 100,
                             loss_trough=(1 - post.min() / p0) * 100, loss_30d=(1 - s[s.index <= e + pd.Timedelta(days=30)].iloc[-1] / p0) * 100))
df = pd.DataFrame(rows).round(2)
df.to_csv(ROOT / "data/processed/v2_var_test.csv", index=False)
print(df.to_string(index=False))
