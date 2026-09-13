import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from src.config import load_config, validate_config
from src.usb_handler import find_connected_device, USBScanner
from src.file_manager import LocalFileManager


def setup_logging(destination_folder: str, sync_timestamp: str) -> Path:
    """Setup logging to both console and file in destination folder."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    dest_path = Path(destination_folder)
    dest_path.mkdir(parents=True, exist_ok=True)
    
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


logger = logging.getLogger(__name__)


class PhoneSync:
    """Main PhoneSync orchestrator."""
    
    def __init__(self, config_path: str = "PhoneSync_config.yaml", sync_timestamp: str = "", 
                 max_files_per_sync_param: int = None):
        self.config = load_config(config_path)
        
        if not validate_config(self.config):
            raise ValueError("Invalid configuration")
        
        self.destination_folder = self.config['destination_folder']
        self.phone_folders = self.config.get('phone_folders', [])
        self.excluded_folders = self.config.get('excluded_folders', [])
        
        # Command-line parameter takes precedence over config
        self.max_files_per_sync = max_files_per_sync_param if max_files_per_sync_param is not None else self.config.get('max_files_per_sync')
        
        self.sync_timestamp = sync_timestamp
        
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
        
        sync_folder = self.file_manager.create_sync_folder(device.normalized_name, self.sync_timestamp)
        existing_folders = self.file_manager.find_existing_sync_folders(device.normalized_name)
        
        scanner = USBScanner(device)
        
        # Scan folders - files already sorted by folder and by modtime within each folder
        phone_files = scanner.find_all_files(self.phone_folders, self.excluded_folders)
        logger.info(f"Found {len(phone_files)} files to scan")
        
        if not phone_files:
            logger.warning("No files found on phone")
            return True
        
        # Process files and collect those that need copying
        # Stop processing when reaching copy limit to avoid unnecessary scanning
        files_to_copy = []
        files_scanned = 0
        
        for file_info in phone_files:
            files_scanned += 1
            
            if self._should_copy_file(file_info, existing_folders):
                files_to_copy.append(file_info)
                
                # Check if we reached the limit of files to copy
                if self.max_files_per_sync is not None and len(files_to_copy) >= self.max_files_per_sync:
                    logger.info(f"Reached copy limit: {self.max_files_per_sync} files to copy (scanned {files_scanned} files)")
                    if files_scanned < len(phone_files):
                        logger.info(f"Stopped early - {len(phone_files) - files_scanned} files remaining not scanned")
                    break
        
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
        
        sync_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = setup_logging(config['destination_folder'], sync_timestamp)
        
        logger.info("=" * 60)
        logger.info("PhoneSync started")
        logger.info(f"Log file: {log_file}")
        if max_files_per_sync is not None:
            logger.info(f"Limiting copy to {max_files_per_sync} files (command-line override)")
        logger.info("=" * 60)
        
        sync = PhoneSync(config_path, sync_timestamp, max_files_per_sync)
        success = sync.run()
        
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
