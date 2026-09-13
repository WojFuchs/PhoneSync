#!/usr/bin/env python3
"""Unit tests for config module."""

import unittest
import tempfile
import shutil
import os
from pathlib import Path
import yaml

from src.config import load_config, validate_config


class TestConfigValidation(unittest.TestCase):
    """Test configuration structure validation."""
    
    def test_validate_config_valid(self):
        """Test validation of correct config structure."""
        config = {
            'phone_folders': ['Pictures'],
            'destination_folder': '/tmp/sync',
            'excluded_folders': ['.thumbnails']
        }
        self.assertTrue(validate_config(config))
    
    def test_validate_config_missing_phone_folders(self):
        """Test validation fails when phone_folders is missing."""
        config = {
            'destination_folder': '/tmp/sync'
        }
        self.assertFalse(validate_config(config))
    
    def test_validate_config_missing_destination_folder(self):
        """Test validation fails when destination_folder is missing."""
        config = {
            'phone_folders': ['Pictures']
        }
        self.assertFalse(validate_config(config))
    
    def test_validate_config_wrong_type_phone_folders(self):
        """Test validation fails when phone_folders is not a list."""
        config = {
            'phone_folders': 'Pictures',
            'destination_folder': '/tmp/sync'
        }
        self.assertFalse(validate_config(config))
    
    def test_validate_config_wrong_type_destination(self):
        """Test validation fails when destination_folder is not a string."""
        config = {
            'phone_folders': ['Pictures'],
            'destination_folder': 12345
        }
        self.assertFalse(validate_config(config))
    
    def test_validate_config_wrong_type_excluded_folders(self):
        """Test validation fails when excluded_folders is not a list."""
        config = {
            'phone_folders': ['Pictures'],
            'destination_folder': '/tmp/sync',
            'excluded_folders': '.thumbnails'
        }
        self.assertFalse(validate_config(config))


class TestConfigLoadingFromFile(unittest.TestCase):
    """Test configuration file loading and creation."""
    
    def setUp(self):
        """Create a temporary directory for test config files."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temporary directory (but keep generated config files for inspection)."""
        # Directories and config files in temp_dir will remain for user inspection
        pass
    
    def test_create_and_load_test_config(self):
        """Test creating a config file and loading it successfully.
        
        This test creates a sample config file and verifies it can be loaded.
        The config file is NOT deleted after the test, allowing manual inspection.
        """
        test_config_path = Path(self.temp_dir) / 'test_PhoneSync_config.yaml'
        
        # Create a test config file
        test_config = {
            'phone_folders': ['Pictures', 'Documents', 'Downloads'],
            'destination_folder': 'c:\\Users\\Wojtek\\PhoneSync',
            'excluded_folders': ['.thumbnails', 'Cache', '.hidden']
        }
        
        with open(test_config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        # Verify file was created
        self.assertTrue(test_config_path.exists())
        
        # Load the config
        loaded_config = load_config(str(test_config_path))
        
        # Verify loaded config matches original
        self.assertEqual(loaded_config['phone_folders'], test_config['phone_folders'])
        self.assertEqual(loaded_config['destination_folder'], test_config['destination_folder'])
        self.assertEqual(loaded_config['excluded_folders'], test_config['excluded_folders'])
        
        # Verify it passes validation
        self.assertTrue(validate_config(loaded_config))
        
        # Print location for user reference
        print(f"\n✓ Test config file created at: {test_config_path}")
        print(f"  This file will remain for manual inspection (not deleted after test)")
    
    def test_load_actual_config_from_file(self):
        """Test loading actual PhoneSync_config.yaml file."""
        config_path = 'PhoneSync_config.yaml'
        
        if not Path(config_path).exists():
            self.skipTest(f"Config file '{config_path}' not found - skipping")
        
        config = load_config(config_path)
        
        self.assertIn('phone_folders', config)
        self.assertIn('destination_folder', config)
        self.assertIsInstance(config['phone_folders'], list)
        self.assertIsInstance(config['destination_folder'], str)
        self.assertTrue(validate_config(config))
    
    def test_load_config_file_not_found(self):
        """Test loading non-existent config file raises error."""
        with self.assertRaises(FileNotFoundError):
            load_config('nonexistent_config_file_12345.yaml')


class TestConfigLoadingInUserPhoneSyncFolder(unittest.TestCase):
    """Test creating and loading config in user's PhoneSync folder."""
    
    def setUp(self):
        """Determine user's PhoneSync folder path."""
        self.home_dir = Path.home()
        self.phonesync_dir = self.home_dir / 'PhoneSync'
        self.config_path = self.phonesync_dir / 'PhoneSync_config.yaml'
        
        # Create PhoneSync folder if it doesn't exist
        self.phonesync_dir.mkdir(parents=True, exist_ok=True)
    
    def test_create_config_in_user_phonesync_folder(self):
        """Test creating config file in c:\\Users\\<USERNAME>\\PhoneSync\\
        
        This test:
        1. Determines current Windows user dynamically (using Path.home())
        2. Creates PhoneSync folder if it doesn't exist
        3. Creates a sample config file in that folder
        4. Verifies it can be loaded
        5. Does NOT delete the file - it remains for user inspection
        """
        # Verify we got the correct path
        self.assertIn('Users', str(self.home_dir))
        self.assertIn('PhoneSync', str(self.phonesync_dir))
        
        # Get current Windows username
        username = self.home_dir.name
        print(f"\n✓ Current Windows user: {username}")
        print(f"✓ Home directory: {self.home_dir}")
        print(f"✓ PhoneSync folder: {self.phonesync_dir}")
        
        # Verify folder was created/exists
        self.assertTrue(self.phonesync_dir.exists(), 
                       f"PhoneSync folder not created: {self.phonesync_dir}")
        
        # Create test config with realistic paths
        test_config = {
            'phone_folders': ['Pictures', 'Documents', 'Downloads'],
            'destination_folder': str(self.phonesync_dir),
            'excluded_folders': ['.thumbnails', 'Cache', '.hidden']
        }
        
        # Write config to file
        with open(self.config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        # Verify file was created
        self.assertTrue(self.config_path.exists(),
                       f"Config file not created: {self.config_path}")
        
        # Load and verify config
        loaded_config = load_config(str(self.config_path))
        self.assertEqual(loaded_config['destination_folder'], str(self.phonesync_dir))
        self.assertTrue(validate_config(loaded_config))
        
        # Print summary
        print(f"✓ Config file created: {self.config_path}")
        print(f"✓ Config file size: {self.config_path.stat().st_size} bytes")
        print(f"✓ File will remain for manual inspection (not deleted after test)")
        print(f"\n✓ Config content:")
        print(f"  destination_folder: {loaded_config['destination_folder']}")
        print(f"  phone_folders: {loaded_config['phone_folders']}")
        print(f"  excluded_folders: {loaded_config['excluded_folders']}")


if __name__ == '__main__':
    unittest.main()
