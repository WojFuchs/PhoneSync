import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def load_config(config_path: str = "PhoneSync_config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.error(f"Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    if not config:
        logger.error("Configuration file is empty")
        raise ValueError("Configuration file is empty")
    
    if 'destination_folder' not in config:
        logger.error("Missing 'destination_folder' in configuration")
        raise ValueError("Missing 'destination_folder' in configuration")
    
    config.setdefault('phone_folders', [])
    config.setdefault('excluded_folders', [])
    config.setdefault('max_files_per_sync', None)
    
    return config


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration structure."""
    if not isinstance(config.get('phone_folders', []), list):
        logger.error("phone_folders must be a list")
        return False
    
    if not isinstance(config.get('destination_folder'), str):
        logger.error("destination_folder must be a string")
        return False
    
    if not isinstance(config.get('excluded_folders', []), list):
        logger.error("excluded_folders must be a list")
        return False
    
    max_files = config.get('max_files_per_sync')
    if max_files is not None and (not isinstance(max_files, int) or max_files <= 0):
        logger.error("max_files_per_sync must be a positive integer or null")
        return False
    
    return True
