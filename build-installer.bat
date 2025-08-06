@echo off
REM Build script for Ben's Accessibility Software
REM Creates both standalone executable and full installer

echo.
echo ========================================
echo  Ben's Accessibility Software Builder
echo ========================================
echo.

REM Note: This build script does not require administrator privileges
REM Only the final installer and application itself need admin rights

REM Change to project root
cd /d "%~dp0"

REM Check if UV is available
uv --version >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ UV package manager not found.
    echo Please install UV from https://docs.astral.sh/uv/
    pause
    exit /b 1
)

echo 📦 Installing dependencies...
uv sync --all-extras
if %errorLevel% neq 0 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo 🔧 Installing PyInstaller...
uv add pyinstaller
if %errorLevel% neq 0 (
    echo ❌ Failed to install PyInstaller
    pause
    exit /b 1
)

echo 🏗️ Building standalone executable...
uv run python build/build.py
if %errorLevel% neq 0 (
    echo ❌ Failed to build executable
    pause
    exit /b 1
)

REM Check if executable was created
if not exist "dist\BensAccessibilitySoftware.exe" (
    echo ❌ Executable not found in dist directory
    pause
    exit /b 1
)

echo ✅ Standalone executable built successfully!

REM Check if NSIS is available for full installer
makensis /VERSION >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ⚠️ NSIS not found. Full installer will not be built.
    echo To build the full installer, install NSIS from:
    echo https://nsis.sourceforge.io/Download
    echo.
    echo 📦 Standalone executable is ready: dist\BensAccessibilitySoftware.exe
    goto :summary
)

echo 📦 Building full installer with NSIS...
cd build
makensis installer.nsi
if %errorLevel% neq 0 (
    echo ❌ Failed to build installer
    cd ..
    pause
    exit /b 1
)
cd ..

REM Check if installer was created
if not exist "build\BensAccessibilitySoftware-Setup.exe" (
    echo ❌ Installer not found
    pause
    exit /b 1
)

echo ✅ Full installer built successfully!

:summary
echo.
echo 🎉 Build completed successfully!
echo.
echo 📁 Output files:
if exist "dist\BensAccessibilitySoftware.exe" (
    for %%F in ("dist\BensAccessibilitySoftware.exe") do (
        set /a exe_size=%%~zF/1024/1024
    )
    echo    📄 Standalone executable: dist\BensAccessibilitySoftware.exe [%exe_size% MB]
    echo       - Run directly, no installation required
    echo       - Requires administrator privileges
)

if exist "build\BensAccessibilitySoftware-Setup.exe" (
    for %%F in ("build\BensAccessibilitySoftware-Setup.exe") do (
        set /a installer_size=%%~zF/1024/1024
    )
    echo    📦 Full installer: build\BensAccessibilitySoftware-Setup.exe [%installer_size% MB]
    echo       - Creates Start Menu shortcuts and desktop shortcut
    echo       - Adds to Add/Remove Programs
    echo       - Requires administrator privileges for installation
)

echo.
echo ✅ Ready for distribution!
echo.
pause
