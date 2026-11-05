"""
The only script that touches the network. Refreshes every raw input of the rating study.

    python scripts/update_data.py

Uses curl (Python's SSL certificates are broken on this machine).
"""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import POOLS, RAW  # noqa: E402

FRED = ["BAMLC0A1CAAA", "BAMLC0A2CAA", "BAMLC0A3CA", "BAMLC0A4CBBB", "BAMLH0A1HYBB", "BAMLH0A2HYB", "BAMLH0A3HYC", "DTB3"]
PROTOCOLS = ["stream-finance", "elixir", "resolv-usr", "lista-lending"]


def get(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["curl", "-s", "-L", "--fail", "--max-time", "60", "-o", str(out), url])
    if r.returncode != 0:
        raise SystemExit(f"download failed: {url}")


# 1. Credora report archive (index + every PDF, converted to text)
get("https://reports.credora.io/index.xml", RAW / "credora_index.xml")
rep = RAW / "credora_reports"
for x in ET.parse(RAW / "credora_index.xml").getroot():
    url, name = x.findtext("url"), x.findtext("filename")
    pdf = rep / name
    if not pdf.exists():
        get(url, pdf)
    txt = pdf.with_suffix(".txt")
    if not txt.exists():
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=True)
get("https://www.credora.network/docs/assets/images/defiRatingScale-27d37519c4d0f4d6440704d0fb106865.png", RAW / "credora_scale.png")

# 2. DefiLlama: daily deposits and yields for each mapped vault, protocol totals for events and controls
for _, pool, *_ in POOLS.values():
    if pool:
        get(f"https://yields.llama.fi/chart/{pool}", RAW / "llama_charts" / f"{pool}.json")
for slug in PROTOCOLS:
    get(f"https://api.llama.fi/protocol/{slug}", RAW / f"llama_{slug}.json")

# 3. FRED: ICE BofA option-adjusted spreads by rating, 3-month Treasury bill
for s in FRED:
    get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}", RAW / "fred" / f"{s}.csv")

# 4. Morpho: hourly supply in the Stream-exposed xUSD/USDC market on Arbitrum (27 Oct - 4 Nov 2025)
markets = json.load(open(RAW / "markets_all.json")) if (RAW / "markets_all.json").exists() else []
mid = next((m["marketId"] for m in markets if m["marketId"].startswith("0x9e90aec7") and m["chain"]["id"] == 42161), None)
if mid:
    q = ('{ marketById(marketId:"%s", chainId:42161) { historicalState { supplyAssetsUsd('
         'options:{startTimestamp:1761523200,endTimestamp:1762214400,interval:HOUR}) { x y } } } }' % mid)
    r = subprocess.run(["curl", "-s", "https://api.morpho.org/graphql", "-H", "content-type: application/json",
                        "-d", json.dumps({"query": q})], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    json.dump(d["data"]["marketById"]["historicalState"]["supplyAssetsUsd"], open(RAW / "xusd_arb_hourly.json", "w"))
print("raw data refreshed")
