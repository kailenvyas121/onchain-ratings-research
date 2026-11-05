# Do DeFi grades move price or money? Check of 13 Oct 2026

## Data
- **Credora public report index** (reports.credora.io/index.xml): 54 reports
  - 35 on Spark (Feb–Oct 2026), 16 on Lista
  - Parsed into engine/data/clean_credora_ratings.csv: 13 vaults, 254 dated observations
- **Credora's own scale** (credora_scale.png, from its docs). Letter → probability of a 1%+ loss → bond equivalent:
  - A+ 0–0.1% → AA+ to BBB+
  - **A 0.1–0.4% → BBB/BBB-**
  - **A- 0.4–0.8% → BB+/BB (junk)**
  - B+ 0.8–1.5% → BB-
  - B 1.5–3% → B+
  - B- 3–6% → B
- **Bond spreads** (FRED ICE BofA, 12 Oct 2026): AAA 0.39 · AA 0.58 · A 0.70 · BBB 1.02 · BB 1.88 · B 3.10 · CCC 12.53. 3-month T-bill (DTB3, 8 Oct) 4.05%.
- **Vault deposits and yields**: DefiLlama yields charts (engine/data/raw/llama_charts)

## Findings
1. **The letters read as investment grade but mostly mean junk.** Only 37% of observations are at a bond-equivalent investment grade. Spark Savings USDS, USDC and USDT are "A-" on screen, which equals BB in Credora's own table.
2. **The raters agree more than the letters suggest.** USDS-backed vaults: Credora A- (= BB). The Sky issuer: S&P B- (Aug 2025) and Moody's B3 (7 Oct 2026). All three are junk.
3. **The grades flicker across the investment-grade line.** There were 16 letter changes, and 11 of them crossed the BBB-/BB+ line. Spark Savings USDT crossed it 4 times in 6 weeks (Jul–Aug); Savings PYUSD 4 times in 8 weeks (Feb–Apr). Lista USDT went BB- → BBB → BB- in 4 months.
4. **Deposits didn't react to the crosses** (7 days after each change, against Spark Savings USDC, which never changed):
   - Spark USDT downgrade on 20 Jul: −1.0% (control −0.3%)
   - Spark USDT downgrade on 17 Aug: −2.6% (control −5.2%)
   - Spark USDT upgrade on 6 Jul: −52.8%. A large exit after an UPGRADE; the rate was raised from 2.50% to 2.75% two days later, so the exit wasn't grade-driven.
   - Lista USD1 three-notch upgrade on 27 May: −0.7%; downgrade on 4 Sep: 0.0% (a flat $138M, probably one large holder)
   - Lista BNB downgrade on 4 Sep: +3.0%
   - Spark PYUSD: under $1M, excluded as noise
5. **Yield doesn't price the grade.**
   - BB-equivalent Spark vaults pay 3.75–3.8%, BELOW the 4.05% T-bill. BB bonds pay +1.88% over Treasuries.
   - BBB-equivalent Spark vaults pay the same 3.8% (BBB bonds +1.02%)
   - Lista USD1 (BB-) pays about 1.2%, roughly 2.85 points below T-bills
   - The exception is Staked USDS (BB-), at 5.87%, about +1.8 over T-bills, close to the BB spread
   - Spark rates are set by governance, not by investors pricing risk

## Caveats
- Small sample: 2 platforms, only the vaults with public reports. Morpho's grades aren't available in bulk; the API is gated and the app blocks scripts.
- The Lista vault-to-DefiLlama-pool mapping is approximate. The Lista USDT vault had no matching pool.
- PSL (a 1%+ loss) is not the same as a bond default. Vaults are overnight-liquid, while bonds carry a term premium.
- Flows are dominated by a few large allocators, so 7-day windows are noisy.
