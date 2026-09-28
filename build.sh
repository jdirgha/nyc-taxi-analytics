#!/usr/bin/env bash
# Rebuilds the report end to end from the raw TLC files.
set -e
cd "$(dirname "$0")"
.venv/bin/python analysis.py     # SQL -> results.json
.venv/bin/python charts.py       # results.json -> charts/*.svg
.venv/bin/python charts_pbi.py   # Power BI-styled dashboard visuals
.venv/bin/python report.py       # -> report.html
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$PWD/NYC_Taxi_Analysis_Dirgha_Jivani.pdf" \
  "file://$PWD/report.html"
echo "Built NYC_Taxi_Analysis_Dirgha_Jivani.pdf"
