"""
Test 1 -- does yield climb with the grade?

Bonds: ICE BofA option-adjusted spread by rating (extra yield over Treasuries), averaged over the window.
Vaults: daily vault APY minus the 3-month Treasury bill (as of that day, never a later print), averaged.

Writes data/processed/bond_spreads.csv and data/processed/vault_spreads.csv
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import BOND_BUCKET, POOLS, PROC, SCALE, asof, load_fred, load_grades, load_pool  # noqa: E402

START, END = pd.Timestamp("2026-02-01"), pd.Timestamp("2026-10-13")
MIN_DAYS = 30  # fewer days at $10M+ is too thin to average
BONDS = [("AAA", "BAMLC0A1CAAA"), ("AA", "BAMLC0A2CAA"), ("A", "BAMLC0A3CA"), ("BBB", "BAMLC0A4CBBB"),
         ("BB", "BAMLH0A1HYBB"), ("B", "BAMLH0A2HYB"), ("CCC", "BAMLH0A3HYC")]

bond = {lab: load_fred(sid) for lab, sid in BONDS}
b = []
for lab, sid in BONDS:
    s = load_fred(sid).loc[START:END]
    b.append(dict(rating=lab, series=sid, mean_spread=s.mean(), latest=s.iloc[-1], n=len(s)))
pd.DataFrame(b).to_csv(PROC / "bond_spreads.csv", index=False)

tbill = load_fred("DTB3")
grades = load_grades()
v = []
for addr, (label, pool, conf, how, dollar) in POOLS.items():
    if not pool or not dollar:
        continue  # dollar products with a resolved pool only: an ETH or BNB vault's yield isn't comparable to a T-bill
    p = load_pool(pool).loc[START:END].dropna(subset=["apy"])
    p = p[p.tvl >= 10e6]  # ignore days when the vault is too small to matter
    if len(p) < MIN_DAYS:
        print(f"skipped {label}: {len(p)} days at $10M+ (< {MIN_DAYS})")
        continue
    tb = [asof(tbill, d) for d in p.index]
    p = p.assign(tbill=tb).dropna(subset=["tbill"])
    sp = p.apy - p.tbill
    gv = grades[grades.address == addr].sort_values("date")
    # Same-dates comparison: the grade in force that day (published on or before it) -> its bond index that day
    in_force = pd.Series(gv.rating.values, index=gv.date).reindex(p.index.union(gv.date)).ffill().reindex(p.index)
    matched = pd.Series([asof(bond[BOND_BUCKET[g]], d) if isinstance(g, str) else None for d, g in in_force.items()],
                        index=p.index, dtype=float)
    ok = matched.notna()
    letters = " / ".join(dict.fromkeys(gv.rating))
    v.append(dict(address=addr, vault=label, pool=pool, mapping=conf, rate_set_by=how, grades=letters,
                  bond_equivalent=" / ".join(dict.fromkeys(SCALE[r][2] for r in gv.rating)),
                  mean_spread=sp.mean(), median_spread=sp.median(), min_spread=sp.min(), max_spread=sp.max(),
                  days=len(sp), avg_tvl_musd=p.tvl.mean() / 1e6,
                  same_grade_bond_spread=matched[ok].mean(), gap_vs_same_grade_bond=(sp[ok] - matched[ok]).mean(),
                  bb_same_dates=pd.Series([asof(bond["BB"], d) for d in p.index], dtype=float).mean(),
                  matched_days=int(ok.sum()), first_day=p.index.min().date(), last_day=p.index.max().date()))
out = pd.DataFrame(v)
out.to_csv(PROC / "vault_spreads.csv", index=False)
print(out[["vault", "grades", "rate_set_by", "mean_spread", "same_grade_bond_spread", "gap_vs_same_grade_bond",
           "days", "matched_days"]].round(2).to_string(index=False))
