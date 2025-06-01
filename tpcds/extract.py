#!/usr/bin/env python3
"""
Sample, filter, and emit schema JSON for TPC-DS SF=1 tables.

This one script performs two steps in order:

  1. **Sample** the first 64×1024 rows (65 536) of each full CSV
     under `tpcds/temp/<table>/<table>.csv` (pipe-delimited, with header),
     writing them (no header) to `tpcds/tables/<table>/<table>.csv`.

  2. **Filter**: for each directory `tpcds/tables/<table>/` just created,
     if the sampled CSV has fewer than 65 536 rows, delete the entire `<table>/`
     folder. Otherwise, connect to `tpcds/tpcds_sf1.duckdb`, run
     `DESCRIBE "<table>"`, and write a `schema.json` with:

       {
         "columns": [
           { "name": "col1", "type": "TYPE1", "index": 0 },
           { "name": "col2", "type": "TYPE2", "index": 1 },
           ...
         ]
       }

     placing that `schema.json` next to `<table>.csv`.

After running, you’ll end up with:

  tpcds/
    ├── tpcds_sf1.duckdb       ← existing DuckDB file
    ├── temp/
    │   ├── call_center/call_center.csv
    │   ├── catalog_page/catalog_page.csv
    │   └── … (full exports)
    └── tables/
        ├── <table>/            ← only those with ≥ 65 536 rows
        │   ├── <table>.csv     ← sampled rows, no header
        │   └── schema.json      ← JSON schema for that table
        └── …

Run this as:

    python tpcds/process_tpcds_samples.py
"""

import json
import shutil
from pathlib import Path

import duckdb

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

# Number of data rows (excluding header) to sample
SAMPLE_ROWS = 64 * 1024  # 65 536

# Root dirs (relative to this script)
HERE         = Path(__file__).resolve().parent
TEMP_ROOT    = HERE / "temp"    # holds full CSVs: temp/<table>/<table>.csv
TABLES_ROOT  = HERE / "tables"  # to be created: tables/<table>/<table>.csv
DB_FILE      = HERE / "tpcds_sf1.duckdb"

# ──────────────────────────────────────────────────────────────────────────────
# Step 1: Sample first SAMPLE_ROWS rows from each full CSV
# ──────────────────────────────────────────────────────────────────────────────

def sample_tables():
    if not TEMP_ROOT.exists():
        print(f"Error: expected `{TEMP_ROOT}` not found.")
        return

    TABLES_ROOT.mkdir(exist_ok=True)
    for table_dir in sorted(TEMP_ROOT.iterdir()):
        if not table_dir.is_dir():
            continue
        table_name = table_dir.name
        full_csv = table_dir / f"{table_name}.csv"
        if not full_csv.exists():
            print(f"Warning: `{full_csv}` missing; skipping.")
            continue

        out_dir = TABLES_ROOT / table_name
        out_dir.mkdir(exist_ok=True)
        sample_csv = out_dir / f"{table_name}.csv"

        with full_csv.open("r", encoding="utf-8") as fin, \
                sample_csv.open("w", encoding="utf-8") as fout:
            # Skip header
            header = fin.readline()
            if not header:
                print(f"Warning: `{full_csv}` is empty; skipping.")
                continue

            # Copy up to SAMPLE_ROWS lines (data rows only)
            count = 0
            for line in fin:
                fout.write(line)
                count += 1
                if count >= SAMPLE_ROWS:
                    break

        print(f"Sampled {count} rows → `{sample_csv.relative_to(HERE)}`")

# ──────────────────────────────────────────────────────────────────────────────
# Step 2: Remove undersized tables and write schema.json for the rest
# ──────────────────────────────────────────────────────────────────────────────

def count_rows(csv_path: Path) -> int:
    """Count lines in CSV (no header)."""
    cnt = 0
    with csv_path.open("r", encoding="utf-8") as f:
        for _ in f:
            cnt += 1
    return cnt

def write_schema_json(con: duckdb.DuckDBPyConnection, tbl: str, out_path: Path):
    """
    Run DESCRIBE "<tbl>" in DuckDB and produce a JSON schema.

    JSON format:
      {
        "columns": [
          { "name": "col1", "type": "TYPE1", "index": 0 },
          ...
        ]
      }
    """
    desc = con.execute(f'DESCRIBE "{tbl}"').fetchall()
    columns = []
    for idx, row in enumerate(desc):
        col_name = row[0]   # column_name
        col_type = row[1]   # column_type
        columns.append({
            "name": col_name,
            "type": col_type,
            "index": idx
        })
    schema = {"columns": columns}
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"  → Wrote schema.json for `{tbl}`")

def filter_and_emit_schema():
    if not TABLES_ROOT.exists():
        print(f"Error: `{TABLES_ROOT}` not found (maybe you skipped sampling?).")
        return
    if not DB_FILE.exists():
        print(f"Error: DuckDB file `{DB_FILE}` not found.")
        return

    con = duckdb.connect(str(DB_FILE))

    for table_dir in sorted(TABLES_ROOT.iterdir()):
        if not table_dir.is_dir():
            continue
        table_name = table_dir.name
        sample_csv = table_dir / f"{table_name}.csv"
        schema_json = table_dir / "schema.json"

        if not sample_csv.exists():
            print(f"Skipping `{table_name}` (no sampled CSV).")
            continue

        n_rows = count_rows(sample_csv)
        if n_rows < SAMPLE_ROWS:
            # Delete entire directory
            shutil.rmtree(table_dir)
            print(f"Removed `{table_name}` ({n_rows} < {SAMPLE_ROWS} rows).")
        else:
            # Write schema.json
            write_schema_json(con, table_name, schema_json)

    con.close()
    print("\nDone. Remaining tables in `tpcds/tables/` each have ≥ 65 536 rows, with schema.json.")

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("▶  Sampling first 64×1024 rows from each full CSV …")
    sample_tables()

    print("\n▶  Filtering out undersized tables and writing schema.json …")
    filter_and_emit_schema()

if __name__ == "__main__":
    main()
