#!/bin/bash
# Script to run ualign.py after word alignments are created

cd /home/{user}/greekroom-data/out

# Set Python path for smart_edit_distance
export PYTHONPATH=/home/{user}/dev/greek-room/smart_edit_distance/src

# Check if alignment file exists
if [ ! -f "align_lc" ]; then
    echo "Error: align_lc file not found!"
    echo "Please run /home/{user}/greekroom-data/run-alignment.sh first"
    exit 1
fi

echo "Running ualign.py..."
echo ""

# Create empty battery file if it doesn't exist (it will be populated by ualign.py)
touch battery.jsonl

# Run ualign.py (without -m flag since morph_variants.txt doesn't exist)
# set the output visualization directory with -v flag
python /home/{user}/dev/greek-room/utilities/ualign.py \
  -t e_f_ref.txt \
  -a align_lc \
  -e English \
  -f Vietnamese \
  -c /home/{user}/dev/greek-room/smart_edit_distance/data/string-distance-cost-rules.txt \
  -b battery.jsonl \
  -l log-ualign.txt \
  -v /home/{user}/greekroom-data/output-visualization \
  -o model.txt

echo ""
echo "Done! Check the output:"
echo "  - HTML visualizations: /home/{user}/greekroom-data/output-visualization"
echo "  - Spell checker: battery-e.html, battery-f.html (in current directory)"
echo "  - Log: log-ualign.txt"
echo "  - Model: model.txt"


