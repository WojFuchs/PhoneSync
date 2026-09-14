import logging
import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class LocalFileManager:
    """Manage local filesystem operations and sync tracking."""
    
    def __init__(self, destination_folder: str):
        self.destination_folder = Path(destination_folder)
        self.destination_folder.mkdir(parents=True, exist_ok=True)
    
    def create_sync_folder(self, phone_name: str, timestamp: str = "") -> Path:
        """Create new Sync_<timestamp>_<Phone_Name> folder."""
        if not timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sync_folder_name = f"Sync_{timestamp}_{phone_name}"
        sync_folder = self.destination_folder / sync_folder_name
        sync_folder.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created sync folder: {sync_folder}")
        return sync_folder
    
    def find_existing_sync_folders(self, phone_name: str) -> List[Path]:
        """Find all existing Sync_*_<Phone_Name> folders sorted by timestamp (oldest to newest)."""
        pattern = f"Sync_*_{phone_name}"
        folders = sorted(self.destination_folder.glob(pattern))
        
        logger.info(f"Found {len(folders)} existing sync folder(s) for {phone_name}")
        
        return folders
    
    def find_file_in_sync_folders(self, file_relative_path: str, sync_folders: List[Path]) -> Optional[Path]:
        """Search for file in all sync folders. Returns path if found."""
        for sync_folder in sync_folders:
            file_path = sync_folder / file_relative_path
            if file_path.exists() and file_path.is_file():
                return file_path
        return None
    
    def get_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Get file size and modification time."""
        stat = file_path.stat()
        return {
            'size': stat.st_size,
            'modtime': int(stat.st_mtime)
        }
    
    def set_file_modtime(self, file_path: Path, modtime: int) -> None:
        """Set file modification time (in seconds since epoch)."""
        try:
            os.utime(file_path, (modtime, modtime))
        except Exception as e:
            logger.error(f"ERROR: Failed to set modtime for {file_path}: {e}")
            raise
    
    def copy_file_from_phone(self, file_relative_path: str, dest_folder: Path, 
                            phone_device_path: str, phone_file_path: str) -> bool:
        """Copy file from phone to destination folder preserving directory structure."""
        dest_file = dest_folder / file_relative_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            mtp_cmd = f'mtp-getfile "{phone_device_path}:{phone_file_path}" "{dest_file}"'
            result = subprocess.run(mtp_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"ERROR: Failed to copy file from phone: {result.stderr}")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"ERROR: Error copying file {file_relative_path}: {e}")
            return False
    
    def verify_copied_file(self, dest_file: Path, expected_size: int, 
                          expected_modtime: int, modtime_tolerance: int = 1) -> Tuple[bool, str]:
        """
        Verify copied file matches size and modtime from phone.
        Returns (success, message).
        """
        if not dest_file.exists():
            return False, f"File does not exist: {dest_file}"
        
        stat = dest_file.stat()
        actual_size = stat.st_size
        actual_modtime = int(stat.st_mtime)
        
        if actual_size != expected_size:
            return False, f"Size mismatch: expected {expected_size}, got {actual_size}"
        
        modtime_diff = abs(actual_modtime - expected_modtime)
        if modtime_diff > modtime_tolerance:
            return False, f"Modtime mismatch: expected {expected_modtime}, got {actual_modtime} (diff: {modtime_diff}s)"
        
        return True, "Verification passed"
    
    def is_file_unchanged(self, existing_file: Path, phone_file_size: int, 
                         phone_file_modtime: int, modtime_tolerance: int = 1) -> bool:
        """Check if file on disk matches phone file (already copied)."""
        try:
            stat = existing_file.stat()
            
            if stat.st_size != phone_file_size:
                return False
            
            modtime_diff = abs(int(stat.st_mtime) - phone_file_modtime)
            if modtime_diff > modtime_tolerance:
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Error checking file {existing_file}: {e}")
            return False
    
    def get_latest_sync_folder(self, sync_folders: List[Path]) -> Optional[Path]:
        """Get the most recent sync folder from list."""
        if not sync_folders:
            return None
        return sync_folders[-1]
    
    def build_existing_files_index(self, sync_folders: List[Path]) -> Tuple[Dict[str, Path], int]:
        """Build index of files from existing sync folders, keeping only newest version per path.
        
        Returns (files_index, total_versions) where:
        - files_index: Dict[relative_path] -> Path of newest version
        - total_versions: Total count of all file versions found
        """
        files_by_path = {}
        total_versions = 0
        
        # Iterate folders in reverse (newest first) so oldest versions are kept in dict if not overwritten
        for folder in reversed(sync_folders):
            for file_path in folder.rglob('*'):
                if file_path.is_file():
                    total_versions += 1
                    relative_path = str(file_path.relative_to(folder)).replace('\\', '/')
                    # Only keep the first occurrence (newest) for each path
                    if relative_path not in files_by_path:
                        files_by_path[relative_path] = file_path
        
        return files_by_path, total_versions
