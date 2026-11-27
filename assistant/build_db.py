"""Materialize the CMS source CSVs into a persistent DuckDB file for the assistant.

The analysis pipeline (src/analyze.py) reads the raw CSVs through views on every
run. The assistant instead opens a small persistent database in read-only mode,
so the Streamlit page starts fast and cannot touch the raw files.

Run from the repo root, after src/download.py:
    python assistant/build_db.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB = Path(__file__).resolve().parent / "medicare.duckdb"

TABLES = {
    "svc": (
        "partb_provider_service_md_2024.csv",
        "SELECT *, Tot_Srvcs*Avg_Sbmtd_Chrg AS sbmtd, Tot_Srvcs*Avg_Mdcr_Alowd_Amt AS allowed, "
        "Tot_Srvcs*Avg_Mdcr_Pymt_Amt AS paid FROM read_csv_auto('{path}')",
    ),
    "prov": ("partb_provider_md_2024.csv", "SELECT * FROM read_csv_auto('{path}')"),
    "inp": ("inpatient_provider_fy2024.csv", "SELECT * FROM read_csv_auto('{path}')"),
    "leie": ("leie.csv", "SELECT * FROM read_csv_auto('{path}', all_varchar=true)"),
}


def main():
    for name, (fname, _) in TABLES.items():
        if not (RAW / fname).exists():
            raise SystemExit(f"missing data/raw/{fname} - run python src/download.py first")
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    counts = {}
    for name, (fname, sql) in TABLES.items():
        con.execute(f"CREATE TABLE {name} AS " + sql.format(path=(RAW / fname).as_posix()))
        counts[name] = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"{name}: {counts[name]} rows")
    con.execute("CREATE TABLE snapshot (built_at varchar, counts_json varchar)")
    con.execute(
        "INSERT INTO snapshot VALUES (?, ?)",
        [datetime.now(timezone.utc).isoformat(timespec="seconds"), json.dumps(counts)],
    )
    con.close()
    print(f"saved {DB}")


if __name__ == "__main__":
    main()
