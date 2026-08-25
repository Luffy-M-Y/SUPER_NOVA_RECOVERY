# 🔑 SUPER NOVA — Clé USB Bootable WinPE : Résumé Complet

## C'est quoi WinPE ?

**Windows PE (Preinstallation Environment)** = un mini-Windows (~500 Mo) qui démarre directement depuis une clé USB, **sans avoir besoin du Windows installé sur le disque dur**.

C'est exactement ce qu'utilisent :
- Les installateurs Windows (quand tu boot sur la clé USB d'installation)
- Hiren's Boot CD
- Les techniciens IT pour réparer des PC

**Pourquoi c'est la solution parfaite pour toi** : Au lieu de demander à l'utilisateur de naviguer dans WinRE, taper des commandes, appuyer 5x Shift, etc. → il branche la clé, boot dessus, et **tout se fait automatiquement**.

---

## Le flux utilisateur idéal (ce que tu veux atteindre)

```
1. L'utilisateur ouvre SUPER NOVA sur un PC fonctionnel
2. Il branche une clé USB
3. Il clique "CRÉER CLÉ DE RÉCUPÉRATION"
4. SUPER NOVA crée la clé bootable WinPE automatiquement
5. L'utilisateur branche la clé sur le PC bloqué
6. Il boot dessus (F12 / F2 au démarrage)
7. Un mini-Windows démarre avec une interface SUPER NOVA
8. L'interface liste les comptes Windows trouvés sur le disque
9. L'utilisateur sélectionne le compte à réinitialiser
10. Clic sur "RÉINITIALISER" → le mot de passe est supprimé
11. L'utilisateur redémarre → il peut se connecter sans mot de passe
```

**Zéro commande à taper. Zéro manipulation manuelle. Zéro connaissance technique requise.**

---

## Prérequis pour construire ça

### Outils nécessaires

| Outil | Taille | Rôle |
|-------|--------|------|
| **Windows ADK** (Assessment and Deployment Kit) | ~2 Go | Fournit les outils pour créer des images WinPE |
| **WinPE Add-on** pour l'ADK | ~5 Go | Contient les fichiers de base de WinPE (le mini-Windows) |
| **oscdimg.exe** (inclus dans ADK) | — | Crée l'image ISO bootable |

> [!NOTE]
> L'ADK est gratuit, fourni par Microsoft.
> Téléchargement : https://learn.microsoft.com/en-us/windows-hardware/get-started/adk-install

### Sur la machine de développement (ton PC)
- Windows 10/11 (64-bit)
- ~10 Go d'espace disque libre pour l'ADK + le workspace WinPE
- Droits administrateur
- Une clé USB d'au moins **2 Go**

---

## Architecture technique

### Comment ça marche sous le capot

```
CLÉ USB BOOTABLE
│
├── Boot/                        ← Fichiers de boot UEFI/BIOS
├── EFI/                         ← Boot UEFI (Secure Boot)
├── sources/
│   └── boot.wim                 ← L'image WinPE (le mini-Windows compressé)
│       │
│       └── Contenu monté :
│           ├── Windows/System32/ ← Mini-Windows fonctionnel
│           ├── SuperNova/
│           │   ├── recovery.bat  ← Script principal de réinitialisation
│           │   ├── recovery.hta  ← Interface graphique (HTML Application)
│           │   └── tools/        ← Utilitaires additionnels
│           └── winpeshl.ini      ← Fichier de démarrage auto (lance recovery.hta)
```

### Le fichier clé : `winpeshl.ini`

Ce fichier dit à WinPE **quoi lancer au démarrage** (au lieu du cmd.exe par défaut) :

```ini
[LaunchApps]
%SYSTEMDRIVE%\SuperNova\recovery.hta
```

→ Au boot, WinPE lance directement ton interface graphique au lieu d'une console noire.

---

## Les 3 approches possibles

### Approche A — Script BAT simple (facile)

WinPE démarre → lance un script `.bat` interactif dans la console :
- Liste les comptes Windows du disque
- L'utilisateur tape le numéro du compte
- Le script reset le mot de passe

**Avantages** : Simple à coder, léger
**Inconvénients** : Interface en mode texte (pas très SUPER NOVA 😄)

### Approche B — Interface HTA (recommandé) ⭐

WinPE démarre → lance un fichier `.hta` (HTML Application) :
- C'est du **HTML + CSS + JavaScript** qui tourne comme une app native Windows
- Tu peux réutiliser le style de SUPER NOVA (thème sombre, couleurs bleues)
- L'utilisateur a une vraie interface graphique avec des boutons

**Avantages** : Belle interface, utilise tes compétences HTML/JS existantes, natif Windows (pas besoin de Python)
**Inconvénients** : HTA utilise le moteur IE (vieux), mais suffisant pour une UI simple

> [!TIP]
> **HTA = le meilleur compromis.** C'est exactement du HTML/CSS/JS comme tu sais faire, mais ça tourne comme un `.exe` natif Windows. Pas besoin d'installer Python, Flask, ou quoi que ce soit dans WinPE.

### Approche C — Intégration Python dans WinPE (complexe)

Embarquer Python + Flask dans l'image WinPE et lancer la vraie app SUPER NOVA.

**Avantages** : Interface identique à l'app principale
**Inconvénients** : Image WinPE très lourde (~1-2 Go), complexe à maintenir, overkill

---

## Processus de création de l'image WinPE — Pas à pas

### Étape 1 : Installer l'ADK

```powershell
# Télécharger et installer l'ADK (interface graphique)
# Cocher uniquement : "Deployment Tools"
# Puis installer le WinPE Add-on séparément
```

### Étape 2 : Créer l'espace de travail WinPE

```powershell
# Ouvrir "Deployment and Imaging Tools Environment" (en admin)
# Créer un workspace WinPE
copype amd64 C:\WinPE_SuperNova
```

Cela crée :
```
C:\WinPE_SuperNova\
├── fwfiles/          ← Fichiers firmware
├── media/            ← Ce qui sera sur la clé USB
│   ├── Boot/
│   ├── EFI/
│   └── sources/
│       └── boot.wim  ← L'image WinPE à personnaliser
└── mount/            ← Point de montage pour modifier l'image
```

### Étape 3 : Monter l'image pour la personnaliser

```powershell
# Monter boot.wim pour pouvoir y ajouter des fichiers
Dism /Mount-Image /ImageFile:"C:\WinPE_SuperNova\media\sources\boot.wim" /Index:1 /MountDir:"C:\WinPE_SuperNova\mount"
```

### Étape 4 : Ajouter tes fichiers SUPER NOVA

```powershell
# Créer le dossier SuperNova dans l'image montée
mkdir "C:\WinPE_SuperNova\mount\SuperNova"

# Copier tes scripts/interface
copy recovery.hta "C:\WinPE_SuperNova\mount\SuperNova\"
copy recovery.bat "C:\WinPE_SuperNova\mount\SuperNova\"
```

### Étape 5 : Configurer le démarrage automatique

```powershell
# Créer winpeshl.ini pour lancer ton interface au boot
echo [LaunchApps] > "C:\WinPE_SuperNova\mount\Windows\System32\winpeshl.ini"
echo %SYSTEMDRIVE%\SuperNova\recovery.hta >> "C:\WinPE_SuperNova\mount\Windows\System32\winpeshl.ini"
```

### Étape 6 : Ajouter le support clavier français (optionnel)

```powershell
Dism /Image:"C:\WinPE_SuperNova\mount" /Set-InputLocale:fr-FR
Dism /Image:"C:\WinPE_SuperNova\mount" /Set-UILang:fr-FR
```

### Étape 7 : Démonter et sauvegarder l'image

```powershell
Dism /Unmount-Image /MountDir:"C:\WinPE_SuperNova\mount" /Commit
```

### Étape 8 : Créer la clé USB bootable

```powershell
# Méthode avec MakeWinPEMedia (inclus dans l'ADK)
MakeWinPEMedia /UFD C:\WinPE_SuperNova E:

# OU créer une ISO (pour tester dans une VM d'abord)
MakeWinPEMedia /ISO C:\WinPE_SuperNova C:\WinPE_SuperNova\SuperNova_Recovery.iso
```

---

## Le script de réinitialisation — Ce qu'il doit faire dans WinPE

### Logique principale (ce que ferait `recovery.bat` ou `recovery.hta`)

```bat
@echo off
REM ══════════════════════════════════════
REM  SUPER NOVA RECOVERY — Script WinPE
REM ══════════════════════════════════════

REM 1. Trouver la partition Windows
for %%d in (C D E F G H) do (
    if exist "%%d:\Windows\System32\config\SAM" (
        set WINDRIVE=%%d
        goto :FOUND
    )
)
echo Partition Windows non trouvée.
goto :EOF

:FOUND
echo Windows trouvé sur %WINDRIVE%:\

REM 2. Charger le registre SAM (base de données des comptes)
reg load HKLM\OFFLINE_SAM "%WINDRIVE%:\Windows\System32\config\SAM"

REM 3. Lister les comptes utilisateurs
reg query "HKLM\OFFLINE_SAM\SAM\Domains\Account\Users\Names"

REM 4. Activer le compte Admin intégré (RID 500)
REM    Modifier la valeur "F" dans le registre pour activer le compte
REM    Le byte à l'offset 0x38 : 0x11 = désactivé, 0x10 = activé

REM 5. Décharger le registre
reg unload HKLM\OFFLINE_SAM

REM 6. Modifier sethc.exe → cmd.exe (méthode alternative)
ren "%WINDRIVE%:\Windows\System32\sethc.exe" sethcold.exe
copy "%WINDRIVE%:\Windows\System32\cmd.exe" "%WINDRIVE%:\Windows\System32\sethc.exe"

REM 7. Informer l'utilisateur
echo.
echo Opération terminée !
echo Retirez la clé USB et redémarrez.
echo Sur l'écran de login, le compte Administrateur sera disponible.
```

### Méthode avancée : Reset direct via le registre SAM (sans passer par sethc.exe)

> [!TIP]
> **La vraie méthode pro** : Au lieu de remplacer `sethc.exe` et de passer par un compte Admin intermédiaire, on peut directement **modifier la base de registre SAM** pour supprimer le mot de passe d'un compte. C'est ce que font les outils comme `chntpw` (Linux) ou `NTPWEdit`.

Le registre SAM (`C:\Windows\System32\config\SAM`) contient les hash des mots de passe. En le chargeant hors-ligne depuis WinPE, on peut :
1. Lister les comptes
2. Supprimer le hash du mot de passe d'un compte spécifique
3. L'utilisateur redémarre → le compte n'a plus de mot de passe

**C'est plus propre** car :
- Pas besoin de toucher à `sethc.exe`
- Pas besoin d'activer le compte Admin caché
- Pas besoin de nettoyage après
- Une seule étape au lieu de 3

Pour manipuler le SAM directement, tu aurais besoin d'un outil comme :
- **`chntpw`** (portage Windows) — outil open source qui sait lire/modifier le SAM
- **Écriture Python avec la lib `python-registry`** — lecture/écriture du registre offline
- **Manipulation directe en HTA via WScript.Shell** + `reg load` / `reg` commands

---

## L'interface HTA (recommandée) — Exemple de structure

```html
<!DOCTYPE html>
<html>
<head>
    <title>SUPER NOVA Recovery</title>
    <HTA:APPLICATION
        ID="SuperNovaRecovery"
        APPLICATIONNAME="SuperNovaRecovery"
        BORDER="thin"
        BORDERSTYLE="normal"
        CAPTION="yes"
        ICON="supernova.ico"
        MAXIMIZEBUTTON="no"
        MINIMIZEBUTTON="no"
        SHOWINTASKBAR="yes"
        SINGLEINSTANCE="yes"
        SYSMENU="yes"
        WINDOWSTATE="normal"
    />
    <style>
        /* Même thème sombre que SUPER NOVA */
        body { background: #0a0e1a; color: #e0e0e0; font-family: 'Segoe UI'; }
        /* ... ton CSS ... */
    </style>
</head>
<body>
    <h1>🔑 SUPER NOVA RECOVERY</h1>

    <!-- Liste des comptes détectés -->
    <div id="accounts-list"></div>

    <!-- Bouton reset -->
    <button onclick="resetPassword()">RÉINITIALISER</button>

    <script language="VBScript">
        ' VBScript pour exécuter des commandes système
        Sub resetPassword()
            Set shell = CreateObject("WScript.Shell")
            ' ... logique de reset ...
        End Sub
    </script>

    <script language="JavaScript">
        // JavaScript pour l'UI dynamique
        // ... logique d'affichage ...
    </script>
</body>
</html>
```

> [!NOTE]
> HTA supporte **VBScript** (pour les commandes système comme `WScript.Shell`) ET **JavaScript** (pour l'UI). Tu peux mixer les deux dans le même fichier.

---

## Intégration dans SUPER NOVA — Comment l'app génère la clé

L'idée finale dans ton app SUPER NOVA :

### Ce que l'app doit faire (backend Python)

```
1. Vérifier que l'ADK est installé (ou embarquer les fichiers WinPE pré-construits)
2. Détecter la clé USB branchée
3. Formater la clé USB (après confirmation utilisateur)
4. Copier l'image WinPE pré-configurée sur la clé
5. Rendre la clé bootable
```

### Option la plus réaliste : Embarquer une image WinPE pré-construite

Au lieu de demander à l'utilisateur d'installer l'ADK, tu peux :

1. **Toi, sur ton PC de dev** : créer l'image WinPE une seule fois avec l'ADK
2. **Compresser** le contenu de `media/` en `.zip` (~300 Mo)
3. **L'embarquer** dans l'installateur SUPER NOVA ou le proposer en téléchargement séparé
4. **L'app** n'a plus qu'à extraire le `.zip` sur la clé USB et la rendre bootable

```python
# Pseudo-code backend
@app.route('/create_recovery_usb', methods=['POST'])
def create_recovery_usb():
    drive = request.json['drive']  # ex: "E:"
    
    # 1. Extraire l'image WinPE pré-construite sur la clé
    shutil.unpack_archive('winpe_supernova.zip', drive + '\\')
    
    # 2. Rendre la clé bootable (bootsect.exe)
    subprocess.run(['bootsect', '/nt60', drive, '/mbr'])
    
    return jsonify({"success": True})
```

---

## Limitations à connaître

| Limitation | Impact | Contournement |
|-----------|--------|---------------|
| **BitLocker** | Si le disque est chiffré, WinPE ne peut pas lire les fichiers | L'utilisateur doit fournir la clé de récupération BitLocker |
| **Comptes Microsoft** | Le mot de passe est stocké en ligne, pas dans le SAM local | Afficher un message : "Utilisez account.live.com" |
| **UEFI Secure Boot** | Certains PC refusent de booter sur des clés non signées | L'image WinPE de Microsoft est signée, donc ça marche. Sinon, désactiver Secure Boot dans le BIOS |
| **BIOS vs UEFI** | Certains vieux PC utilisent le BIOS legacy | L'image WinPE créée avec l'ADK supporte les deux |
| **ARM** | Les PC Windows sur ARM (Surface Pro X, etc.) | Nécessite une image WinPE ARM64 séparée |
| **Taille de l'installateur** | L'image WinPE fait ~300-500 Mo | Proposer en téléchargement séparé plutôt qu'embarqué dans le .exe |

---

## Estimation de la complexité

| Tâche | Difficulté | Temps estimé |
|-------|-----------|-------------|
| Installer l'ADK et créer l'image WinPE de base | 🟢 Facile | 1-2h |
| Écrire le script de reset (BAT) | 🟢 Facile | 2-3h |
| Créer l'interface HTA avec le thème SUPER NOVA | 🟡 Moyen | 4-6h |
| Implémenter la manipulation directe du SAM | 🔴 Difficile | 8-12h |
| Intégrer la création de clé USB dans l'app Flask | 🟡 Moyen | 3-4h |
| Ajouter l'onglet RECOVERY dans l'UI | 🟢 Facile | 2-3h |
| Tests sur différentes configs (UEFI, BIOS, Win10, Win11) | 🟡 Moyen | 4-6h |
| **Total estimé** | | **~25-35h** |

---

## Idées d'améliorations futures

- 🔄 **Reset direct du SAM** sans passer par sethc.exe (méthode la plus propre)
- 🌍 **Multi-langue** dans l'interface HTA (FR/EN/ES comme ton app principale)
- 💾 **Backup du SAM** avant modification (sécurité)
- 📊 **Liste visuelle des comptes** avec infos (dernière connexion, admin ou pas, compte Microsoft ou local)
- 🔐 **Détection BitLocker** avec prompt pour la clé de récupération
- 🖥️ **Test en VM** : créer une ISO pour tester dans VirtualBox/Hyper-V avant de graver sur USB
