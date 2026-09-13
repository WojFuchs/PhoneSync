#!/usr/bin/env python3

import sys
from src.phone_sync import main

if __name__ == "__main__":
    # Parse command-line arguments
    config_path = "PhoneSync_config.yaml"
    max_files_per_sync = None
    
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            max_files_per_sync = int(sys.argv[2])
        except ValueError:
            print(f"Error: max_files_per_sync must be an integer, got '{sys.argv[2]}'")
            sys.exit(1)
    
    exit_code = main(config_path, max_files_per_sync)
    sys.exit(exit_code)
