#!/usr/bin/env python3
"""
remove_large_text_columns.py

Iterate over each tables/<name>/<name>.csv, detect any columns where at least one row’s text
length exceeds 10,000 characters, drop those columns, and overwrite the CSV without them.

Usage:
    Place this script alongside the existing `tables` directory (i.e., same parent).
    Then run:
        python3 remove_large_text_columns.py
"""

import sys
import traceback
from pathlib import Path

import pandas as pd

MAX_LENGTH = 5000  # threshold in characters for “large text”


def process_csv(csv_path: Path):
    """
    Load the CSV at `csv_path` (assuming '|' delimiter and a header row),
    find any columns where any cell exceeds MAX_LENGTH characters,
    drop those columns, and overwrite the CSV without them.

    Returns a list of dropped columns (empty if none).
    """
    print(f"Processing: {csv_path}")

    # Read everything as string so that we can measure length of text
    try:
        df = pd.read_csv(csv_path, sep='|', dtype=str, keep_default_na=False)
    except Exception as e:
        print(f"  ❌ Failed to read CSV: {e}")
        return []

    drop_cols = []
    for col in df.columns:
        # Compute length of each entry in this column (empty string for NaN)
        # Since dtype=str + keep_default_na=False, NaN is already read as ''
        # so we can safely map len()
        try:
            max_len = df[col].map(len).max()
        except Exception as e:
            print(f"  ❌ Error computing lengths for column '{col}': {e}")
            # If something weird happens, skip this column
            continue

        if max_len > MAX_LENGTH:
            drop_cols.append(col)

    if not drop_cols:
        print("  → No columns exceed length threshold; nothing to drop.\n")
        return []

    # Drop the oversized-text columns
    print(f"  → Dropping columns (exceed {MAX_LENGTH} chars): {drop_cols}")
    df = df.drop(columns=drop_cols)

    # Overwrite the CSV in-place (same delimiter and no index column)
    try:
        df.to_csv(csv_path, sep='|', index=False)
    except Exception as e:
        print(f"  ❌ Failed to write updated CSV: {e}")
        return drop_cols

    print("  → Overwritten CSV without large-text columns.\n")
    return drop_cols


def main():
    base = Path(__file__).resolve().parent / "tables"
    if not base.is_dir():
        print(f"❌ Error: tables directory not found at '{base}'")
        sys.exit(1)

    for table_dir in sorted(base.iterdir()):
        if not table_dir.is_dir():
            continue

        # Skip any 'metadata' folder
        if table_dir.name == "metadata":
            print(f"-- Skipping '{table_dir.name}' (metadata folder)\n")
            continue

        # Find the first CSV in this directory
        csv_files = list(table_dir.glob("*.csv"))
        if not csv_files:
            print(f"-- Warning: no .csv file found in '{table_dir.name}'\n")
            continue

        # If there are multiple CSVs, process each one
        for csv_path in csv_files:
            try:
                process_csv(csv_path)
            except Exception:
                print(f"  ❌ Unexpected error processing '{csv_path.name}':")
                traceback.print_exc()
                print()

if __name__ == "__main__":
    main()
