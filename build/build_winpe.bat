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
set PROJECT=%~dp0..
set OUTPUT=%PROJECT%output

echo.
echo ══════════════════════════════════════
echo  SUPER NOVA RECOVERY — Build WinPE
echo ══════════════════════════════════════
echo.

REM ── Étape 1 : Nettoyer le workspace précédent ──────────────────────────────
if exist "%WORKSPACE%" (
    echo [1/7] Nettoyage du workspace precedent...
    rmdir /s /q "%WORKSPACE%"
)

REM ── Étape 2 : Créer le workspace WinPE ────────────────────────────────────
echo [2/7] Creation du workspace WinPE...
copype amd64 "%WORKSPACE%"
if errorlevel 1 (
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
mkdir "%MOUNT%\SuperNova"
copy /Y "%PROJECT%recovery.hta" "%MOUNT%\SuperNova\"
copy /Y "%PROJECT%recovery.bat" "%MOUNT%\SuperNova\"
if exist "%PROJECT%assets\supernova.ico" (
    copy /Y "%PROJECT%assets\supernova.ico" "%MOUNT%\SuperNova\"
)

REM ── Étape 5 : Configurer le démarrage automatique ─────────────────────────
echo [5/7] Configuration du demarrage automatique...
copy /Y "%PROJECT%build\winpeshl.ini" "%MOUNT%\Windows\System32\winpeshl.ini"

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

REM ── Étape 8 : Créer le ZIP final ──────────────────────────────────────────
echo.
echo Creation du ZIP final...
if not exist "%OUTPUT%" mkdir "%OUTPUT%"
if exist "%OUTPUT%\SUPER_NOVA_RECOVERY.zip" del "%OUTPUT%\SUPER_NOVA_RECOVERY.zip"

powershell -Command "Compress-Archive -Path 'C:\WinPE_SuperNova\media\*' -DestinationPath '%OUTPUT%\SUPER_NOVA_RECOVERY.zip'"
if errorlevel 1 (
    echo ERREUR : Impossible de creer le ZIP.
    goto :EOF
)

echo.
echo ══════════════════════════════════════
echo  Build termine avec succes !
echo  Livrable : %OUTPUT%\SUPER_NOVA_RECOVERY.zip
echo ══════════════════════════════════════
echo.

endlocal
pause
