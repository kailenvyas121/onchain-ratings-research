# Rating study engine: "A Rating Nobody Has to Read"

Methods and pre-registration for the rating study (written Oct 2026, before results). Conventions:
- Raw data comes in through one network script.
- Build scripts produce `data/processed/`.
- A `verify_` script re-derives every headline number by hand.
- Final exhibits come from `scripts/chart_*.py`, using the same house style.

```
python run_all.py            # rebuild, audit, redraw (offline, cached data)
python run_all.py --online   # refresh raw data first
```

## Pre-registered question and tests (written before results; changes logged below)
**Question:** in bond markets, ratings move money mainly because rules force action at the investment-grade line (BBB-/BB+). Do DeFi grades move deposits or yields?

| Test | Statistic | Null | What would falsify the thesis |
|---|---|---|---|
| 1. Yield vs grade | Mean daily (vault APY − 3-month T-bill as of that day) by Credora grade, compared with ICE BofA spreads by rating | Yield rises with grade the way bond spreads do | Junk-equivalent vaults paying a BB-like spread (+1.7) consistently |
| 2. Grade change vs deposits | Abnormal flow = vault deposit change from day −1 to day +h (h = 3, 7, 14), minus the same-platform control | Placebo distribution: the same statistic on every non-event day for that vault (±10 days around any change excluded) | Downgrades crossing the investment-grade line sitting in the bottom 10% of the placebo distribution |
| 3. What does move money | Deposits indexed to 100 at 00:00 UTC on 28 Oct 2025 (Stream warning): hourly Morpho lenders vs. daily Stream and Elixir depositors | — | Depositors exiting as fast as professional lenders |

**Integrity rules:**
- A grade is dated to the report that published it, never earlier.
- The T-bill used for each day is the latest print on or before that day.
- Vaults are keyed by on-chain address.
- Vaults with less than $10M in deposits on day −1 are excluded from tests.
- Any event with a rate change within 3 days is flagged as confounded.

## Data (data/raw, refreshed only by scripts/update_data.py)
| Input | Source |
|---|---|
| 54 Credora reports (35 Spark, 16 Lista, others), Feb–Oct 2026 | `reports.credora.io/index.xml` (public archive), PDFs converted with pdftotext |
| Credora letter → probability → bond-equivalent table | Credora docs, DeFi Rating Scale image (`credora_scale.png`) |
| Daily vault deposits and APY | DefiLlama yields `/chart/{pool}` |
| Protocol totals (Stream, Elixir, Resolv, Lista Lending) | DefiLlama `/protocol/{slug}` |
| Corporate spreads by rating; 3-month T-bill | FRED: BAMLC0A1CAAA … BAMLH0A3HYC, DTB3 |
| Hourly xUSD/USDC market supply on Arbitrum | Morpho GraphQL API |

## Results (run of 13 Oct 2026; `verify_rating_study.py` passes)
- **Panel:** 10 vaults, 254 dated grades, 19 grade changes, **11 crossing the investment-grade line**.
- **Only 37% of grades are investment grade in bond terms.** Credora "A-" = BB+/BB.
- **Test 1:**
  - Governance-set Spark vaults rated A-/A (BB to BBB equivalent) averaged **−0.65 to −0.02 points versus T-bills**. BBB bonds paid +1.00 and BB bonds +1.72.
  - The one market-rate vault (Staked USDS, B+ = BB-) paid **+1.87**, close to BB bond pricing.
- **Test 2:**
  - Downgrades: n = 5, mean abnormal 7-day flow **−1.3%**, mean placebo percentile **42** (no forced-selling signature)
  - The largest move (Spark USDT −51%) followed an **upgrade**, and coincided with a rate change
- **Test 3:**
  - Morpho xUSD lenders (MEV Capital, Hyperithm and Clearstar vaults) fell to **3** by 3 Nov
  - Stream depositors fell to **77**, Elixir depositors to **80**

## Caveats (state them in the article)
- **Two platforms only.** Morpho grades are not public in bulk: the API is gated and the app blocks scripts.
- **Probability of a 1%+ loss is not the same as a bond default.** Vaults are withdrawable daily, while bond spreads include term and liquidity premia.
- **Small event sample** (7 testable). Flows are dominated by a few large allocators.
- **Lista naming:** Credora's reports swap two vault names in Sep 2026 (0xfa27… and 0x6d67…). Those two vaults are left out of the deposit and yield tests until their assets are confirmed on-chain.
- **DefiLlama data:** pool mapping is "medium" confidence for Savings USDS, Staked USDS and Lista BNB. DefiLlama TVL has occasional one-day glitches (May 2026 Spark USDT spikes).

## Changes after seeing results
- 13 Oct: switched vault keys from name to address after finding the Lista name swap. Counts moved from 13 vaults and 16 changes to 10 vaults and 19 changes; the crossing count stayed at 11.

## Still to check
- On the Internet Archive, that the scale image (hash 27d37519…) was the same in Feb 2026. Every grade already fits the current bands.
- On-chain `asset()` for Lista vaults 0xfa27… and 0x6d67… (BNB Chain).
- The exact timestamp of the @Cbb0fe warning (28 or 29 Oct 2025).

### 13 Oct 2026 (evening): data rebuild
- Data refreshed to 13 Oct 2026 (Credora to 12 Oct report; FRED bonds to 12 Oct, T-bill to 9 Oct; DefiLlama to 13 Oct).
- Parser reads both report layouts: 3 Feb report added, so 260 grades, 20 changes, 12 IG-line crossings (was 254 / 19 / 11). Five single-asset reports (EtherFi, Lotus, slisBNB, stETH, U) have no vault table and are out of scope.
- Lista name swap resolved on-chain: asset() of 0xfa27 = USD1, 0x6d67 = USDT (Gauntlet vaults); pools matched by current totalAssets. Lista USD1 is now tested (4 events); Lista USDT is under $10M.
- DefiLlama deposits checked against Spark ERC-4626 totalAssets() at 23:00 UTC on every event-window day: median gap 0.02%, max 0.10% (41 vault-days). On-chain readings fill DefiLlama's 20-26 Jul gap, so the 27 Jul USDT upgrade is now tested (12 of 20 changes testable; 5 of 12 crossings).
- Yield test is period- and grade-matched: each day's vault spread minus the ICE index for the grade in force that day (BOND_BUCKET). Vaults with < 30 days at $10M+ are dropped.
- Lista BNB vault re-measured in BNB units (scripts/build_bnb_robustness.py) to strip the BNB price.
- Caveats: Lista USD1 deposits sit near $138mn from April onward in DefiLlama and can't be checked historically on BNB Chain (no archive RPC). The 0.1-point "rate change" flag is meaningful for governance rates; for market rates (Lista) it fires on ordinary utilisation moves.
