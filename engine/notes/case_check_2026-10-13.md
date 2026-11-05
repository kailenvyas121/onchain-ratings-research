# Case check, 13 Oct 2026 (raw files in engine/data/raw)

## Resolv (DefiLlama resolv-usr TVL, 1st of month)
- Rated junk by Credora from May 2025 (TO CHECK the exact date)
- Deposits after the junk rating: May 2025 $340M → Aug 2025 $564M → Feb 2026 $584M
- Fell to $154M on 1 Mar 2026, then $142M on 21 Mar, the day before the exploit (22 Mar)

## Stream Finance (DefiLlama stream-finance TVL)
- Total deposits: $201M on 28 Oct → $156M on 3 Nov. About 22% left after the 29 Oct warning; about 78% was still there at the collapse.
- Morpho xUSD/USDC market on Arbitrum: supply fell $26.2M on 27 Oct → $0.7M on 2 Nov (−97%), while borrow fell $23.1M → $0.7M. The professional lenders were repaid or exited.
- Morpho sdeUSD/USDC market on World Chain: supply fell $7.3M → $0.2M between 30 Oct and 4 Nov

## Elixir (DefiLlama elixir TVL)
- $44M on 28 Oct → $35M on 30 Oct → $29M on 5 Nov → $3M on 7 Nov

## Curator concentration (Morpho API, v1 vaults only, pulled 13 Oct 2026)
- 1,408 vaults, $2.43B total; $953M (39%) has no curator listed
- Among named curators ($1.48B, 22 curators): the top 3 (Gauntlet $568M, SparkDAO $452M, Steakhouse $358M) hold 93%, and the top 5 hold 96%
- Caveat: v2 vaults are not included yet, so pull vaultV2s next

## Warnings about the data
- Morpho API "badDebt" figures for Resolv and Stream markets are NOT usable. They price worthless collateral at oracle values (e.g. $316M "bad debt" in a market with $6M supply that only existed after the exploit). Do not cite them.
- Correction: S&P DID assess USDe, scoring it 5 ("weak") on its Stablecoin Stability Assessment (Jan 2025), and it applied a 1,250% risk weight to USDe in its Sky rating. Moody's has no USDe rating found.

## Fast-money check (13 Oct, second pass)
- Morpho xUSD/USDC market on Arbitrum, hourly (xusd_arb_hourly.json): $24.7M on 28 Oct 06:00 UTC → $11.4M on 29 Oct 12:00 (half gone in about 30 hours) → $5.6M on 30 Oct → $0.7M on 1 Nov. About 97% was out before Stream's 3–4 Nov halt.
- The lenders were curated vaults: MEV Capital USDC (0xa606…) and Hyperithm USDC Apex (0x4B6F…), plus Clearstar
- Their exit was possible only because borrower 0x1597E4B7… repaid about $20M, starting 28 Oct 14:36 UTC. The same address borrowed in the sdeUSD market on World Chain.
- Exits started on the morning of 28 Oct UTC. The @Cbb0fe post is dated 28 Oct by some outlets and 29 Oct by others. GET THE EXACT TIMESTAMP: it decides whether the exits came before the public warning.
- Counter-evidence: professional curators that did NOT get out. YAM's estimate: TelosC about $124M, Elixir $68M, MEV Capital about $25M (MEV itself says about $34M across other venues), Re7 $14.65M on Euler. (The Block, Forklog)
- Resolv: Credora's junk rating is NOT confirmed by search yet. "About 15 vaults with exposure" is MORPHO's figure, not Credora's. Morpho's oracle hardcoded wstUSR at $1.13 after the exploit, and arbitrage drained the vaults (Steakhouse, 26 Mar 2026). Deposits fell 75% in Feb 2026 ($584M → $142M) BEFORE the exploit, with the cause unknown.
- Literature:
  - Liu, Makarov & Schoar, NBER w31160 (Terra): the wealthy and sophisticated ran first and lost less
  - Jump report: wallets with over $1M ran 40% in 3 days while wallets under $10k added
  - Cipriani, Eisenbach & Kovner, NY Fed SR1104 (2023 bank runs): runs were driven by a small number of large depositors
  - Ma, Zeng & Zhang, NBER w33882: an average of 6 agents a month redeem USDT
