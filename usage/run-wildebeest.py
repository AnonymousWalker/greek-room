import argparse
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from utilities.prep_usfm import convert_usfm_to_vref
from wildebeest import wb_analysis

def run_wildebeest_analysis(usfm_path: Path, output_path: Path) -> Path:
    """Run the Wildebeest analysis on the given USFM file and write JSON output."""
    with tempfile.TemporaryDirectory(dir="/home/tony-tran/greekroom-data/temp") as temp_dir:
        temp_path = Path(temp_dir)
        vref_text_path = convert_usfm_to_vref(usfm_path, temp_path)
        ref_id_dict = wb_analysis.load_ref_ids("/home/tony-tran/dev/greek-room/ephesus/data/vref.txt")

        output_path = output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        suffix = output_path.suffix.lower()
        if suffix in {".txt", ".text"}:
            with output_path.open("w", encoding="utf-8") as pp_output:
                wb_analysis.process(
                    in_file=str(vref_text_path),
                    ref_id_dict=ref_id_dict,
                    pp_output=pp_output,
                )
        elif suffix == ".json":
            with output_path.open("w", encoding="utf-8") as json_output:
                wb_analysis.process(
                    in_file=str(vref_text_path),
                    ref_id_dict=ref_id_dict,
                    json_output=json_output,
                )

        return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Run the Wildebeest analysis on the given USFM file."
    )
    parser.add_argument(
        "-f", "--usfm-file",
        required=True,
        type=Path,
        help="Path to the USFM file to process.",
    )
    parser.add_argument(
        "-o", "--output-file",
        required=True,
        type=Path,
        help="Path to the output JSON file.",
    )
    args = parser.parse_args()
    run_wildebeest_analysis(args.usfm_file, args.output_file)

if __name__ == "__main__":
    main()