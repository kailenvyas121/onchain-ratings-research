"""
Build the Credora grade panel from the public report archive.

Reads data/raw/credora_reports/REP-*.txt (pdftotext of reports.credora.io PDFs)
Writes data/processed/credora_grades.csv: one row per vault per report date.
A grade's effective date is the report date (when it became public), never earlier.
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import POOLS, PROC, RAW, SCALE, is_investment_grade  # noqa: E402

# Two layouts: "Name Address PSL Rating" and (3 Feb, 23 Feb V1) "Symbol Address Name PSL Rating".
ROW = re.compile(r"^\s*(.+?)\s+(0x[0-9a-fA-F]{40})\s+(?:(\D.*?)\s+)?([\d.]+)%\s+([A-D][+-]?)\s*$")
NAME = re.compile(r"REP-([A-Z]+)-(\d{8})-V(\d+)")

rows, skipped = [], []
for f in sorted((RAW / "credora_reports").glob("REP-*.txt")):
    proto, date, ver = NAME.match(f.name).groups()
    found = 0
    for line in f.read_text(errors="ignore").splitlines():
        m = ROW.match(line)
        if m:
            rows.append(dict(protocol=proto, date=pd.Timestamp(date), version=int(ver), vault=(m.group(3) or m.group(1)).strip(),
                             address=m.group(2).lower(), psl_pct=float(m.group(4)), rating=m.group(5), source=f.name))
            found += 1
    if not found:
        skipped.append(f.name)
if skipped:
    print("reports without a rating table:", ", ".join(skipped))

g = pd.DataFrame(rows)
# Same vault, same date, several versions: keep the latest version published that day.
g = g.sort_values(["protocol", "address", "date", "version"]).drop_duplicates(["protocol", "address", "date"], keep="last")
g = g.rename(columns={"vault": "name_in_report"})
g["vault"] = g.address.map(lambda a: POOLS[a][0] if a in POOLS else a)
g["bond_equivalent"] = g.rating.map(lambda r: SCALE[r][2])
g["investment_grade"] = g.rating.map(is_investment_grade)
PROC.mkdir(parents=True, exist_ok=True)
g.to_csv(PROC / "credora_grades.csv", index=False)
print(f"{len(g)} grades, {g.address.nunique()} vaults (by address), "
      f"{g.date.min():%d %b %Y} to {g.date.max():%d %b %Y}; reports without a rating table: {len(skipped)}")
