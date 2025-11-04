import sys
from pathlib import Path
from machine.corpora import (
    UsfmFileTextCorpus,
    extract_scripture_corpus,
)

def build_corpus_from_path(path: Path):
    """Return a Machine corpus given a path to a USFM file or a directory.

    Preference order:
    - If a USFM/SFM file is provided, use its parent dir and suffix
    - Else, if a directory contains USFM files, use the first one's suffix for pattern
    """
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    # If a single file is given
    if path.is_file():
        parent = path.parent
        suffix = path.suffix
        return UsfmFileTextCorpus(parent.resolve(strict=True), file_pattern=f"*{suffix}")

    # Otherwise, treat as a directory of USFM files
    if path.is_dir():
        return UsfmFileTextCorpus(
            path.resolve(strict=True),
            file_pattern="*.usfm"
        )

    return None


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python utilities/dummy.py <path-to-usfm-file-or-dir> <output-vref.txt>"
        )
        sys.exit(1)

    target_path = Path(sys.argv[1]).expanduser().resolve()
    output_path = Path(sys.argv[2]).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    corpus = build_corpus_from_path(target_path)

    if not corpus:
        print(
            "Unable to create a corpus. Provide a USFM/SFM file or a directory containing USFM files."
        )
        sys.exit(2)

    # Extract and write VREFs with verse text (empty line if verse text is missing)
    with output_path.open("w", encoding="utf-8") as vref_file:
        for verse_text, _, vref in extract_scripture_corpus(corpus):
            if verse_text is not None and verse_text.strip() != "":
                vref_file.write(f"{verse_text}\n")
            else:
                vref_file.write("\n")


if __name__ == "__main__":
    main()


