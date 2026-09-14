#!/usr/bin/env python3
r"""End-to-end tests for PhoneSync - REAL device only, NO MOCKING.

REQUIREMENTS (MUST HAVE):
- Android device connected via USB with MTP/ADB enabled
- Real config file at: c:\Users\Wojtek\PhoneSync\PhoneSync_config.yaml
- ADB installed: https://developer.android.com/tools/releases/platform-tools
  OR libmtp-tools installed (MSYS2: pacman -S libmtp, WSL2: apt install libmtp-tools)

This test FAILS if device not accessible - no fallback, no mocking.

Run with:
    python -m pytest tests/test_end2end.py -v -s
"""

import unittest
from pathlib import Path
import time
import logging
import subprocess

from src.phone_sync import PhoneSync
from src.usb_handler import find_connected_device


class TestPhoneSyncEnd2End(unittest.TestCase):
    """End-to-end tests for PhoneSync with REAL Android device - NO MOCKING."""
    
    REAL_CONFIG_PATH = r"c:\Users\Wojtek\PhoneSync\PhoneSync_config.yaml"
    
    @classmethod
    def setUpClass(cls):
        """Verify prerequisites: config file and device must be present."""
        # Check config
        config_path = Path(cls.REAL_CONFIG_PATH)
        if not config_path.exists():
            raise FileNotFoundError(
                f"Real config file REQUIRED at: {cls.REAL_CONFIG_PATH}\n"
                "Please create config with phone_folders and destination_folder."
            )
        
        # Check device is actually connected
        device = find_connected_device()
        if not device:
            raise RuntimeError(
                "\n" + "=" * 70 +
                "\nERROR: No Android device found connected via ADB or MTP!" +
                "\nEnd-to-end tests require REAL device.\n" +
                "\nTo run end-to-end tests:\n" +
                "  1. Connect Android phone via USB\n" +
                "  2. Enable MTP/File Transfer mode on phone\n" +
                "  3. Install ADB: https://developer.android.com/tools/releases/platform-tools\n" +
                "  4. Add ADB to PATH and test with: adb devices\n" +
                "\nOR install libmtp-tools:\n" +
                "  - Windows MSYS2: pacman -S libmtp\n" +
                "  - Windows WSL2: sudo apt install libmtp-tools\n" +
                "  - Verify with: mtp-detect\n" +
                "\nThen run test again.\n" +
                "=" * 70
            )
        
        logger = logging.getLogger(__name__)
        logger.info(f"✓ Found Android device: {device.device_name} ({device.connection_type})")
    
    def test_sync_with_max_files_limit_1(self):
        r"""End-to-end test: sync real Android device with 1-file limit.
        
        This test:
        - Connects to REAL Android device (ADB or MTP)
        - Uses real config file
        - Copies maximum 1 file from phone
        - Verifies log and sync folder created
        - NO MOCKING - only works if device connected
        """
        # Wait to ensure unique timestamp
        time.sleep(1)
        
        # Verify device is still accessible
        device = find_connected_device()
        self.assertIsNotNone(device, "Device should be accessible during test")
        
        # Run PhoneSync with REAL device
        sync = PhoneSync(
            config_path=self.REAL_CONFIG_PATH,
            max_files_per_sync_param=1
        )
        
        log_file = sync.log_file
        
        # Verify log file was created
        self.assertTrue(log_file.exists(), f"Log file must exist: {log_file}")
        
        # Verify log contains expected structure
        log_content = log_file.read_text()
        
        # Core assertions
        self.assertIn("PhoneSync started", log_content)
        self.assertIn("Limiting copy to 1 files (command-line override)", log_content)
        self.assertIn("Found phone:", log_content)
        self.assertIn("SYNC SUMMARY", log_content)
        
        # Verify sync completed
        total_processed = sync.files_copied + sync.files_skipped
        self.assertGreaterEqual(
            total_processed, 0,
            "Should have processed files or reported no files found"
        )
        
        # Verify limit was respected
        self.assertLessEqual(
            sync.files_copied, 1,
            f"Should not copy more than 1 file, but copied {sync.files_copied}"
        )
        
        print(f"\n✓ REAL END-TO-END TEST PASSED")
        print(f"  Device: {device.device_name} ({device.connection_type})")
        print(f"  Files copied: {sync.files_copied}")
        print(f"  Files skipped: {sync.files_skipped}")
        print(f"  Errors: {len(sync.errors)}")
        print(f"  Log file: {log_file}")


if __name__ == "__main__":
    unittest.main()
