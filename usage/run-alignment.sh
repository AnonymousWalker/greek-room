#!/bin/bash
# Script to create word alignments using fast_align

cd /home/{user}/greekroom-data/out

# Check if fast_align exists
FAST_ALIGN=/home/{user}/dev/fast_align/build/fast_align
ATOOLS=/home/{user}/dev/fast_align/build/atools

if [ ! -f "$FAST_ALIGN" ]; then
    echo "Error: fast_align not found at $FAST_ALIGN"
    echo "Please build fast_align first:"
    echo "  cd /home/{user}/dev/fast_align"
    echo "  mkdir -p build && cd build"
    echo "  cmake .. && make"
    exit 1
fi

echo "Creating word alignments..."

# Prepare input (without reference column)
awk -F' \\|\\|\\| ' '{print $1" ||| "$2}' e_f_ref.txt > e_f_lc_noref.txt

# Run forward alignment (English -> Vietnamese)
echo "Running forward alignment..."
$FAST_ALIGN -i e_f_lc_noref.txt -d -o -v > forward.align

# Run reverse alignment (Vietnamese -> English)
echo "Running reverse alignment..."
$FAST_ALIGN -i e_f_lc_noref.txt -d -o -v -r > reverse.align

# Symmetrize alignments using grow-diag-final-and
echo "Symmetrizing alignments..."
$ATOOLS -i forward.align -j reverse.align -c grow-diag-final-and > align_lc

echo "Done! Alignment file created: align_lc"
echo ""
echo "Line count:"
wc -l align_lc
echo ""
echo "First 5 alignments:"
head -5 align_lc

