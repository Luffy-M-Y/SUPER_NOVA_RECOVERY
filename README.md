# SUPER NOVA RECOVERY

Environnement WinPE bootable pour réinitialiser un mot de passe de compte local Windows.

## Architecture

```
SUPER_NOVA_RECOVERY/
├── recovery.hta          ← Interface graphique + flux de réinitialisation (IFEO)
├── recovery.bat          ← Inerte (ancienne méthode sethc.exe, ne plus utiliser)
├── assets/
│   └── supernova.ico     ← Icône de l'application
├── build/
│   ├── build_winpe.bat   ← Construit l'image WinPE (nécessite ADK)
│   └── winpeshl.ini      ← Lance recovery.hta au démarrage WinPE
└── output/               ← Contient SUPER_NOVA_RECOVERY.zip (livrable final)
```

## Prérequis (Phase 4 — Build)

Installer dans cet ordre :
1. **Windows ADK** — cocher uniquement "Deployment Tools"
   https://learn.microsoft.com/en-us/windows-hardware/get-started/adk-install
2. **WinPE Add-on pour l'ADK** (lien sur la même page)

Espace requis : ~10 Go | Droits administrateur requis

## Méthode de réinitialisation

**Méthode IFEO (via `recovery.hta` uniquement)** :
1. WinPE démarre → `recovery.hta` se lance automatiquement (`winpeshl.ini`)
2. L'utilisateur choisit un compte et confirme
3. L'outil écrit les scripts sur la partition Windows et pose un Debugger IFEO sur `sethc.exe`
4. Après redémarrage, 5× Maj lance le script (SYSTEM) pour réinitialiser le mot de passe
5. Le script retire la clé IFEO et se supprime s'il va jusqu'au bout

`recovery.bat` n'est **pas** copié dans l'image WinPE. S'il est lancé à la main, il n'effectue **aucune** modification système (plus de remplacement de `sethc.exe` par `cmd.exe`).

## Limitations connues

| Cas | Comportement |
|-----|-------------|
| Compte Microsoft (@outlook, @hotmail) | ❌ Impossible — passer par account.live.com |
| Disque chiffré BitLocker | ⚠️ Nécessite la clé de récupération BitLocker |
| Compte Azure AD / Microsoft 365 | ❌ Impossible — contacter l'admin IT |
| Compte local | ✅ Fonctionne |

## Build

```bat
REM Ouvrir "Deployment and Imaging Tools Environment" en admin
cd build
build_winpe.bat
REM → Produit output/SUPER_NOVA_RECOVERY.zip
```

## Livrable

`output/SUPER_NOVA_RECOVERY.zip` = contenu du dossier `media\` WinPE.  
Ce fichier est extrait sur une clé USB FAT32 par l'application SUPER NOVA.
