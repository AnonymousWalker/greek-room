#!/bin/bash
# Script to run ualign.py after word alignments are created

# --- Configurable paths ---
DATA_OUTPUT_DIR=/home/tony-tran/greekroom-data/output-EPH
VIS_OUTPUT=/home/tony-tran/greekroom-data/output-EPH-visualization
SMART_EDIT_DISTANCE_SRC=/home/tony-tran/dev/greek-room/smart_edit_distance/src
COST_RULES_FILE=/home/tony-tran/dev/greek-room/smart_edit_distance/data/string-distance-cost-rules.txt
SCRIPT=/home/tony-tran/dev/greek-room/utilities/ualign.py

# --- Execution ---
cd "$DATA_OUTPUT_DIR"

# Set Python path for smart_edit_distance
export PYTHONPATH="$SMART_EDIT_DISTANCE_SRC"

# Check if alignment file exists
if [ ! -f "align_lc" ]; then
    echo "Error: align_lc file not found!"
    echo "Please run \"run-alignment.sh\" first"
    exit 1
fi

echo "Running ualign.py..."
echo ""

# Create empty battery file if it doesn't exist (it will be populated by ualign.py)
touch battery.jsonl

# Run ualign.py (without -m flag since morph_variants.txt doesn't exist)
python "$SCRIPT" \
  -t e_f_ref.txt \
  -a align_lc \
  -e English \
  -f Vietnamese \
  -c "$COST_RULES_FILE" \
  -b battery.jsonl \
  -l log-ualign.txt \
  -v "$VIS_OUTPUT" \
  -o model.txt

echo ""
echo "Done! Check the output:"
echo "  - HTML visualizations: $VIS_OUTPUT"
echo "  - Spell checker: battery-e.html, battery-f.html (in current directory)"
echo "  - Log: log-ualign.txt"
echo "  - Model: model.txt"


