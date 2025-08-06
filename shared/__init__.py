# © 2025 NARBE House – Licensed under CC BY-NC 4.0

"""
Shared utilities package for Ben's Accessibility Software.
"""

from .utils import (
    TTSManager,
    # Cleanup
    cleanup_resources,
    create_control_bar,
    # UI utilities
    create_tts_button,
    get_data_dir,
    get_games_dir,
    get_images_dir,
    # Path utilities
    get_project_root,
    get_soundfx_dir,
    get_tts_manager,
    # Application launcher functions
    launch_main_app,
    launch_script,
    quit_to_main,
    # File operations
    safe_file_exists,
    safe_read_file,
    safe_write_file,
    # TTS functions
    speak,
    speak_sync,
)

__all__ = [
    "TTSManager",
    # Cleanup
    "cleanup_resources",
    "create_control_bar",
    # UI utilities
    "create_tts_button",
    "get_data_dir",
    "get_games_dir",
    "get_images_dir",
    # Path utilities
    "get_project_root",
    "get_soundfx_dir",
    "get_tts_manager",
    # Application launcher functions
    "launch_main_app",
    "launch_script",
    "quit_to_main",
    # File operations
    "safe_file_exists",
    "safe_read_file",
    "safe_write_file",
    # TTS functions
    "speak",
    "speak_sync",
]
