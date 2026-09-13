#!/usr/bin/env python3
"""Unit tests for USB handler module."""

import unittest
from unittest.mock import Mock, patch

from src.usb_handler import AndroidDevice, USBScanner


class TestAndroidDeviceNameNormalization(unittest.TestCase):
    """Test Android device name normalization."""
    
    def test_normalize_simple_device_name(self):
        """Test normalization of simple device name."""
        device = AndroidDevice('/mtp', 'SM-A515F')
        self.assertEqual(device.normalized_name, 'SM_A515F')
    
    def test_normalize_device_name_with_spaces(self):
        """Test normalization converts spaces to underscores."""
        device = AndroidDevice('/mtp', 'Samsung Galaxy')
        self.assertIn('Samsung', device.normalized_name)
        self.assertIn('Galaxy', device.normalized_name)
        self.assertNotIn(' ', device.normalized_name)
    
    def test_normalize_device_name_with_special_chars(self):
        """Test normalization removes special characters."""
        device = AndroidDevice('/mtp', 'Samsung Galaxy!@#$A51')
        # All non-alphanumeric chars become _, doubled underscores collapse
        self.assertNotIn('!', device.normalized_name)
        self.assertNotIn('@', device.normalized_name)
        self.assertNotIn('#', device.normalized_name)
        self.assertNotIn('$', device.normalized_name)
    
    def test_normalize_device_name_collapse_underscores(self):
        """Test normalization collapses multiple underscores."""
        device = AndroidDevice('/mtp', 'Phone___Name')
        self.assertEqual(device.normalized_name, 'Phone_Name')
    
    def test_normalize_device_name_trim_underscores(self):
        """Test normalization trims underscores from edges."""
        device = AndroidDevice('/mtp', '_Phone_Name_')
        self.assertFalse(device.normalized_name.startswith('_'))
        self.assertFalse(device.normalized_name.endswith('_'))
    
    def test_normalize_device_name_keeps_alphanumeric(self):
        """Test normalization preserves alphanumeric characters."""
        device = AndroidDevice('/mtp', 'Phone123Device456')
        self.assertEqual(device.normalized_name, 'Phone123Device456')


class TestUSBScanner(unittest.TestCase):
    """Test USB device scanning."""
    
    def setUp(self):
        self.device = AndroidDevice('/mtp', 'TestPhone')
        self.scanner = USBScanner(self.device)
    
    def test_extract_file_info_valid_line(self):
        """Test extracting file metadata from mtp-ls output line."""
        line = "photo.jpg           FILE       102400"
        info = self.scanner._extract_file_info(line, '/Pictures', 'photo.jpg')
        
        self.assertIsNotNone(info)
        self.assertEqual(info['name'], 'photo.jpg')
        self.assertEqual(info['size'], 102400)
        self.assertEqual(info['path'], '/Pictures/photo.jpg')
        self.assertEqual(info['folder'], '/Pictures')
    
    def test_extract_file_info_large_file(self):
        """Test extracting metadata from large file."""
        line = "video.mp4           FILE       5242880"  # 5MB
        info = self.scanner._extract_file_info(line, '/Videos', 'video.mp4')
        
        self.assertIsNotNone(info)
        self.assertEqual(info['size'], 5242880)
    
    def test_extract_file_info_invalid_line(self):
        """Test extracting file info from invalid line returns None."""
        line = "invalid"
        info = self.scanner._extract_file_info(line, '/Pictures', 'photo.jpg')
        
        self.assertIsNone(info)


if __name__ == '__main__':
    unittest.main()
