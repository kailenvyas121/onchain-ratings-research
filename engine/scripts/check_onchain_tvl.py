"""
Check DefiLlama's daily deposits for the Spark dollar vaults against the vault contracts themselves.

For every Spark grade event, reads ERC-4626 totalAssets() on Ethereum (archive RPC, eth.drpc.org) at the block
nearest 23:00 UTC (DefiLlama's snapshot time) on days -1, +3, +7 and +14, plus the control vault on the same days.
Network script (like update_data.py). Writes data/raw/onchain_spark_tvl.csv.

    python scripts/check_onchain_tvl.py
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import CONTROL_ADDRESS, POOLS, PROC, RAW  # noqa: E402

RPC = "https://eth.drpc.org"
DECIMALS = {"0xe2e7a17dff93280dec073c995595155283e3c372": 6, "0x28b3a8fb53b741a8fd78c0fb9a6b2393d896a43d": 6,
            "0x80128dbb9f07b93dde62a6daeadb69ed14a7d354": 6}


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    for _ in range(4):
        out = subprocess.run(["curl", "-s", "--max-time", "30", "-X", "POST", "-H", "content-type: application/json",
                              "--data", body, RPC], capture_output=True, text=True).stdout
        try:
            r = json.loads(out)
            if "result" in r:
                return r["result"]
        except json.JSONDecodeError:
            pass
        time.sleep(2)
    raise SystemExit(f"RPC failed: {method} {params} -> {out[:200]}")


def block_ts(n):
    return int(rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)


def block_at(ts):
    """Last block at or before ts (12s slots, refined by search)."""
    hi = int(rpc("eth_blockNumber", []), 16)
    lo = max(1, hi - (block_ts(hi) - ts) // 12 - 2000)
    while block_ts(lo) > ts:
        lo -= 5000
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if block_ts(mid) <= ts else (lo, mid)
    return lo


def total_assets(addr, block):
    return int(rpc("eth_call", [{"to": addr, "data": "0x01e1d114"}, hex(block)]), 16) / 10 ** DECIMALS[addr] / 1e6


ev = pd.read_csv(PROC / "grade_events.csv", parse_dates=["date"])
name_to_addr = {v[0]: a for a, v in POOLS.items()}
rows = []
for _, e in ev[ev.protocol == "SPARK"].iterrows():
    addr = name_to_addr[e.vault]
    for h in (-1, 3, 7, 14):
        day = e.date + timedelta(days=h)
        ts = int(datetime(day.year, day.month, day.day, 23, 0, tzinfo=timezone.utc).timestamp())
        if ts > time.time():
            continue
        b = block_at(ts)
        for a in {addr, CONTROL_ADDRESS}:
            rows.append(dict(event_vault=e.vault, event_date=e.date.date(), horizon=h, day=day.date(), block=b,
                             vault=POOLS[a][0], address=a, onchain_musd=total_assets(a, b)))
        print(f"{e.vault:22} {e.date:%Y-%m-%d} h={h:+d} block {b}")
out = pd.DataFrame(rows).drop_duplicates(["address", "day"])
out.to_csv(RAW / "onchain_spark_tvl.csv", index=False)
print(f"saved {len(out)} on-chain readings")
