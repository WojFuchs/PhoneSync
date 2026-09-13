#!/usr/bin/env python3
"""Quick tests without phone connected."""

from pathlib import Path
from src.config import load_config, validate_config
from src.file_manager import LocalFileManager
from src.usb_handler import AndroidDevice

print("\n" + "="*60)
print("TESTING PHONESYNC WITHOUT PHONE")
print("="*60 + "\n")

# Test 1: Config loading
print("1. Testing config loading...")
try:
    config = load_config('PhoneSync_config.yaml')
    print(f"   ✓ Config loaded successfully")
    print(f"     - phone_folders: {config['phone_folders']}")
    print(f"     - destination: {config['destination_folder']}")
    print(f"     - excluded_folders: {config['excluded_folders']}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 2: Config validation
print("\n2. Testing config validation...")
try:
    is_valid = validate_config(config)
    print(f"   ✓ Config is valid: {is_valid}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 3: Phone name normalization
print("\n3. Testing phone name normalization...")
test_devices = [
    ('SM-A515F', 'SM_A515F'),
    ('Samsung Galaxy!', 'Samsung_Galaxy'),
    ('Phone___Name', 'Phone_Name'),
]
for phone_name, expected in test_devices:
    device = AndroidDevice('/mtp', phone_name)
    result = "✓" if device.normalized_name == expected else "✗"
    print(f"   {result} '{phone_name}' -> '{device.normalized_name}'")

# Test 4: File manager operations
print("\n4. Testing file manager operations...")
import tempfile
import shutil
try:
    temp_dir = tempfile.mkdtemp()
    manager = LocalFileManager(temp_dir)
    
    sync_folder = manager.create_sync_folder('TestPhone')
    print(f"   ✓ Created sync folder: {sync_folder.name}")
    
    test_file = sync_folder / 'test.txt'
    test_file.write_text('test content')
    metadata = manager.get_file_metadata(test_file)
    print(f"   ✓ File metadata: size={metadata['size']} bytes, modtime={metadata['modtime']}")
    
    found = manager.find_file_in_sync_folders('test.txt', [sync_folder])
    print(f"   ✓ Found file in sync folder: {found.name}")
    
    shutil.rmtree(temp_dir)
except Exception as e:
    print(f"   ✗ Error: {e}")
    shutil.rmtree(temp_dir, ignore_errors=True)

print("\n" + "="*60)
print("ALL TESTS COMPLETED")
print("="*60 + "\n")
