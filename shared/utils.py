#!/usr/bin/env python3
# © 2025 NARBE House – Licensed under CC BY-NC 4.0

"""
Shared utilities module for Ben's Accessibility Software.
Consolidates duplicate functions across the codebase.
"""

from pathlib import Path
import queue
import subprocess
import sys
import threading

try:
    import tkinter as tk

    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

    # Create a dummy tk module for non-GUI environments
    class DummyTk:
        class Button:
            def __init__(self, *args, **kwargs):
                pass

            def pack(self, *args, **kwargs):
                pass

            def bind(self, *args, **kwargs):
                pass

        class Frame:
            def __init__(self, *args, **kwargs):
                pass

            def pack(self, *args, **kwargs):
                pass

    tk = DummyTk()

try:
    # Try to import py3-tts-wrapper (avoid local tts-wrapper directory)
    import importlib.util

    # Check if py3-tts-wrapper is installed in site-packages
    spec = importlib.util.find_spec("tts_wrapper")
    if spec and spec.origin and "site-packages" in spec.origin:
        from tts_wrapper import GoogleTransClient, SAPIClient, eSpeakClient

        TTS_WRAPPER_AVAILABLE = True
    else:
        raise ImportError("py3-tts-wrapper not found in site-packages")

except ImportError:
    # Fallback to pyttsx3 if py3-tts-wrapper is not available

    TTS_WRAPPER_AVAILABLE = False


# ------------------------------ #
#         TTS Management         #
# ------------------------------ #


class TTSManager:
    """Centralized Text-to-Speech manager with thread safety and multiple engine support."""

    def __init__(self):
        self.client = None
        self.queue = queue.Queue()
        self.lock = threading.Lock()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._initialize_client()
        self.worker_thread.start()

    def _initialize_client(self):
        """Initialize the best available TTS client."""
        # Try pyttsx3 first on Windows (most reliable)
        if sys.platform == "win32":
            try:
                import pyttsx3

                self.client = pyttsx3.init()
                print("✅ TTS: Using pyttsx3 (Windows)")
                return
            except Exception as e:
                print(f"⚠️ pyttsx3 initialization failed: {e}")

        if TTS_WRAPPER_AVAILABLE:
            try:
                # Try SAPI (Windows)
                if sys.platform == "win32":
                    self.client = SAPIClient()
                    print("✅ TTS: Using SAPI (Windows)")
                    return
            except Exception as e:
                print(f"⚠️ SAPI initialization failed: {e}")

            try:
                # Try eSpeak (cross-platform, offline)
                self.client = eSpeakClient()
                print("✅ TTS: Using eSpeak (offline)")
                return
            except Exception as e:
                print(f"⚠️ eSpeak initialization failed: {e}")

            try:
                # Try Google Translate TTS (online, free)
                self.client = GoogleTransClient()
                print("✅ TTS: Using Google Translate TTS (online)")
                return
            except Exception as e:
                print(f"⚠️ Google TTS initialization failed: {e}")

        # Final fallback to pyttsx3 if not Windows
        try:
            import pyttsx3

            self.client = pyttsx3.init()
            print("✅ TTS: Using pyttsx3 (fallback)")
        except Exception as e:
            print(f"❌ All TTS engines failed: {e}")
            self.client = None

    def _worker(self):
        """Background worker thread for TTS processing."""
        while True:
            text = self.queue.get()
            if text is None:
                break
            try:
                self._speak_internal(text)
            except Exception as e:
                print(f"TTS error: {e}")
            finally:
                self.queue.task_done()

    def _speak_internal(self, text):
        """Internal method to speak text using the appropriate engine."""
        if not self.client or not text:
            return

        with self.lock:
            if TTS_WRAPPER_AVAILABLE and hasattr(self.client, "speak"):
                # py3-tts-wrapper client
                self.client.speak(text)
            elif hasattr(self.client, "say"):
                # pyttsx3 client
                self.client.say(text)
                self.client.runAndWait()

    def speak(self, text):
        """Queue text for speech synthesis."""
        if not text:
            return

        # Clear queue if it's getting too long
        if self.queue.qsize() >= 2:
            with self.queue.mutex:
                self.queue.queue.clear()

        self.queue.put(text)

    def speak_sync(self, text):
        """Speak text synchronously (blocking)."""
        if not text:
            return

        try:
            self._speak_internal(text)
        except Exception as e:
            print(f"TTS sync error: {e}")

    def get_voices(self):
        """Get available voices."""
        if not self.client:
            return []

        try:
            if TTS_WRAPPER_AVAILABLE and hasattr(self.client, "get_voices"):
                return self.client.get_voices()
            elif hasattr(self.client, "getProperty"):
                # pyttsx3
                return self.client.getProperty("voices")
        except Exception as e:
            print(f"Error getting voices: {e}")

        return []

    def set_voice(self, voice_id):
        """Set the TTS voice."""
        if not self.client:
            return False

        try:
            if TTS_WRAPPER_AVAILABLE and hasattr(self.client, "set_voice"):
                self.client.set_voice(voice_id)
                return True
            elif hasattr(self.client, "setProperty"):
                # pyttsx3
                self.client.setProperty("voice", voice_id)
                return True
        except Exception as e:
            print(f"Error setting voice: {e}")

        return False

    def set_rate(self, rate):
        """Set the speech rate."""
        if not self.client:
            return False

        try:
            if TTS_WRAPPER_AVAILABLE and hasattr(self.client, "set_property"):
                # Map numeric rate to py3-tts-wrapper rate strings
                if rate < 150:
                    self.client.set_property("rate", "slow")
                elif rate > 250:
                    self.client.set_property("rate", "fast")
                else:
                    self.client.set_property("rate", "medium")
                return True
            elif hasattr(self.client, "setProperty"):
                # pyttsx3
                self.client.setProperty("rate", rate)
                return True
        except Exception as e:
            print(f"Error setting rate: {e}")

        return False

    def set_volume(self, volume):
        """Set the speech volume (0.0 to 1.0)."""
        if not self.client:
            return False

        try:
            if TTS_WRAPPER_AVAILABLE and hasattr(self.client, "set_property"):
                # Convert 0.0-1.0 to 0-100 for py3-tts-wrapper
                volume_percent = int(volume * 100)
                self.client.set_property("volume", str(volume_percent))
                return True
            elif hasattr(self.client, "setProperty"):
                # pyttsx3
                self.client.setProperty("volume", volume)
                return True
        except Exception as e:
            print(f"Error setting volume: {e}")

        return False

    def stop(self):
        """Stop the TTS worker thread."""
        self.queue.put(None)
        self.worker_thread.join(timeout=2)


# Global TTS instance
_tts_manager = None


def get_tts_manager():
    """Get the global TTS manager instance."""
    global _tts_manager
    if _tts_manager is None:
        _tts_manager = TTSManager()
    return _tts_manager


def speak(text):
    """Convenience function for speaking text."""
    get_tts_manager().speak(text)


def speak_sync(text):
    """Convenience function for speaking text synchronously."""
    get_tts_manager().speak_sync(text)


# ------------------------------ #
#       Application Launcher     #
# ------------------------------ #


def launch_main_app():
    """Launch the main communication application."""
    return launch_script("comm-v10.py")


def launch_script(script_name, close_current=False):
    """
    Launch a Python script and optionally close the current application.

    Args:
        script_name (str): Name of the script to launch
        close_current (bool): Whether to close the current application

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the project root directory
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent
        script_path = project_root / script_name

        if not script_path.exists():
            print(f"❌ Script not found: {script_path}")
            return False

        print(f"🚀 Launching: {script_name}")
        subprocess.Popen([sys.executable, str(script_path)], cwd=str(project_root))

        if close_current:
            # Give the new process time to start
            threading.Timer(1.0, lambda: sys.exit(0)).start()

        return True

    except Exception as e:
        print(f"❌ Failed to launch {script_name}: {e}")
        return False


def quit_to_main(current_window=None):
    """
    Quit current application and return to main menu.

    Args:
        current_window: Tkinter window to destroy (optional)
    """
    if current_window:
        current_window.destroy()

    launch_main_app()


# ------------------------------ #
#         UI Utilities           #
# ------------------------------ #


def create_tts_button(
    parent,
    text,
    command,
    font_size=36,
    pady=10,
    bg="gray",
    activebackground="gray",
    fg="white",
):
    """
    Create a button with TTS functionality on hover.

    Args:
        parent: Parent widget
        text (str): Button text
        command: Button command function
        font_size (int): Font size for the button
        pady (int): Vertical padding
        bg (str): Background color
        activebackground (str): Active background color
        fg (str): Foreground color

    Returns:
        tk.Button: The created button (or None if tkinter not available)
    """
    if not TKINTER_AVAILABLE:
        print(f"⚠️ Cannot create button '{text}': tkinter not available")
        return None

    btn = tk.Button(
        parent,
        text=text,
        command=command,
        font=("Arial", font_size),
        bg=bg,
        activebackground=activebackground,
        fg=fg,
    )
    btn.pack(pady=pady)
    btn.bind("<Enter>", lambda e: speak(text))
    return btn


def create_control_bar(parent, on_minimize=None, on_close=None, title="Application"):
    """
    Create a standard control bar with minimize and close buttons.

    Args:
        parent: Parent widget
        on_minimize: Function to call on minimize (default: parent.iconify)
        on_close: Function to call on close (default: quit_to_main)
        title (str): Window title

    Returns:
        tk.Frame: The control bar frame
    """
    if on_minimize is None:
        on_minimize = getattr(parent, "iconify", lambda: None)
    if on_close is None:
        on_close = lambda: quit_to_main(parent)

    bar = tk.Frame(parent, bg="gray20")
    bar.pack(fill="x", side="top")

    # Close button
    tk.Button(
        bar,
        text="Close",
        command=on_close,
        bg="red",
        fg="white",
        font=("Arial", 12),
    ).pack(side="right", padx=4, pady=4)

    # Minimize button
    tk.Button(
        bar,
        text="Minimize",
        command=on_minimize,
        bg="light blue",
        fg="black",
        font=("Arial", 12),
    ).pack(side="right", padx=4, pady=4)

    return bar


# ------------------------------ #
#        Path Utilities          #
# ------------------------------ #


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).resolve().parent.parent


def get_data_dir():
    """Get the data directory path."""
    return get_project_root() / "data"


def get_images_dir():
    """Get the images directory path."""
    return get_project_root() / "images"


def get_soundfx_dir():
    """Get the sound effects directory path."""
    return get_project_root() / "soundfx"


def get_games_dir():
    """Get the games directory path."""
    return get_project_root() / "games"


# ------------------------------ #
#      File Operations           #
# ------------------------------ #


def safe_file_exists(file_path):
    """Safely check if a file exists."""
    try:
        return Path(file_path).exists()
    except (OSError, ValueError):
        return False


def safe_read_file(file_path, encoding="utf-8"):
    """Safely read a file with error handling."""
    try:
        return Path(file_path).read_text(encoding=encoding)
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error reading file {file_path}: {e}")
        return None


def safe_write_file(file_path, content, encoding="utf-8"):
    """Safely write to a file with error handling."""
    try:
        Path(file_path).write_text(content, encoding=encoding)
        return True
    except (OSError, UnicodeEncodeError) as e:
        print(f"Error writing file {file_path}: {e}")
        return False


# ------------------------------ #
#      Cleanup Functions         #
# ------------------------------ #


def cleanup_resources():
    """Clean up global resources."""
    global _tts_manager
    if _tts_manager:
        _tts_manager.stop()
        _tts_manager = None


# Register cleanup function
import atexit

atexit.register(cleanup_resources)
