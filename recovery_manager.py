"""SUPER NOVA Recovery USB manager."""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parent
ISO = ROOT / "output" / "SUPER_NOVA_RECOVERY.iso"
ICON = ROOT / "assets" / "SUPER_NOVA.ico"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
COPY_PROGRESS_CONTINUE = 0
COPY_PROGRESS_CANCEL = 1


class OperationCancelled(RuntimeError):
    """Raised when the user cancels USB creation."""


def usb_drives() -> list[tuple[str, str, int]]:
    query = (
        "Get-CimInstance Win32_DiskDrive -Filter \"InterfaceType='USB'\" | "
        "Select Model,Size,DeviceID | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query],
        capture_output=True,
        text=True,
        check=True,
        creationflags=CREATE_NO_WINDOW,
    )
    if not result.stdout.strip():
        return []
    rows = json.loads(result.stdout)
    rows = rows if isinstance(rows, list) else [rows]
    return [
        (
            str(row.get("DeviceID") or "Unknown"),
            str(row.get("Model") or "USB"),
            int(row.get("Size") or 0),
        )
        for row in rows
    ]


def format_size(size: int) -> str:
    return f"{size / 1_000_000_000:.2f} GB"


def copy_file_ex(source: Path, target: Path, progress, cancel_event: threading.Event) -> None:
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.DWORD,
        wintypes.LARGE_INTEGER,
        wintypes.LARGE_INTEGER,
        wintypes.LARGE_INTEGER,
        wintypes.LARGE_INTEGER,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.LPVOID,
    )

    def callback(total, transferred, *_):
        if cancel_event.is_set():
            return COPY_PROGRESS_CANCEL
        if total:
            progress(float(transferred) / float(total))
        return COPY_PROGRESS_CONTINUE

    callback_ref = callback_type(callback)
    cancel = wintypes.BOOL(False)
    kernel32 = ctypes.windll.kernel32
    kernel32.CopyFileExW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        callback_type,
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.BOOL),
        wintypes.DWORD,
    ]
    if not kernel32.CopyFileExW(str(source), str(target), callback_ref, None, ctypes.byref(cancel), 0):
        if cancel_event.is_set():
            try:
                target.unlink()
            except OSError:
                pass
            raise OperationCancelled("Opération annulée.")
        raise ctypes.WinError()


def copy_tree(source: Path, target: Path, progress, cancel_event: threading.Event) -> None:
    files = [path for path in source.rglob("*") if path.is_file()]
    total = sum(path.stat().st_size for path in files) or 1
    completed = 0
    for source_file in files:
        if cancel_event.is_set():
            raise OperationCancelled("Opération annulée.")
        target_file = target / source_file.relative_to(source)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        start = completed
        size = source_file.stat().st_size
        copy_file_ex(
            source_file,
            target_file,
            lambda value: progress((start + value * size) / total),
            cancel_event,
        )
        completed += size


def prepare_usb(device: str, status, progress, cancel_event: threading.Event) -> None:
    temp_handle, temp_name = tempfile.mkstemp(prefix="supernova_recovery_", suffix=".iso")
    os.close(temp_handle)
    local_iso = Path(temp_name)
    try:
        status("Préparation")
        shutil.copy2(ISO, local_iso)
        if cancel_event.is_set():
            raise OperationCancelled("Opération annulée.")

        iso_path = str(local_iso).replace("'", "''")
        device_id = device.replace("'", "''")
        script = f"""
$ErrorActionPreference = 'Stop'
$iso = '{iso_path}'
$device = '{device_id}'
$usb = Get-CimInstance Win32_DiskDrive | Where-Object DeviceID -eq $device
if (-not $usb -or $usb.InterfaceType -ne 'USB') {{ throw 'Le disque USB sélectionné est introuvable.' }}
$disk = Get-Disk | Where-Object Number -eq $usb.Index
if (-not $disk) {{ throw 'Disque USB introuvable.' }}
$null = Mount-DiskImage -ImagePath $iso -PassThru
Start-Sleep -Seconds 2
$volume = Get-DiskImage -ImagePath $iso | Get-Volume | Where-Object DriveLetter | Select-Object -First 1
if ($volume) {{ $source = $volume.DriveLetter + ':\\' }} else {{
    $isoSize = (Get-Item $iso).Length
    $source = (Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=5\" | Where-Object Size -eq $isoSize | Select-Object -First 1).DeviceID + '\\'
}}
if (-not $source -or -not (Test-Path (Join-Path $source 'sources\\boot.wim'))) {{ throw 'Lecteur source ISO introuvable.' }}
Clear-Disk -Number $disk.Number -RemoveData -Confirm:$false
$disk = Get-Disk -Number $usb.Index
if ($disk.PartitionStyle -eq 'RAW') {{ Initialize-Disk -Number $disk.Number -PartitionStyle GPT }}
$partition = New-Partition -DiskNumber $disk.Number -Size 30000000000 -AssignDriveLetter
Format-Volume -Partition $partition -FileSystem FAT32 -NewFileSystemLabel 'SUPER_NOVA' -Confirm:$false | Out-Null
$target = (Get-Volume -Partition $partition).DriveLetter + ':\\'
Write-Output ($source + '|' + $target)
"""
        status("Formatage")
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            check=True,
            creationflags=CREATE_NO_WINDOW,
        )
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines or "|" not in lines[-1]:
            raise RuntimeError("Le lecteur source ou cible n'a pas été retourné par PowerShell.")
        source_name, target_name = lines[-1].split("|", 1)
        if cancel_event.is_set():
            raise OperationCancelled("Opération annulée.")
        status("Copie des fichiers")
        copy_tree(Path(source_name), Path(target_name), progress, cancel_event)
        status("Vérification")
        if not (Path(target_name) / "sources" / "boot.wim").is_file():
            raise RuntimeError("boot.wim est absent de la clé USB.")
        progress(1.0)
        status("Terminé")
    except subprocess.CalledProcessError as error:
        details = (error.stderr or error.stdout or "").strip()
        raise RuntimeError(details or f"PowerShell a échoué (code {error.returncode}).") from error
    finally:
        cleanup_path = str(local_iso).replace("'", "''")
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"Dismount-DiskImage -ImagePath '{cleanup_path}' -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
        )
        try:
            local_iso.unlink()
        except OSError:
            pass


root = tk.Tk()
root.title("SUPER NOVA RECOVERY")
root.geometry("760x430")
if ICON.is_file():
    root.iconbitmap(str(ICON))
ttk.Label(root, text="SUPER NOVA RECOVERY", font=("Segoe UI", 18, "bold")).pack(pady=18)
ttk.Label(root, text=f"ISO : {'trouvée' if ISO.is_file() else 'introuvable'}").pack()
drives = tk.Listbox(root, width=100, height=8)
drives.pack(pady=16)
controls = ttk.Frame(root)
controls.pack()
refresh_button = ttk.Button(controls, text="Actualiser")
refresh_button.pack(side=tk.LEFT, padx=6)
create_button = ttk.Button(controls, text="Créer la clé")
create_button.pack(side=tk.LEFT, padx=6)
cancel_button = ttk.Button(controls, text="Annuler", state=tk.DISABLED)
cancel_button.pack(side=tk.LEFT, padx=6)
close_button = ttk.Button(controls, text="Fermer", command=root.destroy, state=tk.DISABLED)
close_button.pack(side=tk.LEFT, padx=6)
status_label = ttk.Label(root, text="En attente")
status_label.pack(pady=(18, 4))
progress_bar = ttk.Progressbar(root, orient="horizontal", length=650, mode="determinate", maximum=100)
progress_bar.pack()

cancel_event = threading.Event()
operation_running = False


def refresh() -> None:
    drives.delete(0, tk.END)
    try:
        items = usb_drives()
    except Exception as error:
        messagebox.showerror("Détection USB", str(error))
        return
    for device, model, size in items:
        drives.insert(tk.END, f"{device} | {model} | {format_size(size)}")
    if not items:
        drives.insert(tk.END, "Aucune clé USB détectée")


def cancel_operation() -> None:
    if operation_running:
        cancel_event.set()
        cancel_button.config(state=tk.DISABLED)
        status_label.config(text="Annulation...")


def create_usb() -> None:
    global operation_running
    if not ISO.is_file():
        messagebox.showerror("ISO introuvable", str(ISO))
        return
    selection = drives.curselection()
    if not selection or not drives.get(selection[0]).startswith("\\\\.\\PHYSICALDRIVE"):
        messagebox.showwarning("Sélection requise", "Sélectionnez une clé USB détectée.")
        return
    try:
        items = usb_drives()
    except Exception as error:
        messagebox.showerror("Détection USB", str(error))
        return
    if selection[0] >= len(items):
        messagebox.showwarning("Sélection invalide", "Actualisez la liste des clés USB.")
        return
    device, model, size = items[selection[0]]
    if not messagebox.askyesno("ATTENTION", f"Toutes les données de {model} ({format_size(size)}) seront supprimées. Continuer ?"):
        return
    if not messagebox.askyesno("CONFIRMATION FINALE", f"Confirmer le formatage de {device} et la création de la clé WinPE ?"):
        return

    operation_running = True
    cancel_event.clear()
    refresh_button.config(state=tk.DISABLED)
    create_button.config(state=tk.DISABLED)
    cancel_button.config(state=tk.NORMAL)
    close_button.config(state=tk.DISABLED)
    progress_bar.config(value=0)
    status_label.config(text="Préparation")
    threading.Thread(target=worker, args=(device,), daemon=True).start()


def worker(device: str) -> None:
    global operation_running
    try:
        prepare_usb(
            device,
            lambda text: root.after(0, status_label.config, {"text": text}),
            lambda value: root.after(0, progress_bar.config, {"value": value * 100}),
            cancel_event,
        )
    except OperationCancelled as error:
        root.after(0, status_label.config, {"text": "Annulée"})
        root.after(0, messagebox.showinfo, "Opération annulée", str(error))
    except Exception as error:
        root.after(0, status_label.config, {"text": "Échec"})
        root.after(0, messagebox.showerror, "Échec", str(error))
    else:
        root.after(0, status_label.config, {"text": "Terminé"})
        root.after(0, progress_bar.config, {"value": 100})
        root.after(0, close_button.config, {"state": tk.NORMAL})
        root.after(0, messagebox.showinfo, "Succès", "La clé WinPE a été créée.")
    finally:
        operation_running = False
        root.after(0, refresh_button.config, {"state": tk.NORMAL})
        root.after(0, create_button.config, {"state": tk.NORMAL})
        root.after(0, cancel_button.config, {"state": tk.DISABLED})


refresh_button.config(command=refresh)
create_button.config(command=create_usb)
cancel_button.config(command=cancel_operation)
refresh()
root.mainloop()
