import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.config import load_config, validate_config
from src.file_manager import LocalFileManager
from src.usb_handler import AndroidDevice, USBScanner


class TestConfig(unittest.TestCase):
    """Test configuration loading and validation."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_validate_config_valid(self):
        config = {
            'phone_folders': ['Pictures'],
            'destination_folder': '/tmp/sync',
            'excluded_folders': ['.thumbnails']
        }
        self.assertTrue(validate_config(config))
    
    def test_validate_config_missing_phone_folders(self):
        config = {
            'destination_folder': '/tmp/sync'
        }
        self.assertFalse(validate_config(config))
    
    def test_validate_config_wrong_type(self):
        config = {
            'phone_folders': 'Pictures',
            'destination_folder': '/tmp/sync'
        }
        self.assertFalse(validate_config(config))


class TestAndroidDevice(unittest.TestCase):
    """Test Android device handling."""
    
    def test_phone_name_normalization(self):
        device = AndroidDevice('/mtp', 'SM-A515F')
        self.assertEqual(device.normalized_name, 'SM_A515F')
    
    def test_phone_name_normalization_complex(self):
        device = AndroidDevice('/mtp', 'Samsung Galaxy!@#$A51')
        # All non-alphanumeric chars become _, doubled underscores collapse, trim edges
        self.assertIn('Samsung', device.normalized_name)
    
    def test_phone_name_normalization_special_chars(self):
        device = AndroidDevice('/mtp', 'Phone___Name')
        # Should collapse multiple underscores
        self.assertEqual(device.normalized_name, 'Phone_Name')


class TestLocalFileManager(unittest.TestCase):
    """Test local file manager operations."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = LocalFileManager(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_create_sync_folder(self):
        folder = self.manager.create_sync_folder('TestPhone')
        self.assertTrue(folder.exists())
        self.assertIn('Sync_', folder.name)
        self.assertIn('TestPhone', folder.name)
    
    def test_find_existing_sync_folders(self):
        folder1 = self.manager.create_sync_folder('TestPhone')
        folder1.exists()
        folder2 = self.manager.create_sync_folder('TestPhone')
        folder2.exists()
        
        folders = self.manager.find_existing_sync_folders('TestPhone')
        self.assertGreaterEqual(len(folders), 1)
    
    def test_find_file_in_sync_folders(self):
        folder1 = self.manager.create_sync_folder('TestPhone')
        test_file = folder1 / 'Pictures' / 'test.jpg'
        test_file.parent.mkdir(parents=True)
        test_file.write_text('test content')
        
        found = self.manager.find_file_in_sync_folders('Pictures/test.jpg', [folder1])
        self.assertEqual(found, test_file)
    
    def test_get_file_metadata(self):
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        metadata = self.manager.get_file_metadata(test_file)
        self.assertIn('size', metadata)
        self.assertIn('modtime', metadata)
        self.assertGreater(metadata['size'], 0)
    
    def test_is_file_unchanged_same_file(self):
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        stat = test_file.stat()
        unchanged = self.manager.is_file_unchanged(
            test_file,
            stat.st_size,
            int(stat.st_mtime)
        )
        self.assertTrue(unchanged)
    
    def test_is_file_unchanged_different_size(self):
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        unchanged = self.manager.is_file_unchanged(
            test_file,
            phone_file_size=9999,
            phone_file_modtime=int(test_file.stat().st_mtime)
        )
        self.assertFalse(unchanged)
    
    def test_get_latest_sync_folder(self):
        folder1 = self.manager.create_sync_folder('TestPhone')
        folder2 = self.manager.create_sync_folder('TestPhone')
        
        folders = [folder1, folder2]
        latest = self.manager.get_latest_sync_folder(folders)
        self.assertEqual(latest, folder2)
    
    def test_verify_copied_file_correct(self):
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        stat = test_file.stat()
        verified, msg = self.manager.verify_copied_file(
            test_file,
            stat.st_size,
            int(stat.st_mtime)
        )
        self.assertTrue(verified)
    
    def test_verify_copied_file_wrong_size(self):
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        verified, msg = self.manager.verify_copied_file(
            test_file,
            expected_size=9999,
            expected_modtime=int(test_file.stat().st_mtime)
        )
        self.assertFalse(verified)


class TestUSBScanner(unittest.TestCase):
    """Test USB device scanning."""
    
    def test_extract_file_info(self):
        device = AndroidDevice('/mtp', 'TestPhone')
        scanner = USBScanner(device)
        
        line = "photo.jpg           FILE       102400"
        info = scanner._extract_file_info(line, '/Pictures', 'photo.jpg')
        
        self.assertIsNotNone(info)
        self.assertEqual(info['name'], 'photo.jpg')
        self.assertEqual(info['size'], 102400)


if __name__ == '__main__':
    unittest.main()
