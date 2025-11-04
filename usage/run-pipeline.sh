#!/bin/bash
# Pipeline to run: prep -> alignment -> ualign

# example:
# ./run-pipeline.sh \
#   -e en_EPH-vref.txt \
#   -f vi-EPH-vref.txt \
#   -c /home/tony-tran/greekroom-data/envi-lc-config.jsonl \
#   -E en-ULB \
#   -F vi-ULB \
#   -o output-EPH

# --- Configurable paths ---
DATA_DIR=/home/tony-tran/greekroom-data
DATA_OUTPUT_DIR=$DATA_DIR/output-EPH
VIS_OUTPUT=/home/tony-tran/greekroom-data/output-EPH-visualization

BASE_VREF_FILE=/home/tony-tran/dev/greek-room/ephesus/data/vref.txt
SMART_EDIT_DISTANCE_SRC=/home/tony-tran/dev/greek-room/smart_edit_distance/src
COST_RULES_FILE=/home/tony-tran/dev/greek-room/smart_edit_distance/data/string-distance-cost-rules.txt

EXEC_DIR=/home/tony-tran/dev/greek-room/utilities
PREP_SCRIPT=$EXEC_DIR/parallel-corpus-prep.py
UALIGN_SCRIPT=$EXEC_DIR/ualign.py

FAST_ALIGN_SRC_DIR=/home/tony-tran/dev/fast_align

echo "================ PREP ================="
cd "$DATA_DIR"
export PYTHONPATH="$SMART_EDIT_DISTANCE_SRC"
python "$PREP_SCRIPT" "$@" -r "$BASE_VREF_FILE"

echo "\n================ ALIGNMENT ================="
cd "$DATA_OUTPUT_DIR"
if [ ! -f "$FAST_ALIGN_SRC_DIR/build/fast_align" ]; then
    echo "Error: fast_align not found at $FAST_ALIGN_SRC_DIR/build/fast_align"
    echo "Please build fast_align first:"
    echo "  cd $FAST_ALIGN_SRC_DIR"
    echo "  mkdir -p build && cd build"
    echo "  cmake .. && make"
    exit 1
fi

awk -F' \|\|\| ' '{print $1" ||| "$2}' e_f_ref.txt > e_f_lc_noref.txt

"$FAST_ALIGN_SRC_DIR/build/fast_align" -i e_f_lc_noref.txt -d -o -v > forward.align

"$FAST_ALIGN_SRC_DIR/build/fast_align" -i e_f_lc_noref.txt -d -o -v -r > reverse.align

"$FAST_ALIGN_SRC_DIR/build/atools" -i forward.align -j reverse.align -c grow-diag-final-and > align_lc

echo "Done! Alignment file created: align_lc"

echo "\n================ UALIGN ================="
cd "$DATA_OUTPUT_DIR"
export PYTHONPATH="$SMART_EDIT_DISTANCE_SRC"

if [ ! -f "align_lc" ]; then
    echo "Error: align_lc file not found!"
    echo "Please run alignment step first"
    exit 1
fi

echo "Running ualign.py..."
echo ""

touch battery.jsonl
python "$UALIGN_SCRIPT" \
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
echo "Pipeline completed. Check outputs:"
echo "  - Alignments: $DATA_OUTPUT_DIR/align_lc"
echo "  - HTML visualizations: $VIS_OUTPUT"
echo "  - Spell checker: battery-e.html, battery-f.html (in $DATA_OUTPUT_DIR)"
echo "  - Log: $DATA_OUTPUT_DIR/log-ualign.txt"
echo "  - Model: $DATA_OUTPUT_DIR/model.txt"


