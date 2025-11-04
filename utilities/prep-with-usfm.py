#!/usr/bin/env python3
"""
Wrapper script for parallel-corpus-prep.py that automatically converts USFM files
to vref.txt files when needed.

This script processes command-line arguments, checks if -e and -f arguments
point to USFM files (.usfm or .sfm), and converts them to vref.txt files
before passing all arguments to parallel-corpus-prep.py.
"""

import argparse
import sys
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from machine.corpora import (
    UsfmFileTextCorpus,
    extract_scripture_corpus,
)


def is_usfm_file(file_path: Path) -> bool:
    """Check if a file is a USFM file based on its extension."""
    if not file_path.exists():
        return False
    return file_path.suffix.lower() in ('.usfm', '.sfm')


def _build_corpus_from_path(path: Path) -> Optional[UsfmFileTextCorpus]:
    """Return a Machine corpus given a path to a USFM file or a directory.

    Preference order:
    - If a USFM/SFM file is provided, use its parent dir and suffix
    - Else, if a directory contains USFM files, use the first one's suffix for pattern
    """
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    if path.is_file() and is_usfm_file(path):
        parent = path.parent
        suffix = path.suffix
        return UsfmFileTextCorpus(parent.resolve(strict=True), file_pattern=path.name)

    if path.is_dir():
        return UsfmFileTextCorpus(path.resolve(strict=True), file_pattern="*.usfm")

    return None


def convert_usfm_to_vref(usfm_path: Path, output_dir: Path, config_id: Optional[str] = None) -> Path:
    """Convert a USFM file to vref.txt format.
    
    Args:
        usfm_path: Path to the USFM file
        output_dir: Directory where the converted file should be saved
        config_id: Optional config ID to prefix the filename (from -E or -F)
        
    Returns:
        Path to the converted vref.txt file
        
    Raises:
        ValueError: If unable to create a corpus from the path
        FileNotFoundError: If the path does not exist
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create output filename: use config_id if provided, otherwise use input filename stem
    output_filename = f"{config_id}-vref.txt" if config_id else f"{usfm_path.stem}-vref.txt"
    vref_path = output_dir / output_filename
    
    print(f"Converting USFM file: {usfm_path} -> {vref_path}")
    
    corpus = _build_corpus_from_path(usfm_path)
    if not corpus:
        raise ValueError(
            "Unable to create a corpus. Provide a USFM/SFM file or a directory containing USFM files."
        )
    
    # Extract and write VREFs with verse text (empty line if verse text is missing)
    with vref_path.open("w", encoding="utf-8") as vref_file:
        for verse_text, _, _ in extract_scripture_corpus(corpus):
            if verse_text and verse_text.strip():
                vref_file.write(f"{verse_text}\n")
            else:
                vref_file.write("\n")
    
    return vref_path

# def process_arguments(e_usfm_path: Path, f_usfm_path: Path, e_id: Optional[str], f_id: Optional[str], output_dir: Path) -> Tuple[Path, Path]:
#     if is_usfm_file(e_usfm_path):
#         e_vref_path = convert_usfm_to_vref(e_usfm_path, output_dir, e_id)
#     if is_usfm_file(f_usfm_path):
#         f_vref_path = convert_usfm_to_vref(f_usfm_path, output_dir, f_id)

#     return (e_vref_path, f_vref_path)

def main() -> None:
    """Main entry point for the script."""
    args = sys.argv[1:]
    
    # Parse arguments to find output_dir first (needed before processing)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-e', '--e_filename', type=Path)
    parser.add_argument('-f', '--f_filename', type=Path)
    parser.add_argument('-E', '--e_config_id', type=str)
    parser.add_argument('-F', '--f_config_id', type=str)
    parser.add_argument('-p', '--prep_corpus_script', type=str)
    parser.add_argument('-o', '--output_dir', type=Path)
    known_args, _ = parser.parse_known_args(args)
    
    if not known_args.output_dir:
        print("Error: Must specify output directory with -o or --output_dir", file=sys.stderr)
        sys.exit(1)
    
    output_dir = Path(known_args.output_dir).expanduser().resolve()
    e_usfm_path = Path(known_args.e_filename).expanduser().resolve()
    f_usfm_path = Path(known_args.f_filename).expanduser().resolve()
    e_id = known_args.e_config_id
    f_id = known_args.f_config_id
    
    e_vref_path = convert_usfm_to_vref(e_usfm_path, output_dir, e_id)
    f_vref_path = convert_usfm_to_vref(f_usfm_path, output_dir, f_id)

    # Build processed_args by replacing e_filename and f_filename with vref paths
    # and excluding -p/--prep_corpus_script and its value
    processed_args = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('-e', '--e_filename'):
            processed_args.append(arg)
            if i + 1 < len(args):
                processed_args.append(str(e_vref_path))
                i += 2  # Skip the next argument (original filename)
                continue
        elif arg in ('-f', '--f_filename'):
            processed_args.append(arg)
            if i + 1 < len(args):
                processed_args.append(str(f_vref_path))
                i += 2  # Skip the next argument (original filename)
                continue
        elif arg in ('-p', '--prep_corpus_script'):
            i += 2  # Skip -p flag and its value
            continue
        processed_args.append(arg)
        i += 1
    

    prep_script = known_args.prep_corpus_script
    print("processed_args: ", processed_args)
    print("prep_script: ", prep_script)
    
    # Call the prep script with processed arguments
    sys.exit(subprocess.run([sys.executable, prep_script] + processed_args).returncode)


if __name__ == '__main__':
    main()

