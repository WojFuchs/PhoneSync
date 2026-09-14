import logging
import re
from pathlib import Path, PureWindowsPath
from typing import List, Dict, Any, Optional, Tuple
import os
import subprocess

logger = logging.getLogger(__name__)


class AndroidDevice:
    """Represents an Android device connected via USB (ADB or MTP)."""
    
    def __init__(self, device_path: str, device_name: str):
        self.device_path = device_path  # Device serial number for ADB or MTP path
        self.device_name = device_name
        self.normalized_name = self._normalize_phone_name(device_name)
        self.connection_type = "unknown"  # adb, mtp, or unknown
    
    def _normalize_phone_name(self, name: str) -> str:
        """Normalize phone name: replace non-alphanumeric with underscore."""
        normalized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        normalized = re.sub(r'_+', '_', normalized)
        normalized = normalized.strip('_')
        return normalized
    
    def get_phone_folders(self, config: Dict[str, Any]) -> List[str]:
        """Get list of phone folders to scan from config."""
        return config.get('phone_folders', [])


class USBScanner:
    """Scan and find files on connected Android device via ADB or MTP."""
    
    def __init__(self, device: AndroidDevice):
        self.device = device
    
    def find_files_for_copying(self, folder_paths: List[str], excluded_folders: List[str], 
                               validator_callback, max_results: int = None) -> List[Dict[str, Any]]:
        """
        Scan phone folders and collect files to copy until limit is reached.
        Uses validator_callback to check each file if it should be copied.
        Stops scanning when max_results is reached to save time.
        
        Args:
            folder_paths: List of folders to scan (or empty for entire phone)
            excluded_folders: List of folders to skip
            validator_callback: Function(file_info) -> bool, returns True if file should be copied
            max_results: Max files to collect before stopping (None = no limit)
        
        Returns:
            List of files that should be copied
        """
        files_to_copy = []
        folders_to_scan = folder_paths if folder_paths else ["/"]
        
        for folder in folders_to_scan:
            # Scan folder and collect files that should be copied
            files = self._scan_folder_recursive(folder, excluded_folders)
            # Sort files within folder by modtime (oldest first)
            files_sorted = sorted(files, key=lambda x: x.get('modtime', 0))
            
            for file_info in files_sorted:
                if validator_callback(file_info):
                    files_to_copy.append(file_info)
                    
                    # Stop if we reached the limit
                    if max_results is not None and len(files_to_copy) >= max_results:
                        logger.info(f"Reached copy limit during scan: {len(files_to_copy)} files collected")
                        return files_to_copy
        
        logger.info(f"Collected {len(files_to_copy)} files to copy from phone")
        return files_to_copy
    
    def _scan_folder_recursive(self, folder: str, excluded_folders: List[str]) -> List[Dict[str, Any]]:
        """Recursively scan folder on phone for files via ADB."""
        files = []
        
        try:
            if self.device.connection_type == "adb":
                files = self._scan_folder_adb(folder, excluded_folders)
            else:
                # Fall back to mtp-ls
                files = self._scan_folder_mtp(folder, excluded_folders)
            
            return files
        
        except Exception as e:
            logger.error(f"ERROR: Error scanning folder {folder}: {e}")
            return []
    
    def _scan_folder_adb(self, folder: str, excluded_folders: List[str]) -> List[Dict[str, Any]]:
        """Scan folder using ADB shell."""
        files = []
        
        try:
            # Use adb shell ls to list files
            # Format: ls -la /path
            cmd = ['adb', '-s', self.device.device_path, 'shell', 'ls', '-la', folder]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                logger.warning(f"WARNING: Could not scan folder {folder} via ADB: {result.stderr}")
                return files
            
            for line in result.stdout.split('\n'):
                if not line.strip():
                    continue
                
                # Parse ls -la output
                # Format: drwxrwx--- 2 root sdcard_r 4096 2023-01-01 12:00 foldername
                # or:     -rw-rw---- 1 root sdcard_r 12345 2023-01-01 12:00 filename
                parts = line.split()
                if len(parts) < 9:
                    continue
                
                mode = parts[0]
                name = ' '.join(parts[8:])  # Handle names with spaces
                
                # Check if it's excluded
                if name in excluded_folders:
                    logger.debug(f"Skipping excluded folder: {name}")
                    continue
                
                if mode.startswith('d'):
                    # It's a directory - recurse
                    subfolder = f"{folder}/{name}"
                    sub_files = self._scan_folder_adb(subfolder, excluded_folders)
                    files.extend(sub_files)
                else:
                    # It's a file
                    try:
                        size = int(parts[4])
                        file_path = f"{folder}/{name}"
                        files.append({
                            'path': file_path,
                            'name': name,
                            'size': size,
                            'folder': folder,
                            'modtime': 0  # ADB ls doesn't easily give us modtime, would need stat
                        })
                    except (ValueError, IndexError):
                        logger.debug(f"Could not parse file info: {line}")
            
            return files
        
        except Exception as e:
            logger.error(f"ERROR: ADB scan error for {folder}: {e}")
            return []
    
    def _scan_folder_mtp(self, folder: str, excluded_folders: List[str]) -> List[Dict[str, Any]]:
        """Scan folder using mtp-ls (fallback)."""
        files = []
        
        try:
            mtp_cmd = ['mtp-ls', f'--device="{self.device.device_path}"', f'"{folder}"']
            result = subprocess.run(mtp_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"WARNING: Could not scan folder {folder}: {result.stderr}")
                return files
            
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) < 5:
                    continue
                
                name = parts[0]
                is_dir = line.startswith('DIR')
                
                if name in excluded_folders:
                    logger.debug(f"Skipping excluded folder: {name}")
                    continue
                
                if is_dir:
                    subfolder = f"{folder}/{name}"
                    sub_files = self._scan_folder_mtp(subfolder, excluded_folders)
                    files.extend(sub_files)
                else:
                    file_info = self._extract_file_info(line, folder, name)
                    if file_info:
                        files.append(file_info)
            
            return files
        
        except Exception as e:
            logger.error(f"ERROR: MTP scan error for {folder}: {e}")
            return []
    
    def _extract_file_info(self, line: str, folder: str, name: str) -> Optional[Dict[str, Any]]:
        """Extract file metadata from mtp-ls output line."""
        try:
            parts = line.split()
            if len(parts) < 2:
                return None
            
            size = int(parts[-1])
            
            file_path = f"{folder}/{name}"
            
            return {
                'path': file_path,
                'name': name,
                'size': size,
                'folder': folder
            }
        except (ValueError, IndexError) as e:
            logger.warning(f"WARNING: Could not parse file info for {name}: {e}")
            return None


def find_connected_device() -> Optional[AndroidDevice]:
    """Find first Android device connected via USB (ADB, MTP, or other)."""
    
    # Method 1: Try ADB first (most reliable for programmatic access)
    device = _find_device_via_adb()
    if device:
        logger.info("Found device via ADB")
        return device
    
    # Method 2: Try mtp-detect (libmtp-tools)
    device = _find_device_via_mtp_detect()
    if device:
        logger.info("Found device via MTP detection")
        return device
    
    # No device found
    logger.error("ERROR: No Android device found. Please ensure:")
    logger.error("  - Device is connected via USB in MTP/File Transfer mode")
    logger.error("  - ADB is installed: https://developer.android.com/tools/releases/platform-tools")
    logger.error("  - OR libmtp-tools is installed (via MSYS2: pacman -S libmtp)")
    return None


def _find_device_via_adb() -> Optional[AndroidDevice]:
    """Try to find Android device via ADB (Android Debug Bridge)."""
    try:
        # Check if adb is available
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=5)
        
        if result.returncode != 0:
            logger.debug("ADB not available or returned error")
            return None
        
        # Parse adb devices output
        # Format:
        # List of attached devices
        # device_id device
        lines = result.stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line or 'attached' in line.lower() or 'device' in line.lower():
                continue
            
            parts = line.split()
            if len(parts) >= 2 and parts[1] == 'device':
                device_id = parts[0]
                # Get device name/model via adb shell
                device_name = _get_adb_device_name(device_id)
                if device_name:
                    device = AndroidDevice(device_id, device_name)
                    device.connection_type = "adb"
                    return device
        
        return None
    
    except FileNotFoundError:
        logger.debug("ADB command not found in PATH")
        return None
    except Exception as e:
        logger.debug(f"ADB detection failed: {e}")
        return None


def _get_adb_device_name(device_id: str) -> str:
    """Get device name from ADB device properties."""
    try:
        result = subprocess.run(
            ['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.model'],
            capture_output=True, text=True, timeout=5
        )
        model = result.stdout.strip()
        if model:
            return model
    except Exception as e:
        logger.debug(f"Could not get device model: {e}")
    
    return f"Android_{device_id[:8]}"


def _find_device_via_mtp_detect() -> Optional[AndroidDevice]:
    """Try to find Android device via mtp-detect (libmtp-tools)."""
    try:
        result = subprocess.run(['mtp-detect'], capture_output=True, text=True, timeout=5)
        
        if result.returncode != 0:
            logger.debug("mtp-detect returned error")
            return None
        
        for line in result.stdout.split('\n'):
            if 'Device:' in line or 'Serial:' in line:
                device_path = '/mtp'
                device_name = 'AndroidPhone'
                
                device = AndroidDevice(device_path, device_name)
                device.connection_type = "mtp"
                return device
        
        return None
    
    except FileNotFoundError:
        logger.debug("mtp-detect command not found in PATH")
        return None
    except Exception as e:
        logger.debug(f"MTP detection failed: {e}")
        return None
