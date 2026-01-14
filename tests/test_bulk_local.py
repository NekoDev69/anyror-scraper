#!/usr/bin/env python3
"""
Quick local test of bulk scraper - single taluka
"""
import os

# Test with 1 context, 1 district, 1 taluka
os.environ["NUM_CONTEXTS"] = "1"
os.environ["DISTRICT_CODE"] = "02"  # Amreli
os.environ["TALUKA_CODE"] = "04"    # Babra
os.environ["SURVEY_FILTER"] = ""

# Run
from vm_bulk_scraper import main
main()
