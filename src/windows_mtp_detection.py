"""
Windows MTP device detection using Windows Shell API (COM).
This module tries to detect Android phones without requiring libmtp-tools CLI tools.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def find_android_device_windows_api() -> Optional[str]:
    """
    Try to find Android device via Windows IPortableDevice COM API.
    Returns device path if found, None otherwise.
    """
    try:
        import win32com.client
        from win32com.shell import shell
        
        # Get portable device manager
        manager = win32com.client.Dispatch("PortableDeviceManager.PortableDeviceManager")
        
        # Get list of devices
        device_ids = manager.GetDevices()
        
        logger.info(f"Found {len(device_ids)} portable devices via Windows API")
        
        for device_id in device_ids:
            try:
                # Try to get device name
                device = win32com.client.Dispatch("PortableDevice.PortableDevice")
                device.Open(device_id, manager)
                
                # Check if it's an Android device
                prop = device.Content().Properties()
                device_name = prop.GetStringValue(device.Properties().WPD_DEVICE_FRIENDLY_NAME)
                
                if "android" in device_name.lower() or "phone" in device_name.lower():
                    logger.info(f"Found Android device: {device_name}")
                    return device_id
            except Exception as e:
                logger.debug(f"Error checking device: {e}")
                continue
        
        return None
    
    except ImportError:
        logger.debug("pywin32 not installed - Windows API method unavailable")
        return None
    except Exception as e:
        logger.debug(f"Windows API method failed: {e}")
        return None


def find_android_device_via_wmi() -> Optional[str]:
    """
    Try to find Android device via Windows WMI.
    Returns device path if found, None otherwise.
    """
    try:
        import wmi
        
        c = wmi.WMI()
        
        # Query USB devices
        for device in c.Win32_PnPDevice():
            if device.Name and ("android" in device.Name.lower() or "mtp" in device.Name.lower()):
                logger.info(f"Found Android device via WMI: {device.Name}")
                return device.DeviceID
        
        return None
    
    except ImportError:
        logger.debug("wmi module not installed")
        return None
    except Exception as e:
        logger.debug(f"WMI method failed: {e}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    result = find_android_device_windows_api()
    if result:
        print(f"Found via Windows API: {result}")
    
    result = find_android_device_via_wmi()
    if result:
        print(f"Found via WMI: {result}")
