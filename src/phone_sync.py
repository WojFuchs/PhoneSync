import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from src.config import load_config, validate_config
from src.usb_handler import find_connected_device, USBScanner
from src.file_manager import LocalFileManager


def setup_logging(log_file: str = "phonesync.log") -> None:
    """Setup logging to both console and file."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)


logger = logging.getLogger(__name__)


class PhoneSync:
    """Main PhoneSync orchestrator."""
    
    def __init__(self, config_path: str = "PhoneSync_config.yaml"):
        self.config = load_config(config_path)
        
        if not validate_config(self.config):
            raise ValueError("Invalid configuration")
        
        self.destination_folder = self.config['destination_folder']
        self.phone_folders = self.config['phone_folders']
        self.excluded_folders = self.config.get('excluded_folders', [])
        
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
        
        scanner = USBScanner(device)
        
        phone_files = scanner.find_all_files(self.phone_folders, self.excluded_folders)
        logger.info(f"Found {len(phone_files)} files to process")
        
        if not phone_files:
            logger.warning("No files found on phone")
            return True
        
        sync_folder = self.file_manager.create_sync_folder(device.normalized_name)
        existing_folders = self.file_manager.find_existing_sync_folders(device.normalized_name)
        
        for file_info in phone_files:
            self._process_file(file_info, sync_folder, existing_folders, device)
        
        self._report_summary()
        
        logger.info("PhoneSync sync operation completed successfully")
        return True
    
    def _process_file(self, file_info: Dict[str, Any], sync_folder: Path, 
                     existing_folders: List[Path], device) -> None:
        """Process single file: check if already synced, copy if needed."""
        file_path = file_info['path']
        file_size = file_info['size']
        file_relative_path = file_path.lstrip('/')
        
        existing_file = self.file_manager.find_file_in_sync_folders(file_relative_path, existing_folders)
        
        if existing_file:
            if self.file_manager.is_file_unchanged(existing_file, file_size, 
                                                   file_info.get('modtime', 0)):
                logger.debug(f"File already synced (unchanged): {file_relative_path}")
                self.files_skipped += 1
                return
            else:
                logger.warning(f"File changed on phone: {file_relative_path}")
                self.files_changed.append(file_relative_path)
        
        if self._copy_and_verify_file(file_info, sync_folder, device):
            self.files_copied += 1
        else:
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


def main(config_path: str = "PhoneSync_config.yaml") -> int:
    """Main entry point."""
    try:
        setup_logging("phonesync.log")
        logger.info("=" * 60)
        logger.info("PhoneSync started")
        logger.info("=" * 60)
        
        sync = PhoneSync(config_path)
        success = sync.run()
        
        logger.info("=" * 60)
        if success:
            logger.info("PhoneSync completed successfully")
        else:
            logger.error("PhoneSync completed with errors")
        logger.info("=" * 60)
        
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
