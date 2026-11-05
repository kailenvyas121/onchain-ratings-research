"""
Robustness for the Lista BNB vault: its DefiLlama deposits are in dollars, so they move with the BNB price.
Re-measure each grade event's flow in BNB units (deposits / BNB price) and rank it against the same vault's
non-event days (same 10-day exclusion as the main test). No control needed: the price effect is removed directly.

Price: DefiLlama coins API, daily points at ~00:00 UTC; DefiLlama pool snapshots are ~23:00 UTC, so day d's
deposits are divided by the price stamped d+1 00:00 (1 hour later, the nearest point).
Writes data/processed/bnb_vault_token_flows.csv
"""
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import PROC, RAW, load_pool  # noqa: E402

POOL, ADDR, EXCLUDE = "e15db93c-9c49-490c-896d-24092b4d7471", "0x57134a64b7cd9f9eb72f8255a671f5bf2fe3e2d0", 10
pts = list(json.load(open(RAW / "llama_price_wbnb.json"))["coins"].values())[0]["prices"]
px = pd.Series({pd.Timestamp(dt.datetime.fromtimestamp(x["timestamp"] - 3600, dt.UTC).date()): x["price"] for x in pts})
px = px[~px.index.duplicated(keep="first")]
units = (load_pool(POOL).tvl / px).dropna()

ev = pd.read_csv(PROC / "grade_events.csv", parse_dates=["date"])
ev = ev[ev.vault == "Lista BNB vault"]


def flow(d0, h):
    a, b = d0 - pd.Timedelta(days=1), d0 + pd.Timedelta(days=h)
    return 100 * (units[b] / units[a] - 1) if a in units.index and b in units.index else None


near = {d + pd.Timedelta(days=k) for d in ev.date for k in range(-EXCLUDE, EXCLUDE + 1)}
null = pd.Series([flow(d, 7) for d in units.index if d not in near and d >= pd.Timestamp("2026-02-03")]).dropna()
rows = []
for _, e in ev.iterrows():
    f = flow(e.date, 7)
    rows.append(dict(date=e.date.date(), from_grade=e.from_grade, to_grade=e.to_grade, crosses_ig_line=e.crosses_ig_line,
                     flow_7d_usd=e.flow_7d, flow_7d_bnb_units=f, percentile_7d_bnb_units=100 * (null <= f).mean()))
out = pd.DataFrame(rows)
out.to_csv(PROC / "bnb_vault_token_flows.csv", index=False)
print(f"null days: {len(null)}")
print(out.round(1).to_string(index=False))
