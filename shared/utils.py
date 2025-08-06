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
import json

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


# TTS Configuration
TTS_CONFIG_FILE = Path(__file__).parent / "tts_config.json"

# Default TTS configuration
DEFAULT_TTS_CONFIG = {
    "engine_priority": ["sapi", "espeak", "google", "pyttsx3"],
    "preferred_voice_id": None,
    "speech_rate": 200,
    "speech_volume": 0.8,
    "auto_save_settings": True,
    "azure": {
        "subscription_key": None,
        "region": "eastus",
        "voice_name": "en-US-AriaNeural",
        "language": "en-US",
        "output_format": "audio-16khz-32kbitrate-mono-mp3"
    },
    "elevenlabs": {
        "api_key": None,
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "model_id": "eleven_monolingual_v1"
    },
    "openai": {
        "api_key": None,
        "model": "tts-1",
        "voice": "alloy"
    }
}

# Global TTS configuration
tts_config = DEFAULT_TTS_CONFIG.copy()


def load_tts_config():
    """Load TTS configuration from JSON file."""
    global tts_config
    try:
        if TTS_CONFIG_FILE.exists():
            with TTS_CONFIG_FILE.open(encoding="utf-8") as file:
                loaded_config = json.load(file)
                tts_config = DEFAULT_TTS_CONFIG.copy()
                tts_config.update(loaded_config)
                print("✅ TTS configuration loaded successfully")
        else:
            save_tts_config()
            print("📝 Default TTS configuration created")
    except (OSError, json.JSONDecodeError) as e:
        print(f"⚠️ TTS config load error: {e}. Using defaults.")
        tts_config = DEFAULT_TTS_CONFIG.copy()


def save_tts_config():
    """Save current TTS configuration to JSON file."""
    try:
        with TTS_CONFIG_FILE.open("w", encoding="utf-8") as file:
            json.dump(tts_config, file, indent=4)
    except OSError as e:
        print(f"⚠️ TTS config save error: {e}")


def get_tts_config(key, default=None):
    """Get a TTS configuration value."""
    return tts_config.get(key, default)


def set_tts_config(key, value):
    """Set a TTS configuration value and save to file."""
    tts_config[key] = value
    if get_tts_config("auto_save_settings", True):
        save_tts_config()


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
        
        # Load TTS configuration
        load_tts_config()
        
        self._initialize_client()
        self._apply_saved_settings()
        self.worker_thread.start()

    def _initialize_client(self):
        """Initialize TTS client based on configuration priority."""
        engine_priority = get_tts_config("engine_priority", ["sapi", "espeak", "google", "pyttsx3"])
        
        for engine in engine_priority:
            if self._try_initialize_engine(engine):
                return
        
        print("❌ All TTS engines failed to initialize")
        self.client = None

    def _try_initialize_engine(self, engine):
        """Try to initialize a specific TTS engine."""
        try:
            if engine == "sapi" and TTS_WRAPPER_AVAILABLE and sys.platform == "win32":
                self.client = SAPIClient()
                print("✅ TTS: Using SAPI (Windows)")
                return True
            elif engine == "azure" and TTS_WRAPPER_AVAILABLE:
                azure_config = get_tts_config("azure", {})
                if azure_config.get("subscription_key"):
                    from tts_wrapper import AzureClient
                    self.client = AzureClient(
                        subscription_key=azure_config["subscription_key"],
                        region=azure_config.get("region", "eastus")
                    )
                    # Apply Azure-specific settings
                    if azure_config.get("voice_name"):
                        self.client.set_voice(azure_config["voice_name"])
                    print("✅ TTS: Using Azure Cognitive Services")
                    return True
                else:
                    print("⚠️ Azure TTS: No subscription key configured")
            elif engine == "elevenlabs" and TTS_WRAPPER_AVAILABLE:
                elevenlabs_config = get_tts_config("elevenlabs", {})
                if elevenlabs_config.get("api_key"):
                    from tts_wrapper import ElevenLabsClient
                    self.client = ElevenLabsClient(api_key=elevenlabs_config["api_key"])
                    if elevenlabs_config.get("voice_id"):
                        self.client.set_voice(elevenlabs_config["voice_id"])
                    print("✅ TTS: Using ElevenLabs")
                    return True
                else:
                    print("⚠️ ElevenLabs TTS: No API key configured")
            elif engine == "openai" and TTS_WRAPPER_AVAILABLE:
                openai_config = get_tts_config("openai", {})
                if openai_config.get("api_key"):
                    from tts_wrapper import OpenAIClient
                    self.client = OpenAIClient(api_key=openai_config["api_key"])
                    print("✅ TTS: Using OpenAI TTS")
                    return True
                else:
                    print("⚠️ OpenAI TTS: No API key configured")
            elif engine == "espeak" and TTS_WRAPPER_AVAILABLE:
                self.client = eSpeakClient()
                print("✅ TTS: Using eSpeak (offline)")
                return True
            elif engine in ["google", "googletrans"] and TTS_WRAPPER_AVAILABLE:
                self.client = GoogleTransClient()
                print("✅ TTS: Using Google Translate TTS (online)")
                return True
            elif engine == "pyttsx3":
                import pyttsx3
                self.client = pyttsx3.init()
                print("⚠️ TTS: Using pyttsx3 (fallback)")
                return True
        except Exception as e:
            print(f"⚠️ {engine} initialization failed: {e}")
        return False

    def _apply_saved_settings(self):
        """Apply saved TTS settings from configuration."""
        if not self.client:
            return

        # Apply saved voice
        preferred_voice = get_tts_config("preferred_voice_id")
        if preferred_voice:
            self.set_voice(preferred_voice)

        # Apply saved volume first
        self.set_volume(get_tts_config("speech_volume", 0.8))

        # Skip rate setting for SAPI due to division by zero issue
        # SAPI will use its default rate which should be reasonable
        if not (TTS_WRAPPER_AVAILABLE and hasattr(self.client, "set_property")):
            # Only apply rate for non-SAPI engines (like pyttsx3)
            self.set_rate(get_tts_config("speech_rate", 200))

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

    def _set_voice_internal(self, voice_id):
        """Internal method to set voice."""
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

    def _set_rate_internal(self, rate):
        """Internal method to set speech rate."""
        if not self.client:
            return False

        try:
            if TTS_WRAPPER_AVAILABLE and hasattr(self.client, "set_property"):
                # py3-tts-wrapper uses set_property
                self.client.set_property("rate", rate)
                return True
            elif hasattr(self.client, "setProperty"):
                # pyttsx3
                self.client.setProperty("rate", rate)
                return True
        except Exception as e:
            print(f"Error setting rate: {e}")

        return False

    def _set_volume_internal(self, volume):
        """Internal method to set speech volume."""
        if not self.client:
            return False

        try:
            if TTS_WRAPPER_AVAILABLE and hasattr(self.client, "set_property"):
                # py3-tts-wrapper uses set_property
                self.client.set_property("volume", volume)
                return True
            elif hasattr(self.client, "setProperty"):
                # pyttsx3
                self.client.setProperty("volume", volume)
                return True
        except Exception as e:
            print(f"Error setting volume: {e}")

        return False

    def set_voice(self, voice_id):
        """Set the TTS voice and save to config."""
        success = self._set_voice_internal(voice_id)
        if success:
            set_tts_config("preferred_voice_id", voice_id)
        return success

    def set_rate(self, rate):
        """Set the speech rate and save to config."""
        success = self._set_rate_internal(rate)
        if success:
            set_tts_config("speech_rate", rate)
        return success

    def set_volume(self, volume):
        """Set the speech volume and save to config."""
        success = self._set_volume_internal(volume)
        if success:
            set_tts_config("speech_volume", volume)
        return success

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
