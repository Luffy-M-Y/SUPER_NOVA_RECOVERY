"""SUPER NOVA Recovery USB manager."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
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


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


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


def verify_boot_files(target: Path) -> list[str]:
    required = (
        target / "bootmgr",
        target / "EFI" / "Microsoft" / "Boot" / "bootmgfw.efi",
        target / "sources" / "boot.wim",
    )
    return [str(path.relative_to(target)) for path in required if not path.is_file()]


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
        match = re.search(r"PHYSICALDRIVE(\d+)$", device.upper())
        if not match:
            raise RuntimeError("Identifiant de disque USB invalide.")
        disk_number = int(match.group(1))
        script = f"""
$ErrorActionPreference = 'Stop'
$iso = '{iso_path}'
$device = '{device_id}'
$diskNumber = {disk_number}
$disk = Get-Disk -Number $diskNumber -ErrorAction SilentlyContinue
$usb = Get-CimInstance Win32_DiskDrive | Where-Object Index -eq $diskNumber
if (-not $disk -or (-not $usb -and $disk.BusType -ne 'USB')) {{ throw 'Disque USB introuvable.' }}
if ($usb -and $usb.InterfaceType -ne 'USB' -and $disk.BusType -ne 'USB') {{ throw 'Selected disk is not USB.' }}
if ($disk.IsSystem -or $disk.IsBoot) {{ throw 'Le disque sélectionné est un disque système ou de démarrage.' }}
if ($disk.IsOffline) {{ Set-Disk -Number $disk.Number -IsOffline $false }}
if ($disk.IsReadOnly) {{ Set-Disk -Number $disk.Number -IsReadOnly $false }}
$null = Mount-DiskImage -ImagePath $iso -PassThru
Start-Sleep -Seconds 2
$volume = Get-DiskImage -ImagePath $iso | Get-Volume | Where-Object DriveLetter | Select-Object -First 1
if ($volume) {{ $source = $volume.DriveLetter + ':\\' }} else {{
    $isoSize = (Get-Item $iso).Length
    $source = (Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=5\" | Where-Object Size -eq $isoSize | Select-Object -First 1).DeviceID + '\\'
}}
if (-not $source -or -not (Test-Path (Join-Path $source 'sources\\boot.wim'))) {{ throw 'Lecteur source ISO introuvable.' }}
Clear-Disk -Number $diskNumber -RemoveData -Confirm:$false
Start-Sleep -Seconds 1
$disk = Get-Disk -Number $diskNumber
if ($disk.PartitionStyle -eq 'RAW') {{ Initialize-Disk -Number $disk.Number -PartitionStyle GPT }}
Start-Sleep -Seconds 1
$disk = Get-Disk -Number $diskNumber
$free = [int64]$disk.LargestFreeExtent
$partitionSize = [math]::Min([int64]30000000000, $free - 1048576)
$partitionSize = [math]::Floor($partitionSize / 1048576) * 1048576
if ($partitionSize -lt 1000000000) {{ throw 'Espace libre insuffisant pour créer la partition FAT32.' }}
$partition = New-Partition -DiskNumber $diskNumber -Size $partitionSize -AssignDriveLetter
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
        status("Vérification du démarrage")
        missing = verify_boot_files(Path(target_name))
        if missing:
            raise RuntimeError("Fichiers bootables manquants : " + ", ".join(missing))
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


COLORS = {
    "bg": "#0B1220",
    "panel": "#121C2E",
    "panel_alt": "#17243A",
    "border": "#263A59",
    "text": "#EDF4FF",
    "muted": "#9DB0CA",
    "blue": "#4EA1FF",
    "blue_dark": "#1E5EA8",
    "green": "#32D583",
    "red": "#F97068",
}


root = tk.Tk()
root.title("SUPER NOVA RECOVERY")
root.geometry("900x640")
root.resizable(False, False)
root.configure(bg=COLORS["bg"])
if ICON.is_file():
    try:
        root.iconbitmap(str(ICON))
    except tk.TclError:
        pass

style = ttk.Style(root)
style.theme_use("clam")
style.configure("App.TFrame", background=COLORS["bg"])
style.configure("Panel.TFrame", background=COLORS["panel"])
style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 22, "bold"))
style.configure("Subtitle.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 10))
style.configure("PanelTitle.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 12, "bold"))
style.configure("PanelText.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9))
style.configure("Status.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 10, "bold"))
style.configure("Primary.TButton", background=COLORS["blue_dark"], foreground="white", padding=(18, 9), font=("Segoe UI", 10, "bold"), borderwidth=0)
style.map("Primary.TButton", background=[("active", COLORS["blue"]), ("disabled", "#24324A")], foreground=[("disabled", "#71829B")])
style.configure("Secondary.TButton", background=COLORS["panel_alt"], foreground=COLORS["text"], padding=(15, 9), font=("Segoe UI", 10), borderwidth=0)
style.map("Secondary.TButton", background=[("active", COLORS["border"]), ("disabled", "#172033")], foreground=[("disabled", "#71829B")])
style.configure("Danger.TButton", background="#642C38", foreground="#FFD9D5", padding=(15, 9), font=("Segoe UI", 10), borderwidth=0)
style.map("Danger.TButton", background=[("active", "#8E3B4A"), ("disabled", "#242433")], foreground=[("disabled", "#71829B")])
style.configure("Green.Horizontal.TProgressbar", troughcolor=COLORS["panel_alt"], background=COLORS["green"], lightcolor=COLORS["green"], darkcolor=COLORS["green"], bordercolor=COLORS["border"])
style.configure("Modern.Treeview", background=COLORS["panel_alt"], fieldbackground=COLORS["panel_alt"], foreground=COLORS["text"], rowheight=34, borderwidth=0, font=("Segoe UI", 10))
style.configure("Modern.Treeview.Heading", background=COLORS["border"], foreground=COLORS["text"], font=("Segoe UI", 9, "bold"), relief="flat", padding=8)
style.map(
    "Modern.Treeview.Heading",
    background=[("active", COLORS["border"]), ("pressed", COLORS["border"])],
    foreground=[("active", COLORS["text"]), ("pressed", COLORS["text"])],
)
style.map("Modern.Treeview", background=[("selected", COLORS["blue_dark"])], foreground=[("selected", "white")])

container = ttk.Frame(root, style="App.TFrame", padding=(22, 18, 22, 16))
container.pack(fill=tk.BOTH, expand=True)
ttk.Label(container, text="SUPER NOVA RECOVERY", style="Title.TLabel").pack(anchor="w")
ttk.Label(container, text="Créez une clé de récupération Windows en quelques étapes.", style="Subtitle.TLabel").pack(anchor="w", pady=(3, 20))

iso_card = tk.Frame(container, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
iso_card.pack(fill=tk.X, pady=(0, 10))
iso_inner = tk.Frame(iso_card, bg=COLORS["panel"])
iso_inner.pack(fill=tk.X, padx=18, pady=13)
tk.Label(iso_inner, text="●", fg=COLORS["green"] if ISO.is_file() else COLORS["red"], bg=COLORS["panel"], font=("Segoe UI", 13)).pack(side=tk.LEFT, padx=(0, 10))
tk.Label(iso_inner, text="Image ISO", fg=COLORS["text"], bg=COLORS["panel"], font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
tk.Label(iso_inner, text="trouvée" if ISO.is_file() else "introuvable", fg=COLORS["green"] if ISO.is_file() else COLORS["red"], bg=COLORS["panel"], font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT)
iso_details = tk.Label(
    iso_card,
    text=(
        f"Taille : {format_size(ISO.stat().st_size)}  •  FAT32 30 Go  •  UEFI / BIOS"
        if ISO.is_file()
        else "Aucune image ISO disponible"
    ),
    fg=COLORS["muted"],
    bg=COLORS["panel"],
    font=("Segoe UI", 8),
    anchor="w",
    justify="left",
    wraplength=820,
)
iso_details.pack(fill=tk.X, padx=48, pady=(0, 5))
iso_hash_label = tk.Label(
    iso_card,
    text="SHA-256 : calcul en cours…" if ISO.is_file() else "SHA-256 : indisponible",
    fg=COLORS["muted"],
    bg=COLORS["panel"],
    font=("Segoe UI", 8),
    anchor="w",
)
iso_hash_label.pack(fill=tk.X, padx=48, pady=(0, 12))

usb_card = tk.Frame(container, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
usb_card.pack(fill=tk.X)
usb_header = tk.Frame(usb_card, bg=COLORS["panel"])
usb_header.pack(fill=tk.X, padx=18, pady=(15, 10))
ttk.Label(usb_header, text="1  Sélectionnez votre clé USB", style="PanelTitle.TLabel").pack(anchor="w")
ttk.Label(usb_header, text="Toutes les données de la clé sélectionnée seront effacées.", style="PanelText.TLabel").pack(anchor="w", pady=(3, 0))

table_frame = tk.Frame(usb_card, bg=COLORS["panel"])
table_frame.pack(fill=tk.X, padx=18, pady=(0, 12))
table_frame.configure(height=160)
table_frame.pack_propagate(False)
drive_tree = ttk.Treeview(table_frame, columns=("model", "size", "device"), show="headings", selectmode="browse", height=4, style="Modern.Treeview")
drive_tree.heading("model", text="PÉRIPHÉRIQUE")
drive_tree.heading("size", text="TAILLE")
drive_tree.heading("device", text="IDENTIFIANT")
drive_tree.column("model", width=280, anchor="w")
drive_tree.column("size", width=110, anchor="center")
drive_tree.column("device", width=270, anchor="w")
drive_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=drive_tree.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
drive_tree.configure(yscrollcommand=scrollbar.set)

controls = ttk.Frame(container, style="App.TFrame")
controls.pack(fill=tk.X, pady=(12, 9))
refresh_button = ttk.Button(controls, text="Actualiser", style="Secondary.TButton")
refresh_button.pack(side=tk.LEFT)
create_button = ttk.Button(controls, text="Créer la clé", style="Primary.TButton")
create_button.pack(side=tk.RIGHT)
cancel_button = ttk.Button(controls, text="Annuler", style="Danger.TButton", state=tk.DISABLED)
cancel_button.pack(side=tk.RIGHT, padx=(0, 10))
close_button = ttk.Button(controls, text="Fermer", style="Secondary.TButton", command=root.destroy)
close_button.pack(side=tk.RIGHT, padx=(0, 10))

status_label = ttk.Label(container, text="Prêt — sélectionnez une clé USB pour commencer.", style="Status.TLabel")
status_label.pack(anchor="w", pady=(0, 5))
progress_track = tk.Frame(container, bg=COLORS["panel_alt"], height=16, highlightbackground=COLORS["border"], highlightthickness=1)
progress_track.pack(fill=tk.X)
progress_track.pack_propagate(False)
progress_fill = tk.Frame(progress_track, bg=COLORS["green"], height=14)
progress_fill.place(x=0, y=0, relheight=1, width=0)
tk.Label(container, text="SUPER NOVA fonctionne hors ligne. Vérifiez attentivement le périphérique sélectionné.", fg=COLORS["muted"], bg=COLORS["bg"], font=("Segoe UI", 8)).pack(anchor="w", pady=(8, 0))

drive_items: list[tuple[str, str, int]] = []
cancel_event = threading.Event()
operation_running = False


def set_progress(value: float) -> None:
    value = max(0.0, min(1.0, value))
    progress_fill.place_configure(relwidth=value)


def refresh() -> None:
    """Refresh USB devices without blocking the Tkinter event loop."""
    refresh_button.config(state=tk.DISABLED)
    status_label.config(text="Détection des clés USB…")
    threading.Thread(target=refresh_worker, daemon=True).start()


def refresh_worker() -> None:
    try:
        drives = usb_drives()
    except Exception as error:
        root.after(0, refresh_error, error)
        return
    root.after(0, apply_drive_items, drives)


def refresh_error(error: Exception) -> None:
    refresh_button.config(state=tk.NORMAL)
    status_label.config(text="Impossible de détecter les clés USB.")
    messagebox.showerror("Détection USB", str(error))


def apply_drive_items(drives: list[tuple[str, str, int]]) -> None:
    global drive_items
    drive_items = drives
    for item in drive_tree.get_children():
        drive_tree.delete(item)
    for index, (device, model, size) in enumerate(drive_items):
        drive_tree.insert("", tk.END, iid=str(index), values=(model, format_size(size), device))
    if not drive_items:
        drive_tree.insert("", tk.END, iid="empty", values=("Aucune clé USB détectée", "—", "—"))
        status_label.config(text="Aucune clé USB détectée.")
    else:
        status_label.config(text=f"{len(drive_items)} clé(s) USB détectée(s). Sélectionnez-en une.")
    refresh_button.config(state=tk.NORMAL)


def load_iso_hash() -> None:
    if not ISO.is_file():
        return
    try:
        digest = sha256_file(ISO)
        root.after(0, iso_hash_label.config, {"text": f"SHA-256 : {digest}"})
    except OSError as error:
        root.after(0, iso_hash_label.config, {"text": f"SHA-256 : erreur ({error})"})


def cancel_operation() -> None:
    if operation_running:
        cancel_event.set()
        cancel_button.config(state=tk.DISABLED)
        status_label.config(text="Annulation en cours…")


def create_usb() -> None:
    global operation_running
    if not is_admin():
        messagebox.showwarning(
            "Droits administrateur requis",
            "Lancez recovery_manager.py dans un terminal administrateur avant de créer une clé USB.",
        )
        return
    selection = drive_tree.selection()
    if not selection or selection[0] == "empty":
        messagebox.showwarning("Sélection requise", "Sélectionnez une clé USB détectée.")
        return
    index = int(selection[0])
    if index >= len(drive_items):
        messagebox.showwarning("Sélection invalide", "Actualisez la liste des clés USB.")
        return
    device, model, size = drive_items[index]
    if not ISO.is_file():
        messagebox.showerror("ISO introuvable", str(ISO))
        return
    if not messagebox.askyesno("Attention", f"Toutes les données de {model} ({format_size(size)}) seront supprimées. Continuer ?"):
        return
    if not messagebox.askyesno("Confirmation finale", f"Formater {device} et créer la clé WinPE ?"):
        return

    operation_running = True
    cancel_event.clear()
    refresh_button.config(state=tk.DISABLED)
    create_button.config(state=tk.DISABLED)
    cancel_button.config(state=tk.NORMAL)
    close_button.config(state=tk.DISABLED)
    set_progress(0)
    status_label.config(text="Préparation…")
    threading.Thread(target=worker, args=(device,), daemon=True).start()


def worker(device: str) -> None:
    global operation_running
    try:
        prepare_usb(
            device,
            lambda text: root.after(0, status_label.config, {"text": text}),
            lambda value: root.after(0, set_progress, value),
            cancel_event,
        )
    except OperationCancelled as error:
        root.after(0, status_label.config, {"text": "Opération annulée"})
        root.after(0, messagebox.showinfo, "Opération annulée", str(error))
    except Exception as error:
        root.after(0, status_label.config, {"text": "Échec de la création"})
        root.after(0, messagebox.showerror, "Échec", str(error))
    else:
        root.after(0, status_label.config, {"text": "Clé créée avec succès"})
        root.after(0, set_progress, 1.0)
        root.after(0, messagebox.showinfo, "Succès", "La clé WinPE a été créée avec succès.")
    finally:
        operation_running = False
        root.after(0, refresh_button.config, {"state": tk.NORMAL})
        root.after(0, create_button.config, {"state": tk.NORMAL})
        root.after(0, cancel_button.config, {"state": tk.DISABLED})
        root.after(0, close_button.config, {"state": tk.NORMAL})


refresh_button.config(command=refresh)
create_button.config(command=create_usb)
cancel_button.config(command=cancel_operation)
root.after(100, refresh)
if ISO.is_file():
    root.after(100, lambda: threading.Thread(target=load_iso_hash, daemon=True).start())
root.mainloop()
