#!/usr/bin/env python3
"""
Pipeline to run: prep -> alignment -> ualign

This script converts the bash pipeline script to Python, maintaining the same
functionality for running the three-step pipeline process.

Example:
    python run_pipeline.py

Note: needs to run twice to render the chapters correctly!
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from alignment_config import AlignmentConfig, default_config


# --- Configurable paths ---
DATA_DIR = Path("/home/tony-tran/greekroom-data")
DATA_OUTPUT_DIR = DATA_DIR / "output-with-py-pipeline"

BASE_VREF_FILE = Path("/home/tony-tran/dev/greek-room/ephesus/data/vref.txt")
SMART_EDIT_DISTANCE_SRC = Path("/home/tony-tran/dev/greek-room/smart_edit_distance/src")
COST_RULES_FILE = Path("/home/tony-tran/dev/greek-room/smart_edit_distance/data/string-distance-cost-rules.txt")

EXEC_DIR = Path("/home/tony-tran/dev/greek-room/utilities")
PREP_WRAPPER_SCRIPT = EXEC_DIR / "prep_usfm.py"
PREP_CORPUS_SCRIPT = EXEC_DIR / "parallel-corpus-prep.py"
UALIGN_SCRIPT = EXEC_DIR / "ualign.py"
VIS_OUTPUT = DATA_OUTPUT_DIR / "visualization"

# note: needs to clone fast_align repo first. See https://github.com/clab/fast_align
FAST_ALIGN_SRC_DIR = Path("/home/tony-tran/dev/fast_align")
FAST_ALIGN_BINARY = FAST_ALIGN_SRC_DIR / "build" / "fast_align"
ATOOLS_BINARY = FAST_ALIGN_SRC_DIR / "build" / "atools"


class AlignmentPipeline:
    """Pipeline executor for running prep -> alignment -> ualign steps.
    
    Attributes:
        config: AlignmentConfig instance containing the required arguments for alignment.
    """
    
    def __init__(self, config: AlignmentConfig):
        """Initialize alignment pipeline with configuration.
        
        Args:
            config: AlignmentConfig instance. If None, uses default_config.
        """
        self.config = config
    
    @staticmethod
    def _run_command(cmd: List[str], cwd: Optional[Path] = None, check: bool = True, env: Optional[dict] = None) -> subprocess.CompletedProcess:
        """Run a command and return the result.
        
        Args:
            cmd: Command and arguments as a list
            cwd: Working directory for the command
            check: If True, raise CalledProcessError on non-zero exit
            env: Environment variables dict (if None, uses current environment)
            
        Returns:
            CompletedProcess object
        """
        print(f"Running: {' '.join(str(x) for x in cmd)}")
        if cwd:
            print(f"  in directory: {cwd}")
        
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            env=env,
            capture_output=False  # Let output go to stdout/stderr
        )
        return result


    def _run_prep_step(self) -> None:
        """Run the prep step of the pipeline using instance config."""
        print("================ PREP =================")
        
        # Change to DATA_DIR
        os.chdir(DATA_DIR)
        
        # Set PYTHONPATH
        env = os.environ.copy()
        pythonpath = str(SMART_EDIT_DISTANCE_SRC)
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{pythonpath}:{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = pythonpath
        
        # Build arguments for prep_usfm.py from config
        prep_args: List[str] = [
            "-e", self.config.e_filename,
            "-f", self.config.f_filename,
            "-E", self.config.e_config_id,
            "-F", self.config.f_config_id,
            "-c", self.config.config_path,
        ]

        # Build command: prep_usfm.py with all args plus -r, -p, -o
        cmd = [
            sys.executable,
            str(PREP_WRAPPER_SCRIPT),
            *prep_args,
            "-r", str(BASE_VREF_FILE),
            "-p", str(PREP_CORPUS_SCRIPT),
            "-o", str(DATA_OUTPUT_DIR)
        ]
        
        self._run_command(cmd, cwd=DATA_DIR, check=True, env=env)


    def _run_alignment_step(self) -> None:
        """Run the alignment step using fast_align."""
        print("\n================ ALIGNMENT =================")
        
        # Check if fast_align binary exists
        if not FAST_ALIGN_BINARY.exists():
            print(f"Error: fast_align not found at {FAST_ALIGN_BINARY}")
            print("Please build fast_align first:")
            print(f"  cd {FAST_ALIGN_SRC_DIR}")
            print("  mkdir -p build && cd build")
            print("  cmake .. && make")
            sys.exit(1)
        
        # Check if atools binary exists
        if not ATOOLS_BINARY.exists():
            print(f"Error: atools not found at {ATOOLS_BINARY}")
            print("Please build fast_align first:")
            print(f"  cd {FAST_ALIGN_SRC_DIR}")
            print("  mkdir -p build && cd build")
            print("  cmake .. && make")
            sys.exit(1)
        
        # Change to output directory
        os.chdir(DATA_OUTPUT_DIR)
        
        # Check if e_f_ref.txt exists
        e_f_ref_file = DATA_OUTPUT_DIR / "e_f_ref.txt"
        if not e_f_ref_file.exists():
            print(f"Error: e_f_ref.txt not found in {DATA_OUTPUT_DIR}")
            print("Please run prep step first")
            sys.exit(1)
        
        # Run awk command to create e_f_lc_noref.txt
        e_f_lc_noref_file = DATA_OUTPUT_DIR / "e_f_lc_noref.txt"
        with open(e_f_ref_file, 'r', encoding='utf-8') as infile, \
             open(e_f_lc_noref_file, 'w', encoding='utf-8') as outfile:
            for line in infile:
                # Split on ' ||| ' and take first two parts
                parts = line.strip().split(' ||| ')
                if len(parts) >= 2:
                    outfile.write(f"{parts[0]} ||| {parts[1]}\n")
        
        # Run forward alignment
        forward_align_file = DATA_OUTPUT_DIR / "forward.align"
        with open(forward_align_file, 'w', encoding='utf-8') as outfile:
            result = subprocess.run(
                [str(FAST_ALIGN_BINARY), "-i", str(e_f_lc_noref_file), "-d", "-o", "-v"],
                cwd=DATA_OUTPUT_DIR,
                stdout=outfile,
                stderr=subprocess.DEVNULL,
                check=True
            )
        
        # Run reverse alignment
        reverse_align_file = DATA_OUTPUT_DIR / "reverse.align"
        with open(reverse_align_file, 'w', encoding='utf-8') as outfile:
            result = subprocess.run(
                [str(FAST_ALIGN_BINARY), "-i", str(e_f_lc_noref_file), "-d", "-o", "-v", "-r"],
                cwd=DATA_OUTPUT_DIR,
                stdout=outfile,
                stderr=subprocess.DEVNULL,
                check=True
            )
        
        # Run atools to combine alignments
        align_lc_file = DATA_OUTPUT_DIR / "align_lc"
        with open(align_lc_file, 'w', encoding='utf-8') as outfile:
            result = subprocess.run(
                [str(ATOOLS_BINARY), "-i", str(forward_align_file), "-j", str(reverse_align_file), 
                 "-c", "grow-diag-final-and"],
                cwd=DATA_OUTPUT_DIR,
                stdout=outfile,
                stderr=subprocess.DEVNULL,
                check=True
            )
        
        print("Done! Alignment file created: align_lc")


    def _run_ualign_step(self) -> None:
        """Run the ualign step of the pipeline using instance config."""
        print("\n================ UALIGN =================")
        
        # Change to output directory
        os.chdir(DATA_OUTPUT_DIR)
        
        # Check if align_lc exists
        align_lc_file = DATA_OUTPUT_DIR / "align_lc"
        if not align_lc_file.exists():
            print("Error: align_lc file not found!")
            print("Please run alignment step first")
            sys.exit(1)
        
        # Check if e_f_ref.txt exists
        e_f_ref_file = DATA_OUTPUT_DIR / "e_f_ref.txt"
        if not e_f_ref_file.exists():
            print(f"Error: e_f_ref.txt not found in {DATA_OUTPUT_DIR}")
            print("Please run prep step first")
            sys.exit(1)
        
        # Set PYTHONPATH
        env = os.environ.copy()
        pythonpath = str(SMART_EDIT_DISTANCE_SRC)
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{pythonpath}:{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = pythonpath
        
        # Create battery.jsonl if it doesn't exist
        battery_file = DATA_OUTPUT_DIR / "battery.jsonl"
        battery_file.touch()
        
        print("Running ualign.py...")
        print()
        
        # Build ualign command
        cmd = [
            sys.executable,
            str(UALIGN_SCRIPT),
            "-t", str(e_f_ref_file),
            "-a", str(align_lc_file),
            "-e", self.config.e_lang_name,
            "-f", self.config.f_lang_name,
            "-c", str(COST_RULES_FILE),
            "-b", str(battery_file),
            "-l", str(DATA_OUTPUT_DIR / "log-ualign.txt"),
            "-v", str(VIS_OUTPUT),
            "-o", str(DATA_OUTPUT_DIR / "model.txt")
        ]
        
        self._run_command(cmd, cwd=DATA_OUTPUT_DIR, check=True, env=env)
        
        print()
        print("Pipeline completed. Check outputs:")
        print(f"  - Alignments: {DATA_OUTPUT_DIR / 'align_lc'}")
        print(f"  - HTML visualizations: {VIS_OUTPUT}")
        print(f"  - Spell checker: battery-e.html, battery-f.html (in {DATA_OUTPUT_DIR})")
        print(f"  - Log: {DATA_OUTPUT_DIR / 'log-ualign.txt'}")
        print(f"  - Model: {DATA_OUTPUT_DIR / 'model.txt'}")
    
    def run(self) -> None:
        """Run the complete pipeline: prep -> alignment -> ualign."""
        self._run_prep_step()
        self._run_alignment_step()
        self._run_ualign_step()


def main() -> None:
    """Main entry point for the pipeline script.
    
    Args:
        config: Optional AlignmentConfig instance. If None, uses default_config.
                This allows other modules to provide custom configuration.
    """
    try:
        # Create pipeline instance with provided or default config
        pipeline = AlignmentPipeline(config=default_config)
        
        # Run the complete pipeline
        pipeline.run()
        
    except subprocess.CalledProcessError as e:
        print(f"\nError: Command failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()