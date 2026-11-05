"""Daily price history for every USD-pegged stablecoin DefiLlama tracks (with a CoinGecko id). 500-day windows (API max)."""
import json, subprocess, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/v2"
OUT = RAW / "stable_prices"; OUT.mkdir(exist_ok=True)
coins = [a for a in json.load(open(sorted(RAW.glob("stablecoins_*.json"))[-1]))["peggedAssets"]
         if a.get("pegType") == "peggedUSD" and a.get("gecko_id")]
START, NOW, SPAN = 1546300800, int(time.time()), 499
def fetch(a):
    f = OUT / f"{a['gecko_id']}.json"
    if f.exists(): return
    prices = []
    for s in range(START, NOW, SPAN * 86400):
        url = f"https://coins.llama.fi/chart/coingecko:{a['gecko_id']}?start={s}&span={SPAN}&period=1d"
        for _ in range(3):
            r = subprocess.run(["curl", "-s", "-m", "40", url], capture_output=True, text=True).stdout
            try: d = json.loads(r); break
            except Exception: time.sleep(2); d = {}
        prices += next(iter(d.get("coins", {}).values()), {}).get("prices", [])
        time.sleep(0.15)
    f.write_text(json.dumps({"id": a["id"], "name": a["name"], "symbol": a["symbol"], "mech": a.get("pegMechanism"), "prices": prices}))
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(8) as ex: list(ex.map(fetch, coins))
print("done", len(coins))
