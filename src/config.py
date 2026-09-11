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
    
    if 'phone_folders' not in config:
        logger.error("Missing 'phone_folders' in configuration")
        raise ValueError("Missing 'phone_folders' in configuration")
    
    if 'destination_folder' not in config:
        logger.error("Missing 'destination_folder' in configuration")
        raise ValueError("Missing 'destination_folder' in configuration")
    
    config.setdefault('excluded_folders', [])
    
    return config


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration structure."""
    if not isinstance(config.get('phone_folders'), list):
        logger.error("phone_folders must be a list")
        return False
    
    if not isinstance(config.get('destination_folder'), str):
        logger.error("destination_folder must be a string")
        return False
    
    if not isinstance(config.get('excluded_folders', []), list):
        logger.error("excluded_folders must be a list")
        return False
    
    return True
