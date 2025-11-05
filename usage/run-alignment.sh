#!/bin/bash
# Script to create word alignments using fast_align

# --- Configurable paths ---
DATA_OUTPUT_DIR=/home/tony-tran/greekroom-data/output-EPH
FAST_ALIGN_SRC_DIR=/home/tony-tran/dev/fast_align

# Derived paths
FAST_ALIGN_BUILD_DIR="$FAST_ALIGN_SRC_DIR/build"
FAST_ALIGN="$FAST_ALIGN_BUILD_DIR/fast_align"
ATOOLS="$FAST_ALIGN_BUILD_DIR/atools"

# --- Execution ---
cd "$DATA_OUTPUT_DIR"

# Check if fast_align exists
if [ ! -f "$FAST_ALIGN" ]; then
    echo "Error: fast_align not found at $FAST_ALIGN"
    echo "Please build fast_align first:"
    echo "  cd $FAST_ALIGN_SRC_DIR"
    echo "  mkdir -p build && cd build"
    echo "  cmake .. && make"
    exit 1
fi

echo "Creating word alignments..."

# Prepare input (without reference column)
awk -F' \\|\\|\\| ' '{print $1" ||| "$2}' e_f_ref.txt > e_f_lc_noref.txt

# Run forward alignment (English -> Vietnamese)
echo "Running forward alignment..."
"$FAST_ALIGN" -i e_f_lc_noref.txt -d -o -v > forward.align

# Run reverse alignment (Vietnamese -> English)
echo "Running reverse alignment..."
"$FAST_ALIGN" -i e_f_lc_noref.txt -d -o -v -r > reverse.align

# Symmetrize alignments using grow-diag-final-and
echo "Symmetrizing alignments..."
"$ATOOLS" -i forward.align -j reverse.align -c grow-diag-final-and > align_lc

echo "Done! Alignment file created: align_lc"
echo ""
echo "Line count:"
wc -l align_lc
echo ""
echo "First 5 alignments:"
head -5 align_lc

