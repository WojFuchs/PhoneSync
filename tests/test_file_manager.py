#!/usr/bin/env python3
"""Unit tests for file manager module."""

import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from src.file_manager import LocalFileManager


class TestLocalFileManagerCreation(unittest.TestCase):
    """Test sync folder creation."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = LocalFileManager(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_create_sync_folder(self):
        """Test creating a new sync folder."""
        folder = self.manager.create_sync_folder('TestPhone')
        
        self.assertTrue(folder.exists())
        self.assertIn('Sync_', folder.name)
        self.assertIn('TestPhone', folder.name)
    
    def test_create_sync_folder_timestamp_format(self):
        """Test sync folder has correct timestamp format."""
        folder = self.manager.create_sync_folder('TestPhone')
        name = folder.name
        
        # Format: Sync_<YYYYMMDD>_<HHMMSS>_<phone_name>
        parts = name.split('_')
        self.assertEqual(parts[0], 'Sync')
        self.assertEqual(len(parts[1]), 8)  # YYYYMMDD = 8 chars
        self.assertEqual(len(parts[2]), 6)  # HHMMSS = 6 chars
        self.assertEqual(parts[3], 'TestPhone')


class TestLocalFileManagerFolderDiscovery(unittest.TestCase):
    """Test finding existing sync folders."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = LocalFileManager(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_find_existing_sync_folders(self):
        """Test finding multiple existing sync folders."""
        folder1 = self.manager.create_sync_folder('TestPhone')
        folder2 = self.manager.create_sync_folder('TestPhone')
        
        folders = self.manager.find_existing_sync_folders('TestPhone')
        self.assertGreaterEqual(len(folders), 1)
    
    def test_find_existing_sync_folders_sorted(self):
        """Test sync folders are returned in chronological order."""
        folder1 = self.manager.create_sync_folder('TestPhone')
        folder2 = self.manager.create_sync_folder('TestPhone')
        
        folders = self.manager.find_existing_sync_folders('TestPhone')
        # Folders should be sorted (oldest to newest)
        self.assertEqual(folders[-1], folder2)
    
    def test_find_existing_sync_folders_wrong_phone(self):
        """Test finding sync folders for different phone returns empty."""
        folder1 = self.manager.create_sync_folder('Phone1')
        
        folders = self.manager.find_existing_sync_folders('Phone2')
        self.assertEqual(len(folders), 0)


class TestLocalFileManagerFileSearch(unittest.TestCase):
    """Test finding files in sync folders."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = LocalFileManager(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_find_file_in_sync_folders(self):
        """Test finding file in sync folder."""
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'Pictures' / 'test.jpg'
        test_file.parent.mkdir(parents=True)
        test_file.write_text('test content')
        
        found = self.manager.find_file_in_sync_folders('Pictures/test.jpg', [folder])
        self.assertEqual(found, test_file)
    
    def test_find_file_in_sync_folders_not_found(self):
        """Test file not found returns None."""
        folder = self.manager.create_sync_folder('TestPhone')
        
        found = self.manager.find_file_in_sync_folders('nonexistent.jpg', [folder])
        self.assertIsNone(found)
    
    def test_find_file_searches_multiple_folders(self):
        """Test searching file in multiple sync folders."""
        folder1 = self.manager.create_sync_folder('TestPhone')
        folder2 = self.manager.create_sync_folder('TestPhone')
        
        # Create file only in folder1
        test_file = folder1 / 'Pictures' / 'test.jpg'
        test_file.parent.mkdir(parents=True)
        test_file.write_text('test')
        
        # Should find it when searching both
        found = self.manager.find_file_in_sync_folders('Pictures/test.jpg', [folder1, folder2])
        self.assertEqual(found, test_file)


class TestLocalFileManagerMetadata(unittest.TestCase):
    """Test file metadata operations."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = LocalFileManager(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_get_file_metadata(self):
        """Test getting file metadata."""
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        metadata = self.manager.get_file_metadata(test_file)
        
        self.assertIn('size', metadata)
        self.assertIn('modtime', metadata)
        self.assertGreater(metadata['size'], 0)
        self.assertGreater(metadata['modtime'], 0)
    
    def test_set_file_modtime(self):
        """Test setting file modification time."""
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        target_modtime = 1000000000  # Some timestamp
        self.manager.set_file_modtime(test_file, target_modtime)
        
        actual_modtime = int(test_file.stat().st_mtime)
        # Allow 1 second tolerance
        self.assertAlmostEqual(actual_modtime, target_modtime, delta=1)


class TestLocalFileManagerVerification(unittest.TestCase):
    """Test file verification operations."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = LocalFileManager(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_is_file_unchanged_same_file(self):
        """Test unchanged check passes for identical file."""
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
        """Test unchanged check fails for different size."""
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        unchanged = self.manager.is_file_unchanged(
            test_file,
            phone_file_size=9999,
            phone_file_modtime=int(test_file.stat().st_mtime)
        )
        self.assertFalse(unchanged)
    
    def test_is_file_unchanged_different_modtime(self):
        """Test unchanged check fails for significantly different modtime."""
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        stat = test_file.stat()
        old_modtime = int(stat.st_mtime) - 100  # 100 seconds older
        
        unchanged = self.manager.is_file_unchanged(
            test_file,
            stat.st_size,
            old_modtime
        )
        self.assertFalse(unchanged)
    
    def test_is_file_unchanged_modtime_within_tolerance(self):
        """Test unchanged check passes for modtime within 1 second tolerance."""
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        stat = test_file.stat()
        slight_modtime = int(stat.st_mtime) + 1  # 1 second newer (within tolerance)
        
        unchanged = self.manager.is_file_unchanged(
            test_file,
            stat.st_size,
            slight_modtime
        )
        self.assertTrue(unchanged)
    
    def test_verify_copied_file_correct(self):
        """Test verification passes for correct file."""
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
        """Test verification fails for wrong file size."""
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        verified, msg = self.manager.verify_copied_file(
            test_file,
            expected_size=9999,
            expected_modtime=int(test_file.stat().st_mtime)
        )
        self.assertFalse(verified)
        self.assertIn('Size mismatch', msg)
    
    def test_verify_copied_file_wrong_modtime(self):
        """Test verification fails for wrong modification time."""
        folder = self.manager.create_sync_folder('TestPhone')
        test_file = folder / 'test.txt'
        test_file.write_text('test')
        
        verified, msg = self.manager.verify_copied_file(
            test_file,
            expected_size=test_file.stat().st_size,
            expected_modtime=1000000000
        )
        self.assertFalse(verified)
        self.assertIn('Modtime mismatch', msg)
    
    def test_verify_copied_file_not_exists(self):
        """Test verification fails for non-existent file."""
        nonexistent = Path(self.temp_dir) / 'nonexistent.txt'
        
        verified, msg = self.manager.verify_copied_file(
            nonexistent,
            expected_size=100,
            expected_modtime=1000000000
        )
        self.assertFalse(verified)
        self.assertIn('does not exist', msg)


class TestLocalFileManagerLatestFolder(unittest.TestCase):
    """Test finding latest sync folder."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = LocalFileManager(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_get_latest_sync_folder(self):
        """Test getting the most recent sync folder."""
        folder1 = self.manager.create_sync_folder('TestPhone')
        folder2 = self.manager.create_sync_folder('TestPhone')
        
        folders = [folder1, folder2]
        latest = self.manager.get_latest_sync_folder(folders)
        self.assertEqual(latest, folder2)
    
    def test_get_latest_sync_folder_empty_list(self):
        """Test getting latest folder from empty list returns None."""
        latest = self.manager.get_latest_sync_folder([])
        self.assertIsNone(latest)


if __name__ == '__main__':
    unittest.main()
