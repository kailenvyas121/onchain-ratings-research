"""
Test 3 -- what does move money? Stream Finance, Oct-Nov 2025.

Indexes three deposit series to 100 at 00:00 UTC on 28 Oct 2025 (the morning of the first public warning):
  - Morpho xUSD/USDC market on Arbitrum (hourly; lenders = curated vaults: MEV Capital, Hyperithm, Clearstar)
  - Stream Finance total deposits (DefiLlama, daily)
  - Elixir total deposits (DefiLlama, daily)

Writes data/processed/stream_reaction.csv (long format: series, time, index_value, usd)
"""
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import PROC, RAW, load_protocol_tvl  # noqa: E402

BASE = pd.Timestamp("2025-10-28")
WINDOW = (pd.Timestamp("2025-10-24"), pd.Timestamp("2025-11-06"))

h = json.load(open(RAW / "xusd_arb_hourly.json"))
morpho = pd.Series({pd.Timestamp(dt.datetime.fromtimestamp(p["x"], dt.UTC).replace(tzinfo=None)): p["y"] for p in h}).sort_index()
series = {"Morpho xUSD lenders (curated vaults)": morpho,
          "Stream Finance depositors": load_protocol_tvl("stream-finance"),
          "Elixir depositors": load_protocol_tvl("elixir")}
rows = []
for name, s in series.items():
    s = s.loc[WINDOW[0]:WINDOW[1] + pd.Timedelta(hours=23)]
    base = s.loc[:BASE].iloc[-1]  # last value at or before the base time: no look-ahead
    for t, v in s.items():
        rows.append(dict(series=name, time=t, index_value=100 * v / base, usd=v))
out = pd.DataFrame(rows)
out.to_csv(PROC / "stream_reaction.csv", index=False)
for name, g in out.groupby("series"):
    pre = g[g.time <= pd.Timestamp("2025-11-03")]
    print(f"{name}: index {pre.index_value.iloc[-1]:.0f} on 3 Nov (100 = 28 Oct)")
