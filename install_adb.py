import urllib.request
import zipfile
import os
from pathlib import Path
import sys

print("=" * 70)
print("Installing Android Debug Bridge (ADB)...")
print("=" * 70)

# Create installation directory
install_dir = Path("C:\\Android\\platform-tools")
install_dir.parent.mkdir(parents=True, exist_ok=True)

adb_exe = install_dir / "adb.exe"

# Check if already installed
if adb_exe.exists():
    print(f"\n✓ ADB already installed at: {adb_exe}")
    os.system(f'"{adb_exe}" version')
    sys.exit(0)

print(f"\nDownloading to: {install_dir.parent}")

try:
    # Download platform-tools from Google
    url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    zip_path = install_dir.parent / "platform-tools.zip"
    
    print(f"Downloading platform-tools...")
    urllib.request.urlretrieve(url, str(zip_path))
    print(f"✓ Downloaded {zip_path.stat().st_size / (1024*1024):.1f} MB")
    
    # Extract
    print("Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(install_dir.parent)
    
    # Verify
    if adb_exe.exists():
        print(f"✓ ADB installed at: {adb_exe}")
        
        # Test ADB
        print("\nTesting ADB...")
        os.system(f'"{adb_exe}" version')
        
        # Add to PATH
        print("\n" + "=" * 70)
        print("Adding to system PATH...")
        print("=" * 70)
        
        # Try to add to PATH via registry (requires admin)
        import subprocess
        pathvar = os.environ.get('PATH', '')
        if str(install_dir) not in pathvar:
            # Set for current session
            os.environ['PATH'] = str(install_dir) + os.pathsep + pathvar
            print(f"✓ Added to current session PATH")
            
            # Try to add permanently via setx (user-level, no admin needed)
            try:
                subprocess.run(
                    ['setx', 'PATH', f'{install_dir};%PATH%'],
                    capture_output=True,
                    check=False
                )
                print(f"✓ Added to user environment (requires new terminal to take effect)")
            except Exception as e:
                print(f"Could not add to permanent PATH: {e}")
                print(f"  Workaround: Manually add to PATH or use full path: {install_dir}\\adb.exe")
        
        # Clean up
        zip_path.unlink()
        print(f"\n✓ Installation complete!")
        print(f"✓ ADB ready at: {adb_exe}")
        print(f"\nNext step: Connect your Android phone via USB and run:")
        print(f"  adb devices")
        
    else:
        print(f"✗ ADB executable not found after extraction")
        print(f"  Check: {install_dir}")
        
except Exception as e:
    print(f"✗ Installation failed: {e}")
    print(f"\nManual installation:")
    print(f"  1. Download: https://developer.android.com/tools/releases/platform-tools")
    print(f"  2. Extract to: C:\\Android\\platform-tools")
    print(f"  3. Add to PATH or use: C:\\Android\\platform-tools\\adb.exe")
