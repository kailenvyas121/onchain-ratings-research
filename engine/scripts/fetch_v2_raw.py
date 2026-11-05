"""Re-download every raw input the v2 and X-thread charts read into data/raw/v2/ (dated files, one per pull).
Uses curl (Python's SSL certificates were unreliable on the build machine). Then fetches per-coin prices and supply.

    python scripts/fetch_v2_raw.py

Not re-fetched: cg_*.json (CoinGecko histories used only as a second source in v2_var_test.py; the free CoinGecko
API now caps history at 365 days).
"""
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/v2"
(RAW / "stable_prices_dead").mkdir(parents=True, exist_ok=True)
TODAY = date.today().strftime("%Y%m%d")


def get(url, out):
    r = subprocess.run(["curl", "-s", "-m", "120", "-o", str(out), "-w", "%{http_code}", url], capture_output=True, text=True)
    print(f"{r.stdout} {out.relative_to(ROOT)}")
    time.sleep(0.2)


get("https://stablecoins.llama.fi/stablecoins?includePrices=true", RAW / f"stablecoins_{TODAY}.json")
get("https://stablecoins.llama.fi/stablecoincharts/all", RAW / "stablecoin_total_latest.json")
get("https://api.llama.fi/v2/historicalChainTvl", RAW / f"defi_tvl_{TODAY}.json")
get("https://api.llama.fi/hacks", RAW / f"hacks_{TODAY}.json")

# Price windows before three collapses (VaR inputs): coins.llama.fi, 499-day spans (API max) from two start points
for coin in ("resolv-usr", "staked-stream-usd", "elixir-deusd"):
    for start in (1740000000, 1755000000):
        get(f"https://coins.llama.fi/chart/coingecko:{coin}?start={start}&span=499&period=1d", RAW / f"var_{coin}_{start}.json")

# Dead algorithmic stablecoins DefiLlama no longer lists: daily prices from 2020, in 499-day chunks (API max)
for gid in ("iron-stablecoin", "basis-cash", "empty-set-dollar", "dynamic-set-dollar", "dei-token"):
    chunks, s = [], 1577836800
    while s < time.time():
        r = subprocess.run(["curl", "-s", "-m", "40", f"https://coins.llama.fi/chart/coingecko:{gid}?start={s}&span=499&period=1d"],
                           capture_output=True, text=True).stdout
        chunks.append(r.strip() or "{}")
        s += 499 * 86400
        time.sleep(0.2)
    out = RAW / "stable_prices_dead" / f"{gid}_{TODAY}.json"
    out.write_text("[" + ",".join(chunks) + "]")
    print(f"ok {out.relative_to(ROOT)}")

for script in ("v2_fetch_stable_prices.py", "v2_fetch_stable_supply.py"):
    subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True)
