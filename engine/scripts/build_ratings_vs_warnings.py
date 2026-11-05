"""
Ratings vs warnings, head to head, on one common yardstick: how unusual was the week after the event for that
series, ranked against its own history (0 = worst week on record, 50 = typical)?

Rating events (15): 12 testable Credora changes (7-day abnormal flow vs control) and three outside ratings
  (S&P USDT 26 Nov 2025 and S&P Sky 8 Aug 2025 at 7 days vs USDC; Moody's Sky 7 Oct 2026 at 3 days, all that exists).
Warning (1 episode, 3 series): the Stream warning, 28 Oct -> 3 Nov 2025.
Stress without a warning: the 10 Oct 2025 crash week for the same 3 series.
Tests: KS test of rating-event ranks against "no effect" (uniform); share of rating events in the worst 5%.
Writes data/processed/ratings_vs_warnings.csv
"""
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, kstest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import PROC, RAW, load_protocol_tvl  # noqa: E402

ev = pd.read_csv(PROC / "grade_events.csv")
ev = ev[(ev.status == "tested") & ev.percentile_7d.notna()]
rows = [dict(kind="rating", rater="Credora", event=f"{r.vault} {r.from_grade}->{r.to_grade} {r.date[:10]}", pct=r.percentile_7d)
        for _, r in ev.iterrows()]
oos = pd.read_csv(PROC / "extra_out_of_sample.csv")
for ev_name, series, h, rater in (("S&P cuts USDT to 5 'weak'", "USDT supply", 7, "S&P"),
                                  ("S&P rates Sky B- / USDS 4", "Sky supply (USDS+DAI)", 7, "S&P"),
                                  ("Moody's rates Sky B3", "Sky supply (USDS+DAI)", 3, "Moody's")):
    r = oos[(oos.event == ev_name) & (oos.series == series) & (oos.horizon_d == h)].iloc[0]
    rows.append(dict(kind="rating", rater=rater, event=f"{ev_name} ({h}d)", pct=r.percentile))

xd = json.load(open(RAW / "xusd_arb_daily.json"))["data"]["marketById"]["historicalState"]["supplyAssetsUsd"]
xusd = pd.Series({pd.Timestamp(dt.datetime.fromtimestamp(p["x"], dt.UTC).date()): p["y"] for p in xd}).sort_index()
for name, s, first in (("Morpho xUSD market", xusd, "2025-09-22"), ("Stream Finance", load_protocol_tvl("stream-finance"), "2024-01-01"),
                       ("Elixir", load_protocol_tvl("elixir"), "2024-01-01")):
    s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))
    f = 100 * (s.shift(-6) / s - 1)
    for kind, day in (("warning", "2025-10-28"), ("stress, no warning", "2025-10-10")):
        d0 = pd.Timestamp(day)
        hist = f.loc[first:d0 - pd.Timedelta(days=7)].dropna()
        rows.append(dict(kind=kind, rater="-", event=f"{name} {day}", pct=100 * (hist <= f[d0]).mean(), flow_6d=f[d0]))
out = pd.DataFrame(rows)
out.to_csv(PROC / "ratings_vs_warnings.csv", index=False)

rt = out[out.kind == "rating"].pct / 100
ks = kstest(rt, "uniform")
low = int((rt <= 0.05).sum())
bt = binomtest(low, len(rt), 0.05, alternative="greater")
print(out.round(1).to_string(index=False))
print(f"\nRating events: n={len(rt)}, median rank {100 * rt.median():.0f} (no effect = 50); "
      f"KS test vs no-effect p = {ks.pvalue:.2f}; {low} of {len(rt)} in the worst 5% (expected by chance {0.05 * len(rt):.1f}, p = {bt.pvalue:.2f})")
w = out[out.kind == "warning"]
c = out[out.kind == "stress, no warning"]
print(f"Warning: all {len(w)} exposed series in their worst {w.pct.max():.0f}% of weeks; "
      f"crash week without a warning: ranks {', '.join(f'{x:.0f}' for x in c.pct)}")
