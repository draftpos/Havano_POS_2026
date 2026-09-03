@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  Havano POS - Build Script
echo ============================================

REM --- Resolve qtawesome fonts path dynamically (avoids hardcoded venv paths) ---
for /f "delims=" %%i in ('python -c "import qtawesome, os; print(os.path.dirname(qtawesome.__file__))"') do set QTA_PATH=%%i

if "%QTA_PATH%"=="" (
    echo BUILD FAILED: could not resolve qtawesome install path. Is the venv active?
    exit /b 1
)

echo Using qtawesome fonts from: %QTA_PATH%\fonts

REM --- Clean previous build output so we never ship a stale/corrupt copy ---
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM --- Run PyInstaller ---
pyinstaller --noconfirm --onedir --windowed --icon "assets/havano_new_blue.ico" ^
  --add-data "assets;assets" ^
  --add-data "%QTA_PATH%\fonts;qtawesome/fonts" ^
  --exclude-module "pandas" --exclude-module "numpy" --exclude-module "matplotlib" ^
  --exclude-module "scipy" --exclude-module "tensorflow" --exclude-module "keras" ^
  --exclude-module "torch" --exclude-module "PySide6.QtWebEngineWidgets" ^
  --exclude-module "PySide6.QtWebEngineCore" --exclude-module "PySide6.QtQuick" ^
  --exclude-module "PySide6.QtQml" --exclude-module "PySide6.QtOpenGL" ^
  --exclude-module "PySide6.QtQuick3D" --exclude-module "PySide6.QtPdf" ^
  --exclude-module "IPython" --exclude-module "jupyter" ^
  --exclude-module "notebook" --exclude-module "cv2" ^
  --name "HavanoPOS" main.py

if errorlevel 1 (
    echo BUILD FAILED: PyInstaller returned an error.
    exit /b 1
)

REM --- Locate the bundled font file automatically (path can vary by PyInstaller version) ---
set FONT_CHECK=
for /f "delims=" %%f in ('dir /s /b "dist\HavanoPOS\fontawesome6-regular-webfont-6.7.2.ttf" 2^>nul') do set FONT_CHECK=%%f

if "%FONT_CHECK%"=="" (
    echo BUILD FAILED: qtawesome font not found anywhere in dist output!
    echo The --add-data flag may not be pointing at the right source path.
    exit /b 1
)

for %%A in ("%FONT_CHECK%") do set FONT_SIZE=%%~zA

if %FONT_SIZE% LSS 10000 (
    echo BUILD FAILED: qtawesome font is only %FONT_SIZE% bytes - looks empty or corrupt.
    echo File: %FONT_CHECK%
    exit /b 1
)

echo ----------------------------------------------
echo Font check passed: %FONT_SIZE% bytes
echo   %FONT_CHECK%
echo ----------------------------------------------
echo BUILD COMPLETE: dist\HavanoPOS
echo ============================================

endlocal
