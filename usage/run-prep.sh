#!/bin/bash
# Helper script to run parallel-corpus-prep.py

cd /home/{user}/greekroom-data
export PYTHONPATH=/home/{user}/dev/greek-room/smart_edit_distance/src

python /home/{user}/dev/greek-room/utilities/parallel-corpus-prep.py "$@"

