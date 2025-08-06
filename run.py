#!/usr/bin/env python3
# © 2025 NARBE House – Licensed under CC BY-NC 4.0

"""Simple launcher script for Ben's Accessibility Software.

Provides easy access to main applications and utilities.
"""

from pathlib import Path
import subprocess
import sys
from typing import Dict, List, Optional

# Constants
MAIN_SCRIPT = "comm-v10.py"
KEYBOARD_SCRIPT = "keyboard/keyboard.py"


def main():
    """Main launcher with menu options."""
    print("🚀 Ben's Accessibility Software Launcher")
    print("=" * 50)
    print()
    print("Available Applications:")
    print("1. Main Communication Software (comm-v10.py)")
    print("2. Enhanced Keyboard Interface (keyboard/keyboard.py)")
    print("3. Test Predictive Text System (keyboard/test_predictive_enhanced.py)")
    print("4. Trivia Game (games/Trivia.py)")
    print("5. Tower Defense Game (games/towerdefense.py)")
    print("6. Word Jumble Game (games/wordjumble.py)")
    print("7. Exit")
    print()

    while True:
        try:
            choice = input("Select an option (1-7): ").strip()

            if choice == "1":
                print("🎯 Starting Main Communication Software...")
                run_script("comm-v10.py")
                break
            elif choice == "2":
                print("⌨️ Starting Enhanced Keyboard Interface...")
                run_script("keyboard/keyboard.py")
                break
            elif choice == "3":
                print("🧪 Running Predictive Text Tests...")
                run_script("keyboard/test_predictive_enhanced.py")
                break
            elif choice == "4":
                print("🧠 Starting Trivia Game...")
                run_script("games/Trivia.py")
                break
            elif choice == "5":
                print("🏰 Starting Tower Defense Game...")
                run_script("games/towerdefense.py")
                break
            elif choice == "6":
                print("🔤 Starting Word Jumble Game...")
                run_script("games/wordjumble.py")
                break
            elif choice == "7":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please select 1-7.")
                continue

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            continue


def run_script(script_path: str) -> None:
    """Run a Python script using the current Python interpreter.

    Args:
        script_path: Relative path to the Python script to execute

    Raises:
        Exception: If script execution fails
    """
    try:
        script_path_obj = Path(script_path)

        # Check if file exists
        if not script_path_obj.exists():
            print(f"❌ Error: {script_path} not found!")
            return

        # Run the script
        result = subprocess.run(
            [sys.executable, str(script_path_obj)],
            cwd=Path.cwd(),
            capture_output=False
        )

        if result.returncode != 0:
            print(f"⚠️ Script exited with code {result.returncode}")
        else:
            print("✅ Script completed successfully")

    except Exception as e:
        print(f"❌ Error running {script_path}: {e}")


def check_dependencies() -> bool:
    """Check if required dependencies are available.

    Attempts to import all critical dependencies and reports status.

    Returns:
        True if all dependencies are available, False otherwise
    """
    dependencies = [
        "pandas", "psutil", "pyautogui", "pygame",
        "pymunk", "pynput", "pyttsx3", "requests"
    ]

    missing = []
    for dep in dependencies:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)

    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print("💡 Run 'uv sync' to install all dependencies")
        return False
    else:
        print("✅ All dependencies are available")
        return True


if __name__ == "__main__":
    # Check if we're in the right directory
    if not Path(MAIN_SCRIPT).exists():
        print("❌ Error: Please run this script from the Ben-s-Software- directory")
        sys.exit(1)

    # Check dependencies
    if not check_dependencies():
        print("\n🔧 To install dependencies, run:")
        print("   uv sync")
        print("\nThen try running this launcher again.")
        sys.exit(1)

    main()
