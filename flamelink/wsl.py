import os
import shutil
import subprocess


def is_wsl():
    return True if os.getenv("WSL_DISTRO_NAME") else False

def to_windows_path(path):
    if not is_wsl():
        return None
    wsl_path = shutil.which("wslpath")
    if wsl_path is None:
        return None
    try:
        result = subprocess.run([wsl_path, "-w", path], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception:
        return None
