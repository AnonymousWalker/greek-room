"""Pipeline configuration settings."""

from dataclasses import dataclass


@dataclass
class AlignmentConfig:
    """Configuration for alignment pipeline execution.
    
    All fields are required. Use default_config for default values.
    """
    
    # Language names for ualign
    e_lang_name: str
    f_lang_name: str
    
    # Default values for arguments (used when not provided on CLI)
    # E and F could be usfm files or directories
    e_filename: str
    f_filename: str
    e_config_id: str
    f_config_id: str
    config_path: str


# Default configuration instance with default values
default_config = AlignmentConfig(
    e_lang_name="English",
    f_lang_name="Vietnamese",
    e_filename="en-EPH.usfm",
    f_filename="vi-EPH.usfm",
    e_config_id="en-ULB",
    f_config_id="vi-ULB",
    config_path="/home/tony-tran/greekroom-data/envi-lc-config.jsonl"
)

