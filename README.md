# SUPER NOVA RECOVERY

Environnement WinPE bootable pour réinitialiser un mot de passe de compte local Windows.

## Architecture

```
SUPER_NOVA_RECOVERY/
├── recovery.hta          ← Interface graphique (lancée au boot WinPE)
├── recovery.bat          ← Script de réinitialisation (sethc.exe method)
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

**Méthode sethc.exe (Sticky Keys)** :
1. WinPE démarre → `recovery.hta` se lance automatiquement
2. L'utilisateur clique "RÉINITIALISER"
3. `recovery.bat` remplace `sethc.exe` par `cmd.exe` sur la partition Windows
4. L'utilisateur redémarre → sur l'écran de login, appuie 5x sur Maj
5. Un CMD s'ouvre avec les droits SYSTEM → `net user administrateur /active:yes`
6. Connexion avec le compte Admin → changer le mot de passe du compte bloqué
7. Nettoyage : remettre `sethc.exe` en place + désactiver le compte Admin

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
