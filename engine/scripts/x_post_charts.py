"""
Charts for the X thread "we need onchain rating agencies" (Nov 2026). Written to 2_Charts/x_post/ at 2x.
CLAUDE.md house rules: one message per chart, a title that states the finding, a source line, no dual axes,
#2a78d6 main, #eb6834 contrast, grey for context. Every value comes from data/raw/v2 or data/processed (v2_*).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT / "data/raw/v2", ROOT / "data/processed"
OUT = ROOT.parent / "2_Charts" / "x_post"
OUT.mkdir(parents=True, exist_ok=True)

FONT = "Helvetica, Arial"
MAIN, CONTRAST, GREY, LGREY, BLACK, SRC = "#2a78d6", "#eb6834", "#8A8A8A", "#C4C4C4", "#111111", "#6b6b6b"
MIN_SUPPLY, TH, RUN = 10e6, 0.95, 3

# Dead algorithmic coins DefiLlama no longer lists. Prices: coins.llama.fi (pulled 3 Nov 2026).
# Peak supply above $10mn is hand-sourced (see README, 'Dead coins'), since no free API keeps their supply history.
DEAD_ALGO = {"iron-stablecoin": "IRON (Iron Finance)", "basis-cash": "Basis Cash", "empty-set-dollar": "Empty Set Dollar",
             "dynamic-set-dollar": "Dynamic Set Dollar", "dei-token": "DEI (Deus Finance)"}


def base(title, source, width=1200, height=675, b=110, l=80, t=95):
    fig = go.Figure()
    fig.update_layout(width=width, height=height, plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=l, r=50, t=t, b=b), font=dict(family=FONT, size=17, color=BLACK), showlegend=False,
                      title=dict(text=f"<b>{title}</b>", x=0.02, xanchor="left", y=0.97, yanchor="top",
                                 font=dict(family=FONT, size=27, color=BLACK)))
    fig.update_xaxes(linecolor=BLACK, linewidth=0.75, showgrid=False, tickfont=dict(size=17))
    fig.update_yaxes(linecolor=BLACK, linewidth=0.75, showgrid=True, gridcolor="#e3e3e3", tickfont=dict(size=17))
    fig.add_annotation(text=source, xref="paper", yref="paper", x=-(l - 30) / (width - l - 50), y=0, yshift=-b + 12, xanchor="left", yanchor="bottom",
                       showarrow=False, align="left", font=dict(family=FONT, size=13.5, color=SRC))
    return fig


def save(fig, name, *log):
    fig.write_image(OUT / f"{name}.png", scale=2)
    print(f"{name}: " + "; ".join(log))


def latest(pattern):
    return sorted(RAW.glob(pattern))[-1]


def daily(prices):
    s = pd.DataFrame(prices).drop_duplicates("timestamp")
    s["d"] = pd.to_datetime(s.timestamp, unit="s").dt.normalize()
    return s.groupby("d").price.last()


# ============================================================ 1. Stablecoin supply
s = pd.DataFrame(json.load(open(RAW / "stablecoin_total_latest.json")))
s["d"] = pd.to_datetime(s.date.astype(int), unit="s")
s["bn"] = s.totalCirculatingUSD.apply(lambda d: d.get("peggedUSD", 0)) / 1e9
s = s[s.d >= "2021-01-01"].set_index("d").bn   # DefiLlama undercounts supply before 2020-21
start, end = s.iloc[0], s.iloc[-1]
fig = base(f"Stablecoin supply has grown more than tenfold since 2021, to &#36;{end:.0f}bn",
           f"Source: DefiLlama stablecoins API, total USD-pegged supply, daily, 1 Jan 2021 (&#36;{start:.0f}bn) to {s.index[-1]:%-d %b %Y}.")
fig.add_scatter(x=s.index, y=s.values, mode="lines", line=dict(color=MAIN, width=3), fill="tozeroy", fillcolor="rgba(42,120,214,0.12)")
fig.add_annotation(x=s.index[-1], y=end, text=f"<b>&#36;{end:.0f}bn</b>", showarrow=False, xanchor="right", yanchor="bottom",
                   yshift=8, font=dict(size=20, color=MAIN))
fig.update_yaxes(tickprefix="&#36;", ticksuffix="bn", rangemode="tozero")
save(fig, "x1_stablecoin_supply", f"start {start:.1f}bn", f"end {end:.1f}bn")

# ============================================================ 2. Agencies timeline
EVENTS = [
    ("2023-04-25", "S&P backs Credora's &#36;6mn funding round", GREY),
    ("2025-08-07", "S&P rates Sky B-, its first rating of a DeFi protocol", MAIN),
    ("2025-09-04", "RedStone buys Credora", GREY),
    ("2025-11-26", "S&P cuts Tether's USDT stability score to 'weak'", MAIN),
    ("2026-09-01", "S&P launches crypto indices with Kaiko", MAIN),
    ("2026-09-14", "S&P leads the extension of Kaiko's Series B", MAIN),
    ("2026-09-17", "S&P agrees to buy OpenZeppelin (smart-contract security)", MAIN),
    ("2026-10-04", "S&P launches Vault Risk Assessments, AAA(v) to D(v)", MAIN),
    ("2026-10-07", "Moody's rates Sky B3", CONTRAST),
]
n = len(EVENTS); ys = list(range(n, 0, -1))
fig = base("S&P and Moody's made seven moves into crypto risk in 14 months",
           "Sources: CoinDesk (2023, 2026); The Block (2025, 2026); RedStone (2025); Reuters (2025); S&P Global press releases (2026); "
           "Moody's (2026).", height=720)
fig.add_scatter(x=[0] * n, y=ys, mode="lines+markers", line=dict(color=LGREY, width=2),
                marker=dict(size=15, color=[c for _, _, c in EVENTS]))
for (d, t, c), y in zip(EVENTS, ys):
    fig.add_annotation(x=-0.03, y=y, text=f"<b>{pd.Timestamp(d):%-d %b %Y}</b>", showarrow=False, xanchor="right", font=dict(size=18))
    fig.add_annotation(x=0.03, y=y, text=t, showarrow=False, xanchor="left", font=dict(size=18, color=BLACK))
fig.update_xaxes(visible=False, range=[-0.32, 1.0]); fig.update_yaxes(visible=False, range=[0.4, n + 0.5])
save(fig, "x2_agencies_timeline", f"{n} events")

# ============================================================ 3. The grades so far (table)
rows = [
    ("S&P", "Sky (issuer of USDS)", "B-", "Junk", "Aug 2025"),
    ("Moody's", "Sky (issuer of USDS)", "B3", "Junk", "7 Oct 2026"),
    ("S&P", "Tether USDT (stability score)", "'Weak'", "Bottom of the scale", "Nov 2025"),
    ("S&P", "Vault Risk Assessments", "None yet", "No vault scored by mid-Oct", "4 Oct 2026"),
    ("Credora", "Vaults on Morpho, Spark, Lista", "Mostly 'A'", "Credora maps A to BBB/BBB-", "Feb-Oct 2026"),
]
cols = list(zip(*rows))
grade_color = [CONTRAST, CONTRAST, CONTRAST, GREY, MAIN]
fig = go.Figure(go.Table(
    columnwidth=[0.8, 1.9, 0.9, 1.9, 1.0],
    header=dict(values=[f"<b>{h}</b>" for h in ("Agency", "What was graded", "Grade", "What it means", "When")],
                fill_color=MAIN, font=dict(family=FONT, size=19, color="white"), align="left", height=48),
    cells=dict(values=cols, fill_color=[["white", "#f4f6f9"] * 3], align="left", height=52,
               font=dict(family=FONT, size=18, color=[[BLACK] * 5, [BLACK] * 5, grade_color, [BLACK] * 5, [GREY] * 5]))))
fig.update_layout(width=1200, height=520, paper_bgcolor="white", margin=dict(l=30, r=30, t=95, b=90),
                  title=dict(text="<b>S&P and Moody's have not given any DeFi protocol an investment grade</b>", x=0.02, y=0.96,
                             font=dict(family=FONT, size=27, color=BLACK)))
fig.add_annotation(text="Sources: S&P Global (Aug 2025, Nov 2025, Oct 2026); Moody's (Oct 2026); Credora public rating archive and "
                        "methodology (Feb-Oct 2026).<br>Investment grade = BBB-/Baa3 or above. Four in five Credora grades from "
                        "Feb to Oct 2026 were 'A'. S&P says a Vault Risk Assessment 'is not a credit rating'.",
                   xref="paper", yref="paper", x=0, y=0, yshift=-80, xanchor="left", yanchor="bottom", showarrow=False, align="left",
                   font=dict(family=FONT, size=13.5, color=SRC))
save(fig, "x3_grades_so_far", f"{len(rows)} rows")

# ============================================================ 4. Peg breaks by design, with the dead algorithmic coins added back
res = []
for f in sorted((RAW / "stable_prices").glob("*.json")):
    m = json.loads(f.read_text()); sf = RAW / "stable_supply" / f.name
    if not m["prices"] or not sf.exists(): continue
    p = daily(m["prices"])
    sp = pd.DataFrame(json.loads(sf.read_text()), columns=["t", "supply"]); sp["d"] = pd.to_datetime(sp.t, unit="s").dt.normalize()
    df = pd.concat([p, sp.groupby("d").supply.last()], axis=1, sort=True); df["supply"] = df.supply.ffill(); df = df.dropna(subset=["price"])
    if not (df.supply >= MIN_SUPPLY).any(): continue
    b = df.price < TH; r = b.groupby((~b).cumsum()).cumsum()
    res.append(dict(coin=m["name"], mech=(m["mech"] or "").replace("crytpo", "crypto"),
                    broke=bool(((r >= RUN) & (df.supply.shift(RUN) >= MIN_SUPPLY)).any()), listed=True))
for gid, nm in DEAD_ALGO.items():
    p = []
    for chunk in json.load(open(latest(f"stable_prices_dead/{gid}_*.json"))):
        p += next(iter(chunk.get("coins", {}).values()), {}).get("prices", [])
    b = daily(p) < TH; r = b.groupby((~b).cumsum()).cumsum()
    res.append(dict(coin=nm, mech="algorithmic", broke=bool((r >= RUN).any()), listed=False))
res = pd.DataFrame(res)
res.to_csv(PROC / "x_post_breaks_by_coin.csv", index=False)
g = res.groupby("mech").broke.agg(["sum", "size"]); g["pct"] = g["sum"] / g["size"] * 100
mechs = [("fiat-backed", "Backed by cash<br>and Treasuries", GREY), ("crypto-backed", "Backed by crypto or<br>trading strategies", MAIN),
         ("algorithmic", "Algorithmic", CONTRAST)]
fig = base(f"{int(g.loc['algorithmic', 'sum'])} of {int(g.loc['algorithmic', 'size'])} algorithmic stablecoins have broken their peg",
           "Sources: DefiLlama stablecoin prices and supply, 2019 to Oct 2026; coins.llama.fi prices for five dead algorithmic coins DefiLlama "
           "no longer lists<br>(IRON, Basis Cash, Empty Set Dollar, Dynamic Set Dollar, DEI). Coins that reached &#36;10mn in supply. "
           "Break: below &#36;0.95 for 3+ days in a row.", height=700, b=120)
fig.add_bar(x=[m[1] for m in mechs], y=[g.loc[m[0], "pct"] for m in mechs], marker_color=[m[2] for m in mechs], width=0.55)
for m in mechs:
    fig.add_annotation(x=m[1], y=g.loc[m[0], "pct"], yanchor="bottom", yshift=6, showarrow=False,
                       text=f"<b>{g.loc[m[0], 'pct']:.0f}%</b><br>{int(g.loc[m[0], 'sum'])} of {int(g.loc[m[0], 'size'])} coins",
                       font=dict(size=20, color=BLACK))
fig.update_yaxes(range=[0, 100], ticksuffix="%", title=dict(text="Share that ever broke its peg", font=dict(size=17)))
save(fig, "x4_peg_breaks_by_design", *[f"{k} {int(v['sum'])}/{int(v['size'])}" for k, v in g.iterrows()])

# ============================================================ 5. Hack losses by cause (refreshed 3 Nov 2026: includes Binance, 29 Oct 2026)
h = pd.DataFrame(json.load(open(latest("hacks_*.json"))))
h["dt"] = pd.to_datetime(h.date, unit="s"); h["yr"] = h.dt.dt.year
h = h[(h.yr >= 2020) & ~h.name.str.contains("LuBian", case=False)]   # 2020 mining-pool theft, disclosed in 2025, not onchain finance
by = h.groupby("classification").amount.sum().sort_values(ascending=False) / h.amount.sum() * 100
top = by.head(8); other = by.iloc[8:].sum()
OPS = ("Key Compromise", "Social Engineering", "Frontend & Infrastructure")
lab = {"Key Compromise": "Stolen or leaked private keys", "Social Engineering": "People tricked (phishing, fake signers)",
       "Frontend & Infrastructure": "Servers, laptops and websites breached", "Bridge & Cross-Chain": "Bridge and cross-chain flaws",
       "Access Control": "Access-control bugs", "Token & Share Accounting": "Token accounting bugs",
       "Oracle Manipulation": "Price-feed (oracle) manipulation", "Input Validation": "Input-validation bugs", "Protocol Logic": "Protocol logic bugs"}
names = [lab.get(k, k) for k in top.index] + ["Everything else"]
vals = list(top.values) + [other]
colors = [CONTRAST if k in OPS else GREY for k in top.index] + [LGREY]
ops = sum(by.get(k, 0) for k in OPS)
bn = h[h.name == "Binance CEX"].amount.sum() / 1e9
fig = base(f"{ops:.0f}% of crypto hack losses came from keys, people and servers, not code",
           f"Source: DefiLlama hacks database, accessed 3 Nov 2026. {len(h):,} incidents, Jan 2020 to {h.dt.max():%-d %b %Y}, "
           f"&#36;{h.amount.sum() / 1e9:.1f}bn in total, valued on the day. Includes the<br>&#36;{bn:.1f}bn Binance breach "
           "(29 Oct 2026, preliminary). Excludes the &#36;3.5bn LuBian mining-pool theft (2020, disclosed in 2025). Cause as classified by DefiLlama.",
           height=700, b=120, l=400)
fig.add_bar(y=names, x=vals, orientation="h", marker_color=colors, text=[f"{v:.0f}%" for v in vals], textposition="outside",
            textfont=dict(size=18, color=BLACK), cliponaxis=False)
fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=17))
fig.update_xaxes(ticksuffix="%", showgrid=True, gridcolor="#e3e3e3", range=[0, max(vals) * 1.15])
save(fig, "x5_hack_losses_by_cause", f"ops {ops:.1f}%", f"n {len(h)}", f"${h.amount.sum() / 1e9:.2f}bn", f"binance {bn:.2f}bn",
     *[f"{k} {v:.1f}%" for k, v in top.items()])

# ============================================================ 6. VaR vs what holders lost
vb = pd.read_csv(PROC / "v2_var_all_breaks.csv").dropna(subset=["var99"]).sort_values("loss")
short = {"TerraClassicUSD": "TerraUSD (UST)", "USDX Money USDX": "Stables Labs USDX", "Magic Internet Money": "Magic Internet Money",
         "Resolv USD": "Resolv USR", "YUSD Stablecoin": "YUSD"}
lab6 = [short.get(c, c) for c in vb.coin]
med30, medl = vb.var99_30d.median(), vb.loss.median()
fig = base(f"Risk models expected a {med30:.0f}% loss. The median stablecoin lost {medl:.0f}%",
           f"Source: DefiLlama daily prices and supply. All {len(vb)} stablecoins that broke their peg (below &#36;0.95 for 3+ days, "
           "&#36;10mn+ supply) with 30+ days of earlier prices.<br>Value at Risk (VaR): 99% one-day historical from the 90 days ending a "
           "week before the break, scaled to 30 days by the square root of 30. Loss: last earlier price to the low within 30 days.",
           width=1200, height=1100, b=120, l=230)
for x0, x1, y in zip(vb.var99_30d, vb.loss, lab6):
    fig.add_scatter(x=[x0, x1], y=[y, y], mode="lines", line=dict(color=LGREY, width=2), hoverinfo="skip", showlegend=False)
fig.add_scatter(x=vb.var99_30d, y=lab6, mode="markers", marker=dict(size=14, color=GREY), name="What the risk model expected (30-day VaR)")
fig.add_scatter(x=vb.loss, y=lab6, mode="markers", marker=dict(size=14, color=CONTRAST), name="What holders actually lost within 30 days")
fig.update_layout(showlegend=True, legend=dict(orientation="h", x=0, y=1.0, yanchor="bottom", font=dict(size=17)), margin=dict(t=150))
fig.update_xaxes(range=[0, 102], ticksuffix="%", showgrid=True, gridcolor="#e3e3e3")
fig.update_yaxes(showgrid=False, tickfont=dict(size=16))
save(fig, "x6_var_vs_actual_loss", f"n {len(vb)}", f"median 30d VaR {med30:.1f}%", f"median loss {medl:.1f}%",
     f"loss > VaR30 in {(vb.loss > vb.var99_30d).sum()}")

# ============================================================ 7. Who paid back after the biggest hacks
rc = pd.read_csv(PROC / "v2_top_hacks_recovery.csv")
parts = [("from_attacker_or_freeze_mn", "Returned by the attacker or frozen", GREY),
         ("paid_by_backer_mn", "Paid by a backer that chose to step in", MAIN),
         ("not_recovered_mn", "Never recovered", CONTRAST)]
tot = rc[["stolen_mn"] + [p[0] for p in parts]].sum()
rc = rc.assign(o=rc.not_recovered_mn / rc.stolen_mn).sort_values(["o", "stolen_mn"], ascending=[False, True])
labels = [f"{a} ({d[:4]}), &#36;{v:,.0f}mn" for a, d, v in zip(rc.hack, rc.date, rc.stolen_mn)] + [f"<b>All eight, &#36;{tot.stolen_mn / 1000:.1f}bn</b>"]
backer = tot.paid_by_backer_mn / tot.stolen_mn * 100
fig = base("After the biggest DeFi hacks, recovery depended on attackers and backers, not courts",
           "Sources: protocol post-mortems; The Block, Blockworks, Decrypt (2021-2026). Eight largest DeFi-protocol hacks in DefiLlama, excluding "
           "two mint exploits<br>(BNB Bridge, PlayDapp). Approximate, at prices on the day. Ronin: users were repaid; the unrecovered part was "
           "the Axie DAO treasury.", height=760, b=120, l=330)
for col, nm, c in parts:
    v = list(rc[col] / rc.stolen_mn * 100) + [tot[col] / tot.stolen_mn * 100]
    fig.add_bar(y=labels, x=v, orientation="h", name=nm, marker_color=c, text=[f"{x:.0f}%" if x >= 8 else "" for x in v],
                textposition="inside", insidetextanchor="middle", textfont=dict(size=16, color="white"))
fig.update_layout(barmode="stack", showlegend=True, legend=dict(orientation="h", x=0, y=1.01, yanchor="bottom", font=dict(size=16), traceorder="normal"),
                  margin=dict(t=135))
fig.update_yaxes(autorange="reversed", showgrid=False)
fig.update_xaxes(range=[0, 100], ticksuffix="%")
save(fig, "x7_who_paid_back", f"stolen {tot.stolen_mn:.0f}mn", *[f"{p[0]} {tot[p[0]] / tot.stolen_mn:.1%}" for p in parts])
