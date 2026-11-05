"""
Who left the Stream-exposed Morpho market, and how fast? (xUSD/USDC on Arbitrum, Oct-Nov 2025)

Rebuilds every lender's principal at 28 Oct 2025 00:00 UTC from the market's full transaction history
(data/raw/tx_xusd_arb_full.json, Morpho API marketTransactions from market creation, 15 Sep 2025), then tracks each
lender to 3 Nov 00:00 (Stream froze withdrawals on 4 Nov). Lender type: Morpho vault (named by the Morpho API),
other contract, or wallet (no contract code on Arbitrum; checked 13 Oct 2026).
Writes data/processed/xusd_lenders.csv
"""
import collections
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import PROC, RAW  # noqa: E402

T0, T1 = 1761609600, 1762128000  # 28 Oct 2025 00:00 UTC, 3 Nov 2025 00:00 UTC
USDC = 1e6
KIND = {  # eth_getCode on Arbitrum + Morpho vaultByAddress, 13 Oct 2026
    "0xa60643c90a542a95026c0f1dbdb0615ff42019cf": "curated vault: MEV Capital USDC",
    "0x4b6f1c9e5d470b97181786b26da0d0945a7cf027": "curated vault: Hyperithm USDC Apex",
    "0x3014ed70b39be395e1a5eb8ab4c4b8a5378e6522": "curated vault: 'Not Gauntlet'",
    "0x64a651d825fc70ebba88f2e1bad90be9a496c4b9": "curated vault: Avantgarde USDC Core",
    "0x46ce9aa8167fa3e154395c25d19db25ddfcfeab4": "other contract",
    "0x3ae7c943b2186033bfb772193a007ff41c69940b": "wallet (EIP-7702 delegated)",
}
tx = sorted(json.load(open(RAW / "tx_xusd_arb_full.json")), key=lambda x: x["timestamp"])
flows = [x for x in tx if x["type"] in ("Supply", "Withdraw")]
sign = lambda x: 1 if x["type"] == "Supply" else -1  # noqa: E731

pos = collections.defaultdict(float)
for x in flows:
    if x["timestamp"] < T0:
        pos[x["user"]["address"].lower()] += sign(x) * int(x["data"]["assets"]) / USDC
held = {a: v for a, v in pos.items() if v > 1}
bal, half = dict(held), {}
for x in flows:
    a = x["user"]["address"].lower()
    if T0 <= x["timestamp"] < T1 and a in held:
        bal[a] += sign(x) * int(x["data"]["assets"]) / USDC
        if bal[a] <= held[a] / 2 and a not in half:
            half[a] = (x["timestamp"] - T0) / 3600
rows = [dict(address=a, lender=KIND.get(a, "wallet"), principal_usd=v, hours_to_half_out=half.get(a),
             remaining_pct_3nov=100 * max(bal[a], 0) / v) for a, v in held.items()]
out = pd.DataFrame(rows).sort_values("principal_usd", ascending=False)
out.to_csv(PROC / "xusd_lenders.csv", index=False)
repaid = sum(int(x["data"]["assets"]) for x in tx if x["type"] == "Repay" and T0 <= x["timestamp"] < T1) / USDC
borrowed = sum(int(x["data"]["assets"]) for x in tx if x["type"] == "Borrow" and T0 <= x["timestamp"] < T1) / USDC

print(f"{len(out)} lenders, ${out.principal_usd.sum() / 1e6:.1f}mn principal at 28 Oct 00:00 UTC; "
      f"{100 * (1 - (out.principal_usd * out.remaining_pct_3nov / 100).sum() / out.principal_usd.sum()):.1f}% withdrawn by 3 Nov")
print(f"borrowers repaid ${repaid / 1e6:.1f}mn and borrowed ${borrowed / 1e6:.1f}mn in the window (the exit lenders used)")
print(out.assign(principal_usd=lambda d: (d.principal_usd / 1e6).round(3)).to_string(index=False))
for k, g in out.assign(t=out.lender.str.startswith("curated")).groupby("t"):
    print(("curated vaults" if k else "everyone else"), f"median hours to half out: {g.hours_to_half_out.median():.0f}")
