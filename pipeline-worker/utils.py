import logging
import os
import re
import zipfile
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def extract_file_from_zip(zip_path: Path, filename: str, output_path: Path):
    """Extract a specific file from a zip archive to a target file path."""
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        file_content = zip_file.read(filename)
        with open(output_path, 'wb') as f:
            f.write(file_content)


def split_alignment_zip_by_prefix(zip_path: Path, output_dir: Path) -> List[Path]:
    """
    Split an alignment zip file into multiple zip files grouped by three-letter prefix.
    The original zip contains files like:
    - visualization/1CH-001.html
    - visualization/EXO-002.html
    
    This function creates separate zip files for each three-letter prefix (e.g., 1CH, EXO).
    """
    os.makedirs(str(output_dir), exist_ok=True)
    
    pattern = re.compile(r'visualization/(\w{3})-\d{3}\.html')    
    prefix_groups: Dict[str, List[tuple]] = {}
    other_files: List[tuple] = []
    
    # Read the original zip and group files by prefix
    with zipfile.ZipFile(zip_path, 'r') as source_zip:
        for file_info in source_zip.infolist():
            filename = file_info.filename
            match = pattern.match(filename)
            
            if match:
                prefix = match.group(1)
                if prefix not in prefix_groups:
                    prefix_groups[prefix] = []

                file_data = source_zip.read(filename)
                prefix_groups[prefix].append((filename, file_info, file_data))
    
    # Create a zip file for each prefix group
    zip_splits: List[Path] = []
    
    for prefix, files in prefix_groups.items():
        zip_filename = output_dir / f"{prefix}.zip"
        
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as prefix_zip:
            # Add all files for this prefix
            for filename, file_info, file_data in files:
                prefix_zip.writestr(file_info, file_data)
            
            # Also include non-visualization files (e.g., spell-check files) in each prefix zip
            for filename, file_info, file_data in other_files:
                prefix_zip.writestr(file_info, file_data)
        
        zip_splits.append(zip_filename)
    
    logger.info(f"Split alignment zip into {len(zip_splits)} files by prefix")
    return zip_splits
