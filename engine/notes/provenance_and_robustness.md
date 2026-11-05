# Where every number comes from, and why it isn't overfit (13 Oct 2026)

Run everything: `python engine/run_all.py`. The pipeline is offline. Only `update_data.py` and `check_onchain_tvl.py` use the network.

## 1. Number → source → formula → check

| Headline number | Raw input (data/raw) | Script and formula | Independent check |
|---|---|---|---|
| **260 grades, 10 vaults, 3 Feb–12 Oct 2026** | `credora_reports/REP-*.txt` (pdftotext of the public PDFs listed in `credora_index.xml`) | `build_credora_panel.py`: regex on each table row (address, PSL, letter); latest version per day; vaults keyed by address | `verify` #1: a token-split re-parse with different code gives the same 260, with 0 letter mismatches |
| **Letter → bond grade** (A- = BB+/BB, …) | `credora_scale.png` (Credora's own table) | `src/rating.py` `SCALE` | `verify` #2: all 260 PSLs sit inside their letter's band |
| **36.9% investment grade** (count-weighted) | the grades above | share of grades that are A+ or A | `verify` #3 recount. Also vault-weighted 39.7%, first half 29.9%, second half 41.8% (`robustness` R8) |
| **Deposit-weighted: 3.3%** (16.3% without sUSDS); latest day: **0.9% of $6.8bn** | grades + DefiLlama deposits on each report day | `robustness` R8 | sUSDS (the $5bn vault) checked on-chain: 5,037.8mn vs DefiLlama 5,038.3mn |
| **20 changes, 12 crossings** | grades | consecutive reports with a different letter; a crossing = A/A+ on one side only | `verify` #3 recount |
| **Yield gap vs same-grade bond** (Spark −1.3 to −2.3 pts; Staked USDS +0.2) | `llama_charts/{pool}.json` (APY), `fred/*.csv` | `build_yield_spreads.py`: each day: APY − T-bill (as of that day) − ICE spread of the grade in force that day; mean over days with $10M+ | `verify` #10 recomputes Spark USDC by hand (−1.745) |
| **Abnormal 7-day flow per event** | DefiLlama deposits; on-chain `totalAssets()` fills missing days | `build_grade_events.py`: (vault day +7 / day −1 − 1) − same for the control | `verify` #9 recomputes all 12 from the raw files; `verify` #12 matches DefiLlama to the contracts (median 0.02%, max 0.10%) |
| **Placebo percentile** | same | the event's rank among the same vault's ordinary days (±10 days around any change excluded) | `verify` #7 (centred); `robustness` R2 (calibrated at 5.0%) |
| **Stream: 3 / 77 / 80** | `xusd_arb_hourly.json` (Morpho), `llama_stream-finance.json`, `llama_elixir.json` | `build_stream_reaction.py`: index = value / value at or before 28 Oct 00:00 UTC | `verify` #8; `robustness` R6 ranks it against each series' own history |
| **Lista vault identities** | `lista_onchain_2026-10-13.json` | `asset()` + `totalAssets()` on BNB Chain | `verify` #11: each matches its DefiLlama pool within 2% |

## 2. Hindsight and look-ahead: what could leak, and what stops it

| Risk | Guard | Status |
|---|---|---|
| Using a grade before it was public | Grade dated to its PDF's date, never earlier | ✔ |
| **The grade was public earlier than the PDF** (reports say API ratings "may be updated within 24 hours") | Spec curve also starts the window at day −3 and −7 | ✔ Same result |
| The grade followed money (reverse causality) | Pre-trend: flow from day −8 to −1 | ✔ None (+0.7%, p = 0.54) |
| Using a T-bill or bond spread printed later | `asof()`: latest print on or before the day, at most 7 days old | ✔ Unit-tested |
| DefiLlama back-filling or glitches | Checked against the vault contracts at the snapshot hour | ✔ Spark: max 0.10%. ✘ Lista history can't be checked (no BNB archive RPC) |
| Choosing vaults by outcome | Every vault with an address table in Credora's public archive is in. None were picked | ✔ |
| Choosing Stream because we know it failed | Stream is labelled a **positive control**: it shows the test *can* see a run. It is not evidence about rated vaults | ✔ Framing |
| Using the 2026 scale on February grades | All 260 grades fit the current bands | Partly: needs a Feb 2026 Wayback copy |

## 3. Overfitting: did our choices create the result?

The test was written down before the results (README, pre-registered table). Every choice made after seeing data is logged:

| Change after seeing data | Effect | Biased toward the thesis? |
|---|---|---|
| Name keys → address keys (Lista name swap) | 13 vaults → 10; crossings 11 → 11 | No: a data-correctness fix |
| Parser reads the second table layout | +6 grades; crossings 11 → 12 | No: adds data |
| Lista vaults mapped on-chain | +4 tested events | No: adds data |
| On-chain fill of DefiLlama's July gap | +1 tested event (27 Jul) | No: adds data; result −4.1% (34th pct) |
| Yield test grade- and period-matched | The comparison became stricter | No: it was the fairer test |
| Claim narrowed: "every *testable* crossing" | Wording | Against the thesis (a smaller claim) |

**Specification curve (R1).** 288 versions of the event test, varying:
- horizon: 3, 7, 14 or 30 days
- start: day −1, −3 or −7
- minimum deposits: $1M, $5M, $10M or $25M
- control: same-platform or none
- placebo exclusion: 5, 10 or 20 days

240 of the 288 specs have usable data:
- **0 of 240** show a significant outflow after downgrades (p < 0.05).
- **0 of 240** do for downgrades across the investment-grade line.
- The median mean flow is +0.1% for all downgrades and +1.8% for IG-line downgrades.

So the null result does not depend on our settings.

**Leave-one-out (R4).** Dropping any single downgrade keeps p between 0.36 and 0.52.

## 4. What the test can and cannot see (the honest limit)

- **Calibration (R2).** Fake downgrades placed on ordinary days are flagged 5.0% of the time, exactly what a fair test should do.
- **Power (R3).** We injected outflows of known size into ordinary days to see how often the test catches them:

| Injected 7-day outflow | 1% | 2% | 3% | 5% | 10% | 20% |
|---|---|---|---|---|---|---|
| Caught (p < 0.05) | 7% | 9% | 11% | 18% | 49% | **88%** |

- **Why power is low.** These vaults are noisy. On ordinary weeks, the 5th–95th percentile range of a Spark dollar vault spans from about −41% to +24% (USDS) up to −60% to +90% (USDG). A few large allocators move hundreds of millions for their own reasons.
- **So the defensible claim is:** *no downgrade triggered a run*. A forced-selling exit of about 20% or more would have shown up 88% of the time. None did, under any of 240 specs.
- **We cannot claim** that grades have *no* effect. Effects under about 10% are invisible with 7 downgrades.
- **The positive control (R6) shows the tool can see a real exit.** After the Stream warning:
  - Morpho's xUSD market fell 97% in 6 days. Its worst prior 6-day move was −15% (0th percentile; only 30 prior days, because the market opened on 15 Sep 2025).
  - Stream fell 22.7% (1.2th percentile of 660 days).
  - Elixir fell 20.1% (2.7th percentile).

## 5. Yield robustness (R7)

- **Spark's governance-set vaults pay less than a same-grade bond on 100% of days.** This holds:
  - in both halves of the sample (Feb–Jun and Jul–Oct)
  - on medians as well as means
  - when we read each grade one bond bucket *more generously* (Spark gap still −1.0 to −1.6 pts)
- **Staked USDS (market rate)** is above its bond on 42% of days, with a mean of +0.2. It roughly matches its bond, but doesn't clearly price above it.
- **Lista USD1 (market rate)** is −4.7 pts below its bond on every day. A market rate is not enough on its own to price the grade.

## 6. Where to go with more data (true out-of-sample tests)

1. **Other raters' grade changes** (events we did not use to form the thesis):
   - S&P's stablecoin stability assessment downgrade of USDT (Nov 2025, date to confirm) → USDT supply and lending-pool flows
   - S&P's B- on Sky (Aug 2025) and Moody's B3 on Sky (7 Oct 2026) → sUSDS/USDS deposits
2. **More warning-plus-exit cases** (other Nov 2025 synthetic-dollar failures; confirm the list first) → does the professionals-first pattern repeat?
3. **Wallet-size split of the xUSD exit** (Arbitrum transfer logs; RPC works) → is "professional" really "large and fast"?
4. **A forward test.** Snapshot Credora grades and vault deposits daily from now on: a clean out-of-sample record. It won't be ready for this deadline, but it's worth a line in the piece.

## 7. Extra evidence added after the robustness run (`build_extra_evidence.py`)

These were added after seeing results, so they are logged here.

| Finding | Number | Source | Caveat |
|---|---|---|---|
| **Grades flip across the investment-grade line** | Credora: chance an investment-grade grade turns junk-equivalent within a year ≈ **93%** (6 crossings in 2.26 vault-years); junk-equivalent → IG ≈ 81%. S&P bonds, 1981–2023: BBB- → junk **9.08%**, BB+ → IG 12.67% | Credora panel; S&P 2023 Annual Global Corporate Default and Rating Transition Study, table 23 (`data/raw/ref/`) | Small exposure (2.3 vault-years). Spark PYUSD (5 crossings) held under $2mn, and Spark USDT has 4. Weekly reports undercount flips |
| **Yield doesn't follow the risk number** | Change in PSL vs change in yield across 78 report pairs: r = +0.06 (p = 0.49) | grades + DefiLlama APY | Governance rates mostly move with the Sky Savings Rate |
| **One grade step is priced at about a third of the bond step** | Spark A → A- (= BBB → BB): +0.23 pts on average (−0.15 to +0.96, 13 dates). ICE BBB → BB: +0.72 | same + FRED | Ranks agree (riskier pays a little more), but the size is small |
| **S&P's lowest score on USDT (26 Nov 2025): no redemptions** | USDT supply +0.08% in 7 days, +1.27% (≈ $2.3bn) in 30 days | DefiLlama stablecoins | USDC grew faster that week (+4.1%) after a −2.1% month, so the gap vs USDC (5.6th pct) comes from USDC's rebound |
| **S&P's B- on Sky (7 Aug 2025): no sustained exit** | USDS alone −11% in 7 days, but DAI +7% (conversion, not exit). USDS+DAI: −3.0% on 15 Aug, back by 18 Aug; +4.4% at 30 days. sUSDS deposits +4.8% in 7 days | same | The dip came a week after the rating and reversed in 3 days |
| **Moody's B3 on Sky (7 Oct 2026)** | Sky supply −0.01% in 3 days; sUSDS +1.6% | same | Only 3 days of data so far |

## 8. Later checks (13 Oct 2026, night)

| Finding | Number | Source | Effect on the claims |
|---|---|---|---|
| **Who left the xUSD market** | 10 lenders held $24.3mn at 28 Oct 00:00 UTC; **97.8% was withdrawn by 3 Nov**. Borrowers repaid $21.7mn, which is what made the exit possible. Median time to withdraw half: curated vaults 30h, everyone else 23h. Hyperithm was already trimming on 27 Oct | Morpho `marketTransactions` from market creation (`tx_xusd_arb_full.json`); `eth_getCode` on Arbitrum; `build_xusd_lenders.py` | **Drop "professionals left first."** Say instead: every lender with an open exit used it within days |
| **The Spark USDT −53% after the 6 Jul upgrade** | One unlabelled wallet (0x7213…5991, no contract code) withdrew **$414.6mn of $428.7mn** (5–9 Jul). The rate was then *raised*, 2.50% → 2.75% on 9 Jul (USDC paid 3.60%) | Ethereum `Withdraw` logs (`spark_usdt_withdraw_logs_jul2026.json`), DefiLlama APY | It isn't a rating reaction; it's concentration. The "rate change" flag on this event was a response, not the cause |
| **Credora reports carry no accountability** | Reports refer to "the client" and a services agreement; contents are provided "as is", without warranty of accuracy, and Credora disclaims liability for reliance | Report disclaimer text (e.g. REP-U-20260404, REP-SPARK-20261005) | Supports the accountability point. Who the client is isn't stated: don't say "issuer-pays" without a source |
| **Credora invites the bond comparison** | Its PD curve "is derived from analysis of the historic realized defaults" of the three big agencies, with data "at minimum 1990 to 2023", meant to enable "direct comparisons" | credora.network/docs/methodologies/defi-rating-scale | Justifies the conversion and stability comparisons |
| **Citations checked** | Ellul, Jotikasthira and Lundblad (2011) JFE 101(3) 596–620; Chen, Lookman, Schürhoff and Seppi (2014) RAPS 4(2) 162–205 (Lehman index relabelling, −21bp, no regulatory change); Hull, Predescu and White (2004) JBF 28(11) 2789–2811; Liu, Makarov and Schoar (2023) NBER w31160 ("wealthier and more sophisticated investors were the first to run"); Cookson et al., SSRN 4422754; Gorton and Zhang (2023) 90 U. Chi. L. Rev. 909 | Publisher and RePEc listings | Verified via the open web. LibKey wasn't connected, so confirm full text before final |
| **Stream warning date** | Earliest dated public warning: Schlag (Yearn), 28 Oct 2025; CBB0FE 28–29 Oct; freeze 4 Nov | Arunights research note; Decrypt; The Block | 28 Oct base kept. Withdrawal terms (queued or instant) still unconfirmed |

## 9. Curator concentration and market regimes (13 Oct 2026, late)

| Check | Result | Source / script | Caveat |
|---|---|---|---|
| **Curator concentration** | Morpho V2 vaults ($5.11bn, 3,615 vaults): Steakhouse 40.1%, Sentora 24.0%, Gauntlet 8.2% = **72.3%** (77.2% with the joint Sentora+SparkDAO vault). V1 ($2.41bn): Gauntlet, SparkDAO and Steakhouse = 57% (39% has no curator listed) | Morpho API snapshot `morpho_vaults_2026-10-13.json`; `build_curator_concentration.py` | V2 can deposit into V1, so don't add the two. A one-day snapshot. Spark's own savings vaults are governed by Sky, not a curator |
| **Curators chose the Stream exposure** | MEV Capital and Hyperithm vaults supplied **95.3%** of the $24.3mn lent against xUSD on that market | `xusd_lenders.csv` | One market on Arbitrum |
| **Regime-matched downgrades** | Mean percentile 48 against same-regime days (50 against all days); p = 0.44. 6 of 7 downgrades came in rising markets | `build_regime_checks.py` (Bitcoin's trailing 30-day return as the regime) | Only one downgrade in a falling market |
| **Flips aren't a crash effect** | IG → junk-equivalent: 93% in rising markets, 92% in falling. Credora window: Bitcoin +11%, worst drawdown −28% | same | Small counts (4 and 2) |
| **Crash week vs warning week** | 10 Oct 2025 crash (no warning), 6-day change: Morpho xUSD **+91%**, Stream +13%, Elixir −4%. Warning week: −97%, −23%, −20% | same | The exits came from the warning, not market stress |
| **S&P USDT downgrade came in a falling market** | Bitcoin −22% over the prior 30 days. Stablecoins can gain in sell-offs, which may have propped USDT up; it still lagged USDC that week (5.6th pct) | same | State it: "no redemptions", not "no effect" |
| **Bond benchmark is conservative** | 2026 spreads were tight: BBB and BB at the 23rd–27th percentile of the 3 years FRED serves. A longer-run benchmark would make the DeFi gap *larger* | same | FRED now limits ICE data to 3 years |

## 10. Ratings vs warnings, and who rates whom (13 Oct 2026, late)

| Finding | Number | Source | Caveat |
|---|---|---|---|
| **Rating events look like ordinary weeks** | 15 events, 3 raters: median rank 41 (50 = typical); KS test vs no effect p = 0.50; 2 of 15 in the worst 5% (chance 0.8; p = 0.17). The two are the one-wallet exit after an *upgrade* and the one-day Sky dip that reversed | `build_ratings_vs_warnings.py` | Low power for small effects (R3) |
| **The warning was extreme; the crash wasn't** | Stream warning: all 3 exposed series in their worst 3% of weeks (0.0, 1.2, 2.7). 10 Oct crash week, no warning: ranks 83, 85, 28 | same | One warning episode, three series |
| **Rating-agency concentration (bonds)** | Fitch, Moody's and S&P held **94.0%** of all NRSRO ratings outstanding (31 Dec 2022) and about **91.1%** of NRSRO revenue | SEC Office of Credit Ratings Staff Report, Feb 2024 (`data/raw/ref/sec_ocr_staff_report_feb2024.pdf`) | US-registered raters |
| **Issuer-pays conflict (bonds)** | SEC: the "primary business model of the NRSROs is the 'issuer-pay' model, which is subject to a conflict in that the credit rating agency may be influenced to determine more favorable (i.e., higher) ratings than warranted in order to retain … issuers as clients" | same | |
| **The GFC record** | FCIC: "The three credit rating agencies were key enablers of the financial meltdown … This crisis could not have happened without the rating agencies." 83% of the mortgage securities Moody's rated triple-A in 2006 were later downgraded | FCIC Final Report (2011), conclusions (`data/raw/ref/fcic_report_2011.pdf`) | The FCIC PDF's digits don't extract as text; the 83% is cross-checked with CFR's backgrounder. Check the page number in print |
| **DeFi: the rated party controls the grade** | Morpho: integration "at no cost for the Morpho DAO"; "vault curators will have the ability to opt-in"; "the display of a vault's rating requires curator approval" (27 Mar 2025) | forum.morpho.org/t/credora-network-risk-ratings-on-morpho/1652 | Who pays Credora isn't public |
| **DeFi: nobody stands behind the grade** | Spark: ratings are "provided by Credora and do not represent Spark's own analysis". Credora reports: "as is", no warranty, no liability for reliance, terms set "between Credora and the client" | docs.spark.finance (Credora rating page); Credora report disclaimers | |
| **DeFi: the same raters are arriving** | S&P (Sky B-, USDT 5, Vault Risk Assessment), Moody's (Sky B3) and Credora (owned by the oracle firm RedStone since Sep 2025, per Signalbase) | earlier rows; trysignalbase.com | Confirm the RedStone deal date with a primary source |

## 11. Final pass: corrections and new checks (13 Oct 2026, night)

| Item | Result | Action |
|---|---|---|
| **The stability comparison wasn't like-for-like** | Our 93% counted every crossing; S&P's 9.08% compares start-of-year and end-of-year ratings, so round trips aren't counted. Measured the same way: 12% at 90 days vs about 2% for BBB- bonds, but a vault bootstrap gives 3–43%, so not robust | **Dropped "93% vs 9%" and "ten times."** We now say: 4 of 10 vaults crossed the line; 12 crossings in 5.9 vault-years (about 2 a year); Spark USDT crossed four times in six weeks. S&P's 9% appears only as context. Figure 2 shows the grade timelines |
| **Independent mapping** | Rebuilt from S&P's own one-year default rates (table 23): A+ = BBB+ or better; A = BBB to BB+; A- = BB; B+ = BB-; B = B+/B. Investment grade at PSL ≤ 0.245%: **17.7% of grades** (Credora's table: 36.9%) | 37% is the generous figure. This also removes the dependence on the February copy of Credora's table (Wayback has only an Oct 2026 copy of that image) |
| **Duration check on yields** | 1–3 year investment-grade corporate spread +0.51 (BAMLC1A0C13Y, Feb–Oct 2026). Spark vaults sit −0.02 to −0.65 vs T-bills | Shown as a reference line in the yield figure |
| **Deposit-weighted figure** | 3.3% Feb–Oct (deposit-weighted); 0.9% on 12 Oct; 16.3% without sUSDS | Figure 1 uses 3% and notes the other two |
| **Prior work** | Zbandut and Goldstein (2025, arXiv:2512.11976): curators intermediate "a disproportionate share" of TVL (no figures in the abstract); their 2026 paper (arXiv:2604.17579) is a framework with no Credora test. CoinDesk Jan 2026 (by RedStone's co-founder): a "C" grade would have deterred xUSD investors, a hypothetical | Cite them. Our tests are, as far as we can find, new |
| **RedStone counter-claim** | "Rated vaults grow faster and attract more liquidity than unrated ones" (RedStone blog, 4 Sep 2025); no figure or method given | Address it: curators opt in, so the comparison is confounded |
| **S&P invested in Credora** | "$6m strategic funding round with S&P Global and Coinbase Ventures as major investors" (Mondo Visione, 25 Apr 2023) | Use in the accountability section |
| **RedStone deal date** | 4 Sep 2025 (RedStone blog) | Confirmed |
| **FCIC quote** | p. xxv, checked against the page image: "83% of the mortgage securities rated triple-A that year ultimately were downgraded"; also "the pressure from financial firms that paid for the ratings" | Confirmed |
| **Credora loss record** | None published (searched 13 Oct 2026); docs mention backtests but give no results | "No published loss record" |
| **Stream withdrawal terms** | No documented queue; users reported delays about 10 hours before the 4 Nov disclosure | Still open |

## 12. Adversarial pass on the core claims (`attack_core_claims.py`)

| Angle | Result | Effect |
|---|---|---|
| T-bill on a bond-equivalent basis (DGS3MO) and APY as a simple rate | Spark vs T-bill −0.21 to −0.82; vs same-grade bond −1.48 to −2.41 (larger than before) | Holds; the original figures were conservative |
| Days below a T-bill | 68–100% depending on the vault (always below a same-grade bond) | Say "on average below a T-bill" |
| Before the ratings existed (2025) | sUSDS +0.56 above T-bills on every day | Scope "below a T-bill" to the rated window; the claim is that yield doesn't track the grade |
| Calibration haircut (PSL overstates default-like risk) | S&P-based investment-grade share: 18% (×1), 46% (×0.5), 87% (×0.25); under Credora's table 37% | Always say "by Credora's own table" |
| Crossings as tiny moves around the line | 4 of 12 within 0.1 pts (all Spark USDT); the other 8 are large moves | Fits the cliff argument |
| Same-day changes (possible methodology change) | 4 Sep (3 vaults), 9 Sep (3), 22 Sep (2), 27 May (2), all Lista; no methodology note in the reports | Shared collateral risk across Lista markets |
| A- grades bunched just under the line | 5% of A- grades at PSL 0.40–0.45%; reclassifying them gives 39% | Not knife-edge |
| Token rewards missing from APY | DefiLlama shows no rewards on any Spark vault | Holds (outside points programmes not tracked) |
| Two chart titles overstated | Figure 3 implied all same-grade vaults pay below T-bills (Staked USDS pays +1.86); Figure 1 lacked "by the rater's own table" | Both retitled |
