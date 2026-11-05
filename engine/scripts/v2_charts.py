"""
Charts for "Rating Agencies Are Coming Onchain" (v2), in the house style (scripts/house_style.py).
Every value is read from data/processed (v2_*) or data/raw/v2. Writes 2_Charts/v2/*.png.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent))
from house_style import BLACK, BLUE, FONT, GREY, LGREY, NAVY, create_default_figure  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT / "data/raw/v2", ROOT / "data/processed"
OUT = ROOT.parent / "2_Charts" / "v2"
OUT.mkdir(parents=True, exist_ok=True)


def save(fig, name, *headline):
    fig.write_image(OUT / f"{name}.png", scale=2)
    print(f"{name}: " + "; ".join(headline))


def latest(pattern):
    return sorted(RAW.glob(pattern))[-1]


# ============================================================ Losses by year (intro)
h = pd.DataFrame(json.load(open(latest("hacks_*.json"))))
h["yr"] = pd.to_datetime(h.date, unit="s").dt.year
h = h[(h.yr >= 2020)]
h["grp"] = np.where(h.targetType == "DeFi Protocol", "DeFi protocols",
                    np.where(h.targetType == "CEX", "Centralised exchanges", "Other (tokens, chains, wallets)"))
by = h.pivot_table(index="yr", columns="grp", values="amount", aggfunc="sum").fillna(0) / 1e9
fig = create_default_figure(ylabel="Lost to hacks and exploits",
                            source_text="DefiLlama hacks database, accessed 14 Oct 2026. 2026 runs to 10 Oct. 2020 includes the &#36;3.5bn LuBian "
                                        "mining-pool theft, first disclosed in 2025.",
                            ysource_text_offset=0.28, ylegend_offset=0.2, width=1000, height=560)
for col, c in (("DeFi protocols", BLUE), ("Centralised exchanges", GREY), ("Other (tokens, chains, wallets)", LGREY)):
    fig.add_bar(x=by.index.astype(str), y=by[col], name=col, marker_color=c)
tot = by.sum(axis=1)
fig.add_scatter(x=tot.index.astype(str), y=tot + 0.25, mode="text", text=[f"&#36;{v:.1f}bn" for v in tot],
                textfont=dict(family=FONT, size=15, color=BLACK), showlegend=False)
fig.update_layout(barmode="stack", legend=dict(traceorder="normal"))
fig.update_yaxes(tickprefix="&#36;", ticksuffix="bn")
save(fig, "fig_losses_by_year", f"total 2020-26 ${tot.sum():.1f}bn", f"events {len(h)}")

# ============================================================ VaR said vs what was lost
v = pd.read_csv(PROC / "v2_var_test.csv")
v = v[(v.source == "DefiLlama") & (v.window_days == 90)].set_index("coin")
order = ["Resolv USR", "Elixir deUSD", "Stream xUSD"]
dates = {"Resolv USR": "Mar 2026", "Elixir deUSD": "Nov 2025", "Stream xUSD": "Nov 2025"}
labels = [f"{c}<br>({dates[c]})" for c in order]
fig = create_default_figure(
                            source_text="DefiLlama and CoinGecko daily prices. VaR: 1-day 99% historical, from the 90 days ending a week "
                                        "before each collapse<br>(Stream xUSD: 26 days, all available). Loss: last pre-collapse price to "
                                        "the low within 30 days.",
                            ysource_text_offset=0.32, ylegend_offset=0.22, width=1000, height=520)
fig.add_bar(y=labels, x=v.loc[order, "var99_1d"], orientation="h", name="Worst daily loss VaR expected (99% confidence)",
            marker_color=GREY, text=[f"{x:.1f}%" for x in v.loc[order, "var99_1d"]], textposition="outside",
            textfont=dict(family=FONT, size=16, color=BLACK), cliponaxis=False)
fig.add_bar(y=labels, x=v.loc[order, "loss_trough"], orientation="h", name="What holders actually lost",
            marker_color=BLUE, text=[f"{x:.1f}%" for x in v.loc[order, "loss_trough"]], textposition="outside",
            textfont=dict(family=FONT, size=16, color=BLACK), cliponaxis=False)
fig.update_layout(barmode="group", bargap=0.3, margin=dict(l=170, r=80, t=20, b=150))
fig.update_yaxes(autorange="reversed", showgrid=False)
fig.update_xaxes(range=[0, 108], ticksuffix="%", showgrid=True, gridcolor="lightgray")
fig.layout.annotations[0].update(x=-0.19)
save(fig, "fig_var_three", *[f"{c} VaR {v.loc[c, 'var99_1d']:.2f}% loss {v.loc[c, 'loss_trough']:.1f}%" for c in order])

# ============================================================ How often stablecoins break, by design
gr = pd.read_csv(PROC / "v2_depeg_grid.csv")
prim = gr[(gr.th == 0.95) & (gr.run == 3) & (gr.min_supply_mn == 10)].set_index("mech")
rng = gr.groupby("mech").pct.agg(["min", "max"])
mechs = [("fiat-backed", "Backed by cash and<br>Treasuries"), ("crypto-backed", "Backed by crypto<br>or trading strategies"),
         ("algorithmic", "Algorithmic")]
fig = create_default_figure(ylabel="Share that ever broke its peg",
                            source_text="DefiLlama stablecoin prices and supply, 2019 to Oct 2026. Coins that reached &#36;10mn in supply. "
                                        "Break: below &#36;0.95 for 3+ days.<br>Whiskers: range across 18 versions of the test "
                                        "(&#36;0.97, &#36;0.95 or &#36;0.90; 2, 3 or 7 days; &#36;10mn or &#36;50mn).",
                            ysource_text_offset=0.27, ylegend_offset=0.2, width=1000, height=600)
fig.update_layout(margin=dict(b=150))
fig.add_bar(x=[m[1] for m in mechs], y=[prim.loc[m[0], "pct"] for m in mechs], marker_color=[GREY, BLUE, NAVY],
            width=0.55, showlegend=False,
            error_y=dict(type="data", symmetric=False, color=BLACK, thickness=1.2, width=8,
                         array=[rng.loc[m[0], "max"] - prim.loc[m[0], "pct"] for m in mechs],
                         arrayminus=[prim.loc[m[0], "pct"] - rng.loc[m[0], "min"] for m in mechs]),
            text=[f"{prim.loc[m[0], 'pct']:.0f}%<br>({int(prim.loc[m[0], 'sum'])} of {int(prim.loc[m[0], 'size'])})" for m in mechs],
            textposition="none")
gr_all = prim["sum"].sum() / prim["size"].sum() * 100
for m in mechs:
    fig.add_annotation(x=m[1], y=max(rng.loc[m[0], "max"], gr_all + 3) + 2, yanchor="bottom", showarrow=False,
                       text=f"<b>{prim.loc[m[0], 'pct']:.0f}%</b><br>{int(prim.loc[m[0], 'sum'])} of {int(prim.loc[m[0], 'size'])} coins",
                       font=dict(family=FONT, size=16, color=BLACK))
a = prim["sum"].sum(); n = prim["size"].sum()
fig.add_hline(y=a / n * 100, line=dict(color=BLACK, width=1.2, dash="dash"))
fig.add_scatter(x=[None], y=[None], mode="lines", line=dict(color=BLACK, width=1.2, dash="dash"),
                name=f"All stablecoins: {a / n * 100:.0f}% ({a} of {n})")
fig.update_yaxes(range=[0, 85], ticksuffix="%")
save(fig, "fig_stablecoin_breaks", *[f"{m[0]} {prim.loc[m[0], 'pct']:.1f}% ({int(prim.loc[m[0], 'sum'])}/{int(prim.loc[m[0], 'size'])}) range "
                                     f"{rng.loc[m[0], 'min']:.0f}-{rng.loc[m[0], 'max']:.0f}%" for m in mechs], f"all {a}/{n} = {a / n * 100:.0f}%")


# ============================================================ The November 2025 wave
def prices(fname, var=False):
    p = []
    if var:
        for f in sorted(RAW.glob(f"var_{fname}_*.json")):
            p += next(iter(json.load(open(f)).get("coins", {}).values()), {}).get("prices", [])
    else:
        p = json.load(open(RAW / "stable_prices" / f"{fname}.json"))["prices"]
    s = pd.DataFrame(p).drop_duplicates("timestamp")
    s["d"] = pd.to_datetime(s.timestamp, unit="s").dt.normalize()
    return s.groupby("d").price.last()


wave = [("Stream xUSD", "staked-stream-usd", True, BLUE), ("Elixir deUSD", "elixir-deusd", False, NAVY),
        ("Stables Labs USDX (separate failure, cause unconfirmed)", "usdx-money-usdx", False, GREY)]
fig = create_default_figure(ylabel="Value of $1 held on 20 October",
                            source_text="DefiLlama daily prices, each coin indexed to 20 Oct 2025 (xUSD was a yield-bearing token priced above &#36;1). "
                                        "Elixir had lent<br>about &#36;68mn to Stream (Cointelegraph, 7 Nov 2025).",
                            ysource_text_offset=0.28, ylegend_offset=0.2, width=1000, height=560)
lo, hi = pd.Timestamp("2025-10-20"), pd.Timestamp("2025-12-15")
for nm, f, isvar, c in wave:
    s = prices(f, isvar)
    s = s[(s.index >= lo) & (s.index <= hi)]
    s = s / s.iloc[0]
    fig.add_scatter(x=s.index, y=s.values, mode="lines", name=nm, line=dict(color=c, width=2.5))
fig.add_vline(x=pd.Timestamp("2025-11-04").timestamp() * 1000, line=dict(color=BLACK, width=1, dash="dash"))
fig.add_annotation(x=pd.Timestamp("2025-11-04"), y=1.08, text="4 Nov: Stream freezes withdrawals", showarrow=False,
                   xanchor="left", xshift=6, font=dict(family=FONT, size=15, color=BLACK))
fig.update_yaxes(range=[0, 1.15], tickprefix="$", tickformat=".2f")
fig.update_xaxes(tickformat="%-d %b", dtick=7 * 86400000)
save(fig, "fig_november_wave", "indexed prices 20 Oct-15 Dec 2025")


# ============================================================ DeFi's loss rate vs bond credit losses
# Bond benchmark: S&P 2024 Annual Global Corporate Default and Rating Transition Study (27 Mar 2025), 1981-2024 average
# one-year default rates, times (1 - recovery). Recovery 47.1% (Moody's-derived 1987-2022 senior unsecured, via Barings);
# the older Moody's 1982-2006 average is 38.4%, which would make bond losses higher.
SP_DEFAULT = {"Investment grade": 0.08, "Speculative grade (junk)": 3.54}
RECOVERY = 0.471
tv = pd.DataFrame(json.load(open(latest("defi_tvl_*.json"))))
tv["yr"] = pd.to_datetime(tv.date.astype(int), unit="s").dt.year
avg_tvl = tv.groupby("yr").tvl.mean()
hd = pd.DataFrame(json.load(open(latest("hacks_*.json"))))
hd["dt"] = pd.to_datetime(hd.date, unit="s"); hd["yr"] = hd.dt.dt.year
dd = hd[(hd.targetType == "DeFi Protocol") & (hd.yr.between(2021, 2026))]
lost = dd.groupby("yr").amount.sum()
days_2026 = (hd.dt.max().normalize() - pd.Timestamp("2026-01-01")).days + 1
lost.loc[2026] *= 365 / days_2026
rate = lost / avg_tvl.loc[lost.index] * 100
pooled = lost.sum() / avg_tvl.loc[lost.index].sum() * 100
nob = dd[dd.bridgeHack != True].groupby("yr").amount.sum(); nob.loc[2026] *= 365 / days_2026
pooled_nob = nob.sum() / avg_tvl.loc[nob.index].sum() * 100
bond = {k: v * (1 - RECOVERY) for k, v in SP_DEFAULT.items()}
rows_b = [("Investment-grade bonds: defaults", SP_DEFAULT["Investment grade"], LGREY),
          ("DeFi: hacks, excluding bridges", pooled_nob, BLUE),
          ("DeFi: all hacks", pooled, BLUE),
          ("Junk bonds: defaults", SP_DEFAULT["Speculative grade (junk)"], GREY)]
fig = create_default_figure(xlabel="Share hit each year, before any recovery (DeFi: dollars; bonds: issuers)",
                            source_text="DefiLlama: hacks on DeFi protocols over average DeFi deposits, 2021 to 10 Oct 2026 (2026 annualised). "
                                        "Bonds: S&P average one-year<br>default rates, 1981-2024. Both before recoveries. Bond rates count "
                                        "issuers, DeFi counts dollars.<br>DeFi counts hacks only, not frauds, depegs or failed loans.",
                            ysource_text_offset=0.36, width=1000, height=500)
fig.add_bar(y=[r[0] for r in rows_b], x=[r[1] for r in rows_b], orientation="h", marker_color=[r[2] for r in rows_b],
            showlegend=False, text=[f"{r[1]:.2f}%" for r in rows_b], textposition="outside",
            textfont=dict(family=FONT, size=18, color=BLACK), cliponaxis=False)
fig.update_layout(margin=dict(l=300, r=80, t=20, b=150), bargap=0.35)
fig.update_yaxes(autorange="reversed", showgrid=False)
fig.update_xaxes(range=[0, 4.1], ticksuffix="%", showgrid=True, gridcolor="lightgray")
fig.layout.annotations[0].update(x=-0.42)
save(fig, "fig_defi_vs_bond_losses", *[f"{y} {r:.2f}%" for y, r in rate.items()], f"pooled 2021-26 {pooled:.2f}%",
     f"pooled ex-bridge {pooled_nob:.2f}%", *[f"{k} {v:.3f}%" for k, v in bond.items()])

# ============================================================ Rating agencies are coming onchain: timeline
EVENTS = [
    ("2023-04-25", "S&P backs Credora's<br>&#36;6mn round", 1),
    ("2025-08-07", "S&P rates Sky B-, its first<br>rating of a DeFi protocol", -1),
    ("2025-09-04", "RedStone buys<br>Credora", 1),
    ("2025-11-26", "S&P cuts Tether's<br>stability score to 'weak'", -1),
    ("2026-09-01", "S&P launches indices<br>with Kaiko", 1),
    ("2026-09-14", "S&P leads investment<br>in Kaiko", -1),
    ("2026-09-17", "S&P agrees to buy<br>OpenZeppelin", 1.9),
    ("2026-10-04", "S&P launches Vault<br>Risk Assessments", -1.9),
    ("2026-10-07", "Moody's rates<br>Sky B3", 2.8),
]
fig = go.Figure()
n = len(EVENTS)
ys = list(range(n, 0, -1))
fig.add_scatter(x=[0.0] * n, y=ys, mode="lines+markers", line=dict(color=LGREY, width=2),
                marker=dict(size=13, color=[GREY if t.startswith("RedStone") else NAVY if t.startswith("Moody") else BLUE for _, t, _ in EVENTS]),
                showlegend=False)
for (d, t, _), y in zip(EVENTS, ys):
    fig.add_annotation(x=-0.04, y=y, text=f"<b>{pd.Timestamp(d):%-d %b %Y}</b>", showarrow=False, xanchor="right",
                       font=dict(family=FONT, size=16, color=BLACK))
    fig.add_annotation(x=0.04, y=y, text=t.replace("<br>", " "), showarrow=False, xanchor="left",
                       font=dict(family=FONT, size=16, color=BLACK))
first14 = [y for (d, t, _), y in zip(EVENTS, ys) if pd.Timestamp(d) >= pd.Timestamp("2025-08-01")]
n_agency = sum(1 for d, t, _ in EVENTS if pd.Timestamp(d) >= pd.Timestamp("2025-08-01") and not t.startswith("RedStone"))
fig.add_shape(type="line", x0=0.92, x1=0.92, y0=min(first14) - 0.2, y1=max(first14) + 0.2, line=dict(color=BLUE, width=3))
fig.add_annotation(x=0.95, y=(min(first14) + max(first14)) / 2, text=f"<b>{n_agency} S&P and<br>Moody's moves<br>in 14 months</b>",
                   showarrow=False, xanchor="left", font=dict(family=FONT, size=18, color=BLUE))
fig.update_layout(width=1000, height=600, plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=20, r=20, t=20, b=60),
                  xaxis=dict(visible=False, range=[-0.45, 1.2]), yaxis=dict(visible=False, range=[0.4, n + 0.6]))
fig.add_annotation(text="Sources: CoinDesk (2023, 2026); The Block (2025, 2026); RedStone (2025); Reuters (2025); S&P Global press releases (2026).",
                   xref="paper", yref="paper", x=0, y=-0.07, showarrow=False, xanchor="left",
                   font=dict(family=FONT, size=14, color="grey"))
save(fig, "fig_agencies_timeline", f"{len(EVENTS)} events", f"agency moves since Aug 2025: {n_agency}")

# ============================================================ The trust toolkit: what TradFi built vs crypto today
rows = [
    ("Credit ratings", "Moody's, 1909", "Investors could not compare bonds", "Arriving: S&P, Moody's, Credora"),
    ("Default studies", "Moody's data from 1920", "Ratings could not be checked", "None published"),
    ("Value at Risk", "JPMorgan RiskMetrics, 1994", "No common number for market risk", "Many versions, no standard"),
    ("Credit risk models", "JPMorgan CreditMetrics, 1997", "VaR could not see defaults", "None"),
    ("Deposit insurance", "FDIC, 1933", "Bank runs", "None at scale"),
]
fig = go.Figure(go.Table(
    columnwidth=[1.1, 1.4, 1.6, 1.5],
    header=dict(values=["<b>Tool</b>", "<b>Who and when</b>", "<b>What it fixed</b>", "<b>Crypto today</b>"],
                fill_color=[BLUE, BLUE, BLUE, NAVY], font=dict(family=FONT, size=16, color="white"), align="left", height=40),
    cells=dict(values=list(zip(*rows)), fill_color=[["white", "#F7F7F7"] * 3], align="left", height=42,
               font=dict(family=FONT, size=15, color=[[BLACK] * 5, [BLACK] * 5, [BLACK] * 5, [BLUE] * 5]))))
fig.update_layout(width=1100, height=320, margin=dict(l=10, r=10, t=10, b=40), paper_bgcolor="white")
fig.add_annotation(text="Sources: Moody's (2007); MSCI RiskMetrics and CreditMetrics technical documents; FDIC; authors' review.",
                   xref="paper", yref="paper", x=0, y=-0.08, showarrow=False, xanchor="left",
                   font=dict(family=FONT, size=14, color="grey"))
save(fig, "fig_trust_toolkit", "5 rows")


# ============================================================ What victims got back: the eight largest DeFi hacks
# Hand-verified (14 Oct 2026) from post-mortems and news; BNB Bridge and PlayDapp excluded (newly minted tokens, not user funds).
rc = pd.read_csv(PROC / "v2_top_hacks_recovery.csv")
cols = ["from_attacker_or_freeze_mn", "paid_by_backer_mn", "not_recovered_mn"]
tot = rc[["stolen_mn"] + cols].sum()
rc = rc.assign(order=rc.not_recovered_mn / rc.stolen_mn).sort_values(["order", "stolen_mn"], ascending=[False, True])
labels = [f"{h} ({d[:4]}), &#36;{v:,.0f}mn" for h, d, v in zip(rc.hack, rc.date, rc.stolen_mn)] + [f"<b>All eight, &#36;{tot.stolen_mn / 1000:.1f}bn</b>"]
fig = create_default_figure(
                            source_text="Protocol post-mortems; The Block, Blockworks, Decrypt (2021-2026). Eight largest DeFi-protocol hacks "
                                        "in DefiLlama, excluding two mint<br>exploits (BNB Bridge, PlayDapp). Approximate, at prices on the day. "
                                        "Ronin: users were repaid; the unrecovered part was the Axie DAO treasury.",
                            ysource_text_offset=0.3, ylegend_offset=0.22, width=1000, height=640)
for col, nm, c in (("from_attacker_or_freeze_mn", "Returned by the attacker or frozen by a chain", GREY),
                   ("paid_by_backer_mn", "Paid by a backer that chose to step in", BLUE),
                   ("not_recovered_mn", "Not recovered", LGREY)):
    vals = list(rc[col] / rc.stolen_mn * 100) + [tot[col] / tot.stolen_mn * 100]
    fig.add_bar(y=labels, x=vals, orientation="h", name=nm, marker_color=c,
                text=[f"{v:.0f}%" if v >= 8 else "" for v in vals], textposition="inside", insidetextanchor="middle",
                textfont=dict(family=FONT, size=14, color="white" if c != LGREY else BLACK))
fig.update_layout(barmode="stack", margin=dict(l=330, r=40, t=20, b=150), legend=dict(traceorder="normal"))
fig.update_yaxes(showgrid=False, autorange="reversed")
fig.update_xaxes(range=[0, 100], ticksuffix="%", showgrid=False)
fig.layout.annotations[0].update(x=-0.48)
save(fig, "fig_who_paid_back", f"stolen ${tot.stolen_mn:,.0f}mn", f"attacker/freeze {tot.from_attacker_or_freeze_mn / tot.stolen_mn:.0%}",
     f"backer {tot.paid_by_backer_mn / tot.stolen_mn:.0%}", f"lost {tot.not_recovered_mn / tot.stolen_mn:.0%}")


# ============================================================ VaR vs loss, every stablecoin break (systematic)
vb = pd.read_csv(PROC / "v2_var_all_breaks.csv").dropna(subset=["var99"]).sort_values("loss")
short = {"TerraClassicUSD": "TerraUSD (UST)", "USDX Money USDX": "Stables Labs USDX", "Magic Internet Money": "Magic Internet Money (MIM)",
         "Resolv USD": "Resolv USR", "Elixir deUSD": "Elixir deUSD", "YUSD Stablecoin": "YUSD"}
lab = [short.get(c, c) for c in vb.coin]
fig = create_default_figure(
                            source_text="DefiLlama daily prices and supply. All 21 stablecoins that broke their peg (below &#36;0.95 for 3+ days, "
                                        "&#36;10mn+ supply)<br>with 30+ days of earlier prices. VaR: 1-day 99% historical, 90 days ending a week "
                                        "before the break; 30-day version<br>scaled by the square root of 30. Loss: last earlier price to the low within 30 days.",
                            ysource_text_offset=0.19, ylegend_offset=0.08, width=1000, height=920)
for x0, x1, y in zip(vb.var99, vb.loss, lab):
    fig.add_scatter(x=[x0, x1], y=[y, y], mode="lines", line=dict(color=LGREY, width=2), showlegend=False, hoverinfo="skip")
fig.add_scatter(x=vb.var99, y=lab, mode="markers", marker=dict(size=12, color=GREY), name="1-day VaR (99%)")
fig.add_scatter(x=vb.var99_30d, y=lab, mode="markers", marker=dict(size=11, color="white", line=dict(color=GREY, width=2)),
                name="VaR scaled to 30 days")
fig.add_scatter(x=vb.loss, y=lab, mode="markers", marker=dict(size=12, color=BLUE), name="What holders lost within 30 days")
med_v, med_l = vb.var99.median(), vb.loss.median()
fig.add_annotation(x=0.98, xref="paper", y=0.40, yref="paper", xanchor="right", showarrow=False, align="right",
                   text=f"<b>Median: 1-day VaR {med_v:.1f}%, 30-day {vb.var99_30d.median():.0f}%, actual loss {med_l:.0f}%</b><br>"
                        f"Loss exceeded the 30-day VaR in {(vb.loss > vb.var99_30d).sum()} of {len(vb)} cases",
                   font=dict(family=FONT, size=16, color=BLACK), bgcolor="white")
fig.update_layout(margin=dict(l=230, r=40, t=20, b=230))
fig.update_xaxes(range=[0, 102], ticksuffix="%", showgrid=True, gridcolor="lightgray")
fig.update_yaxes(showgrid=False, tickfont=dict(family=FONT, size=14))
fig.layout.annotations[0].update(x=-0.26)
save(fig, "fig_var_vs_loss", f"n {len(vb)}", f"median VaR {med_v:.2f}%", f"median loss {med_l:.1f}%")


# ============================================================ submission copies, named as in the draft's placeholders
import shutil
SUB = OUT / "submission"; SUB.mkdir(exist_ok=True)
for src, dst in (("fig_trust_toolkit", "figure1_trust-toolkit"), ("fig_agencies_timeline", "figure2_agencies-timeline"),
                 ("fig_var_vs_loss", "figure3_var-vs-actual-loss"), ("fig_stablecoin_breaks", "figure4_stablecoin-breaks-by-design"),
                 ("fig_defi_vs_bond_losses", "figure5_defi-vs-bond-losses"), ("fig_who_paid_back", "figure6_who-paid-back")):
    shutil.copy(OUT / f"{src}.png", SUB / f"{dst}.png")
print("submission copies:", len(list(SUB.glob("*.png"))))
