import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import os

from src.config import load_config, validate_config
from src.usb_handler import find_connected_device, USBScanner
from src.file_manager import LocalFileManager


class PhoneSync:
    """Main PhoneSync orchestrator."""
    
    def __init__(self, config_path: str = "PhoneSync_config.yaml", max_files_per_sync_param: int = None):
        self.logger = logging.getLogger(__name__)
        
        self.sync_prefix = "Sync"
        self.sync_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.config = load_config(config_path)
        
        if not validate_config(self.config):
            raise ValueError("Invalid configuration")
        
        self.destination_folder = self.config['destination_folder']
        self.phone_folders = self.config.get('phone_folders', [])
        self.excluded_folders = self.config.get('excluded_folders', [])
        
        # Command-line parameter takes precedence over config
        self.max_files_per_sync = max_files_per_sync_param if max_files_per_sync_param is not None else self.config.get('max_files_per_sync')
        
        # Setup logging
        self.log_file = self._setup_logging()
        
        self.file_manager = LocalFileManager(self.destination_folder)
        self.files_copied = 0
        self.files_skipped = 0
        self.files_changed = []
        self.errors = []
        
        # Log startup info
        self.logger.info("=" * 60)
        self.logger.info("PhoneSync started")
        self.logger.info(f"Log file: {self.log_file}")
        if max_files_per_sync_param is not None:
            self.logger.info(f"Limiting copy to {max_files_per_sync_param} files (command-line override)")
        self.logger.info("=" * 60)
    
    def _setup_logging(self) -> Path:
        """Setup logging to both console and file. Returns log file path."""
        log_format = '%(asctime)s - %(message)s'
        
        dest_path = Path(self.destination_folder)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        log_file = dest_path / f"Sync_{self.sync_timestamp}.log"
        
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
    
    def _rename_log_file(self, log_file: Path, phone_normalized_name: str) -> Path:
        """Rename log file to include phone name once it's known.
        
        Extracts timestamp from the log filename and uses it in the new name.
        
        Renames from: Sync_<timestamp>.log
        To: Sync_<timestamp>_<phone_name>.log
        """
        if not log_file.exists():
            return log_file
        
        # Extract timestamp from filename: "Sync_20260913_183425.log" -> "20260913_183425"
        parts = log_file.stem.split('_')  # ["Sync", "20260913", "183425"]
        if len(parts) < 3:
            return log_file
        
        timestamp = f"{parts[1]}_{parts[2]}"
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
            log_format = '%(asctime)s - %(message)s'
            file_handler = logging.FileHandler(new_log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(log_format))
            root_logger.addHandler(file_handler)
            
            return new_log_file
        except Exception as e:
            self.logger.warning(f"Could not rename log file: {e}")
            return log_file
    
    def _extract_sync_timestamp(self) -> str:
        """Extract timestamp from log file name."""
        parts = self.log_file.stem.split('_')  # "Sync_20260913_183425" -> ["Sync", "20260913", "183425"]
        return f"{parts[1]}_{parts[2]}" if len(parts) >= 3 else datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def run(self) -> bool:
        """Execute the sync operation."""
        self.logger.info("PhoneSync sync operation started")
        
        device = find_connected_device()
        if not device:
            self.logger.error("ERROR: No Android device found")
            self.errors.append("No Android device found")
            success = False
        else:
            self.logger.info(f"Found phone: {device.device_name} (normalized: {device.normalized_name})")
            
            # Rename log file to include phone name now that we know it
            if self.log_file:
                self.log_file = self._rename_log_file(self.log_file, device.normalized_name)
            
            sync_folder = self.file_manager.create_sync_folder(device.normalized_name, self.sync_timestamp)
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
            
            self.logger.info(f"Ready to copy {len(files_to_copy)} files from phone")
            
            if not files_to_copy:
                self.logger.warning("No new files to copy")
                success = True
            else:
                # Now actually copy the files
                for file_info in files_to_copy:
                    self._copy_file(file_info, sync_folder, device)
                
                self._report_summary()
                
                self.logger.info("PhoneSync sync operation completed successfully")
                success = True
        
        # Log completion and shutdown
        self.logger.info("=" * 60)
        if success:
            self.logger.info("PhoneSync completed successfully")
        else:
            self.logger.error("ERROR: PhoneSync completed with errors")
        self.logger.info(f"Log file: {self.log_file}")
        self.logger.info("=" * 60)
        
        # Flush and close all handlers
        for handler in logging.getLogger().handlers:
            handler.flush()
            handler.close()
        logging.shutdown()
        
        print(f"\n✓ Log saved to: {self.log_file}")
        return success
    
    def _should_copy_file(self, file_info: Dict[str, Any], existing_folders: List[Path]) -> bool:
        """Check if file should be copied (doesn't exist or changed)."""
        file_path = file_info['path']
        file_size = file_info['size']
        file_relative_path = file_path.lstrip('/')
        
        existing_file = self.file_manager.find_file_in_sync_folders(file_relative_path, existing_folders)
        
        if existing_file:
            if self.file_manager.is_file_unchanged(existing_file, file_size, 
                                                   file_info.get('modtime', 0)):
                self.logger.debug(f"File already synced (unchanged): {file_relative_path}")
                self.files_skipped += 1
                return False
            else:
                self.logger.warning(f"WARNING: File changed on phone: {file_relative_path}")
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
        file_modtime = file_info.get('modtime', 0)
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
            
            expected_modtime = int(file_modtime)
            if expected_modtime > 0:
                self.file_manager.set_file_modtime(dest_file, expected_modtime)
            
            verified, message = self.file_manager.verify_copied_file(
                dest_file,
                file_size,
                expected_modtime
            )
            
            if not verified:
                self.logger.error(f"ERROR: Verification failed for {file_relative_path}: {message}")
                self.errors.append(f"Verification failed: {file_relative_path} - {message}")
                return False
            
            # Log file copy with formatted modtime
            modtime_str = datetime.fromtimestamp(expected_modtime).strftime("%Y-%m-%d %H:%M:%S") if expected_modtime > 0 else "unknown"
            self.logger.info(f"File Copied: modtime: {modtime_str} / path: {file_relative_path} / size: {file_size} bytes")
            return True
        
        except Exception as e:
            self.logger.error(f"ERROR: Error processing file {file_path}: {e}")
            self.errors.append(f"Error processing {file_path}: {str(e)}")
            return False
    
    def _report_summary(self) -> None:
        """Log summary of sync operation."""
        self.logger.info("=" * 60)
        self.logger.info("SYNC SUMMARY")
        self.logger.info(f"Files copied: {self.files_copied}")
        self.logger.info(f"Files skipped (unchanged): {self.files_skipped}")
        
        if self.files_changed:
            self.logger.warning(f"WARNING: Files changed on phone ({len(self.files_changed)}):")
            for f in self.files_changed:
                self.logger.warning(f"  - {f}")
        
        if self.errors:
            self.logger.error(f"ERROR: Errors ({len(self.errors)}):")
            for e in self.errors:
                self.logger.error(f"  - {e}")
        else:
            self.logger.info("No errors")
        
        self.logger.info("=" * 60)


def main(config_path: str = "PhoneSync_config.yaml", max_files_per_sync: int = None) -> int:
    """Main entry point. Initialize PhoneSync and run sync operation.
    
    Args:
        config_path: Path to PhoneSync_config.yaml
        max_files_per_sync: Optional limit on number of files to copy (overrides config)
    
    Returns:
        Exit code: 0 on success, 1 on failure
    """
    try:
        sync = PhoneSync(config_path, max_files_per_sync)
        sync.run()
        return 0
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
