#!/usr/bin/env python3
"""
Generate TPC-DS SF = 1 with DuckDB’s built-in `tpcds` extension.

Everything is stored *locally* inside this tpcds/ folder:

    tpcds/
        ├─ tpcds_sf1.duckdb
        └─ temp/
            ├─ <table>/<table>.csv
            └─ schema.sql
"""

from pathlib import Path
import duckdb

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
HERE      = Path(__file__).resolve().parent         # …/FastLanes_Data/tpcds
DB_FILE   = HERE / "tpcds_sf1.duckdb"
TEMP_DIR  = HERE / "temp"
DELIM     = "|"

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def ensure_dirs() -> None:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

def wipe_existing(con):
    for (tbl,) in con.execute("SHOW TABLES").fetchall():
        if not tbl.lower().startswith("duckdb_"):
            con.execute(f'DROP TABLE IF EXISTS "{tbl}";')

def load_extension(con):
    try:
        con.execute("INSTALL tpcds;")
    except duckdb.IOException:
        pass
    con.execute("LOAD tpcds;")

def run_dsdgen(con):
    con.execute("CALL dsdgen(sf => 1);")

def user_tables(con):
    return [
        tbl for (tbl,) in con.execute("SHOW TABLES").fetchall()
        if not tbl.lower().startswith("duckdb_")
    ]

def export_csvs(con, tables):
    for tbl in tables:
        out = TEMP_DIR / tbl / f"{tbl}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        con.execute(f'COPY "{tbl}" TO \'{out}\' (HEADER, DELIMITER \'{DELIM}\');')
        print(f"✓  {tbl}")

def ddl_from_describe(con, tbl):
    cols = [
        f'"{name}" {typ}'
        for name, typ, *_ in con.execute(f'DESCRIBE "{tbl}"').fetchall()
    ]
    return f'CREATE TABLE "{tbl}" (\n  ' + ",\n  ".join(cols) + "\n);"

def write_schema(con, tables):
    path = TEMP_DIR / "schema.sql"
    with path.open("w", encoding="utf-8") as f:
        for tbl in tables:
            try:
                ddl = con.execute(f'SHOW CREATE TABLE "{tbl}"').fetchone()[0]
            except duckdb.ParserException:
                ddl = ddl_from_describe(con, tbl)
            f.write(ddl.rstrip() + ";\n\n")
    print(f"✓  schema.sql → {path.relative_to(HERE)}")

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    print("📦  TPC-DS SF=1 → tpcds/temp/")
    ensure_dirs()

    con = duckdb.connect(DB_FILE)
    wipe_existing(con)
    load_extension(con)

    print("⏳  CALL dsdgen(sf=>1)…")
    run_dsdgen(con)
    print("✅  tables created")

    tables = user_tables(con)
    print("⏳  exporting CSVs …")
    export_csvs(con, tables)

    print("⏳  writing schema.sql …")
    write_schema(con, tables)

    con.close()
    print("\n🎉  Done – files are in tpcds/temp/")

if __name__ == "__main__":
    main()
