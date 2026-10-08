@echo off
REM ============================================================
REM  Forest Runner Adventure - Windows build script
REM  Builds a standalone single-file EXE with PyInstaller.
REM  Output: dist\ForestRunAdventure.exe
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo   Forest Runner Adventure - Windows EXE Builder
echo ============================================================
echo.

REM ---- 1. Locate Python --------------------------------------
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    echo [ERROR] Python was not found on PATH.
    echo Install Python 3.8+ from https://www.python.org/downloads/
    echo ^(tick "Add Python to PATH" during install^).
    goto :end
)
echo Using Python: %PY%
%PY% --version
echo.

REM ---- 2. Install build tooling ------------------------------
echo Installing PyInstaller...
%PY% -m pip install --upgrade pip >nul 2>nul
%PY% -m pip install "pyinstaller>=6.0"
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    goto :end
)
echo.

REM ---- 3. Clean previous builds ------------------------------
echo Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ForestRunAdventure.spec del /q ForestRunAdventure.spec
echo.

REM ---- 4. Build the EXE --------------------------------------
echo Building executable (this can take a minute or two)...
%PY% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --name "ForestRunAdventure" ^
    --collect-submodules tkinter ^
    forest_run_adventure.py
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    goto :end
)
echo.

REM ---- 5. Verify the output ----------------------------------
set "EXE=dist\ForestRunAdventure.exe"
if not exist "%EXE%" (
    echo [ERROR] Build finished but %EXE% was not found.
    goto :end
)
for %%I in ("%EXE%") do echo SUCCESS: Built %EXE% ^(%%~zI bytes^)
echo.

REM ---- 6. Offer to test-run ----------------------------------
set /p "RUN=Launch the game now to test? [y/N]: "
if /i "!RUN!"=="y" start "" "%EXE%"

:end
echo.
echo Done.
endlocal
pause
