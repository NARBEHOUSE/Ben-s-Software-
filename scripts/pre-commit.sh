#!/bin/bash
# © 2025 NARBE House – Licensed under CC BY-NC 4.0

# Pre-commit script for Ben's Accessibility Software
# Runs code formatting, linting, and tests before committing

set -e  # Exit on any error

echo "🚀 Running pre-commit checks..."
echo "================================"

# Check if we're in a UV project
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Not in a UV project directory (no pyproject.toml found)"
    exit 1
fi

# Format code with Black
echo "🎨 Formatting code with Black..."
uv run black .
if [ $? -eq 0 ]; then
    echo "✅ Black formatting completed"
else
    echo "❌ Black formatting failed"
    exit 1
fi

# Lint and fix with Ruff
echo "🔍 Linting code with Ruff..."
uv run ruff check --fix
if [ $? -eq 0 ]; then
    echo "✅ Ruff linting completed"
else
    echo "⚠️ Ruff found issues that need manual fixing"
    echo "Run 'uv run ruff check' to see remaining issues"
fi

# Run tests
echo "🧪 Running tests..."
if uv run pytest --tb=short -q; then
    echo "✅ All tests passed"
else
    echo "❌ Tests failed"
    exit 1
fi

# Type checking (optional - don't fail on type errors for now)
echo "🔍 Running type checks..."
if uv run mypy . --ignore-missing-imports --no-strict-optional; then
    echo "✅ Type checking passed"
else
    echo "⚠️ Type checking found issues (not blocking commit)"
fi

echo ""
echo "🎉 Pre-commit checks completed successfully!"
echo "Your code is ready to commit."
