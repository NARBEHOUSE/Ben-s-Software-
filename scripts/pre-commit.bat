@echo off
REM © 2025 NARBE House – Licensed under CC BY-NC 4.0
REM Pre-commit script for Ben's Accessibility Software (Windows)
REM Runs code formatting, linting, and tests before committing

echo 🚀 Running pre-commit checks...
echo ================================

REM Check if we're in a UV project
if not exist "pyproject.toml" (
    echo ❌ Error: Not in a UV project directory (no pyproject.toml found)
    exit /b 1
)

REM Format code with Black
echo 🎨 Formatting code with Black...
uv run black .
if errorlevel 1 (
    echo ❌ Black formatting failed
    exit /b 1
)
echo ✅ Black formatting completed

REM Lint and fix with Ruff
echo 🔍 Linting code with Ruff...
uv run ruff check --fix
if errorlevel 1 (
    echo ⚠️ Ruff found issues that need manual fixing
    echo Run 'uv run ruff check' to see remaining issues
) else (
    echo ✅ Ruff linting completed
)

REM Run tests
echo 🧪 Running tests...
uv run pytest --tb=short -q
if errorlevel 1 (
    echo ❌ Tests failed
    exit /b 1
)
echo ✅ All tests passed

REM Type checking (optional - don't fail on type errors for now)
echo 🔍 Running type checks...
uv run mypy . --ignore-missing-imports --no-strict-optional
if errorlevel 1 (
    echo ⚠️ Type checking found issues (not blocking commit)
) else (
    echo ✅ Type checking passed
)

echo.
echo 🎉 Pre-commit checks completed successfully!
echo Your code is ready to commit.

pause
