###############################################################################
# FastLanes Data – Makefile
###############################################################################

SHELL  := /bin/bash
PYTHON := python3

# virtual-env directory (absolute path so it works after “cd” commands)
VENV   := $(abspath .venv)

# Always source the venv, then run the remainder of the command.
ACTIVATE = . "$(VENV)/bin/activate" &&

# ──────────────────────────────────────────────────────────────────────────
# Helper scripts
# ──────────────────────────────────────────────────────────────────────────
SCRIPT_PUBLIC_BI := public_bi_extract_schemas.py
REFORMAT_CSVS    := reformat_csvs.py
CSV_SIZE_REPORT  := csv_size_report.py

# ──────────────────────────────────────────────────────────────────────────
# Dataset generators
# ──────────────────────────────────────────────────────────────────────────
TPCH_DIR   := tpch
TPCH_DB    := $(TPCH_DIR)/tpch_sf1.duckdb
TPCH_TEMP  := $(TPCH_DIR)/temp
TPCH_SCRIPT := generate_tpch.py

SSB_DIR    := ssb
SSB_DB     := $(SSB_DIR)/ssb_sf1.duckdb
SSB_TEMP   := $(SSB_DIR)/temp
SSB_SCRIPT := generate_ssb.py

TPCDS_DIR  := tpcds
TPCDS_DB   := $(TPCDS_DIR)/tpcds_sf1.duckdb
TPCDS_TEMP := $(TPCDS_DIR)/temp
TPCDS_SCRIPT := generate_tpcds.py

# ──────────────────────────────────────────────────────────────────────────
# Phony targets
# ──────────────────────────────────────────────────────────────────────────
.PHONY: all install \
        get_public_bi_schemas reformat_csvs check_metadata prepare_nextiajd \
        csv_size_report \
        prepare_tpch clean_tpch \
        prepare_ssb clean_ssb \
        prepare_tpcds clean_tpcds \
        clean

# ===========================================================================
# 1. default
# ===========================================================================
all: install get_public_bi_schemas

# ===========================================================================
# 2. virtual-env & deps
# ===========================================================================
install:
	@if [ ! -d "$(VENV)" ]; then \
	    echo "Creating virtual environment …"; \
	    $(PYTHON) -m venv $(VENV); \
	fi
	@echo "Upgrading pip …"
	$(ACTIVATE) pip install --upgrade pip
	@echo "Installing core packages …"
	$(ACTIVATE) pip install duckdb pyyaml pandas beautifulsoup4 requests
	@if [ -f requirements.txt ]; then \
	    $(ACTIVATE) pip install -r requirements.txt; \
	fi

# ===========================================================================
# 3. Public-BI
# ===========================================================================
get_public_bi_schemas: install
	cd scripts && $(ACTIVATE) $(PYTHON) $(SCRIPT_PUBLIC_BI)

# ===========================================================================
# 4. NextiaJD helpers
# ===========================================================================
reformat_csvs: install
	$(ACTIVATE) $(PYTHON) scripts/$(REFORMAT_CSVS) $(FASTLANES_DATA_DIR)/NextiaJD

check_metadata:
	$(ACTIVATE) $(PYTHON) NextiaJD/check_metadata.py

prepare_nextiajd: install
	cd NextiaJD && $(ACTIVATE) $(PYTHON) prepare.py

csv_size_report: install
	$(ACTIVATE) $(PYTHON) scripts/$(CSV_SIZE_REPORT) > csv_sizes_report.csv
	@echo "→ csv_sizes_report.csv created."

# ===========================================================================
# 5. TPCH
# ===========================================================================
prepare_tpch: install
	cd $(TPCH_DIR) && $(ACTIVATE) $(PYTHON) $(TPCH_SCRIPT)

clean_tpch:
	@rm -f  $(TPCH_DB)
	@rm -rf $(TPCH_TEMP)
	@echo "TPCH cleaned."

# ===========================================================================
# 6. SSB
# ===========================================================================
prepare_ssb: install
	cd $(SSB_DIR) && $(ACTIVATE) $(PYTHON) $(SSB_SCRIPT)

clean_ssb:
	@rm -f  $(SSB_DB)
	@rm -rf $(SSB_TEMP)
	@echo "SSB cleaned."

# ===========================================================================
# 7. TPC-DS
# ===========================================================================
prepare_tpcds: install
	cd $(TPCDS_DIR) && $(ACTIVATE) $(PYTHON) $(TPCDS_SCRIPT)

clean_tpcds:
	@rm -f  $(TPCDS_DB)
	@rm -rf $(TPCDS_TEMP)
	@echo "TPC-DS cleaned."

# ===========================================================================
# 8. global clean
# ===========================================================================
clean: clean_tpch clean_ssb clean_tpcds
	@rm -rf $(VENV) public_bi_benchmark ../public_bi/tables csv_sizes_report.csv
	@rm -rf NextiaJD/temp
	@echo "Global cleanup complete."