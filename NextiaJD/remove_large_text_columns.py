#!/usr/bin/env python3
"""
extract_samples.py

For each .csv file in NextiaJD/temp/, take the first N_ROWS of data
(ignoring the header row), re‑serialize using '|' as delimiter and '\n'
line breaks, and write into tables/<csv_name>/<csv_name>.csv. If the
 target file already exists, it’s skipped.

This version reads the delimiter for each file from temp/metadata.csv,
strips out any NUL bytes before parsing, replaces empty values with
'null', **and removes any column that contains at least one cell whose
length exceeds MAX_CELL_LEN characters (default: 3000).**
"""

import sys
import csv
from pathlib import Path
from typing import List, Set

# how many data rows (excluding header) to extract
N_ROWS = 64 * 1024
# maximum allowed length for any single cell; columns that violate this
# will be entirely removed from the sample
MAX_CELL_LEN = 3000


def load_delimiters(metadata_path: Path):
    """Return a dict mapping filename → delimiter (interpreting '\t')."""
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


def _collect_rows(reader: csv.reader) -> (List[List[str]], Set[int]):
    """Read up to N_ROWS data rows, collect them, and identify columns to skip.

    Returns
    -------
    rows : list of list of str
        The collected rows (without header).
    skip_cols : set of int
        Column indices to be omitted because at least one cell exceeds
        MAX_CELL_LEN characters.
    """
    rows: List[List[str]] = []
    skip_cols: Set[int] = set()

    row_count = 0
    for row in reader:
        if row_count >= N_ROWS:
            break
        rows.append(row)
        for idx, cell in enumerate(row):
            if len(cell) > MAX_CELL_LEN:
                skip_cols.add(idx)
        row_count += 1
    return rows, skip_cols


def _write_rows(writer: csv.writer, rows: List[List[str]], skip_cols: Set[int]):
    """Write cleaned rows, omitting skip_cols and replacing empty cells with 'null'."""
    for row in rows:
        cleaned_row = [cell if cell != '' else 'null'
                       for idx, cell in enumerate(row) if idx not in skip_cols]
        writer.writerow(cleaned_row)


def extract_sample(in_path: Path, out_path: Path, delim: str):
    # if out_path.exists():
    #     print(f"-- Skipping {in_path.name}: sample already exists")
    #     return

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with in_path.open('r', newline='', encoding='utf-8', errors='replace') as src, \
            out_path.open('w', newline='', encoding='utf-8') as dst:

        # Wrap src lines to strip any NUL bytes before parsing:
        def nul_stripped_lines():
            for line in src:
                yield line.replace('\x00', '')

        reader = csv.reader(nul_stripped_lines(), delimiter=delim)
        writer = csv.writer(dst, delimiter='|', lineterminator='\n')

        # skip header
        try:
            next(reader)
        except StopIteration:
            print(f"-- Warning: {in_path.name} is empty, skipping")
            return

        # first pass: collect rows and detect long cells
        rows, skip_cols = _collect_rows(reader)

        # second pass: write rows without offending columns
        _write_rows(writer, rows, skip_cols)

    print(f"-- Wrote {len(rows)} rows to {out_path.relative_to(Path.cwd())} (removed {len(skip_cols)} long columns)")


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

    # process every .csv in temp/
    for csv_file in sorted(input_dir.glob('*.csv')):
        name = csv_file.stem
        out_dir = output_root / name
        out_file = out_dir / f"{name}.csv"
        delim = delim_map.get(csv_file.name, ',')
        extract_sample(csv_file, out_file, delim)


if __name__ == '__main__':
    main()
