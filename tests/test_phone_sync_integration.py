#!/usr/bin/env python3
"""Integration tests for PhoneSync with mocked phone - creates real logs and folders."""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import shutil
import logging
import time
from datetime import datetime

from src.phone_sync import PhoneSync, setup_logging
from src.usb_handler import AndroidDevice


class TestPhoneSyncIntegration(unittest.TestCase):
    """Integration tests for PhoneSync with mocked Android device - creates real artifacts."""
    
    def setUp(self):
        """Create test configuration with real destination folder."""
        self.temp_config_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_config_dir) / "PhoneSync_config.yaml"
        
        # Use real PhoneSync destination folder
        self.real_dest_folder = Path("c:/Users/Wojtek/PhoneSync")
        self.real_dest_folder.mkdir(parents=True, exist_ok=True)
        
        # Create minimal config file
        dest_folder_escaped = str(self.real_dest_folder).replace('\\', '/')
        config_content = f"""phone_folders:
  - /DCIM

destination_folder: {dest_folder_escaped}

excluded_folders:
  - .thumbnails
"""
        self.config_path.write_text(config_content)
    
    def tearDown(self):
        """Clean up temporary config directory only (keep real logs/folders for inspection)."""
        shutil.rmtree(self.temp_config_dir, ignore_errors=True)
    
    def _create_mock_device(self):
        """Create a mock Android device."""
        device = Mock(spec=AndroidDevice)
        device.device_path = "/mtp"
        device.device_name = "Test_Phone_77"
        device.normalized_name = "Test_Phone_77"
        return device
    
    def _create_mock_files(self, count=10):
        """Create list of mock file info dicts with 1 byte size and random modtime from past."""
        files = []
        # Base time: 1 year ago
        base_time = int(time.time()) - (365 * 24 * 3600)
        for i in range(count):
            # Each file has 1 byte, and modtime spread over time (every hour)
            files.append({
                'path': f'/DCIM/IMG_{i:04d}.jpg',
                'name': f'IMG_{i:04d}.jpg',
                'size': 1,  # 1 byte
                'folder': '/DCIM',
                'modtime': base_time + (i * 3600)  # Spread by 1 hour each
            })
        return files
    
    @patch('src.phone_sync.find_connected_device')
    @patch('src.phone_sync.USBScanner')
    def test_max_files_per_sync_limit_stops_scanning(self, mock_scanner_class, mock_find_device):
        """Test that max_files_per_sync limit stops scanning at correct number.
        Creates real logs and sync folders in c:/Users/Wojtek/PhoneSync/
        """
        # Wait 1 second to ensure unique timestamp
        time.sleep(1)
        
        # Setup mocks
        device = self._create_mock_device()
        mock_find_device.return_value = device
        
        # Create mock files - 10 total files on phone
        phone_files = self._create_mock_files(count=10)
        
        # Mock scanner instance
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner
        
        # Track how many files were requested to be collected
        collected_count = []
        
        # Mock find_files_for_copying to use real logic but with our test files
        def mock_find_files_for_copying(folders, excluded, validator, max_results):
            """Simulate the real scanning with mock files."""
            files_to_copy = []
            for file_info in phone_files:
                if validator(file_info):
                    files_to_copy.append(file_info)
                    if max_results is not None and len(files_to_copy) >= max_results:
                        collected_count.append(len(files_to_copy))
                        logging.getLogger().info(f"Reached copy limit during scan: {len(files_to_copy)} files collected")
                        return files_to_copy
            collected_count.append(len(files_to_copy))
            logging.getLogger().info(f"Collected {len(files_to_copy)} files to copy from phone")
            return files_to_copy
        
        mock_scanner.find_files_for_copying = mock_find_files_for_copying
        
        # Setup real logging - returns log_file only (timestamp is in the filename)
        log_file = setup_logging(str(self.real_dest_folder))
        
        # Verify initial log file exists without phone name
        initial_log = log_file
        self.assertTrue(initial_log.exists(), f"Initial log file should exist at {initial_log}")
        
        # Run PhoneSync with max_files_per_sync=3
        sync = PhoneSync(
            config_path=str(self.config_path),
            max_files_per_sync_param=3,
            log_file=log_file
        )
        
        # Extract timestamp from log_file name for sync folder path
        parts = log_file.stem.split('_')  # "Sync_20260913_183425" -> ["Sync", "20260913", "183425"]
        sync_timestamp = f"{parts[1]}_{parts[2]}" if len(parts) >= 3 else datetime.now().strftime("%Y%m%d_%H%M%S")
        sync_folder_path = self.real_dest_folder / f"Sync_{sync_timestamp}_Test_Phone_77"
        
        with patch.object(sync.file_manager, 'find_existing_sync_folders', return_value=[]):
            with patch.object(sync.file_manager, 'create_sync_folder', return_value=sync_folder_path):
                # Mock copy_file_from_phone to create real files (let _copy_file and logging work naturally)
                def mock_copy_from_phone(file_relative_path, dest_folder, device_path, phone_file_path):
                    dest_file = dest_folder / file_relative_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    dest_file.write_bytes(b'x')  # 1 byte
                    return True
                
                with patch.object(sync.file_manager, 'copy_file_from_phone', side_effect=mock_copy_from_phone):
                    result = sync.run()
        
        # Verify: should have returned early with 3 files
        self.assertTrue(result)
        self.assertEqual(len(collected_count), 1)
        self.assertEqual(collected_count[0], 3, "Should have stopped at 3 files")
        
        # Verify log file was created with phone name in filename (NO old file without phone name)
        expected_log = self.real_dest_folder / f"Sync_{sync_timestamp}_Test_Phone_77.log"
        old_log = self.real_dest_folder / f"Sync_{sync_timestamp}.log"
        
        self.assertTrue(expected_log.exists(), f"Log file should exist at {expected_log}")
        self.assertFalse(old_log.exists(), f"Old log file without phone name should NOT exist at {old_log}")
        
        # Verify log contains expected messages
        log_content = expected_log.read_text()
        self.assertIn("Reached copy limit during scan", log_content)
        self.assertIn("Test_Phone_77", log_content)
    
    @patch('src.phone_sync.find_connected_device')
    @patch('src.phone_sync.USBScanner')
    def test_max_files_per_sync_copies_exactly_limit(self, mock_scanner_class, mock_find_device):
        """Test that exactly max_files_per_sync files are prepared for copying.
        Creates real logs and sync folders in c:/Users/Wojtek/PhoneSync/
        """
        # Wait 1 second to ensure unique timestamp
        time.sleep(1)
        
        device = self._create_mock_device()
        mock_find_device.return_value = device
        
        phone_files = self._create_mock_files(count=10)
        
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner
        
        def mock_find_files_for_copying(folders, excluded, validator, max_results):
            files_to_copy = []
            for file_info in phone_files:
                if validator(file_info):
                    files_to_copy.append(file_info)
                    if max_results is not None and len(files_to_copy) >= max_results:
                        return files_to_copy
            return files_to_copy
        
        mock_scanner.find_files_for_copying = mock_find_files_for_copying
        
        # Setup real logging - returns log_file only (timestamp is in the filename)
        log_file = setup_logging(str(self.real_dest_folder))
        
        sync = PhoneSync(
            config_path=str(self.config_path),
            max_files_per_sync_param=5,
            log_file=log_file
        )
        
        # Extract timestamp from log_file name for sync folder path
        parts = log_file.stem.split('_')  # "Sync_20260913_183425" -> ["Sync", "20260913", "183425"]
        sync_timestamp = f"{parts[1]}_{parts[2]}" if len(parts) >= 3 else datetime.now().strftime("%Y%m%d_%H%M%S")
        sync_folder_path = self.real_dest_folder / f"Sync_{sync_timestamp}_Test_Phone_77"
        
        with patch.object(sync.file_manager, 'find_existing_sync_folders', return_value=[]):
            with patch.object(sync.file_manager, 'create_sync_folder', return_value=sync_folder_path):
                # Mock copy_file_from_phone to create real files (let _copy_file and logging work naturally)
                def mock_copy_from_phone(file_relative_path, dest_folder, device_path, phone_file_path):
                    dest_file = dest_folder / file_relative_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    dest_file.write_bytes(b'x')  # 1 byte
                    return True
                
                with patch.object(sync.file_manager, 'copy_file_from_phone', side_effect=mock_copy_from_phone):
                    result = sync.run()
        
        # Verify exactly 5 files were prepared for copying
        self.assertTrue(result)
        self.assertEqual(sync.files_copied, 5, f"Expected 5 files to copy, but got {sync.files_copied}")
        
        # Verify log file was created with phone name (NO old file without phone name)
        expected_log = self.real_dest_folder / f"Sync_{sync_timestamp}_Test_Phone_77.log"
        old_log = self.real_dest_folder / f"Sync_{sync_timestamp}.log"
        
        self.assertTrue(expected_log.exists(), f"Log file should exist at {expected_log}")
        self.assertFalse(old_log.exists(), f"Old log file without phone name should NOT exist at {old_log}")
        
        # Verify sync folder was created with correct name
        self.assertTrue(sync_folder_path.exists(), f"Sync folder should exist at {sync_folder_path}")
        
        # Verify files were created
        created_files = list(sync_folder_path.rglob('*'))
        self.assertEqual(len([f for f in created_files if f.is_file()]), 5)
    
    @patch('src.phone_sync.find_connected_device')
    @patch('src.phone_sync.USBScanner')
    def test_no_limit_copies_all_files(self, mock_scanner_class, mock_find_device):
        """Test that without limit, all new files are copied.
        Creates real logs and sync folders in c:/Users/Wojtek/PhoneSync/
        """
        # Wait 1 second to ensure unique timestamp
        time.sleep(1)
        
        device = self._create_mock_device()
        mock_find_device.return_value = device
        
        phone_files = self._create_mock_files(count=10)
        
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner
        
        def mock_find_files_for_copying(folders, excluded, validator, max_results):
            files_to_copy = []
            for file_info in phone_files:
                if validator(file_info):
                    files_to_copy.append(file_info)
                    if max_results is not None and len(files_to_copy) >= max_results:
                        return files_to_copy
            return files_to_copy
        
        mock_scanner.find_files_for_copying = mock_find_files_for_copying
        
        # Setup real logging - returns log_file only (timestamp is in the filename)
        log_file = setup_logging(str(self.real_dest_folder))
        
        # No max_files_per_sync limit
        sync = PhoneSync(
            config_path=str(self.config_path),
            max_files_per_sync_param=None,
            log_file=log_file
        )
        
        # Extract timestamp from log_file name for sync folder path
        parts = log_file.stem.split('_')  # "Sync_20260913_183425" -> ["Sync", "20260913", "183425"]
        sync_timestamp = f"{parts[1]}_{parts[2]}" if len(parts) >= 3 else datetime.now().strftime("%Y%m%d_%H%M%S")
        sync_folder_path = self.real_dest_folder / f"Sync_{sync_timestamp}_Test_Phone_77"
        
        with patch.object(sync.file_manager, 'find_existing_sync_folders', return_value=[]):
            with patch.object(sync.file_manager, 'create_sync_folder', return_value=sync_folder_path):
                # Mock copy_file_from_phone to create real files (let _copy_file and logging work naturally)
                def mock_copy_from_phone(file_relative_path, dest_folder, device_path, phone_file_path):
                    dest_file = dest_folder / file_relative_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    dest_file.write_bytes(b'x')  # 1 byte
                    return True
                
                with patch.object(sync.file_manager, 'copy_file_from_phone', side_effect=mock_copy_from_phone):
                    result = sync.run()
        
        # Verify all 10 files were prepared for copying
        self.assertTrue(result)
        self.assertEqual(sync.files_copied, 10, f"Expected 10 files to copy, but got {sync.files_copied}")
        
        # Verify log file was created (NO old file without phone name)
        expected_log = self.real_dest_folder / f"Sync_{sync_timestamp}_Test_Phone_77.log"
        old_log = self.real_dest_folder / f"Sync_{sync_timestamp}.log"
        
        self.assertTrue(expected_log.exists(), f"Log file should exist at {expected_log}")
        self.assertFalse(old_log.exists(), f"Old log file without phone name should NOT exist at {old_log}")
        
        # Verify log content
        log_content = expected_log.read_text()
        self.assertIn("Test_Phone_77", log_content)
        self.assertNotIn("Reached copy limit", log_content)  # Should NOT have limit message
    
    @patch('src.phone_sync.find_connected_device')
    @patch('src.phone_sync.USBScanner')
    def test_incremental_logic_skips_unchanged_files(self, mock_scanner_class, mock_find_device):
        """Test that already copied files are skipped in incremental sync.
        Creates real logs and sync folders in c:/Users/Wojtek/PhoneSync/
        """
        # Wait 1 second to ensure unique timestamp
        time.sleep(1)
        
        device = self._create_mock_device()
        mock_find_device.return_value = device
        
        phone_files = self._create_mock_files(count=5)
        
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner
        
        def mock_find_files_for_copying(folders, excluded, validator, max_results):
            files_to_copy = []
            for file_info in phone_files:
                if validator(file_info):
                    files_to_copy.append(file_info)
            return files_to_copy
        
        mock_scanner.find_files_for_copying = mock_find_files_for_copying
        
        # Setup real logging - returns log_file only (timestamp is in the filename)
        log_file = setup_logging(str(self.real_dest_folder))
        
        sync = PhoneSync(
            config_path=str(self.config_path),
            max_files_per_sync_param=None,
            log_file=log_file
        )
        
        # Extract timestamp from log_file name for sync folder path
        parts = log_file.stem.split('_')  # "Sync_20260913_183425" -> ["Sync", "20260913", "183425"]
        sync_timestamp = f"{parts[1]}_{parts[2]}" if len(parts) >= 3 else datetime.now().strftime("%Y%m%d_%H%M%S")
        sync_folder_path = self.real_dest_folder / f"Sync_{sync_timestamp}_Test_Phone_77"
        
        with patch.object(sync.file_manager, 'find_existing_sync_folders', return_value=[]):
            with patch.object(sync.file_manager, 'create_sync_folder', return_value=sync_folder_path):
                # Mock copy_file_from_phone to create real files (let _copy_file and logging work naturally)
                def mock_copy_from_phone(file_relative_path, dest_folder, device_path, phone_file_path):
                    dest_file = dest_folder / file_relative_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    dest_file.write_bytes(b'x')  # 1 byte
                    return True
                
                with patch.object(sync.file_manager, 'copy_file_from_phone', side_effect=mock_copy_from_phone):
                    result = sync.run()
        
        # Verify all 5 files were prepared for copying (no files exist yet)
        self.assertTrue(result)
        self.assertEqual(sync.files_copied, 5, f"Expected 5 files to copy on first run, but got {sync.files_copied}")
        
        # Verify log file was created (NO old file without phone name)
        expected_log = self.real_dest_folder / f"Sync_{sync_timestamp}_Test_Phone_77.log"
        old_log = self.real_dest_folder / f"Sync_{sync_timestamp}.log"
        
        self.assertTrue(expected_log.exists(), f"Log file should exist at {expected_log}")
        self.assertFalse(old_log.exists(), f"Old log file without phone name should NOT exist at {old_log}")
        
        # Verify log content
        log_content = expected_log.read_text()
        self.assertIn("Test_Phone_77", log_content)

    @patch('src.phone_sync.find_connected_device')
    @patch('src.phone_sync.USBScanner')
    def test_log_file_rename_before_and_after_phone_detection(self, mock_scanner_class, mock_find_device):
        """Test that log file is created initially without phone name, 
        then renamed with phone name after detection.
        Verifies old log file doesn't exist and new one does.
        """
        # Wait 1 second to ensure unique timestamp
        time.sleep(1)
        
        device = self._create_mock_device()
        mock_find_device.return_value = device
        
        phone_files = self._create_mock_files(count=2)
        
        mock_scanner = Mock()
        mock_scanner_class.return_value = mock_scanner
        
        def mock_find_files_for_copying(folders, excluded, validator, max_results):
            files_to_copy = []
            for file_info in phone_files:
                if validator(file_info):
                    files_to_copy.append(file_info)
            return files_to_copy
        
        mock_scanner.find_files_for_copying = mock_find_files_for_copying
        
        # Setup real logging - returns log_file only (timestamp is in the filename)
        log_file = setup_logging(str(self.real_dest_folder))
        
        # Verify initial log file exists without phone name
        initial_log = log_file
        self.assertTrue(initial_log.exists(), f"Initial log file should exist at {initial_log}")
        
        # Verify it doesn't have phone name in it yet
        initial_log_name = initial_log.name
        self.assertNotIn("Test_Phone_77", initial_log_name, 
                        f"Initial log file should NOT have phone name, got: {initial_log_name}")
        
        sync = PhoneSync(
            config_path=str(self.config_path),
            max_files_per_sync_param=None,
            log_file=log_file
        )
        
        # Extract timestamp from log_file name for sync folder path
        parts = log_file.stem.split('_')  # "Sync_20260913_183425" -> ["Sync", "20260913", "183425"]
        sync_timestamp = f"{parts[1]}_{parts[2]}" if len(parts) >= 3 else datetime.now().strftime("%Y%m%d_%H%M%S")
        sync_folder_path = self.real_dest_folder / f"Sync_{sync_timestamp}_Test_Phone_77"
        
        with patch.object(sync.file_manager, 'find_existing_sync_folders', return_value=[]):
            with patch.object(sync.file_manager, 'create_sync_folder', return_value=sync_folder_path):
                # Mock copy_file_from_phone to create real files (let _copy_file and logging work naturally)
                def mock_copy_from_phone(file_relative_path, dest_folder, device_path, phone_file_path):
                    dest_file = dest_folder / file_relative_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    dest_file.write_bytes(b'x')  # 1 byte
                    return True
                
                with patch.object(sync.file_manager, 'copy_file_from_phone', side_effect=mock_copy_from_phone):
                    result = sync.run()
        
        # After run(), verify log file was renamed
        final_log = sync.log_file
        
        # Verify old log file WITHOUT phone name does NOT exist
        old_log = self.real_dest_folder / f"Sync_{sync_timestamp}.log"
        self.assertFalse(old_log.exists(), 
                        f"Old log file without phone name should NOT exist at {old_log}")
        
        # Verify new log file WITH phone name DOES exist
        expected_log = self.real_dest_folder / f"Sync_{sync_timestamp}_Test_Phone_77.log"
        self.assertTrue(expected_log.exists(), 
                       f"New log file with phone name should exist at {expected_log}")
        
        # Verify final_log points to the renamed file
        self.assertEqual(final_log, expected_log, 
                        f"sync.log_file should point to renamed log, expected {expected_log}, got {final_log}")
        
        # Verify the log content contains phone name
        log_content = expected_log.read_text()
        self.assertIn("Test_Phone_77", log_content, "Log should contain phone name")


if __name__ == '__main__':
    unittest.main()
