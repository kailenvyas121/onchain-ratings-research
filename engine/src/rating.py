"""
Shared definitions for the rating study: Credora's scale, pool mapping, loaders.

Everything here is offline. Only scripts/update_data.py touches the network.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"

# Credora DeFi rating scale (credora.network/docs/methodologies/defi-rating-scale, image saved as
# data/raw/credora_scale.png). PSL = annualised probability of a 1%+ principal loss.
# letter: (min PSL %, max PSL %, bond equivalent per Credora's own table)
SCALE = {
    "A+": (0.0, 0.1, "BBB+ or better"),
    "A":  (0.1, 0.4, "BBB / BBB-"),
    "A-": (0.4, 0.8, "BB+ / BB"),
    "B+": (0.8, 1.5, "BB-"),
    "B":  (1.5, 3.0, "B+"),
    "B-": (3.0, 6.0, "B"),
    "C+": (6.0, 12.0, "B-"),
    "C":  (12.0, 32.0, "CCC+ / CCC"),
    "C-": (32.0, 99.9, "CCC- to C"),
    "D":  (99.9, 100.0, "D"),
}
ORDER = list(SCALE)
# Which ICE BofA rating index stands in for each letter's bond equivalent (broad buckets: BB- sits in the BB index,
# B+ and B in the B index; A+ spans AA+ to BBB+, so it is compared with the single-A index).
BOND_BUCKET = {"A+": "A", "A": "BBB", "A-": "BB", "B+": "BB", "B": "B", "B-": "B", "C+": "B", "C": "CCC", "C-": "CCC"}


def is_investment_grade(letter: str) -> bool:
    """Bond-equivalent investment grade (BBB- or better) under Credora's own table."""
    return letter in ("A+", "A")


def notch(letter: str) -> int:
    """0 = best. Positive change = downgrade."""
    return ORDER.index(letter)


# Vaults are keyed by on-chain address: Credora's reports swap two Lista vault names in Sep 2026
# (0xfa27... "USD1 Vault" -> "USDT"; 0x6d67... "USDT Vault" -> "USD1"), so names are not reliable keys.
# Resolved 13 Oct 2026 on BNB Chain: asset() of 0xfa27 = USD1 (vGauntletUSD1), 0x6d67 = USDT (vGauntletUSDT);
# pools matched by current totalAssets (138.32mn vs DefiLlama 138.1mn; 2.68mn vs 2.7mn). History is DefiLlama's.
# address -> (label, DefiLlama yields pool, mapping confidence, how the rate is set, dollar product?)
#   high = same product and chain; medium = matched by name/chain/size; None = unresolved, not tested.
POOLS = {
    "0xe2e7a17dff93280dec073c995595155283e3c372": ("Spark Savings USDT", "a5d67f7e-5b51-4a9d-969d-caf051a7f5a4", "high", "governance", True),
    "0x28b3a8fb53b741a8fd78c0fb9a6b2393d896a43d": ("Spark Savings USDC", "c5c74dd1-995c-4445-9d84-3e710bad7d52", "high", "governance", True),
    "0x80128dbb9f07b93dde62a6daeadb69ed14a7d354": ("Spark Savings PYUSD", "4d33c615-a969-4c55-9acf-49d8d14a1063", "high", "governance", True),
    "0xde770c84fe66e063336b31737cfe9790f18c4087": ("Spark Savings USDG", "a1371c8f-592f-56d4-a506-7f1530f35a00", "high", "governance", True),
    "0xa3931d71877c0e7a3148cb7eb4463524fec27fbd": ("Spark Savings USDS", "d8c4eff5-c8a9-46fc-a888-057c4c668e72", "medium", "governance", True),
    "0x99cd4ec3f88a45940936f469e4bb72a2a701eeb9": ("Staked USDS", "9f71f0fd-cfac-54b1-865e-37338f481708", "medium", "market", True),
    "0xfe6eb3b609a7c8352a241f7f3a21cea4e9209b8f": ("Spark Savings ETH", "bace601a-530a-432c-9b79-8c6451de25ea", "high", "market", False),
    "0x57134a64b7cd9f9eb72f8255a671f5bf2fe3e2d0": ("Lista BNB vault", "e15db93c-9c49-490c-896d-24092b4d7471", "medium", "market", False),
    "0xfa27f172e0b6ebcef9c51abf817e2cb142fbe627": ("Lista USD1 vault", "d6fec854-4258-495b-95df-e4066214f41d", "medium", "market", True),
    "0x6d6783c146f2b0b2774c1725297f1845dc502525": ("Lista USDT vault", "8b4267ba-69b2-49c9-9a82-df98e24e1f0f", "medium", "market", True),
}
CONTROL_ADDRESS = "0x28b3a8fb53b741a8fd78c0fb9a6b2393d896a43d"  # Spark Savings USDC: grade never changed
# Same-platform control: Spark Savings USDC for Spark; Lista Lending protocol total for Lista.
CONTROLS = {"SPARK": ("pool", "c5c74dd1-995c-4445-9d84-3e710bad7d52"), "LISTA": ("protocol", "lista-lending")}


def load_grades() -> pd.DataFrame:
    g = pd.read_csv(PROC / "credora_grades.csv", parse_dates=["date"])
    return g.sort_values(["protocol", "address", "date"]).reset_index(drop=True)


def load_pool(pool_id: str) -> pd.DataFrame:
    d = json.load(open(RAW / "llama_charts" / f"{pool_id}.json"))["data"]
    df = pd.DataFrame({"date": pd.to_datetime([x["timestamp"][:10] for x in d]),
                       "tvl": [x["tvlUsd"] for x in d], "apy": [x.get("apy") for x in d]})
    return df.drop_duplicates("date", keep="last").set_index("date").sort_index()


def load_protocol_tvl(slug: str) -> pd.Series:
    d = json.load(open(RAW / f"llama_{slug}.json"))["tvl"]
    s = pd.Series({pd.Timestamp(dt.datetime.fromtimestamp(x["date"], dt.UTC).date()): x["totalLiquidityUSD"] for x in d})
    return s[~s.index.duplicated(keep="last")].sort_index()


def load_fred(series_id: str) -> pd.Series:
    rows = list(csv.reader(open(RAW / "fred" / f"{series_id}.csv")))[1:]
    s = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in rows if r[1] not in ("", ".")})
    return s.sort_index()


def asof(s: pd.Series, day: pd.Timestamp, max_gap_days: int = 7):
    """Last value on or before `day` (never after). None if the gap is too long."""
    s = s.loc[:day]
    if s.empty or (day - s.index[-1]).days > max_gap_days:
        return None
    return s.iloc[-1]
