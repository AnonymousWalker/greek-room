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
import json
import zipfile
import yaml
import tempfile
from pathlib import Path
from typing import List, Optional

from alignment_config import AlignmentConfig, default_config


ROOT_DIR = Path(os.getenv("ROOT_DIR", "/home/tony-tran/dev/greek-room"))
BASE_VREF_FILE = os.path.join(ROOT_DIR, "ephesus/data/vref.txt")
SMART_EDIT_DISTANCE_SRC = os.path.join(ROOT_DIR, "smart_edit_distance/src")
COST_RULES_FILE = os.path.join(ROOT_DIR, "smart_edit_distance/data/string-distance-cost-rules.txt")

SCRIPT_DIR = ROOT_DIR / "utilities"
PREP_WRAPPER_SCRIPT = SCRIPT_DIR / "prep_usfm.py"
PREP_CORPUS_SCRIPT = SCRIPT_DIR / "parallel-corpus-prep.py"
UALIGN_SCRIPT = SCRIPT_DIR / "ualign.py"

# note: needs to clone fast_align repo first. See https://github.com/clab/fast_align
FAST_ALIGN_SRC_DIR = Path(os.getenv("FAST_ALIGN_SRC_DIR", "/home/tony-tran/dev/fast_align"))
FAST_ALIGN_BINARY = FAST_ALIGN_SRC_DIR / "build" / "fast_align"
ATOOLS_BINARY = FAST_ALIGN_SRC_DIR / "build" / "atools"


class AlignmentPipeline:
    def __init__(self, config: AlignmentConfig, temp_dir: str | None):
        """Initialize alignment pipeline with configuration.
        
        Args:
            config: AlignmentConfig instance. If None, uses default_config.
        """
        self.config = config
        self.DATA_DIR = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix="greekroom-data"))
        self.DATA_OUTPUT_DIR = self.DATA_DIR / "output"
        self.VIS_OUTPUT = self.DATA_OUTPUT_DIR / "visualization"
    
    @staticmethod
    def _load_metadata_from_yaml(path: str) -> tuple[str, str, str]:
        with open(path, 'r') as f:
            config = yaml.safe_load(f)

        language_id = config['dublin_core']['language']['identifier']
        language_name = config['dublin_core']['language']['title']
        resource_id = config['dublin_core']['identifier']

        return language_id, language_name, resource_id
    
    @classmethod
    def load_config_from_repos(cls, source_repo_path: str, target_repo_path: str, temp_dir: str | None) -> AlignmentConfig:
        """
        Load configuration from source and target repositories.
        Writes a JSONL config file under tempDir and returns an AlignmentConfig instance.
        
        Args:
            source_repo_path: Path to the source repository directory.
            target_repo_path: Path to the target repository directory.
            tempDir: Temporary directory where the JSONL config file will be written.
            
        Returns:
            AlignmentConfig instance configured with the repository metadata.
        """
        src_manifest_path = os.path.join(source_repo_path, "manifest.yaml")
        tgt_manifest_path = os.path.join(target_repo_path, "manifest.yaml")
        
        (src_language_id, src_language_name, src_resource_id) = cls._load_metadata_from_yaml(src_manifest_path)
        (tgt_language_id, tgt_language_name, tgt_resource_id) = cls._load_metadata_from_yaml(tgt_manifest_path)
        src_config_id = f"{src_language_id}-{src_resource_id.upper()}"
        tgt_config_id = f"{tgt_language_id}-{tgt_resource_id.upper()}"

        # Create config list from the repo metadata
        json_configs = [
            {
                "id": src_config_id,
                "lc": src_language_id,
                "lang": src_language_name
            },
            {
                "id": tgt_config_id,
                "lc": tgt_language_id,
                "lang": tgt_language_name
            }
        ]

        # Write config list to a JSONL file in tempDir
        jsonl_path = os.path.join(temp_dir, "lc-config.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for entry in json_configs:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Return an AlignmentConfig instance using the config
        return AlignmentConfig(
            e_lang_name=src_language_name,
            f_lang_name=tgt_language_name,
            e_filename=source_repo_path,
            f_filename=target_repo_path,
            e_config_id=src_config_id,
            f_config_id=tgt_config_id,
            config_path=jsonl_path
        )
    
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
        os.chdir(self.DATA_DIR)
        
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
            "-o", str(self.DATA_OUTPUT_DIR)
        ]
        
        self._run_command(cmd, cwd=self.DATA_DIR, check=True, env=env)


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
        os.chdir(self.DATA_OUTPUT_DIR)
        
        # Check if e_f_ref.txt exists
        e_f_ref_file = self.DATA_OUTPUT_DIR / "e_f_ref.txt"
        if not e_f_ref_file.exists():
            print(f"Error: e_f_ref.txt not found in {self.DATA_OUTPUT_DIR}")
            print("Please run prep step first")
            sys.exit(1)
        
        # Run awk command to create e_f_lc_noref.txt
        e_f_lc_noref_file = self.DATA_OUTPUT_DIR / "e_f_lc_noref.txt"
        with open(e_f_ref_file, 'r', encoding='utf-8') as infile, \
             open(e_f_lc_noref_file, 'w', encoding='utf-8') as outfile:
            for line in infile:
                # Split on ' ||| ' and take first two parts
                parts = line.strip().split(' ||| ')
                if len(parts) >= 2:
                    outfile.write(f"{parts[0]} ||| {parts[1]}\n")
        
        # Run forward alignment
        forward_align_file = self.DATA_OUTPUT_DIR / "forward.align"
        with open(forward_align_file, 'w', encoding='utf-8') as outfile:
            result = subprocess.run(
                [str(FAST_ALIGN_BINARY), "-i", str(e_f_lc_noref_file), "-d", "-o", "-v"],
                cwd=self.DATA_OUTPUT_DIR,
                stdout=outfile,
                stderr=subprocess.DEVNULL,
                check=True
            )
        
        # Run reverse alignment
        reverse_align_file = self.DATA_OUTPUT_DIR / "reverse.align"
        with open(reverse_align_file, 'w', encoding='utf-8') as outfile:
            result = subprocess.run(
                [str(FAST_ALIGN_BINARY), "-i", str(e_f_lc_noref_file), "-d", "-o", "-v", "-r"],
                cwd=self.DATA_OUTPUT_DIR,
                stdout=outfile,
                stderr=subprocess.DEVNULL,
                check=True
            )
        
        # Run atools to combine alignments
        align_lc_file = self.DATA_OUTPUT_DIR / "align_lc"
        with open(align_lc_file, 'w', encoding='utf-8') as outfile:
            result = subprocess.run(
                [str(ATOOLS_BINARY), "-i", str(forward_align_file), "-j", str(reverse_align_file), 
                 "-c", "grow-diag-final-and"],
                cwd=self.DATA_OUTPUT_DIR,
                stdout=outfile,
                stderr=subprocess.DEVNULL,
                check=True
            )
        
        print("Done! Alignment file created: align_lc")


    def _run_ualign_step(self) -> None:
        """Run the ualign step of the pipeline using instance config."""
        print("\n================ UALIGN =================")
        
        # Change to output directory
        os.chdir(self.DATA_OUTPUT_DIR)
        
        # Check if align_lc exists
        align_lc_file = self.DATA_OUTPUT_DIR / "align_lc"
        if not align_lc_file.exists():
            print("Error: align_lc file not found!")
            print("Please run alignment step first")
            sys.exit(1)
        
        # Check if e_f_ref.txt exists
        e_f_ref_file = self.DATA_OUTPUT_DIR / "e_f_ref.txt"
        if not e_f_ref_file.exists():
            print(f"Error: e_f_ref.txt not found in {self.DATA_OUTPUT_DIR}")
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
        battery_file = self.DATA_OUTPUT_DIR / "battery.jsonl"
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
            "-l", str(self.DATA_OUTPUT_DIR / "log-ualign.txt"),
            "-v", str(self.VIS_OUTPUT),
            "-o", str(self.DATA_OUTPUT_DIR / "model.txt")
        ]
        
        self._run_command(cmd, cwd=self.DATA_OUTPUT_DIR, check=True, env=env)
        
        print()
        print("Pipeline completed. Check outputs:")
        print(f"  - Alignments: {self.DATA_OUTPUT_DIR / 'align_lc'}")
        print(f"  - HTML visualizations: {self.VIS_OUTPUT}")
        print(f"  - Spell checker: battery-e.html, battery-f.html (in {self.DATA_OUTPUT_DIR})")
        print(f"  - Log: {self.DATA_OUTPUT_DIR / 'log-ualign.txt'}")
        print(f"  - Model: {self.DATA_OUTPUT_DIR / 'model.txt'}")

    def _compress_output_dir(self):
        """Compress the VIS_OUTPUT directory into a .zip file."""
        zip_file = self.DATA_OUTPUT_DIR / "visualization-output.zip"
        with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as zipf:
            for file in self.VIS_OUTPUT.rglob('*'):
                if file.is_file():
                    zipf.write(file, file.relative_to(self.DATA_OUTPUT_DIR))
            
            # Include spell-check HTML files if they exist
            battery_e = self.DATA_OUTPUT_DIR / "battery-e.html"
            battery_f = self.DATA_OUTPUT_DIR / "battery-f.html"
            if battery_e.exists():
                zipf.write(battery_e, "src-spellings.html")
            if battery_f.exists():
                zipf.write(battery_f, "tgt-spellings.html")
        return zip_file
    
    def run(self) -> Path:
        """Run the complete pipeline: prep -> alignment -> ualign."""
        self._run_prep_step()
        self._run_alignment_step()
        self._run_ualign_step()
        self._run_ualign_step() # run again to render the chapters availability
        return self._compress_output_dir()

        
def main(source_repo_path: str, target_repo_path: str):
    """Main entry point for the pipeline script.
    
    Args:
        config: Optional AlignmentConfig instance. If None, uses default_config.
                This allows other modules to provide custom configuration.
    """
    
    try:
        # Create pipeline instance with provided or default config
        with tempfile.TemporaryDirectory(delete=False) as temp_dir:
            config = AlignmentPipeline.load_config_from_repos(source_repo_path, target_repo_path, temp_dir)
            pipeline = AlignmentPipeline(config=config, temp_dir=temp_dir)
            pipeline.run()
            print(f"Pipeline completed. Check outputs: {temp_dir}")

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
    main(sys.argv[1], sys.argv[2])