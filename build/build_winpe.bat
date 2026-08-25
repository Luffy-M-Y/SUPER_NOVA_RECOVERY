@echo off
setlocal

REM ══════════════════════════════════════════════════════
REM  SUPER NOVA RECOVERY — Build WinPE
REM  Nécessite : Windows ADK + WinPE Add-on
REM  Lancer depuis "Deployment and Imaging Tools Environment" en admin
REM ══════════════════════════════════════════════════════

set WORKSPACE=C:\WinPE_SuperNova
set MOUNT=%WORKSPACE%\mount
set MEDIA=%WORKSPACE%\media
set PROJECT=%~dp0..\
set OUTPUT=%PROJECT%output

echo.
echo ══════════════════════════════════════
echo  SUPER NOVA RECOVERY — Build WinPE
echo ══════════════════════════════════════
echo.

REM ── Étape 1 : Nettoyer le workspace précédent ──────────────────────────────
if exist "%WORKSPACE%" (
    echo [1/7] Nettoyage du workspace precedent...
    Dism /Unmount-Image /MountDir:"%MOUNT%" /Discard >nul 2>&1
    rmdir /s /q "%WORKSPACE%"
)

REM ── Étape 2 : Créer le workspace WinPE ────────────────────────────────────
echo [2/7] Creation du workspace WinPE...
call copype amd64 "%WORKSPACE%"
if not exist "%MEDIA%\sources\boot.wim" (
    echo ERREUR : copype a echoue. Verifiez que l'ADK est installe.
    goto :EOF
)

REM ── Étape 3 : Monter l'image WinPE ────────────────────────────────────────
echo [3/7] Montage de l'image WinPE...
Dism /Mount-Image /ImageFile:"%MEDIA%\sources\boot.wim" /Index:1 /MountDir:"%MOUNT%"
if errorlevel 1 (
    echo ERREUR : Impossible de monter l'image.
    goto :EOF
)

REM ── Étape 4 : Copier les fichiers SUPER NOVA ──────────────────────────────
echo [4/7] Injection des fichiers SUPER NOVA...
Dism /Add-Package /Image:"%MOUNT%" /PackagePath:"%WINPEROOT%\amd64\WinPE_OCs\WinPE-HTA.cab"
if errorlevel 1 (
    echo ERREUR : Impossible d'ajouter WinPE-HTA.cab
    goto :EOF
)
Dism /Add-Package /Image:"%MOUNT%" /PackagePath:"%WINPEROOT%\amd64\WinPE_OCs\fr-fr\WinPE-HTA_fr-fr.cab"
if errorlevel 1 (
    echo ERREUR : Impossible d'ajouter WinPE-HTA_fr-fr.cab
    goto :EOF
)
Dism /Add-Package /Image:"%MOUNT%" /PackagePath:"%WINPEROOT%\amd64\WinPE_OCs\WinPE-Scripting.cab"
if errorlevel 1 (
    echo ERREUR : Impossible d'ajouter WinPE-Scripting.cab
    goto :EOF
)
Dism /Add-Package /Image:"%MOUNT%" /PackagePath:"%WINPEROOT%\amd64\WinPE_OCs\fr-fr\WinPE-Scripting_fr-fr.cab"
if errorlevel 1 (
    echo ERREUR : Impossible d'ajouter WinPE-Scripting_fr-fr.cab
    goto :EOF
)
mkdir "%MOUNT%\SuperNova"
copy /Y "%PROJECT%recovery.hta" "%MOUNT%\SuperNova\"
if errorlevel 1 (
    echo ERREUR : Impossible de copier recovery.hta
    goto :EOF
)
if not exist "%MOUNT%\SuperNova\recovery.hta" (
    echo ERREUR : recovery.hta absent de l'image.
    goto :EOF
)
if exist "%PROJECT%assets\SUPER_NOVA.ico" (
    copy /Y "%PROJECT%assets\SUPER_NOVA.ico" "%MOUNT%\SuperNova\"
)

REM ── Étape 5 : Configurer le démarrage automatique ─────────────────────────
echo [5/7] Configuration du demarrage automatique...
copy /Y "%PROJECT%build\winpeshl.ini" "%MOUNT%\Windows\System32\winpeshl.ini"
if errorlevel 1 (
    echo ERREUR : Impossible de copier winpeshl.ini
    goto :EOF
)

echo        Empreintes SHA256 des fichiers injectes :
certutil -hashfile "%MOUNT%\SuperNova\recovery.hta" SHA256
certutil -hashfile "%MOUNT%\Windows\System32\winpeshl.ini" SHA256
certutil -hashfile "%MOUNT%\SuperNova\recovery.hta" SHA256 > "%WORKSPACE%\SHA256.txt"
certutil -hashfile "%MOUNT%\Windows\System32\winpeshl.ini" SHA256 >> "%WORKSPACE%\SHA256.txt"

REM ── Étape 6 : Configurer le clavier français ──────────────────────────────
echo [6/7] Configuration du clavier francais...
Dism /Image:"%MOUNT%" /Set-InputLocale:fr-FR >nul 2>&1
Dism /Image:"%MOUNT%" /Set-UILang:fr-FR >nul 2>&1

REM ── Étape 7 : Démonter et sauvegarder ────────────────────────────────────
echo [7/7] Demontage et sauvegarde de l'image...
Dism /Unmount-Image /MountDir:"%MOUNT%" /Commit
if errorlevel 1 (
    echo ERREUR : Impossible de demonter l'image.
    goto :EOF
)

REM ── Étape 8 : Créer le ZIP + ISO ────────────────────────────────────────────
echo.
echo Creation des livrables...
if not exist "%OUTPUT%" mkdir "%OUTPUT%"
if exist "%WORKSPACE%\SHA256.txt" copy /Y "%WORKSPACE%\SHA256.txt" "%OUTPUT%\SHA256.txt" >nul

if exist "%OUTPUT%\SUPER_NOVA_RECOVERY.zip" del "%OUTPUT%\SUPER_NOVA_RECOVERY.zip"
powershell -Command "Compress-Archive -Path 'C:\WinPE_SuperNova\media\*' -DestinationPath '%OUTPUT%\SUPER_NOVA_RECOVERY.zip'"
if errorlevel 1 (
    echo ERREUR : Impossible de creer le ZIP.
    goto :EOF
)

if exist "%OUTPUT%\SUPER_NOVA_RECOVERY.iso" del "%OUTPUT%\SUPER_NOVA_RECOVERY.iso"
MakeWinPEMedia /ISO "%WORKSPACE%" "%OUTPUT%\SUPER_NOVA_RECOVERY.iso"
if errorlevel 1 (
    echo ERREUR : Impossible de creer l'ISO.
    goto :EOF
)

echo.
echo ══════════════════════════════════════
echo  Build termine avec succes !
echo  ZIP : %OUTPUT%\SUPER_NOVA_RECOVERY.zip
echo  ISO : %OUTPUT%\SUPER_NOVA_RECOVERY.iso
echo ══════════════════════════════════════
echo.

endlocal
pause
