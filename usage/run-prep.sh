#!/bin/bash
# Helper script to run parallel-corpus-prep.py

# --- Configurable paths ---
DATA_DIR=/home/tony-tran/greekroom-data
SMART_EDIT_DISTANCE_SRC=/home/tony-tran/dev/greek-room/smart_edit_distance/src
UTILITIES_DIR=/home/tony-tran/dev/greek-room/utilities

# --- Execution ---
cd "$DATA_DIR"
export PYTHONPATH="$SMART_EDIT_DISTANCE_SRC"

python "$UTILITIES_DIR/parallel-corpus-prep.py" "$@"

