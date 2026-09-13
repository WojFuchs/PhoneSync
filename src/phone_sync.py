import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import os

from src.config import load_config, validate_config
from src.usb_handler import find_connected_device, USBScanner
from src.file_manager import LocalFileManager


def setup_logging(destination_folder: str) -> Path:
    """Setup logging to both console and file in destination folder.
    
    Creates log file with timestamp in format: Sync_YYYYMMdd_HHMMSS.log
    """
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    dest_path = Path(destination_folder)
    dest_path.mkdir(parents=True, exist_ok=True)
    
    sync_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = dest_path / f"Sync_{sync_timestamp}.log"
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)
    
    return log_file


def rename_log_file(log_file: Path, phone_normalized_name: str) -> Path:
    """Rename log file to include phone name once it's known.
    
    Renames from: Sync_<timestamp>.log
    To: Sync_<timestamp>_<phone_name>.log
    
    Timestamp format: YYYYMMdd_HHMMSS
    """
    if not log_file.exists():
        return log_file
    
    # Extract timestamp from filename
    # stem is like "Sync_20260913_142742"
    parts = log_file.stem.split('_')  # ["Sync", "20260913", "142742"]
    if len(parts) < 3:
        return log_file
    
    timestamp = f"{parts[1]}_{parts[2]}"  # "20260913_142742"
    new_log_file = log_file.parent / f"Sync_{timestamp}_{phone_normalized_name}.log"
    
    # Close all file handlers before renaming
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            root_logger.removeHandler(handler)
    
    # Rename the file - remove destination if it exists (Windows compatibility)
    try:
        if new_log_file.exists():
            new_log_file.unlink()
        os.rename(log_file, new_log_file)
        
        # Re-add file handler with new path
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        file_handler = logging.FileHandler(new_log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)
        
        return new_log_file
    except Exception as e:
        logger.warning(f"Could not rename log file: {e}")
        return log_file


logger = logging.getLogger(__name__)


class PhoneSync:
    """Main PhoneSync orchestrator."""
    
    def __init__(self, config_path: str = "PhoneSync_config.yaml", 
                 max_files_per_sync_param: int = None, log_file: Path = None):
        self.config = load_config(config_path)
        
        if not validate_config(self.config):
            raise ValueError("Invalid configuration")
        
        self.destination_folder = self.config['destination_folder']
        self.phone_folders = self.config.get('phone_folders', [])
        self.excluded_folders = self.config.get('excluded_folders', [])
        
        # Command-line parameter takes precedence over config
        self.max_files_per_sync = max_files_per_sync_param if max_files_per_sync_param is not None else self.config.get('max_files_per_sync')
        
        self.log_file = log_file
        
        self.file_manager = LocalFileManager(self.destination_folder)
        self.files_copied = 0
        self.files_skipped = 0
        self.files_changed = []
        self.errors = []
    
    def run(self) -> bool:
        """Execute the sync operation."""
        logger.info("PhoneSync sync operation started")
        
        device = find_connected_device()
        if not device:
            logger.error("No Android device found")
            self.errors.append("No Android device found")
            return False
        
        logger.info(f"Found phone: {device.device_name} (normalized: {device.normalized_name})")
        
        # Rename log file to include phone name now that we know it
        if self.log_file:
            self.log_file = rename_log_file(self.log_file, device.normalized_name)
        
        sync_folder = self.file_manager.create_sync_folder(device.normalized_name)
        existing_folders = self.file_manager.find_existing_sync_folders(device.normalized_name)
        
        scanner = USBScanner(device)
        
        # Scan folders for files to copy - scanning stops when limit is reached
        # Pass callback to validate each file during scanning (checks incremental state)
        files_to_copy = scanner.find_files_for_copying(
            self.phone_folders, 
            self.excluded_folders,
            lambda file_info: self._should_copy_file(file_info, existing_folders),
            self.max_files_per_sync
        )
        
        logger.info(f"Ready to copy {len(files_to_copy)} files from phone")
        
        if not files_to_copy:
            logger.warning("No new files to copy")
            return True
        
        # Now actually copy the files
        for file_info in files_to_copy:
            self._copy_file(file_info, sync_folder, device)
        
        self._report_summary()
        
        logger.info("PhoneSync sync operation completed successfully")
        return True
    
    def _should_copy_file(self, file_info: Dict[str, Any], existing_folders: List[Path]) -> bool:
        """Check if file should be copied (doesn't exist or changed)."""
        file_path = file_info['path']
        file_size = file_info['size']
        file_relative_path = file_path.lstrip('/')
        
        existing_file = self.file_manager.find_file_in_sync_folders(file_relative_path, existing_folders)
        
        if existing_file:
            if self.file_manager.is_file_unchanged(existing_file, file_size, 
                                                   file_info.get('modtime', 0)):
                logger.debug(f"File already synced (unchanged): {file_relative_path}")
                self.files_skipped += 1
                return False
            else:
                logger.warning(f"File changed on phone: {file_relative_path}")
                self.files_changed.append(file_relative_path)
                return True
        
        return True
    
    def _copy_file(self, file_info: Dict[str, Any], sync_folder: Path, device) -> None:
        """Copy single file and verify it."""
        if self._copy_and_verify_file(file_info, sync_folder, device):
            self.files_copied += 1
        else:
            file_relative_path = file_info['path'].lstrip('/')
            self.errors.append(f"Failed to copy: {file_relative_path}")
    
    def _copy_and_verify_file(self, file_info: Dict[str, Any], sync_folder: Path, device) -> bool:
        """Copy file from phone and verify it."""
        file_path = file_info['path']
        file_size = file_info['size']
        file_relative_path = file_path.lstrip('/')
        
        try:
            copied = self.file_manager.copy_file_from_phone(
                file_relative_path,
                sync_folder,
                device.device_path,
                file_path
            )
            
            if not copied:
                return False
            
            dest_file = sync_folder / file_relative_path
            
            expected_modtime = int(file_info.get('modtime', 0))
            if expected_modtime > 0:
                self.file_manager.set_file_modtime(dest_file, expected_modtime)
            
            verified, message = self.file_manager.verify_copied_file(
                dest_file,
                file_size,
                expected_modtime
            )
            
            if not verified:
                logger.error(f"Verification failed for {file_relative_path}: {message}")
                self.errors.append(f"Verification failed: {file_relative_path} - {message}")
                return False
            
            logger.info(f"Successfully synced: {file_relative_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            self.errors.append(f"Error processing {file_path}: {str(e)}")
            return False
    
    def _report_summary(self) -> None:
        """Log summary of sync operation."""
        logger.info("=" * 60)
        logger.info("SYNC SUMMARY")
        logger.info(f"Files copied: {self.files_copied}")
        logger.info(f"Files skipped (unchanged): {self.files_skipped}")
        
        if self.files_changed:
            logger.warning(f"Files changed on phone ({len(self.files_changed)}):")
            for f in self.files_changed:
                logger.warning(f"  - {f}")
        
        if self.errors:
            logger.error(f"Errors ({len(self.errors)}):")
            for e in self.errors:
                logger.error(f"  - {e}")
        else:
            logger.info("No errors")
        
        logger.info("=" * 60)


def main(config_path: str = "PhoneSync_config.yaml", max_files_per_sync: int = None) -> int:
    """Main entry point.
    
    Args:
        config_path: Path to PhoneSync_config.yaml
        max_files_per_sync: Optional limit on number of files to copy (overrides config)
    """
    try:
        config = load_config(config_path)
        
        if not validate_config(config):
            print("Invalid configuration")
            return 1
        
        log_file = setup_logging(config['destination_folder'])
        
        logger.info("=" * 60)
        logger.info("PhoneSync started")
        logger.info(f"Log file: {log_file}")
        if max_files_per_sync is not None:
            logger.info(f"Limiting copy to {max_files_per_sync} files (command-line override)")
        logger.info("=" * 60)
        
        sync = PhoneSync(config_path, max_files_per_sync, log_file)
        success = sync.run()
        
        # Update log_file reference if it was renamed during run()
        log_file = sync.log_file if sync.log_file else log_file
        
        logger.info("=" * 60)
        if success:
            logger.info("PhoneSync completed successfully")
        else:
            logger.error("PhoneSync completed with errors")
        logger.info(f"Log file: {log_file}")
        logger.info("=" * 60)
        
        # Flush and close all handlers
        for handler in logging.getLogger().handlers:
            handler.flush()
            handler.close()
        logging.shutdown()
        
        print(f"\n✓ Log saved to: {log_file}")
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        for handler in logging.getLogger().handlers:
            handler.flush()
            handler.close()
        logging.shutdown()
        return 1


if __name__ == "__main__":
    exit(main())
