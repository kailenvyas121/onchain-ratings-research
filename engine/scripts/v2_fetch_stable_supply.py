"""Daily circulating supply for each USD stablecoin (for a size filter that does not depend on today's size)."""
import json, subprocess, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/v2"
OUT = RAW / "stable_supply"; OUT.mkdir(exist_ok=True)
coins = [a for a in json.load(open(sorted(RAW.glob("stablecoins_*.json"))[-1]))["peggedAssets"]
         if a.get("pegType") == "peggedUSD" and a.get("gecko_id")]
def fetch(a):
    f = OUT / f"{a['gecko_id']}.json"
    if f.exists(): return
    time.sleep(0.6)
    r = subprocess.run(["curl", "-s", "-m", "60", f"https://stablecoins.llama.fi/stablecoincharts/all?stablecoin={a['id']}"],
                       capture_output=True, text=True).stdout
    try: d = json.loads(r)
    except Exception:
        time.sleep(5); return
    f.write_text(json.dumps([[int(x["date"]), (x.get("totalCirculatingUSD") or {}).get("peggedUSD", 0)] for x in d]))
with ThreadPoolExecutor(2) as ex: list(ex.map(fetch, coins))
print("done", len(list(OUT.glob("*.json"))), "of", len(coins))
