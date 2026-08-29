"""Read-only local manager for the SUPER NOVA recovery media."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ISO_NAME = "SUPER_NOVA_RECOVERY.iso"


@dataclass(frozen=True)
class UsbDrive:
    model: str
    size_bytes: int | None
    device_id: str

    @property
    def size_gb(self) -> float | None:
        return None if self.size_bytes is None else round(self.size_bytes / 1_000_000_000, 2)


def find_iso(project_root: Path) -> Path:
    """Return the expected ISO path, whether or not it exists."""
    return project_root / "output" / ISO_NAME


def inspect_iso(project_root: Path) -> dict[str, object]:
    path = find_iso(project_root)
    return {
        "path": str(path),
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else None,
    }


def _powershell_command() -> list[str]:
    query = (
        "Get-WmiObject Win32_DiskDrive -Filter \"InterfaceType='USB'\" | "
        "Select-Object Model,Size,DeviceID | ConvertTo-Json -Compress"
    )
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query]


def detect_usb_drives(runner=subprocess.run) -> list[UsbDrive]:
    """Read USB disk metadata through Windows WMI; never opens a disk for writing."""
    result = runner(_powershell_command(), capture_output=True, text=True, check=True)
    if not result.stdout.strip():
        return []
    records = json.loads(result.stdout)
    if isinstance(records, dict):
        records = [records]
    return [
        UsbDrive(
            model=str(record.get("Model") or "Unknown USB disk"),
            size_bytes=int(record["Size"]) if record.get("Size") else None,
            device_id=str(record.get("DeviceID") or "Unknown"),
        )
        for record in records
    ]


def format_bytes(size_bytes: int | None) -> str:
    return "unknown" if size_bytes is None else f"{size_bytes / 1_000_000_000:.2f} GB"


def print_report(project_root: Path, drives: Iterable[UsbDrive]) -> None:
    iso = inspect_iso(project_root)
    print(f"ISO: {iso['path']}")
    print(f"  status: {'found' if iso['exists'] else 'missing'}")
    print(f"  size: {format_bytes(iso['size_bytes'])}")
    print("USB drives:")
    drives = list(drives)
    if not drives:
        print("  none detected")
    for drive in drives:
        print(f"  - model: {drive.model}")
        print(f"    size: {format_bytes(drive.size_bytes)}")
        print(f"    id: {drive.device_id}")
    print("Mode: read-only; no formatting or disk writes performed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect recovery ISO and USB disks (read-only).")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        print_report(args.project_root, detect_usb_drives())
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        parser.error(f"USB WMI query failed: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
