# Greek Room Word Alignment Workflow

## Complete Step-by-Step Guide

### Prerequisites
Python 3.11+

#### Replace `{user}` with your local username

1. **Install build tools** (run once):
   ```bash
   sudo apt install -y cmake build-essential
   ```

2. **Build fast_align** (run once):
   ```bash
   cd /home/{user}/dev/fast_align
   mkdir -p build && cd build
   cmake ..
   make
   ```

3. **install python deps**
  Activate python virtual env and install dependencies

   ```bash
   source /path/to/python_venv/activate
   pip install utoken wildebeest-nlp regex
   ```

### Workflow

#### Step 1: Prepare Parallel Corpus
Activate python virtual env.

Prepare a `translation-config.jsonl` file with these two objects below and use it for run-prep:
```json
{"id":"en-ULB","lc":"en","lang":"English"}
{"id":"vi-ULB","lc":"vi","lang":"Vietnamese"}
```
Run the command below, where -c -E -F arguments are optional.

```bash
mkdir -p /home/{user}/greekroom-data
cd /home/{user}/greekroom-data
./run-prep.sh -e {source_sentences_txt_file} -f {target_sentences_txt_file} -r /home/{user}/dev/greek-room/ephesus/data/vref.txt -c /path/to/translation-config.jsonl -E {source_id_in_config} -F {target_id_in_config} -o out
```

**Output**: Creates tokenized and normalized files in `out/` directory

#### Step 2: Generate Word Alignments
```bash
./run-alignment.sh
```

**What it does**:
- Runs fast_align in both directions (forward and reverse)
- Symmetrizes alignments using grow-diag-final-and heuristic
- Creates `out/align_lc` file

**Output format** (Pharaoh): `0-0 1-1 2-3 3-2 4-4`
- Each pair `i-j` means word at position i in English aligns to word at position j in Vietnamese

#### Step 3: Run ualign.py
Check the CLI arguments in run-ualign.sh and adjust them accordingly before running
```bash
./run-ualign.sh
```

**What it does**:
- Refines alignments using linguistic knowledge
- Creates HTML visualizations
- Generates spell-checker reports
- Saves alignment model

**Outputs**:
- `{outputDir}/battery-e.html` - English spell checker
- `{outputDir}/battery-f.html` - Vietnamese spell checker
- `{outputDir}/log-ualign.txt` - Processing log
- `{outputDir}/model.txt` - Trained alignment model (can be reused)

### View Results
Open the html visualization file created from ualign.py denoted by -v {path-to-visualization-output}
