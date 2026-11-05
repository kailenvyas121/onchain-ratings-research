"""
Article chart set in the Coinbase Institutional house style (scripts/house_style.py, unchanged).

No titles inside the charts (the note carries "Chart N." captions), y-gridlines only, black axis lines,
legend below, one grey "Sources:" footnote bottom-left. Every value is read from data/processed or data/raw;
each chart prints its headline numbers after saving so the figure and the prose come from one run.

Writes 2_Charts/final/chart1..chart7.png and table1.png (project root)
"""
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from house_style import BLACK, BLUE, FONT, GREY, LGREY, NAVY, TABLE_ROW, create_default_figure  # noqa: E402
from src.rating import POOLS, PROC, RAW, ROOT, load_grades, load_pool, load_protocol_tvl  # noqa: E402

OUT = ROOT.parent / "2_Charts" / "final"  # project root; superseded sets live in 2_Charts/archive
OUT.mkdir(parents=True, exist_ok=True)
g = load_grades()
g["tvl"] = [load_pool(POOLS[a][1]).tvl.get(d, np.nan) if POOLS[a][1] else np.nan for a, d in zip(g.address, g.date)]
M = "−"  # typographic minus


def neg(v, fmt="{:+.2f}"):
    out = fmt.format(v)
    if out.lstrip("+-") == fmt.format(0).lstrip("+-"):  # rounds to zero: no sign
        return out.lstrip("+-")
    return out.replace("-", M)


def save(fig, name, *headline):
    fig.write_image(OUT / f"{name}.png", scale=2)
    print(f"{name}: " + "; ".join(headline))


# ===================================================================== Chart 1: what the letters mean
show_a = 100 * g.rating.isin(["A+", "A", "A-"]).mean()
ig_c = 100 * g.investment_grade.mean()
ig_sp = 100 * pd.read_csv(PROC / "extra_independent_mapping.csv").ig_by_sp_default.mean()
dw = g.dropna(subset=["tvl"])
dep = 100 * (dw.investment_grade * dw.tvl).sum() / dw.tvl.sum()
cats = ["Grades that display an ‘A’", "Investment grade by Credora's<br>own conversion table",
        "Investment grade by S&P's<br>historical default rates", "Rated deposits in investment-<br>grade-equivalent vaults"]
vals = [show_a, ig_c, ig_sp, dep]
fig = create_default_figure(
    source_text='Credora, S&P Global Ratings, DefiLlama. 260 weekly grades on 10 vaults, Feb to Oct 2026. S&P basis: loss probability at or below 0.245%.',
    ysource_text_offset=0.3, width=1000, height=540)
fig.add_bar(y=cats, x=vals, orientation="h", marker_color=[LGREY, GREY, GREY, BLUE], showlegend=False,
            text=[f"{v:.0f}%" for v in vals], textposition="outside", textfont=dict(family=FONT, size=18, color=BLACK),
            cliponaxis=False)
fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(family=FONT, size=16))
fig.update_xaxes(range=[0, 100], ticksuffix="%", showgrid=True, gridcolor="lightgray", title="Share of grades or deposits",
                 title_font=dict(family="Helvetica, Arial", size=18))
fig.update_layout(margin=dict(l=300, r=60, t=30, b=130), yaxis=dict(showgrid=False))
fig.layout.annotations[0].update(x=-0.42)
save(fig, "chart1_translation", f"display A {show_a:.1f}%", f"IG Credora {ig_c:.1f}%", f"IG S&P {ig_sp:.1f}%", f"deposits {dep:.1f}%")

# ===================================================================== Chart 2: grades cross the line
ROWS = ["A+", "A", "A-", "B+", "B", "B-"]
crossed = sorted([(POOLS[a][0], x.sort_values("date")) for a, x in g.groupby("address") if x.investment_grade.nunique() > 1],
                 key=lambda t: -t[1].tvl.median())
n_cross = {n: int((x.investment_grade.astype(int).diff().abs() > 0).sum()) for n, x in crossed}


def sub_title(n, x):
    med = x.tvl.median() / 1e6
    size = f"median deposits ${med:,.0f}mn" if med >= 10 else f"deposits under ${max(x.tvl.max() / 1e6, 1):.0f}mn"
    k = n_cross[n]
    return f"{n}: {k} crossing{'s' if k != 1 else ''}, {size}"


fig = make_subplots(rows=len(crossed), cols=1, shared_xaxes=True, vertical_spacing=0.075,
                    subplot_titles=[sub_title(n, x) for n, x in crossed])
for i, (n, x) in enumerate(crossed, 1):
    y = [ROWS.index(r) for r in x.rating]
    fig.add_trace(go.Scatter(x=x.date, y=y, mode="lines+markers", line_shape="hv", line=dict(color=BLUE, width=2.5),
                             marker=dict(size=5, color=BLUE), showlegend=False), row=i, col=1)
    fig.add_hline(y=1.5, line=dict(color=BLACK, width=1, dash="dash"), row=i, col=1)
    lo, hi = min(y + [1]), max(y + [2])
    fig.update_yaxes(tickvals=list(range(lo, hi + 1)), ticktext=ROWS[lo:hi + 1], range=[hi + 0.5, lo - 0.5],
                     showgrid=True, gridcolor="lightgray", linecolor="black", linewidth=0.75,
                     tickfont=dict(family=FONT, size=14, color="black"), row=i, col=1)
    fig.update_xaxes(linecolor="black", linewidth=0.75, showgrid=False, tickfont=dict(family=FONT, size=15, color="black"),
                     dtick="M1", tickformat="%b %Y", row=i, col=1)
for a in fig.layout.annotations:
    a.update(x=0, xanchor="left", font=dict(family=FONT, size=15, color="black"))
fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=BLUE, width=2.5), name="Credora grade on each weekly report"))
fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=BLACK, width=1, dash="dash"),
                         name="Investment-grade line (A and above = BBB- or better)"))
fig.update_layout(width=1000, height=760, plot_bgcolor="white", paper_bgcolor="white", font=dict(family=FONT),
                  margin=dict(l=70, r=40, t=40, b=150),
                  legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.49, font=dict(family=FONT, size=15)))
fig.add_annotation(text="Sources: Credora weekly reports, 3 Feb to 12 Oct 2026.",
                   xref="paper", yref="paper", x=-0.05, y=-0.19, showarrow=False, xanchor="left", align="left",
                   font=dict(family=FONT, size=14, color="grey"))
save(fig, "chart2_crossings", f"{len(crossed)} of {g.address.nunique()} vaults crossed", f"{sum(n_cross.values())} crossings")

# ===================================================================== Chart 3: yield vs the bond staircase
bonds = pd.read_csv(PROC / "bond_spreads.csv").set_index("rating").mean_spread
steps = ["AAA", "AA", "A", "BBB", "BB", "B"]
vs = pd.read_csv(PROC / "vault_spreads.csv")
fs = pd.read_csv(RAW / "fred" / "BAMLC1A0C13Y.csv", na_values=".")
fs.columns = ["d", "v"]
short_ig = fs[(fs.d >= "2026-02-01") & (fs.d <= "2026-10-13")].v.mean()
BUCKET = {"A+": "A", "A": "BBB", "A-": "BB", "B+": "BB", "B": "B", "B-": "B"}
fig = create_default_figure(
    ylabel="Yield over Treasuries<br>(percentage points)",
    source_text='FRED (ICE BofA, DTB3), DefiLlama, Credora. Averages, Feb to Oct 2026; vault yield minus the 3-month T-bill.',
    ysource_text_offset=0.3, ylegend_offset=0.20, width=1000, height=620)
fig.add_bar(x=list(range(6)), y=[bonds[s] for s in steps], marker_color="#E6E6E6", width=0.82, name="Corporate bond spread",
            text=[f"+{bonds[s]:.1f}" for s in steps], textposition="inside", insidetextanchor="end",
            textfont=dict(family=FONT, size=15, color=GREY))
fig.add_scatter(x=[-0.5, 5.5], y=[short_ig, short_ig], mode="lines", line=dict(color=GREY, width=1.5, dash="dot"),
                name=f"1-3 year investment-grade bonds (+{short_ig:.1f})")
placed = {}
for _, r in vs.iterrows():
    b = steps.index(BUCKET[g[g.address == r.address].rating.mode().iloc[0]])
    placed.setdefault(b, []).append(r)
shown = set()
for b, rs in placed.items():
    rs = sorted(rs, key=lambda r: -r.mean_spread)
    groups = []
    for r in rs:
        if groups and abs(groups[-1][0].mean_spread - r.mean_spread) < 0.01:
            groups[-1].append(r)
        else:
            groups.append([r])
    for i, grp in enumerate(groups):
        r = grp[0]
        x = b - 0.22 + 0.16 * i
        gov = r.rate_set_by == "governance"
        nm = "Spark vault (governance rate)" if gov else "Market-rate vault"
        fig.add_scatter(x=[x], y=[r.mean_spread], mode="markers", marker=dict(size=15, color=BLUE if gov else NAVY,
                        symbol="circle" if gov else "diamond"), name=nm, showlegend=nm not in shown)
        shown.add(nm)
        label = " & ".join(v.vault.replace("Spark Savings ", "").replace(" vault", "") for v in grp)
        left = r.mean_spread > bonds[steps[b]]
        on_zero = abs(r.mean_spread) < 0.1  # sits on the zero line: label below the dot, clear of the line and bar
        fig.add_annotation(x=x, y=r.mean_spread, text=f"{label} {neg(r.mean_spread)}", showarrow=False,
                           xanchor="left" if on_zero else ("right" if left else "left"),
                           xshift=10 if on_zero else (-11 if left else 11), yshift=18 if on_zero else 0,
                           font=dict(family=FONT, size=13, color=BLUE if gov else NAVY))
fig.add_hline(y=0, line=dict(color=BLACK, width=1))
fig.update_xaxes(tickvals=list(range(6)), ticktext=steps, range=[-0.6, 5.6])
fig.update_yaxes(range=[-2.6, 3.6], dtick=1)
fig.update_layout(margin=dict(l=115, r=50, t=30, b=200), legend=dict(font=dict(family=FONT, size=15)))
save(fig, "chart3_yield", f"short IG +{short_ig:.2f}", "; ".join(f"{r.vault} {r.mean_spread:+.2f}" for _, r in vs.iterrows()))

# ===================================================================== Chart 4: what moved money, event by event
ev = pd.read_csv(PROC / "grade_events.csv")
ev = ev[ev.status == "tested"].copy()
bnb = pd.read_csv(PROC / "bnb_vault_token_flows.csv")
bmap = dict(zip(bnb.date.astype(str), bnb.flow_7d_bnb_units))
ev["flow"] = [bmap.get(d[:10], f) if v == "Lista BNB vault" else f for v, d, f in zip(ev.vault, ev.date, ev.flow_7d)]
oos = pd.read_csv(PROC / "extra_out_of_sample.csv")
pick = lambda e, s, h: float(oos[(oos.event == e) & (oos.series == s) & (oos.horizon_d == h)].raw_flow_pct.iloc[0])  # noqa: E731
pos = pd.read_csv(PROC / "robustness_positive_control.csv").set_index("series")
down = ev[ev.direction == "downgrade"]
cross = down[down.crosses_ig_line].sort_values("date")
up = ev[(ev.direction == "upgrade") & (ev.flow < -30)].iloc[0]
SHORT = {"Spark Savings USDT": "Spark USDT", "Lista BNB vault": "Lista BNB"}
rows = [("<b>Public warning</b>", None, None),
        ("Morpho xUSD market lenders", pos.flow_6d_pct["Morpho xUSD market (curated-vault lenders)"], BLUE),
        ("Stream deposits", pos.flow_6d_pct["Stream Finance deposits"], BLUE),
        ("Elixir deposits", pos.flow_6d_pct["Elixir deposits"], BLUE),
        ("<b>Agency ratings</b>", None, None),
        ("S&P cuts USDT to \"weak\"", pick("S&P cuts USDT to 5 'weak'", "USDT supply", 7), GREY),
        ("S&P rates Sky B-", pick("S&P rates Sky B- / USDS 4", "Sky supply (USDS+DAI)", 7), GREY),
        ("Moody's rates Sky B3 (3 days)", pick("Moody's rates Sky B3", "Sky supply (USDS+DAI)", 3), GREY),
        ("<b>Credora downgrades</b>", None, None)]
rows += [(f"{SHORT[r.vault]} falls below the line, {pd.Timestamp(r.date):%-d %b}", r.flow, NAVY) for _, r in cross.iterrows()]
rows += [(f"Average of all {len(down)} downgrades", down.flow.mean(), NAVY),
         ("<b>Credora upgrade</b>", None, None),
         (f"Spark USDT upgraded, {pd.Timestamp(up.date):%-d %b}", up.flow, LGREY)]
labels = [r[0] for r in rows]
fig = create_default_figure(
    xlabel="Change in deposits or supply in the week after the event",
    source_text="DefiLlama, Morpho API, Ethereum contracts. 7 days after each event; Moody's 3 days; Stream 28 Oct to 3 Nov 2025.",
    ysource_text_offset=0.20, width=1000, height=660)
vals = [r[1] for r in rows]
fig.add_bar(y=labels, x=[0 if v is None else v for v in vals], orientation="h", showlegend=False,
            marker_color=[r[2] or "white" for r in rows], width=0.72,
            text=["" if v is None else (neg(v, "{:+.1f}") + "%") for v in vals], textposition="outside",
            textfont=dict(family=FONT, size=15, color=BLACK), cliponaxis=False)
fig.add_annotation(x=up.flow, y=labels[-1], text="one wallet withdrew $415mn", showarrow=False, yshift=19, xanchor="center",
                   font=dict(family=FONT, size=13, color=GREY))
fig.add_vline(x=0, line=dict(color=BLACK, width=1))
fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(family=FONT, size=15), categoryorder="array", categoryarray=labels)
fig.update_xaxes(range=[-112, 18], ticksuffix="%", showgrid=True, gridcolor="lightgray", dtick=20, zeroline=False)
fig.update_layout(margin=dict(l=330, r=40, t=30, b=120), bargap=0.25)
fig.layout.annotations[0].update(x=-0.48)
save(fig, "chart4_ratings_vs_warning", "; ".join(f"{l}: {v:+.2f}" for l, v, _ in rows if v is not None))

# ===================================================================== Chart 6: the Morpho xUSD market through the crash and the warning
xd = json.load(open(RAW / "xusd_arb_daily.json"))["data"]["marketById"]["historicalState"]["supplyAssetsUsd"]
xs = pd.Series({pd.Timestamp(dt.datetime.fromtimestamp(p["x"], dt.UTC).date()): p["y"] / 1e6 for p in xd}).sort_index()
xs = xs.loc["2025-10-01":"2025-11-12"]
fig = create_default_figure(
    ylabel="Supplied to the market ($mn)",
    source_text='Morpho API (xUSD/USDC market, Arbitrum, daily), Arunights (warning date), The Block (freeze).',
    ysource_text_offset=0.17, width=1000, height=540)
fig.add_scatter(x=xs.index, y=xs.values, mode="lines", line=dict(color=BLUE, width=3), showlegend=False)
for d, txt, ya in (("2025-10-28", "28 Oct<br>public warning", 0.97), ("2025-11-04", "4 Nov<br>Stream freezes<br>withdrawals", 0.62)):
    fig.add_vline(x=pd.Timestamp(d), line=dict(color=GREY, width=1, dash="dash"))
    fig.add_annotation(x=pd.Timestamp(d), y=ya, yref="paper", text=txt, showarrow=False, xanchor="left", xshift=6, align="left",
                       font=dict(family=FONT, size=14, color=BLACK))
fig.update_xaxes(tickformat="%-d %b", dtick=7 * 86400000)
fig.update_yaxes(rangemode="tozero")
fig.update_layout(margin=dict(l=110, r=50, t=30, b=130))
peak = xs.loc["2025-10-20":"2025-10-28"].max()
save(fig, "chart6_xusd_market", f"28 Oct {xs.get(pd.Timestamp('2025-10-28')):.1f}mn", f"3 Nov {xs.get(pd.Timestamp('2025-11-03')):.2f}mn",
     f"10->16 Oct {xs.get(pd.Timestamp('2025-10-10')):.1f}->{xs.get(pd.Timestamp('2025-10-16')):.1f}mn")

# ===================================================================== Chart 5: USDT supply after S&P's lowest score
def supply(i):
    t = json.load(open(RAW / f"llama_stablecoin_{i}.json"))["tokens"]
    s = pd.Series({pd.Timestamp(dt.datetime.fromtimestamp(x["date"], dt.UTC).date()): x["circulating"].get("peggedUSD", np.nan) for x in t})
    return s[~s.index.duplicated(keep="last")].sort_index()


usdt_s, usdc_s = supply(1), supply(2)
base = pd.Timestamp("2025-11-25")
win = slice("2025-10-26", "2025-12-26")
fig = create_default_figure(
    ylabel="Circulating supply<br>(25 Nov 2025 = 100)",
    source_text="DefiLlama stablecoins, S&P Global Ratings. S&P cut USDT to 5 (\"weak\") on 26 Nov 2025.",
    ysource_text_offset=0.26, ylegend_offset=0.22, width=1000, height=540)
for s, nm, col, w in ((usdt_s, f"USDT (${usdt_s[base] / 1e9:.0f}bn on 25 Nov)", BLUE, 3), (usdc_s, f"USDC (${usdc_s[base] / 1e9:.0f}bn)", GREY, 2.5)):
    z = 100 * s.loc[win] / s[base]
    fig.add_scatter(x=z.index, y=z.values, mode="lines", line=dict(color=col, width=w), name=nm)
fig.add_vline(x=pd.Timestamp("2025-11-26"), line=dict(color=BLACK, width=1, dash="dash"))
fig.add_annotation(x=pd.Timestamp("2025-11-26"), y=0.97, yref="paper", text="S&P: USDT to 5 (\"weak\")", showarrow=False,
                   xanchor="left", xshift=6, font=dict(family=FONT, size=14))
fig.update_xaxes(tickformat="%-d %b", dtick=7 * 86400000)
fig.update_layout(margin=dict(l=110, r=50, t=30, b=150))
d30 = usdt_s[pd.Timestamp("2025-12-25")] - usdt_s[base]
save(fig, "chart5_usdt", f"USDT +{d30 / 1e9:.2f}bn in 30 days ({100 * d30 / usdt_s[base]:+.2f}%)")

# ===================================================================== Chart 7: who makes the risk decisions
cc = pd.read_csv(PROC / "curator_concentration.csv")
v2 = cc[cc.vault_type == "v2"].copy()
top = v2.head(6)
other = 100 - top.share_pct.sum()
labels = list(top.curator.str.replace("Steakhouse Financial", "Steakhouse").str.replace(" + ", " & ", regex=False)) + ["All other curators"]
shares = list(top.share_pct) + [other]
fig = create_default_figure(
    xlabel=f"Share of Morpho V2 vault assets (${v2.total_usd.iloc[0] / 1e9:.1f}bn, {int(v2.vaults.iloc[0]):,} vaults)",
    source_text='Morpho API, V2 vaults, 13 Oct 2026.',
    ysource_text_offset=0.26, width=1000, height=520)
fig.add_bar(y=labels, x=shares, orientation="h", marker_color=[BLUE] * 3 + [LGREY] * 4, showlegend=False,
            text=[f"{v:.1f}%" for v in shares], textposition="outside", textfont=dict(family=FONT, size=16, color=BLACK), cliponaxis=False)
fig.update_yaxes(autorange="reversed", showgrid=False)
fig.update_xaxes(range=[0, 48], ticksuffix="%", showgrid=True, gridcolor="lightgray")
fig.update_layout(margin=dict(l=230, r=60, t=30, b=140))
fig.layout.annotations[0].update(x=-0.28)
save(fig, "chart7_curators", f"top three {top.head(3).share_pct.sum():.1f}%")

# ===================================================================== Table 1 (appendix), house table style
e = pd.read_csv(PROC / "grade_events.csv").assign(_d=lambda d: pd.to_datetime(d.date)).sort_values("_d")
t = pd.DataFrame({"Date": e._d.dt.strftime("%-d %b %Y"), "Vault": e.vault, "Change": e.from_grade + " → " + e.to_grade,
                  "Crosses line": np.where(e.crosses_ig_line, "yes", ""),
                  "Deposits ($mn)": e.tvl_day_minus1_musd.map(lambda v: "" if pd.isna(v) else (f"{v:,.1f}" if v >= 1 else f"{v:.2f}")),
                  "7-day abnormal flow": e.abnormal_7d.map(lambda v: "" if pd.isna(v) else neg(v, "{:+.1f}") + "%"),
                  "Rank (50 = typical)": e.percentile_7d.map(lambda v: "" if pd.isna(v) else f"{v:.0f}"),
                  "Tested": e.status.map(lambda s: "yes" if s == "tested" else "no: under $10mn")})
t.to_csv(OUT / "table1_grade_changes.csv", index=False)
fig = go.Figure(go.Table(columnwidth=[85, 150, 65, 65, 80, 95, 85, 110],
                         header=dict(values=[f"<b>{c}</b>" for c in t.columns], fill_color=BLACK, font=dict(family=FONT, color="white", size=13),
                                     align="left", height=32),
                         cells=dict(values=[t[c] for c in t.columns], fill_color=[["white", TABLE_ROW] * len(t)],
                                    font=dict(family=FONT, size=12, color="black"), align="left", height=26)))
fig.update_layout(width=1000, height=680, margin=dict(l=20, r=20, t=20, b=60), paper_bgcolor="white")
fig.add_annotation(text="Sources: Credora, DefiLlama, Ethereum contracts. Abnormal flow: day −1 to +7, minus the same-platform control.",
                   xref="paper", yref="paper", x=0, y=-0.08, showarrow=False, xanchor="left", align="left", font=dict(family=FONT, size=13, color="grey"))
save(fig, "table1_grade_changes", f"{len(t)} changes")

# ===================================================================== submission copies (Writer's Style Guide: separate files, figureN_description.png)
import shutil  # noqa: E402
SUB = ROOT.parent / "2_Charts" / "submission"
SUB.mkdir(exist_ok=True)
for src, dst in (("chart1_translation", "figure1_credora-grades-investment-grade"), ("chart2_crossings", "figure2_credora-grade-crossings"),
                 ("chart3_yield", "figure3_bond-spreads-vs-vault-yields"), ("chart4_ratings_vs_warning", "figure4_flows-after-ratings-and-warning"),
                 ("chart5_usdt", "figure5_usdt-supply-sp-downgrade"), ("chart6_xusd_market", "figure6_morpho-xusd-market"),
                 ("chart7_curators", "figure7_morpho-curator-shares")):
    shutil.copyfile(OUT / f"{src}.png", SUB / f"{dst}.png")
print(f"submission figures copied to {SUB}")
