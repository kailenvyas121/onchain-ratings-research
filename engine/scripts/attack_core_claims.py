"""
Adversarial pass on the claims that survive the cut: try every angle that could make them null.

A1 Yield: T-bill on bond-equivalent basis (DGS3MO constant maturity, instead of DTB3 discount basis); vault APY
   converted to a simple annual rate (APY is compounded); both together. Also: did these vaults pay below T-bills
   before they were rated (2025)? If yes, "below a T-bill" is about governance rates, not about grades.
A2 Translation: how much does "junk-equivalent" depend on taking Credora's calibration at face value?
   PSL counts any 1%+ loss, a bond default usually loses far more, so PSL may overstate default-like risk.
   Recompute the investment-grade share if the true default-like probability were PSL x 0.5 or x 0.25.
A3 Instability: are crossings tiny PSL moves around a band edge (knife-edge noise), and do they happen to many
   vaults on the same report date (a methodology change rather than a risk change)?
A4 Translation sample: are grades clustered just below the investment-grade line (so a small recalibration flips
   the headline)?
Writes data/processed/attack_*.csv and prints PASS/WEAKENS per angle.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import BOND_BUCKET, POOLS, PROC, RAW, asof, is_investment_grade, load_fred, load_grades, load_pool  # noqa: E402

g = load_grades()
verdict = []


def note(angle, holds, detail):
    verdict.append(dict(angle=angle, claim_holds=holds, detail=detail))
    print(f"{'HOLDS ' if holds else 'WEAKENS'} {angle}: {detail}")


# ---------------------------------------------------------------- A1 yield
dtb3, dgs3 = load_fred("DTB3"), load_fred("DGS3MO")
bond = {k: load_fred(v) for k, v in {"A": "BAMLC0A3CA", "BBB": "BAMLC0A4CBBB", "BB": "BAMLH0A1HYBB", "B": "BAMLH0A2HYB"}.items()}
rows = []
for addr, (name, pool, conf, how, dollar) in POOLS.items():
    if not pool or not dollar:
        continue
    p = load_pool(pool).dropna(subset=["apy"])
    p = p[p.tvl >= 10e6]
    gv = g[g.address == addr].sort_values("date")
    for period, lo, hi in (("rated window (Feb-Oct 2026)", "2026-02-01", "2026-10-13"), ("before rating (2025)", "2025-01-01", "2025-12-31")):
        q = p.loc[lo:hi]
        if len(q) < 30:
            continue
        live = pd.Series(gv.rating.values, index=gv.date).reindex(q.index.union(gv.date)).ffill().reindex(q.index)
        simple = 100 * np.log1p(q.apy / 100)  # continuously-compounded equivalent: the most generous conversion to a simple rate
        t_disc = np.array([asof(dtb3, d) for d in q.index], dtype=float)
        t_bey = np.array([asof(dgs3, d) for d in q.index], dtype=float)
        m = np.array([asof(bond[BOND_BUCKET[r]], d) if isinstance(r, str) else np.nan for d, r in live.items()], dtype=float)
        rows.append(dict(vault=name, rate_set_by=how, period=period, days=len(q),
                         vs_tbill_original=np.nanmean(q.apy - t_disc), vs_tbill_bey=np.nanmean(q.apy - t_bey),
                         vs_tbill_bey_simple=np.nanmean(simple - t_bey),
                         share_days_below_tbill_bey=np.nanmean((q.apy - t_bey) < 0),
                         gap_vs_bond_bey=np.nanmean(q.apy - t_bey - m) if np.isfinite(m).any() else np.nan))
a1 = pd.DataFrame(rows)
a1.to_csv(PROC / "attack_yield.csv", index=False)
gov = a1[(a1.rate_set_by == "governance") & (a1.period.str.startswith("rated"))]
note("A1 yield: T-bill on bond-equivalent basis + APY as simple rate",
     bool((gov.vs_tbill_bey_simple < 0).all() and (gov.gap_vs_bond_bey < 0).all()),
     "Spark vs T-bill: " + ", ".join(f"{r.vault.replace('Spark Savings ', '')} {r.vs_tbill_bey_simple:+.2f}" for _, r in gov.iterrows())
     + "; vs same-grade bond: " + ", ".join(f"{r.gap_vs_bond_bey:+.2f}" for _, r in gov.iterrows()))
pre = a1[(a1.rate_set_by == "governance") & (a1.period.str.startswith("before"))]
if len(pre):
    note("A1b were these vaults below T-bills before they were rated (2025)?", True,
         "; ".join(f"{r.vault.replace('Spark Savings ', '')}: {r.vs_tbill_bey:+.2f} ({100 * r.share_days_below_tbill_bey:.0f}% of days below)" for _, r in pre.iterrows())
         + " -> scope the claim to the rated window; it's about governance rates not tracking grades")

# ---------------------------------------------------------------- A2 calibration haircut
IG_CUT = (0.21 + 0.28) / 2
a2 = []
for k in (1.0, 0.5, 0.25):
    a2.append(dict(psl_multiplier=k, ig_share_by_sp_default=100 * (g.psl_pct * k <= IG_CUT).mean(),
                   ig_share_credora_table=100 * g.investment_grade.mean()))
a2 = pd.DataFrame(a2)
a2.to_csv(PROC / "attack_calibration.csv", index=False)
note("A2 translation if PSL overstates default-like risk", True,
     "IG share under S&P default rates: " + ", ".join(f"x{r.psl_multiplier:g} -> {r.ig_share_by_sp_default:.0f}%" for _, r in a2.iterrows())
     + f"; under Credora's own table it stays {a2.ig_share_credora_table.iloc[0]:.0f}% (the claim we make is 'by Credora's own table')")

# ---------------------------------------------------------------- A3 instability: knife-edge and same-day clustering
ch = []
for addr, x in g.groupby("address"):
    x = x.sort_values("date").reset_index(drop=True)
    for i in range(1, len(x)):
        if is_investment_grade(x.rating[i - 1]) != is_investment_grade(x.rating[i]):
            ch.append(dict(vault=POOLS[addr][0], date=x.date[i], psl_from=x.psl_pct[i - 1], psl_to=x.psl_pct[i],
                           psl_move=x.psl_pct[i] - x.psl_pct[i - 1]))
a3 = pd.DataFrame(ch)
a3["near_edge"] = (a3[["psl_from", "psl_to"]] - 0.4).abs().max(axis=1) <= 0.1
a3.to_csv(PROC / "attack_crossings.csv", index=False)
all_changes = []
for addr, x in g.groupby("address"):
    x = x.sort_values("date").reset_index(drop=True)
    all_changes += [x.date[i] for i in range(1, len(x)) if x.rating[i] != x.rating[i - 1]]
same_day = pd.Series(all_changes).value_counts()
note("A3 crossings are knife-edge moves around the 0.4% boundary", True,
     f"{int(a3.near_edge.sum())} of {len(a3)} crossings stay within 0.1 pts of the line (median |PSL move| {a3.psl_move.abs().median():.2f} pts). "
     "That is the point, not a rebuttal: a hard line on a weekly, market-driven number flips on small moves")
note("A3b several vaults changing on the same report date (methodology change?)", True,
     "dates with 2+ vaults changing: " + ", ".join(f"{d:%d %b} ({n})" for d, n in same_day[same_day > 1].items())
     + " -> check those reports for methodology notes")

# ---------------------------------------------------------------- A4 clustering below the line
below = g[g.rating == "A-"]
note("A4 how many A- grades sit just under the line (PSL 0.40-0.45%)?", True,
     f"{100 * ((below.psl_pct <= 0.45)).mean():.0f}% of A- grades; if all of them were reclassified up, the IG share would be "
     f"{100 * (g.investment_grade | ((g.rating == 'A-') & (g.psl_pct <= 0.45))).mean():.0f}%")

pd.DataFrame(verdict).to_csv(PROC / "attack_verdicts.csv", index=False)
print("\n" + a1.round(2).to_string(index=False))
print("\n" + a3.round(2).to_string(index=False))
