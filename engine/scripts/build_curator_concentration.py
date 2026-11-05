"""
Who makes the risk decisions? Curator concentration in Morpho vaults (snapshot 13 Oct 2026, Morpho API).

V1 (MetaMorpho) and V2 vaults are reported separately: a V2 vault can deposit into V1 vaults, so adding the two
would double count. Joint curators ("Sentora + SparkDAO") are kept as their own line, not split.
Also: who supplied the Stream-exposed xUSD market at the 28 Oct 2025 warning (from data/processed/xusd_lenders.csv).
Writes data/processed/curator_concentration.csv
"""
import collections
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import PROC, RAW  # noqa: E402

d = json.load(open(RAW / "morpho_vaults_2026-10-13.json"))
rows = []
for kind in ("v1", "v2"):
    by, total = collections.Counter(), 0.0
    for v in d[kind]:
        usd = ((v.get("state") or {}).get("totalAssetsUsd") if kind == "v1" else v.get("totalAssetsUsd")) or 0
        cur = ([c["name"] for c in (v.get("state") or {}).get("curators") or []] if kind == "v1"
               else [c["name"] for c in (v.get("curators") or {}).get("items", [])])
        by[" + ".join(sorted(cur)) or "(no curator listed)"] += usd
        total += usd
    cum = 0.0
    for rank, (c, usd) in enumerate(by.most_common(), 1):
        cum += usd
        rows.append(dict(vault_type=kind, rank=rank, curator=c, assets_usd=usd, share_pct=100 * usd / total,
                         cumulative_pct=100 * cum / total, total_usd=total, vaults=len(d[kind])))
out = pd.DataFrame(rows)
out.to_csv(PROC / "curator_concentration.csv", index=False)
for kind, g in out.groupby("vault_type"):
    print(f"{kind}: {g.vaults.iloc[0]} vaults, ${g.total_usd.iloc[0] / 1e9:.2f}bn")
    print(g.head(6)[["rank", "curator", "share_pct", "cumulative_pct"]].round(1).to_string(index=False))
v2 = out[(out.vault_type == "v2") & ~out.curator.str.contains(r"\+|no curator")].head(3)
print(f"V2: top three single curators ({', '.join(v2.curator)}) = {v2.share_pct.sum():.1f}% of V2 vault assets")
xl = pd.read_csv(PROC / "xusd_lenders.csv")
top2 = xl.nlargest(2, "principal_usd")
print(f"xUSD market at the warning: {', '.join(top2.lender)} supplied {100 * top2.principal_usd.sum() / xl.principal_usd.sum():.1f}% "
      f"of ${xl.principal_usd.sum() / 1e6:.1f}mn")
