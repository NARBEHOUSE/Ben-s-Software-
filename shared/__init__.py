# © 2025 NARBE House – Licensed under CC BY-NC 4.0

"""
Shared utilities package for Ben's Accessibility Software.
"""

from .utils import (
    # TTS functions
    speak,
    speak_sync,
    get_tts_manager,
    TTSManager,
    
    # Application launcher functions
    launch_main_app,
    launch_script,
    quit_to_main,
    
    # UI utilities
    create_tts_button,
    create_control_bar,
    
    # Path utilities
    get_project_root,
    get_data_dir,
    get_images_dir,
    get_soundfx_dir,
    get_games_dir,
    
    # File operations
    safe_file_exists,
    safe_read_file,
    safe_write_file,
    
    # Cleanup
    cleanup_resources,
)

__all__ = [
    # TTS functions
    'speak',
    'speak_sync', 
    'get_tts_manager',
    'TTSManager',
    
    # Application launcher functions
    'launch_main_app',
    'launch_script',
    'quit_to_main',
    
    # UI utilities
    'create_tts_button',
    'create_control_bar',
    
    # Path utilities
    'get_project_root',
    'get_data_dir',
    'get_images_dir',
    'get_soundfx_dir',
    'get_games_dir',
    
    # File operations
    'safe_file_exists',
    'safe_read_file',
    'safe_write_file',
    
    # Cleanup
    'cleanup_resources',
]
