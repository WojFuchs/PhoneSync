import logging
import re
from pathlib import Path, PureWindowsPath
from typing import List, Dict, Any, Optional, Tuple
import os
import subprocess

logger = logging.getLogger(__name__)


class AndroidDevice:
    """Represents an Android device connected via USB MTP."""
    
    def __init__(self, device_path: str, device_name: str):
        self.device_path = device_path
        self.device_name = device_name
        self.normalized_name = self._normalize_phone_name(device_name)
    
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
    """Scan and find files on connected Android device via MTP."""
    
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
        """Recursively scan folder on phone for files."""
        files = []
        
        try:
            mtp_cmd = ['mtp-ls', f'--device="{self.device.device_path}"', f'"{folder}"']
            result = subprocess.run(mtp_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"Could not scan folder {folder}: {result.stderr}")
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
                    sub_files = self._scan_folder_recursive(subfolder, excluded_folders)
                    files.extend(sub_files)
                else:
                    file_info = self._extract_file_info(line, folder, name)
                    if file_info:
                        files.append(file_info)
        
        except Exception as e:
            logger.error(f"Error scanning folder {folder}: {e}")
        
        return files
    
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
            logger.warning(f"Could not parse file info for {name}: {e}")
            return None


def find_connected_device() -> Optional[AndroidDevice]:
    """Find first Android device connected via USB MTP."""
    try:
        result = subprocess.run(['mtp-detect'], capture_output=True, text=True, timeout=5)
        
        if result.returncode != 0:
            logger.warning("No MTP device detected")
            return None
        
        for line in result.stdout.split('\n'):
            if 'Device:' in line or 'Serial:' in line:
                device_path = '/mtp'
                device_name = 'AndroidPhone'
                
                logger.info(f"Found Android device: {device_name}")
                return AndroidDevice(device_path, device_name)
        
        logger.warning("No Android device found in MTP detection")
        return None
    
    except Exception as e:
        logger.error(f"Error detecting MTP device: {e}")
        return None
