#!/usr/bin/env python3
# © 2025 NARBE House – Licensed under CC BY-NC 4.0

"""
Simple launcher script for Ben's Accessibility Software.
Provides easy access to main applications and utilities.
"""

import os
import subprocess
import sys


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


def run_script(script_path):
    """Run a Python script using the current Python interpreter."""
    try:
        # Check if file exists
        if not os.path.exists(script_path):
            print(f"❌ Error: {script_path} not found!")
            return

        # Run the script
        result = subprocess.run(
            [sys.executable, script_path], cwd=os.getcwd(), capture_output=False
        )

        if result.returncode != 0:
            print(f"⚠️ Script exited with code {result.returncode}")
        else:
            print("✅ Script completed successfully")

    except Exception as e:
        print(f"❌ Error running {script_path}: {e}")


def check_dependencies():
    """Check if required dependencies are available."""
    try:
        import pandas
        import psutil
        import pyautogui
        import pygame
        import pymunk
        import pynput
        import pyttsx3
        import requests

        print("✅ All dependencies are available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("💡 Run 'uv sync' to install all dependencies")
        return False


if __name__ == "__main__":
    # Check if we're in the right directory
    if not os.path.exists("comm-v10.py"):
        print("❌ Error: Please run this script from the Ben-s-Software- directory")
        sys.exit(1)

    # Check dependencies
    if not check_dependencies():
        print("\n🔧 To install dependencies, run:")
        print("   uv sync")
        print("\nThen try running this launcher again.")
        sys.exit(1)

    main()
