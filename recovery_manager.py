"""SUPER NOVA Recovery USB manager.

The USB creation path is intentionally guarded by explicit confirmation.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISO = ROOT / "output" / "SUPER_NOVA_RECOVERY.iso"

def usb_drives():
    q = "Get-CimInstance Win32_DiskDrive -Filter \"InterfaceType='USB'\" | Select Model,Size,DeviceID | ConvertTo-Json -Compress"
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", q], capture_output=True, text=True, check=True)
    if not r.stdout.strip(): return []
    rows = json.loads(r.stdout); rows = rows if isinstance(rows, list) else [rows]
    return [(str(x.get("DeviceID")), str(x.get("Model") or "USB"), int(x.get("Size") or 0)) for x in rows]

def refresh():
    drives.delete(0, tk.END)
    try: items = usb_drives()
    except Exception as e:
        messagebox.showerror("USB detection", str(e)); return
    for device, model, size in items: drives.insert(tk.END, f"{device} | {model} | {size / 1_000_000_000:.2f} GB")
    if not items: drives.insert(tk.END, "Aucune clé USB détectée")

def create_usb():
    if not ISO.is_file(): return messagebox.showerror("ISO introuvable", str(ISO))
    selection = drives.curselection()
    if not selection or not drives.get(selection[0]).startswith("\\\\.\\PHYSICALDRIVE"):
        return messagebox.showwarning("Sélection requise", "Sélectionnez une clé USB détectée.")
    device, model, size = usb_drives()[selection[0]]
    if not messagebox.askyesno("ATTENTION", f"Toutes les données de {model} ({size / 1_000_000_000:.2f} GB) seront supprimées. Continuer ?"):
        return
    if not messagebox.askyesno("CONFIRMATION FINALE", f"Confirmer le formatage de {device} et la création de la clé WinPE ?"):
        return

    temp_handle, temp_name = tempfile.mkstemp(prefix="supernova_recovery_", suffix=".iso")
    os.close(temp_handle)
    local_iso = Path(temp_name)
    try:
        shutil.copy2(ISO, local_iso)
    except OSError as error:
        return messagebox.showerror("ISO inaccessible", str(error))

    iso_path = str(local_iso).replace("'", "''")
    device_id = device.replace("'", "''")
    ps = f"""
$ErrorActionPreference = 'Stop'
$iso = '{iso_path}'
$device = '{device_id}'
$usb = Get-CimInstance Win32_DiskDrive | Where-Object DeviceID -eq $device
if (-not $usb -or $usb.InterfaceType -ne 'USB') {{ throw 'Le disque USB sélectionné est introuvable.' }}
$disk = Get-Disk | Where-Object Number -eq $usb.Index
if (-not $disk) {{ throw 'Disque USB introuvable.' }}
$null = Mount-DiskImage -ImagePath $iso -PassThru
Start-Sleep -Seconds 2
$isoSize = (Get-Item $iso).Length
$source = (Get-CimInstance Win32_LogicalDisk -Filter "DriveType=5" | Where-Object Size -eq $isoSize | Select-Object -First 1).DeviceID + '\\'
if (-not (Test-Path $source)) {{ throw 'ISO mount source not found.' }}
Clear-Disk -Number $disk.Number -RemoveData -Confirm:$false
if ($disk.PartitionStyle -eq 'RAW') {{ Initialize-Disk -Number $disk.Number -PartitionStyle GPT }}
# Windows limite généralement le formatage FAT32 à environ 32 GB.
$partition = New-Partition -DiskNumber $disk.Number -Size 30000000000 -AssignDriveLetter
Format-Volume -Partition $partition -FileSystem FAT32 -NewFileSystemLabel 'SUPER_NOVA' -Confirm:$false
$volume = Get-Volume -Partition $partition
$target = $volume.DriveLetter + ':\\'
Write-Host "ISO source: $source"
Write-Host "USB target: $target"
robocopy $source $target /E /J /MT:8 /R:0 /W:0 /NFL /NDL /NP
if ($LASTEXITCODE -gt 7) {{ throw 'ISO copy failed.' }}
Write-Host "Robocopy exit code: $LASTEXITCODE"
if (-not (Test-Path (Join-Path $target 'sources\\boot.wim'))) {{ throw 'boot.wim was not copied to the USB.' }}
Dismount-DiskImage -ImagePath $iso
"""
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps], check=True)
        messagebox.showinfo("Succès", "La clé WinPE a été créée. Vous pouvez maintenant la tester dans une VM.")
    except subprocess.CalledProcessError as error:
        messagebox.showerror("Échec", f"La création de la clé a échoué (code {error.returncode}).")
    finally:
        cleanup_path = str(local_iso).replace("'", "''")
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             f"Dismount-DiskImage -ImagePath '{cleanup_path}' -ErrorAction SilentlyContinue"],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            local_iso.unlink()
        except OSError:
            pass

root = tk.Tk(); root.title("SUPER NOVA RECOVERY"); root.geometry("700x360")
ttk.Label(root, text="SUPER NOVA RECOVERY", font=("Segoe UI", 18, "bold")).pack(pady=18)
ttk.Label(root, text=f"ISO : {'trouvée' if ISO.is_file() else 'introuvable'}").pack()
drives = tk.Listbox(root, width=90, height=8); drives.pack(pady=16)
bar = ttk.Frame(root); bar.pack()
ttk.Button(bar, text="Actualiser", command=refresh).pack(side=tk.LEFT, padx=6)
ttk.Button(bar, text="Créer la clé", command=create_usb).pack(side=tk.LEFT, padx=6)
refresh(); root.mainloop()
