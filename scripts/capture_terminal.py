"""Capture a real evidence console only after its commands finish successfully."""
import argparse
import ctypes
import subprocess
import time
from pathlib import Path

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]


def capture_terminal(section, destination):
    marker = ROOT / "screenshots/private" / f"{section}-complete.secret"
    marker.parent.mkdir(exist_ok=True)
    marker.unlink(missing_ok=True)
    process = subprocess.Popen(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-File",
         str(ROOT / "scripts/show-evidence.ps1"), "-Section", section,
         "-CompletionFile", str(marker)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    try:
        deadline = time.monotonic() + 90
        while not marker.exists():
            if time.monotonic() > deadline or process.poll() is not None:
                raise RuntimeError(f"Evidence commands did not complete: {section}")
            time.sleep(1)
        user32 = ctypes.windll.user32
        matches = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def visit(window, unused):
            title = ctypes.create_unicode_buffer(1024)
            user32.GetWindowTextW(window, title, 1024)
            if f"Ethereum node evidence - {section}" in title.value and user32.IsWindowVisible(window):
                matches.append(window)
            return True

        user32.EnumWindows(visit, 0)
        if not matches:
            raise RuntimeError("No visible evidence terminal found")
        window = matches[0]
        user32.ShowWindow(window, 3)
        user32.SetForegroundWindow(window)
        time.sleep(2)

        class Rect(ctypes.Structure):
            _fields_ = [(name, ctypes.c_long) for name in ("left", "top", "right", "bottom")]

        rectangle = Rect()
        if not user32.GetWindowRect(window, ctypes.byref(rectangle)):
            raise RuntimeError("Cannot get terminal bounds")
        screenshot = ImageGrab.grab(bbox=(
            max(0, rectangle.left), max(0, rectangle.top), rectangle.right, rectangle.bottom,
        ))
        if not screenshot.convert("RGB").getbbox():
            raise RuntimeError("Terminal capture is blank")
        screenshot.save(destination)
    finally:
        process.terminate()
        marker.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=["sync", "public", "build", "services", "rpc", "storage"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    capture_terminal(arguments.section, arguments.output)
