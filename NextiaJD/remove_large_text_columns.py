#!/usr/bin/env python3
"""
extract_samples.py

For each .csv file in NextiaJD/temp/, take the first N_ROWS of data
(ignoring the header row), re‑serialize using '|' as delimiter and '\n'
line breaks, and write into tables/<csv_name>/<csv_name>.csv. If the
 target file already exists, it’s skipped.

Enhancements over the original script:
• Reads the correct delimiter for each file from temp/metadata.csv.
• Strips out any NUL bytes before parsing.
• Replaces empty values with the literal string 'null'.
• **Drops any column that contains at least one cell whose length exceeds
  MAX_CELL_LEN characters (default 3 000).**
• **Reports how many columns were removed out of the total number of
  columns in *each* file.**
• **At the end, prints an overall summary of columns removed across all
  processed files.**
"""

import sys
import csv
from pathlib import Path
from typing import List, Set, Tuple

# how many data rows (excluding header) to extract
N_ROWS = 64 * 1024
# maximum allowed length for any single cell; columns that violate this
# will be entirely removed from the sample
MAX_CELL_LEN = 1000


def load_delimiters(metadata_path: Path) -> dict:
    """Return a dict mapping filename → delimiter (interpreting escape sequences)."""
    delim_map = {}
    with metadata_path.open(newline='', encoding='utf-8-sig') as mf:
        reader = csv.DictReader(mf)
        for row in reader:
            fname = (row.get('filename') or '').strip()
            raw = (row.get('delimiter') or '').strip()
            if not fname:
                continue
            # decode escape sequences like '\t'
            try:
                delim = raw.encode('utf-8').decode('unicode_escape')
            except Exception:
                delim = raw
            if delim == '':
                delim = ','  # fallback
            delim_map[fname] = delim
    return delim_map


def _collect_rows(reader: csv.reader) -> Tuple[List[List[str]], Set[int]]:
    """Read up to N_ROWS data rows, collect them, and identify columns to skip."""
    rows: List[List[str]] = []
    skip_cols: Set[int] = set()

    for row_count, row in enumerate(reader):
        if row_count >= N_ROWS:
            break
        rows.append(row)
        for idx, cell in enumerate(row):
            if len(cell) > MAX_CELL_LEN:
                skip_cols.add(idx)
    return rows, skip_cols


def _write_rows(writer: csv.writer, rows: List[List[str]], skip_cols: Set[int]):
    """Write cleaned rows, omitting skip_cols and replacing empty cells with 'null'."""
    for row in rows:
        cleaned_row = [cell if cell != '' else 'null'
                       for idx, cell in enumerate(row) if idx not in skip_cols]
        writer.writerow(cleaned_row)


def extract_sample(in_path: Path, out_path: Path, delim: str) -> Tuple[int, int]:
    """Extract and write a sampled version of *in_path*.

    Returns
    -------
    removed_cols : int
        Number of columns removed due to long cells.
    total_cols : int
        Total number of columns in the original file (0 if file empty).
    """

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with in_path.open('r', newline='', encoding='utf-8', errors='replace') as src, \
            out_path.open('w', newline='', encoding='utf-8') as dst:

        # Wrap src lines to strip any NUL bytes before parsing:
        def nul_stripped_lines():
            for line in src:
                yield line.replace('\x00', '')

        reader = csv.reader(nul_stripped_lines(), delimiter=delim)
        writer = csv.writer(dst, delimiter='|', lineterminator='\n')

        # capture and skip header
        try:
            header = next(reader)
        except StopIteration:
            print(f"-- Warning: {in_path.name} is empty, skipping")
            return 0, 0
        total_cols = len(header)

        # first pass: collect rows and detect long cells
        rows, skip_cols = _collect_rows(reader)

        # second pass: write rows without offending columns
        _write_rows(writer, rows, skip_cols)

    removed_cols = len(skip_cols)
    relpath = out_path.relative_to(Path.cwd())
    print(f"-- Wrote {len(rows)} rows to {relpath} (removed {removed_cols}/{total_cols} columns >{MAX_CELL_LEN} chars)")
    return removed_cols, total_cols


def main():
    script_dir = Path(__file__).resolve().parent
    input_dir = script_dir / 'temp'
    metadata_path = input_dir / 'metadata.csv'
    output_root = script_dir / 'tables'

    if not input_dir.is_dir():
        print(f"❌ Error: input directory {input_dir} not found", file=sys.stderr)
        sys.exit(1)
    if not metadata_path.is_file():
        print(f"❌ Error: metadata file {metadata_path} not found", file=sys.stderr)
        sys.exit(1)

    # load per-file delimiters
    delim_map = load_delimiters(metadata_path)

    grand_total_cols = 0
    grand_removed_cols = 0
    processed_files = 0

    # process every .csv in temp/
    for csv_file in sorted(input_dir.glob('*.csv')):
        name = csv_file.stem
        out_dir = output_root / name
        out_file = out_dir / f"{name}.csv"
        delim = delim_map.get(csv_file.name, ',')
        removed, total = extract_sample(csv_file, out_file, delim)
        if total == 0:  # empty file case
            continue
        grand_total_cols += total
        grand_removed_cols += removed
        processed_files += 1

    # overall summary
    if processed_files > 0:
        print(
            f"== Overall: removed {grand_removed_cols}/{grand_total_cols} columns (>={MAX_CELL_LEN} chars) "
            f"across {processed_files} files"
        )
    else:
        print("⚠️  No non‑empty CSV files processed.")


if __name__ == '__main__':
    main()
