## OWL Repeated Words Checker

Command-line tool for detecting consecutive duplicate words (e.g., "the the").

### Environment
- Use the project virtual environment at `.virtual/`.
- Install or update the local package when dependencies or code change:

```bash
cd /home/tony-tran/dev/greek-room
./.virtual/bin/python -m pip install -U pip setuptools wheel
./.virtual/bin/python -m pip install -e ./greekroom
```

### Usage

```bash
./.virtual/bin/python -m greekroom.owl.repeated_words [options]
```

#### Options
- `-j, --json TEXT`  Input JSON text or path to JSON file (alternative 1).
- `-i, --in_filename PATH`  Plain text file with one sentence per line (alternative 2).
- `-r, --ref_filename PATH`  Verse/reference file aligned to `--in_filename` (default: `vref.txt`).
- `-o, --out_filename PATH`  Write JSON output to this file.
- `--html PATH`  Write HTML report to this file.
- `--project_name TEXT`  Full project name for labeling outputs.
- `--lang_code LANGUAGE-CODE`  ISO 639-3 code (e.g., `fas`, `ceb`).
- `--lang_name TEXT`  Human-readable language name.
- `--message_id TEXT`  Identifier for the request (auto-generated when using `-i`).
- `-d, --data_filenames TEXT`  Comma-separated list of data files to load (e.g., `legitimate_duplicates.jsonl`).
- `--verbose`  Increase verbosity (repeat for more verbosity).

At least one of `--json` or `--in_filename` must be provided.

### Data files for legitimate duplicates
If not explicitly provided via `--data_filenames`, the tool searches for `legitimate_duplicates.jsonl` in:
- The package data directory: `greekroom/owl/data/`
- Standard data dirs: `$XDG_DATA_HOME/greekroom/owl/data/`, `$HOME/.local/share/greekroom/owl/data/`, `/usr/share/greekroom/owl/data/`

### Examples

1) JSON input file, JSON output only:
```bash
./.virtual/bin/python -m greekroom.owl.repeated_words \
  -j path/to/input.json \
  --lang_code ceb --lang_name Cebuano \
  --out_filename path/to/output.json
```

2) Inline JSON string, HTML report:
```bash
./.virtual/bin/python -m greekroom.owl.repeated_words \
  -j '{"jsonrpc":"2.0","id":"msg-01","method":"BibleTranslationCheck","params":[{"lang-code":"eng","check-corpus":[{"snt-id":"JHN 1:1","text":"In the the beginning."}]}]}' \
  --html path/to/report.html
```

3) Plain text corpus with verse refs, JSON and HTML outputs:
```bash
./.virtual/bin/python -m greekroom.owl.repeated_words \
  -i path/to/corpus.txt \
  -r path/to/vref.txt \
  --lang_code fas --lang_name Persian \
  --project_name "My Project" \
  --out_filename path/to/output.json \
  --html path/to/output.html
```

### Help
```bash
./.virtual/bin/python -m greekroom.owl.repeated_words -h
```


