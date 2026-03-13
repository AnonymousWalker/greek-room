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


# Sample YAML file:    
# dublin_core:
#   conformsto: 'rc0.2'
#   contributor:
#     - "Vietnamgl1"
#     - "Vietnamgl2"
#     - "Vietnamgl3"
#     - "Vietnamgl4"
#     - 'Tri M Dang'
#     - 'VGM - Vietnamese translation team'
#   creator: 'Wycliffe Associates'
#   description: 'An unrestricted literal Bible'
#   format: 'text/usfm'
#   identifier: 'ulb'
#   issued: '2024-01-18'
#   language:
#     identifier: 'vi'
#     title: "Tiếng Việt"
#     direction: 'ltr'
#   modified: '2024-01-19'
#   publisher: 'WA'
#   relation:
#     - 'vi/tw'
#     - 'vi/tq'
#     - 'vi/tn'
#   rights: 'CC BY-SA 4.0'
#   source:
#     -
#       identifier: 'ulb'
#       language: 'en'
#       version: '6'
#   subject: 'Bible'
#   title: 'Vietnamese Unlocked Literal Bible'
#   type: 'bundle'
#   version: '6.7'

# checking:
#   checking_entity:
#     - 'Tri M Dang'
#     - 'Vietnamese translation team'
#   checking_level: '3'

#config example:
# {"id":"en-ULB","lc":"en","lang":"English"}
# {"id":"vi-ULB","lc":"vi","lang":"Vietnamese"}