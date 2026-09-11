#!/usr/bin/env python3

import sys
from src.phone_sync import main

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
