# © 2025 NARBE House – Licensed under CC BY-NC 4.0

from collections import defaultdict
import ctypes  # For Windows-specific focus handling
from functools import partial
import json
import logging
import os
import platform
import subprocess
import threading
import time
import tkinter as tk

import pandas as pd
import pyautogui
from pynput import keyboard
import win32api
import win32con
import win32gui
import win32process

from shared.utils import speak


def monitor_app_focus(app_title="Accessible Menu"):
    """Continuously monitor Chrome's state and ensure the application is maximized and focused."""
    while True:
        try:
            # Check if Chrome is running
            if not is_chrome_running():
                print(
                    "Chrome is not running. Ensuring application is maximized and in focus."
                )

                hwnd = win32gui.FindWindow(None, app_title)
                if hwnd:
                    # Restore and maximize the application window
                    win32gui.ShowWindow(
                        hwnd, win32con.SW_RESTORE
                    )  # Ensure it's not minimized
                    win32gui.ShowWindow(
                        hwnd, win32con.SW_MAXIMIZE
                    )  # Maximize the window
                    win32gui.SetForegroundWindow(hwnd)  # Bring it to the foreground
                    print("Application is maximized and in focus.")
                else:
                    print(f"Application window with title '{app_title}' not found.")
            else:
                print(
                    "Chrome is running. Application can remain minimized or in the background."
                )
        except Exception as e:
            print(f"Error in monitor_app_focus: {e}")

        time.sleep(2)  # Adjust the monitoring frequency as needed


# Configure logging
logging.basicConfig(
    level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Function to minimize the terminal window
def minimize_terminal():
    if platform.system() == "Windows":
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                print("Terminal minimized.")
        except Exception as e:
            print(f"Error minimizing terminal: {e}")


# Function to minimize the app when Chrome is open
def monitor_and_minimize(app):
    """Continuously monitor for Chrome activity and minimize the Tkinter app if restored."""
    while True:
        try:
            active_window, _ = get_active_window_name()

            # Check if Chrome is the active window
            if "Chrome" in active_window or "Google Chrome" in active_window:
                print("Chrome detected. Minimizing the app.")
                app.iconify()  # Minimize the Tkinter window

            # Check if the app is restored and Chrome is still open
            if app.state() == "normal" and (
                "Chrome" in active_window or "Google Chrome" in active_window
            ):
                print("App restored while Chrome is open. Minimizing again.")
                app.iconify()

        except Exception as e:
            print(f"Error in monitor_and_minimize: {e}")
        time.sleep(1)  # Adjust frequency of checks if needed


import psutil


def is_chrome_running():
    """Check if any Chrome process is running."""
    for process in psutil.process_iter(["name"]):
        if process.info["name"] and "chrome" in process.info["name"].lower():
            return True
    return False


# Function to minimize the on-screen keyboard
def minimize_on_screen_keyboard():
    """Minimizes the on-screen keyboard if it's active."""
    try:
        retries = 5
        for attempt in range(retries):
            hwnd = win32gui.FindWindow(
                "IPTip_Main_Window", None
            )  # Verify this class name
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                print(f"On-screen keyboard minimized on attempt {attempt + 1}.")
                return
            time.sleep(1)  # Wait before retrying
        print("On-screen keyboard not found after retries.")
    except Exception as e:
        print(f"Error minimizing on-screen keyboard: {e}")


# Function to Monitor and Close Start Menu
def send_esc_key():
    """Send the ESC key to close the Start Menu."""
    ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)  # ESC key down
    ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)  # ESC key up
    print("ESC key sent to close Start Menu.")


def is_start_menu_open():
    """Check if the Start Menu is currently open and focused."""
    hwnd = (
        win32gui.GetForegroundWindow()
    )  # Get the handle of the active (focused) window
    class_name = win32gui.GetClassName(hwnd)  # Get the class name of the active window
    return class_name in ["Shell_TrayWnd", "Windows.UI.Core.CoreWindow"]


def monitor_start_menu():
    """Continuously check and close the Start Menu if it is open."""
    while True:
        try:
            # Check if the Start Menu is active
            if is_start_menu_open():
                print("Start Menu detected. Closing it now.")
                send_esc_key()
            else:
                hwnd = win32gui.GetForegroundWindow()
                active_window_title = win32gui.GetWindowText(hwnd)
                print(f"Active window: {active_window_title} (Start Menu not active).")
        except Exception as e:
            print(f"Error in monitor_start_menu: {e}")

        time.sleep(0.5)  # Adjust frequency as needed


# List all available window titles for debugging
def log_window_titles():
    def callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            results.append(win32gui.GetWindowText(hwnd))

    windows = []
    win32gui.EnumWindows(callback, windows)
    print("Available window titles:")
    for title in windows:
        print(f"Window title: {title}")


def log_active_window_title():
    while True:
        try:
            active_window, _ = get_active_window_name()
            print(f"Active window: {active_window}")
        except Exception as e:
            print(f"Error logging window title: {e}")
        time.sleep(1)


# TTS functionality is now handled by shared.utils


# Function to get the active window title
def get_active_window_name():
    hwnd = win32gui.GetForegroundWindow()
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    name = win32gui.GetWindowText(hwnd)
    return name, pid


# Function to close Chrome using Alt+F4
def close_chrome_cleanly():
    """Close Chrome browser cleanly using Alt+F4."""
    try:
        name, _ = get_active_window_name()
        if "Chrome" in name:
            print("Chrome is active. Closing it.")
            pyautogui.hotkey("alt", "f4")  # Close Chrome window
        else:
            print("Chrome is not the active window.")
    except Exception as e:
        print(f"Error closing Chrome: {e}")


# Function to bring the application back into focus
def bring_application_to_focus():
    try:
        app_hwnd = win32gui.FindWindow(
            None, "Accessible Menu"
        )  # Replace with your window title
        if app_hwnd:
            win32gui.ShowWindow(app_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(app_hwnd)
            print("Application brought to focus.")
        else:
            print("No GUI window found.")
    except Exception as e:
        print(f"Error focusing application: {e}")


from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import threading
import time
import urllib.parse

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LAST_WATCHED_FILE = os.path.join(DATA_DIR, "last_watched.json")


# Function to load the last_watched.json data
def load_last_watched():
    if os.path.exists(LAST_WATCHED_FILE):
        with open(LAST_WATCHED_FILE) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


# Function to save the last_watched data to the file
def save_last_watched(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LAST_WATCHED_FILE, "w") as f:
        json.dump(data, f, indent=2)


# HTTP request handler to save URLs
class URLSaveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse the URL from the request
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        url = qs.get("url", [None])[0]

        # Get the active show
        show = MenuFrame.active_show

        if show and url:
            # Read the existing data from last_watched.json
            data = load_last_watched()
            data[show] = url  # Update or add the show and URL
            save_last_watched(data)  # Save the updated data
            print(f"[URL-SAVED] {show} → {url}")

        # Send a response back to indicate success
        self.send_response(204)
        self.end_headers()


# Start the HTTP server
def start_url_server():
    server = HTTPServer(("127.0.0.1", 8765), URLSaveHandler)
    server.serve_forever()


# Start the server in a background thread
threading.Thread(target=start_url_server, daemon=True).start()

# Imports moved to top of file


def load_links(file_path="shows.xlsx"):
    """
    Reads links data from an Excel file and organizes it by type and genre.
    The Excel file should have columns such as:
      - type
      - genre
      - title
      - url
    Returns a nested defaultdict structure.
    """
    # Construct the absolute file path if needed.
    abs_path = os.path.join(os.path.dirname(__file__), "data", file_path)

    try:
        # Read the Excel file into a DataFrame.
        df = pd.read_excel(abs_path)
    except Exception as e:
        print(f"[ERROR] Failed to read {file_path}: {e}")
        return {}

    # Convert the DataFrame to a list of dictionaries.
    links = df.to_dict(orient="records")

    # Organize the data by type and genre.
    organized = defaultdict(lambda: defaultdict(list))
    for entry in links:
        t = entry.get("type", "misc").lower()
        genre = entry.get("genre", "misc").lower()
        organized[t][genre].append(entry)

    # Sort the entries within each type/genre by title.
    for t in organized:
        for genre in organized[t]:
            organized[t][genre].sort(key=lambda e: e.get("title", ""))

    return organized


def load_communication_phrases(file_path="communication.xlsx"):
    """
    Loads phrases from communication.xlsx in the format:
    | Category | Display | Text to Speech |
    Returns a dict: { "Category1": [(label1, speak1), (label2, speak2), ...], ... }
    """
    abs_path = os.path.join(os.path.dirname(__file__), "data", file_path)
    try:
        df = pd.read_excel(abs_path)
    except Exception as e:
        print(f"[ERROR] Failed to load communication.xlsx: {e}")
        return {}

    phrases_by_category = defaultdict(list)
    for _, row in df.iterrows():
        category = str(row["Category"]).strip()
        label = str(row["Display"]).strip()
        speak_text = str(row["Text to Speech"]).strip()
        if category and label and speak_text:
            phrases_by_category[category].append((label, speak_text))
    return phrases_by_category


class KeySequenceListener:
    def __init__(self, app):
        self.app = app
        self.sequence = ["enter", "enter", "enter"]  # Define the key sequence
        self.current_index = 0
        self.last_key_time = None
        self.timeout = 8  # Timeout for completing the sequence (seconds)
        self.held_keys = set()  # Track keys that are currently held
        self.recently_pressed = set()  # To debounce key presses
        self.start_listener()

    def start_listener(self):
        def on_press(key):
            try:
                key_name = (
                    key.char.lower()
                    if hasattr(key, "char") and key.char
                    else str(key).split(".")[-1].lower()
                )
                if (
                    key_name in self.recently_pressed
                ):  # Ignore key if already recently pressed
                    return

                self.recently_pressed.add(key_name)
                self.check_key(key_name)
            except AttributeError:
                pass

        def on_release(key):
            try:
                key_name = (
                    key.char.lower()
                    if hasattr(key, "char") and key.char
                    else str(key).split(".")[-1].lower()
                )
                self.recently_pressed.discard(key_name)  # Allow key to be pressed again
            except AttributeError:
                pass

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

    def check_key(self, key_name):
        # Handle timeout for the sequence
        if self.last_key_time and time.time() - self.last_key_time > self.timeout:
            print("Sequence timeout. Resetting index.")
            self.current_index = 0  # Reset sequence on timeout

        self.last_key_time = time.time()

        # Check the current key against the sequence
        if key_name == self.sequence[self.current_index]:
            print(f"Matched {key_name} at index {self.current_index}")
            self.current_index += 1  # Move to the next key in the sequence
            if self.current_index == len(self.sequence):  # Full sequence detected
                self.handle_sequence()
                self.current_index = 0  # Reset sequence index
        else:
            print("Key mismatch or invalid input. Resetting sequence.")
            self.current_index = 0  # Reset on invalid input

    def handle_sequence(self):
        print("Key sequence detected. Closing Chrome and focusing application.")
        threading.Thread(target=self.perform_actions, daemon=True).start()

    def perform_actions(self):
        close_chrome_cleanly()

        # Introduce a delay before resuming scanning/selecting
        print("Adding delay before resuming scanning/selecting...")
        time.sleep(2)  # Delay in seconds; adjust as needed

        bring_application_to_focus()


import ctypes

import pyautogui
from pynput.keyboard import Controller


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Accessible Menu")
        self.geometry("960x540")  # Default, will adjust to screen size
        self.attributes("-fullscreen", True)
        self.configure(bg="black")
        self.current_frame = None
        self.buttons = []  # Holds buttons for scanning
        self.current_button_index = 0  # Current scanning index
        self.selection_enabled = True  # Flag to manage debounce for selection
        self.keyboard = Controller()  # Initialize the keyboard controller
        self.organized_links = load_links("shows.xlsx")
        self.spacebar_pressed = False
        self.long_spacebar_pressed = False
        self.start_time = 0
        self.backward_time_delay = 2  # Delay in seconds when long holding space

        # Add Close and Minimize buttons
        self.create_window_controls()

        # Minimize terminal and keyboard
        minimize_terminal()
        minimize_on_screen_keyboard()

        # Start monitoring for Chrome in a separate thread
        threading.Thread(target=monitor_and_minimize, args=(self,), daemon=True).start()

        # Start monitoring for Chrome's state and application focus
        threading.Thread(
            target=monitor_app_focus, args=("Accessible Menu",), daemon=True
        ).start()

        # Start monitoring the Start Menu
        threading.Thread(target=monitor_start_menu, daemon=True).start()

        # Delay key bindings to ensure focus
        self.after(3000, self.bind_keys_for_scanning)

        # Focus Application
        self.after(7000, self.force_focus, bring_application_to_focus())
        self.after(9000, lambda: pyautogui.click(x=25, y=25))

        self.menu_stack = []

        # Initialize the main menu
        print("Initializing the main menu...")
        self.show_frame(MainMenuPage)

    def force_focus(self):
        self.focus_force()
        self.lift()
        self.attributes("-topmost", True)
        self.after(500, lambda: self.attributes("-topmost", False))
        print("Forced focus via Tkinter methods.")

    def create_window_controls(self):
        """Adds Close and Minimize buttons to the top of the app window."""
        control_frame = tk.Frame(
            self, bg="gray"
        )  # Change background color to make it visible
        control_frame.pack(side="top", fill="x")

        minimize_button = tk.Button(
            control_frame,
            text="Minimize",
            bg="light blue",
            fg="black",
            command=self.iconify,
            font=("Arial", 12),
        )
        minimize_button.pack(side="right", padx=5, pady=5)

        close_button = tk.Button(
            control_frame,
            text="Close",
            bg="red",
            fg="white",
            command=self.destroy,
            font=("Arial", 12),
        )
        close_button.pack(side="right", padx=5, pady=5)

    def bind_keys_for_scanning(self):
        # Unbind any previous key events (if needed).
        self.unbind("<KeyPress-space>")
        self.unbind("<KeyRelease-space>")
        self.unbind("<KeyRelease-Return>")

        # Bind the keys on the main app (or you could bind them to self.current_frame if you prefer).
        self.bind("<KeyPress-space>", self.track_spacebar_hold)
        self.bind("<KeyRelease-space>", self.reset_spacebar_hold)
        self.bind("<KeyRelease-Return>", self.select_button)
        print("Key bindings activated.")

        # Start key sequence listener
        self.sequencer = KeySequenceListener(self)

        # Start spacebar hold tracking in a separate thread
        threading.Thread(target=self.monitor_spacebar_hold, daemon=True).start()

    def monitor_spacebar_hold(self):
        while True:
            if self.spacebar_pressed and (time.time() - self.start_time >= 3.5):
                self.long_spacebar_pressed = True
                self.scan_backward()
                time.sleep(self.backward_time_delay)

    def track_spacebar_hold(self, event):
        if not self.spacebar_pressed and not self.long_spacebar_pressed:
            self.spacebar_pressed = True
            self.start_time = time.time()

    def reset_spacebar_hold(self, event):
        if self.spacebar_pressed:
            self.spacebar_pressed = False
            if not self.long_spacebar_pressed:
                self.scan_forward()
            else:
                self.long_spacebar_pressed = False
                self.start_time = time.time()

    def show_frame(self, frame_factory):
        if self.current_frame:
            # Save the function (or lambda) that creates the current frame.
            self.menu_stack.append(self.current_frame_factory)
            self.current_frame.destroy()
        self.current_frame = frame_factory(self)
        self.current_frame.pack(expand=True, fill="both")
        self.current_frame_factory = frame_factory  # Save the factory for this frame
        self.buttons = self.current_frame.buttons
        self.current_button_index = 0
        if self.buttons:
            self.highlight_button(0)

    def show_previous_menu(self):
        if self.menu_stack:
            self.current_frame.destroy()
            previous_factory = self.menu_stack.pop()
            self.current_frame = previous_factory(self)
            self.current_frame.pack(expand=True, fill="both")
            self.current_frame_factory = previous_factory
            self.buttons = self.current_frame.buttons
            self.current_button_index = 0
            if self.buttons:
                self.highlight_button(0)
        else:
            self.show_frame(MainMenuPage)

    def scan_forward(self, event=None):
        """Advance to the next button and highlight it upon spacebar release."""
        if not self.selection_enabled or not self.buttons:
            return
        self.selection_enabled = False  # Disable selection temporarily

        self.current_button_index = (self.current_button_index + 1) % len(self.buttons)
        self.highlight_button(self.current_button_index)

        # Speak the button's text if the frame matches
        if isinstance(
            self.current_frame,
            (
                MainMenuPage,
                EntertainmentMenuPage,
                SettingsMenuPage,
                LibraryMenu,
                GamesPage,
                CommunicationPageMenu,
            ),
        ):
            speak(self.buttons[self.current_button_index]["text"])

        # Re-enable selection after a short delay
        threading.Timer(0.5, self.enable_selection).start()

    def scan_backward(self, event=None):
        """Move to the previous button and highlight it."""
        if not self.selection_enabled or not self.buttons:
            return

        self.selection_enabled = False  # Disable selection temporarily
        self.current_button_index = (self.current_button_index - 1) % len(self.buttons)
        self.highlight_button(self.current_button_index)

        # Speak the button's text if the frame matches
        if isinstance(
            self.current_frame,
            (
                MainMenuPage,
                EntertainmentMenuPage,
                SettingsMenuPage,
                LibraryMenu,
                GamesPage,
                CommunicationPageMenu,
            ),
        ):
            speak(self.buttons[self.current_button_index]["text"])

        # Re-enable selection after a short delay
        threading.Timer(0.5, self.enable_selection).start()

    def enable_selection(self):
        """Re-enable scanning and selection after the delay."""
        self.selection_enabled = True

    def select_button(self, event=None):
        """Select the currently highlighted button upon Enter key release with debounce and delay."""
        if self.selection_enabled and self.buttons:
            self.selection_enabled = False  # Disable selection temporarily
            self.buttons[self.current_button_index].invoke()  # Invoke the button action

            # Add delay for both scanning and selection after Enter key
            threading.Timer(
                2, self.enable_selection
            ).start()  # Re-enable selection after 2 seconds

            self.sequencer.current_index = 0
            self.sequencer.last_key_time = None

    def highlight_button(self, index):
        for i, btn in enumerate(self.buttons):
            if i == index:
                btn.config(bg="yellow", fg="black")
            else:
                btn.config(bg="light blue", fg="black")
        self.update()  # Refresh appearance

        # Auto-scroll so that the highlighted button is visible.
        if hasattr(self, "scroll_canvas"):
            try:
                btn = self.buttons[index]
                # Get button’s absolute Y position and canvas’s Y position.
                btn_y = btn.winfo_rooty()
                canvas_y = self.scroll_canvas.winfo_rooty()
                canvas_height = self.scroll_canvas.winfo_height()
                # If the button is not fully in view, adjust the yview.
                if btn_y < canvas_y or (btn_y + btn.winfo_height()) > (
                    canvas_y + canvas_height
                ):
                    relative_y = (btn_y - canvas_y) / self.scroll_canvas.bbox("all")[3]
                    self.scroll_canvas.yview_moveto(relative_y)
            except Exception as e:
                print(f"Error auto-scrolling: {e}")


# Base Frame for Menu Pages
class MenuFrame(tk.Frame):
    active_show = None  # Class-level variable to track the active show

    def __init__(self, parent, title):
        super().__init__(parent, bg="black")
        self.parent = parent
        self.title = title
        self.buttons = []  # Store buttons for scanning
        self.create_title()

    def create_title(self):
        label = tk.Label(
            self, text=self.title, font=("Arial", 36), bg="black", fg="white"
        )
        label.pack(pady=20)

    def create_button_grid(self, buttons, columns=3):
        # Create a frame for the grid directly inside this MenuFrame.
        grid_frame = tk.Frame(self, bg="black")
        grid_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.buttons = []  # Reset the button list.
        rows = (len(buttons) + columns - 1) // columns  # Calculate number of rows.

        for i, (text, command, speak_text) in enumerate(buttons):
            row, col = divmod(i, columns)
            btn = tk.Button(
                grid_frame,
                text=text,
                font=("Arial Black", 36),
                bg="light blue",
                fg="black",
                activebackground="yellow",
                activeforeground="black",
                command=lambda c=command, s=speak_text: self.on_select(c, s),
                wraplength=700,  # Allows text to wrap if needed.
            )
            btn.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            self.buttons.append(btn)

        # Configure the grid rows and columns to expand evenly.
        for r in range(rows):
            grid_frame.rowconfigure(r, weight=1)
        for c in range(columns):
            grid_frame.columnconfigure(c, weight=1)

    def on_select(self, command, speak_text):
        command()
        if speak_text:
            speak(speak_text)

    def open_in_chrome(self, show_name, default_url, persistent=True):
        chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        # ——— Load and override with whatever’s in last_watched.json ———
        url_to_open = default_url
        if persistent:
            last = load_last_watched()
            if show_name in last:
                url_to_open = last[show_name]
                print(f"[LOAD] Resuming {show_name} from saved URL → {url_to_open}")
            else:
                print(f"[LOAD] No saved record for {show_name}, using default.")

        args = [chrome_exe, "--start-fullscreen", url_to_open]

        try:
            subprocess.Popen(args, shell=False)
            print(f"[LAUNCH] Chrome → {url_to_open}")
        except Exception as e:
            print(f"[ERROR] launching Chrome: {e}")

    def movies_in_chrome(self, show_name, default_url):
        """
        Opens the given movie URL in Chrome in fullscreen mode without
        using persistent last-watched data.
        """
        try:
            subprocess.run(
                [
                    "start",
                    "chrome",
                    "--remote-debugging-port=9222",
                    "--start-fullscreen",
                    default_url,
                ],
                shell=True,
            )
            print(f"Opened movie URL for {show_name}: {default_url}")
        except Exception as e:
            print(f"Error opening movie URL for {show_name}: {e}")

    def open_and_click(self, show_name, default_url, x_offset=0, y_offset=0):
        """Open the given URL, click on the specified position, and ensure fullscreen mode."""
        # Use the same logic as open_in_chrome to open the URL
        self.movies_in_chrome(show_name, default_url)
        time.sleep(5)  # Wait for the browser to open and load

        # Bring the browser window to the foreground
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        print("Brought Chrome to the foreground.")

        # Calculate click position with offsets
        screen_width, screen_height = pyautogui.size()
        click_x = (screen_width // 2) + x_offset
        click_y = (screen_height // 2) + y_offset

        # Perform the click
        pyautogui.click(click_x, click_y)
        print(f"Clicked at position: ({click_x}, {click_y})")

        # Allow time for interaction
        time.sleep(2)

    from pynput.keyboard import Controller

    import keyboard

    def open_pluto(self, show_name, pluto_url):
        """Open Pluto TV link in Chrome, ensure focus, unmute, and fullscreen."""

        # Open the URL in Chrome
        self.open_in_chrome(show_name, pluto_url)
        time.sleep(7)  # Wait for page and video player to load

        # Bring Chrome to the foreground
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        print("Brought Chrome to the foreground.")

        # Wait for the video player to load
        time.sleep(6)

        # Use pynput.Controller instead of keyboard module
        keyboard = Controller()

        # Simulate 'm' keypress to mute/unmute
        print("Sending 'm' keypress to unmute the video...")
        keyboard.press("m")
        time.sleep(0.1)
        keyboard.release("m")

        # Wait briefly before fullscreening
        time.sleep(2)

        # Simulate 'f' keypress to fullscreen
        print("Sending 'f' keypress to fullscreen the video...")
        keyboard.press("f")
        time.sleep(0.1)
        keyboard.release("f")

        print("Pluto.TV interaction complete.")

    def click_at(self, x, y, hold_time=0.1, double_click=False):

        # Move the cursor to the given coordinates.
        win32api.SetCursorPos((x, y))
        time.sleep(0.1)  # Give the cursor time to move.

        # Perform the first click.
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        time.sleep(hold_time)  # Hold the click.
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)

        if double_click:
            time.sleep(0.1)  # Short delay between clicks.
            # Perform the second click.
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
            time.sleep(hold_time)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)

    import os
    import subprocess
    import time

    import pyautogui
    from pyautogui import ImageNotFoundException
    import win32con
    import win32gui

    def open_spotify(self, playlist_url):
        """
        Opens the Spotify playlist URL in Chrome, waits for the page to load,
        then tries to locate the Play button via image recognition.
        If the image is not found on the first try, waits a few seconds and tries again.
        If still not found, it falls back to predetermined coordinates.
        Finally, it sends Alt+S to shuffle.
        """
        # Define the path to Chrome.
        chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        if not os.path.exists(chrome_path):
            os.startfile(playlist_url)
        else:
            args = [
                chrome_path,
                "--autoplay-policy=no-user-gesture-required",
                "--start-fullscreen",
                playlist_url,
            ]
            subprocess.Popen(args)

        # Wait for the page to load.
        print("[DEBUG] Waiting for Chrome/Spotify page to load...")
        time.sleep(12)

        # Define the absolute path to your reference image.
        play_image_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "images", "spotifyplay.png"
        )
        if not os.path.exists(play_image_path):
            print(f"[DEBUG] Reference image not found: {play_image_path}")
            location = None
        else:
            print(f"[DEBUG] Searching for play button using image: {play_image_path}")
            try:
                location = pyautogui.locateCenterOnScreen(
                    play_image_path, confidence=0.8
                )
            except Exception as e:
                print(f"[ERROR] Exception during first image search: {e}")
                location = None

        # If not found, try to bring Chrome to the foreground and try again.
        if location is None:
            print(
                "[DEBUG] Play button not found. Attempting to bring Chrome to foreground and waiting a bit..."
            )
            # Attempt to find a window with "Chrome" in its title.
            chrome_hwnd = win32gui.FindWindow(None, "Spotify")  # Adjust this if needed.
            if chrome_hwnd:
                win32gui.ShowWindow(chrome_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(chrome_hwnd)
            else:
                print("[DEBUG] Could not find a Chrome window titled 'Spotify'.")
            time.sleep(3)
            try:
                location = pyautogui.locateCenterOnScreen(
                    play_image_path, confidence=0.8
                )
            except Exception as e:
                print(f"[ERROR] Exception during second image search: {e}")
                location = None

        # If the play button is found, click it; otherwise, use fallback coordinates.
        if location is not None:
            print(f"[DEBUG] Play button found at: {location}")
            pyautogui.click(location)
        else:
            print(
                "[DEBUG] Play button still not found. Using fallback coordinates (75, 785)."
            )
            pyautogui.click((752, 665))

        # Wait before sending the hotkey.
        time.sleep(2)
        pyautogui.hotkey("alt", "s")
        print("[DEBUG] Sent Alt+S to shuffle.")

    def save_current_url(self, show_name, expected_url):
        """
        Every 30 seconds, fetch the active URL and save it under `show_name` in last_watched.json.
        """
        base = "/".join(expected_url.split("/")[:4])
        print(f"[TRACKER] Started URL-tracker for: {show_name}")

        while MenuFrame.active_show == show_name:
            time.sleep(5)  # Wait for 30 seconds

            current_url = expected_url  # Here, you can use the expected URL directly
            print(f"[TRACK] fetched for {show_name}: {current_url}")

            # Check if the current URL matches the base URL and save it
            if current_url and current_url.startswith(base):
                data = load_last_watched()
                data[show_name] = current_url
                save_last_watched(data)
                print(f"[SAVED] {show_name} → {current_url}")
            else:
                print(f"[SKIP] No save for {show_name}, URL: {current_url}")

            if not is_chrome_running():
                print(f"[TRACKER] Chrome closed, stopping tracker for {show_name}")
                break

        print(f"[TRACKER] Exited URL-tracker for: {show_name}")

    def open_plex_movies(self, plex_url, show_name):
        """
        Opens the Plex URL in Chrome and then sends keyboard commands:
        1. Press 'x'
        2. Press 'return'
        3. Wait 2 seconds
        4. Press 'p'
        """
        # Open Plex using your common method.
        self.movies_in_chrome(show_name, plex_url)

        # Wait for the Plex page to load fully.
        time.sleep(7)  # Adjust as necessary for your system.

        # Send the keyboard commands.
        pyautogui.press("x")
        time.sleep(2)
        pyautogui.press("enter")
        time.sleep(2)
        pyautogui.press("p")
        print("Sent keys: x, enter, then after 2 seconds, p.")

    def open_plex(self, plex_url, show_name):
        """
        Opens the Plex URL in Chrome and then sends keyboard commands:
        1. Press 'x'
        2. Press 'return'
        3. Wait 2 seconds
        4. Press 'p'
        """
        # Open Plex using your common method.
        self.open_in_chrome(show_name, plex_url)

        # Wait for the Plex page to load fully.
        time.sleep(7)  # Adjust as necessary for your system.

        # Send the keyboard commands.
        pyautogui.press("x")
        time.sleep(2)
        pyautogui.press("enter")
        time.sleep(2)
        pyautogui.press("p")
        print("Sent keys: x, enter, then after 2 seconds, p.")

    def open_youtube(self, youtube_url, show_name):

        # Open youtube using your common method.
        self.movies_in_chrome(show_name, youtube_url)
        # Wait for the Youtube page to load fully.
        time.sleep(5)  # Adjust as necessary for your system.
        # Send the keyboard commands.
        pyautogui.press("f")
        print("Sent keys: f")

    def open_link(self, entry):
        title = entry["title"]
        url = entry["url"]
        content_type = entry.get("type", "movies").lower()

        print(f"[DEBUG] Requested: {title} - URL: {url} (Type: {content_type})")

        # 1) Tell the URL‐save extension/server which show key to use
        MenuFrame.active_show = title
        print(f"[DEBUG] Active show set → {MenuFrame.active_show}")

        # 2) For shows, overlay with last-watched URL if available
        if content_type == "shows":
            last = load_last_watched()
            if title in last:
                url = last[title]
                print(f"[DEBUG] Last-watched found for {title}: {url}")
            else:
                print(
                    f"[DEBUG] No last-watched found for {title}, using default from spreadsheet"
                )

        print(f"[DEBUG] Final URL for {title}: {url}")

        # 3) Dispatch by type/platform
        if content_type == "shows":
            if "plex.tv" in url:
                print(f"[DEBUG] Detected Plex Show → open_plex({title})")
                self.open_plex(url, title)
            elif "youtube.com" in url or "youtu.be" in url:
                print(f"[DEBUG] Detected YouTube Show → open_youtube({title})")
                self.open_youtube(url, title)
            elif "paramountplus.com/live-tv" in url:
                print(f"[DEBUG] Detected Paramount+ Live TV → open_and_click({title})")
                self.open_and_click(title, url)
            elif "pluto.tv" in url:
                print(f"[DEBUG] Detected Pluto.tv Show → open_pluto({title})")
                self.open_pluto(title, url)
            elif "amazon.com" in url:
                print(f"[DEBUG] Detected Amazon Show → open_and_click({title})")
                self.open_and_click(title, url)
            else:
                print(f"[DEBUG] Non-Plex Show → open_in_chrome({title})")
                self.open_in_chrome(title, url)

        elif content_type == "live":
            if "paramountplus.com/live-tv" in url:
                print(
                    f"[DEBUG] Detected Paramount+ Live Stream → open_and_click({title})"
                )
                self.open_and_click(title, url)
            elif "pluto.tv" in url:
                print(f"[DEBUG] Detected Pluto.tv Live Stream → open_pluto({title})")
                self.open_pluto(title, url)
            elif "youtube.com" in url or "youtu.be" in url:
                print(f"[DEBUG] Detected YouTube Live Stream → open_youtube({title})")
                self.open_youtube(url, title)
            elif "amazon.com" in url:
                print(f"[DEBUG] Detected Amazon Live → open_and_click({title})")
                self.open_and_click(title, url)
            else:
                print(f"[DEBUG] General Live Content → open_in_chrome({title})")
                self.open_in_chrome(title, url)

        elif content_type == "movies":
            if "plex.tv" in url:
                print(f"[DEBUG] Detected Plex Movie → open_plex_movies({title})")
                self.open_plex_movies(url, title)
            elif "amazon.com" in url:
                print(f"[DEBUG] Detected Amazon Movie → open_and_click({title})")
                self.open_and_click(title, url)
            else:
                print(f"[DEBUG] Other Movie Content → movies_in_chrome({title})")
                self.movies_in_chrome(title, url)

        elif content_type == "music":
            if "spotify.com" in url:
                print(f"[DEBUG] Detected Spotify → open_spotify({title})")
                self.open_spotify(url)
            else:
                print(f"[DEBUG] Other Music Source → open_in_chrome({title})")
                self.open_in_chrome(title, url)

        elif content_type == "audiobooks":
            if "plex.tv" in url:
                print(f"[DEBUG] Detected Plex Audiobook → open_plex_movies({title})")
                self.open_plex_movies(url, title)
            else:
                print(f"[DEBUG] Other Audiobook Source → movies_in_chrome({title})")
                self.movies_in_chrome(title, url)

        else:
            print(
                f"[DEBUG] Unknown content type '{content_type}' → movies_in_chrome({title})"
            )
            self.movies_in_chrome(title, url)


import sys


# Define Menu Classes
class MainMenuPage(MenuFrame):
    def __init__(self, parent):
        super().__init__(parent, "Main Menu")
        self.buttons = []  # Store buttons for scanning
        self.current_button_index = 0  # Initialize scanning index
        self.selection_enabled = True  # Flag to manage debounce for selection

        # Create the grid layout for 4 large buttons
        grid_frame = tk.Frame(self, bg="black")
        grid_frame.pack(expand=True, fill="both")

        # Define buttons with their commands and labels
        buttons = [
            ("Emergency", self.emergency_alert, "Emergency Alert"),
            ("Settings", lambda: parent.show_frame(SettingsMenuPage), "Settings Menu"),
            (
                "Communication",
                lambda: parent.show_frame(CommunicationPageMenu),
                "Communication Menu",
            ),
            (
                "Entertainment",
                lambda: parent.show_frame(EntertainmentMenuPage),
                "Entertainment Menu",
            ),
        ]

        for i, (text, command, speak_text) in enumerate(buttons):
            row, col = divmod(i, 2)  # Calculate row and column for 2x2 layout
            btn = tk.Button(
                grid_frame,
                text=text,
                font=("Arial Black", 36),
                bg="light blue",
                fg="black",
                activebackground="yellow",
                activeforeground="black",
                command=lambda c=command, s=speak_text: self.on_select(c, s),
                wraplength=850,  # Wrap text for better display
            )
            btn.grid(
                row=row, column=col, sticky="nsew", padx=10, pady=10
            )  # Adjust padding for spacing
            self.buttons.append(btn)  # Add button to scanning list

        # Configure grid to distribute space equally
        for i in range(2):  # Two rows
            grid_frame.rowconfigure(i, weight=1)
        for j in range(2):  # Two columns
            grid_frame.columnconfigure(j, weight=1)

        # Highlight the first button for scanning
        if self.buttons:
            self.highlight_button(0)

    def scan_forward(self, event=None):
        """Move to the next button and highlight it."""
        if self.selection_enabled and self.buttons:
            self.selection_enabled = False  # Disable selection temporarily to debounce
            self.current_button_index = (self.current_button_index + 1) % len(
                self.buttons
            )
            self.highlight_button(self.current_button_index)
            threading.Timer(
                0.5, self.enable_selection
            ).start()  # Re-enable selection after a delay

    def highlight_button(self, index):
        """Highlight the current button and reset others."""
        for i, button in enumerate(self.buttons):
            if i == index:
                button.config(bg="yellow", fg="black")  # Highlight current button
            else:
                button.config(bg="light blue", fg="black")  # Reset others
        self.update()

    def enable_selection(self):
        """Re-enable selection after a delay."""
        self.selection_enabled = True

    def on_select(self, command, speak_text):
        """Handle button selection logic."""
        command()
        if speak_text:
            speak(speak_text)

    def emergency_alert(self):
        """Trigger emergency alert."""
        ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)  # Volume up key
        for _ in range(50):  # Max volume
            ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
            time.sleep(0.05)

        def alert_loop():
            end_time = time.time() + 15
            while time.time() < end_time:
                speak("Help, help, help, help, help")
                time.sleep(2)

        threading.Thread(target=alert_loop, daemon=True).start()


class CommunicationPageMenu(MenuFrame):
    def __init__(self, parent):
        super().__init__(parent, "Communication")
        self.phrases_by_category = load_communication_phrases()
        self.categories = sorted(self.phrases_by_category.keys())
        self.page = 0
        self.page_size = 14  # back + keyboard + up to 14 categories = 16 buttons max
        self.load_buttons()

    def load_buttons(self):
        start = self.page * self.page_size
        end = start + self.page_size
        current_cats = self.categories[start:end]

        buttons = [
            ("Back", lambda: self.parent.show_frame(MainMenuPage), "Back"),
            ("Keyboard", self.open_keyboard_app, "Keyboard"),
        ]
        for cat in current_cats:
            buttons.append(
                (
                    cat,
                    lambda c=cat: self.parent.show_frame(
                        lambda p: CommunicationCategoryMenu(
                            p, c, self.phrases_by_category[c]
                        )
                    ),
                    cat,
                )
            )

        if end < len(self.categories):
            buttons.append(("Next", self.next_page, "Next Page"))

        self.create_button_grid(buttons, columns=4)

    def next_page(self):
        self.page += 1
        self.load_buttons()

    def open_keyboard_app(self):
        try:
            script_name = "keyboard.py"
            script_path = os.path.join(
                os.path.dirname(__file__), "keyboard", script_name
            )
            subprocess.Popen([sys.executable, script_path])
            self.master.destroy()
        except Exception as e:
            print(f"Failed to open keyboard: {e}")


class CommunicationCategoryMenu(MenuFrame):
    def __init__(self, parent, category_name, phrase_list):
        super().__init__(parent, category_name)
        buttons = [("Back", lambda: parent.show_frame(CommunicationPageMenu), "Back")]
        for label, speak_text in phrase_list:
            buttons.append((label, lambda t=speak_text: speak(t), speak_text))
        self.create_button_grid(buttons, columns=3)


# Imports moved to top of file

import pyautogui
import win32con
import win32gui


class SettingsMenuPage(MenuFrame):
    def __init__(self, parent):
        super().__init__(parent, "Settings")  # Set the title to "Settings"
        self.buttons = []  # Store buttons for scanning

        # Define buttons with actions and TTS
        buttons = [
            ("Back", lambda: parent.show_frame(MainMenuPage), "Back"),
            ("Volume Up", self.volume_up, "Increase volume"),
            ("Volume Down", self.volume_down, "Decrease volume"),
            ("Sleep Timer (60 min)", self.sleep_timer, "Set a 60-minute sleep timer"),
            ("Cancel Sleep Timer", self.cancel_sleep_timer, "Cancel the sleep timer"),
            ("Turn Display Off", self.turn_off_display, "Turn off the display"),
            ("Lock", self.lock_computer, "Lock the computer"),
            ("Restart", self.restart_computer, "Restart the computer"),
            ("Shut Down", self.shut_down_computer, "Shut down the computer"),
        ]

        # Create button grid and bind keys for scanning/selecting
        self.create_button_grid(buttons, columns=3)  # Set columns to 3

    def create_button_grid(self, buttons, columns=5):
        """Creates a grid layout for buttons with a dynamic number of rows and columns."""
        grid_frame = tk.Frame(self, bg="black")
        grid_frame.pack(expand=True, fill="both")

        rows = (len(buttons) + columns - 1) // columns  # Calculate required rows
        for i, (text, command, speak_text) in enumerate(buttons):
            row, col = divmod(i, columns)
            btn = tk.Button(
                grid_frame,
                text=text,
                font=("Arial Black", 36),
                bg="light blue",
                fg="black",
                activebackground="yellow",
                activeforeground="black",
                command=lambda c=command, s=speak_text: self.on_select(c, s),
            )
            btn.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            self.buttons.append(btn)  # Add button to scanning list

        for i in range(rows):
            grid_frame.rowconfigure(i, weight=1)
        for j in range(columns):
            grid_frame.columnconfigure(j, weight=1)

        self.bind("<KeyPress-space>", self.parent.track_spacebar_hold)
        self.bind("<KeyRelease-space>", self.parent.reset_spacebar_hold)
        self.bind("<KeyRelease-Return>", self.parent.select_button)

    def volume_up(self):
        """Increase system volume."""
        for _ in range(4):  # Increase volume by ~10%
            ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
            time.sleep(0.05)
        speak("Volume increased")

    def volume_down(self):
        """Decrease system volume."""
        for _ in range(4):  # Decrease volume by ~10%
            ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
            time.sleep(0.05)
        speak("Volume decreased")

    def turn_off_display(self):
        try:
            ctypes.windll.user32.SendMessageW(
                0xFFFF, 0x112, 0xF170, 2
            )  # Turn off display
            speak("Display turned off")
        except Exception as e:
            speak("Failed to turn off display")
            print(f"Turn Off Display Error: {e}")

    def sleep_timer(self):
        """Set a 60-minute sleep timer."""
        try:
            # Set a sleep timer for 3600 seconds (60 minutes)
            subprocess.run("shutdown /s /t 3600", shell=True)
            speak("Sleep timer set for 60 minutes")
        except Exception as e:
            speak("Failed to set sleep timer")
            print(f"Error setting sleep timer: {e}")

    def cancel_sleep_timer(self):
        """Cancel the sleep timer."""
        try:
            # Cancel the shutdown timer
            subprocess.run("shutdown /a", shell=True)
            speak("Sleep timer canceled")
        except Exception as e:
            speak("Failed to cancel sleep timer")
            print(f"Error canceling sleep timer: {e}")

    def lock_computer(self):
        """Lock the computer."""
        ctypes.windll.user32.LockWorkStation()
        speak("Computer locked")

    def restart_computer(self):
        """Restart the computer."""
        subprocess.run("shutdown /r /t 0")
        speak("Restarting computer")

    def shut_down_computer(self):
        """Shut down the computer."""
        subprocess.run("shutdown /s /t 0")
        speak("Shutting down the computer")


class EntertainmentMenuPage(MenuFrame):
    def __init__(self, parent):
        super().__init__(parent, "Entertainment")
        self.buttons = []
        self.current_button_index = 0
        self.selection_enabled = True

        buttons = [
            ("Back", lambda: parent.show_frame(MainMenuPage), "Back to Main Menu"),
            (
                "Movies",
                lambda: self.parent.show_frame(
                    lambda p: LibraryMenu(
                        p,
                        self.parent.organized_links.get("movies", {}),
                        "genre",
                        parent_key="movies",
                    )
                ),
                "Movies",
            ),
            (
                "Shows",
                lambda: self.parent.show_frame(
                    lambda p: LibraryMenu(
                        p,
                        self.parent.organized_links.get("shows", {}),
                        "genre",
                        parent_key="shows",
                    )
                ),
                "Shows",
            ),
            (
                "Audio",
                lambda: self.parent.show_frame(
                    lambda p: LibraryMenu(
                        p, self._get_audio_data(), "genre", parent_key="audio"
                    )
                ),
                "Audio",
            ),
            (
                "Live Streams",
                lambda: self.parent.show_frame(
                    lambda p: LibraryMenu(
                        p,
                        self.parent.organized_links.get("live", {}),
                        "genre",
                        parent_key="live",
                    )
                ),
                "Live Streams",
            ),
            ("Games", lambda: parent.show_frame(GamesPage), "Games"),
        ]

        self.create_button_grid(buttons, columns=2)

    def _get_audio_data(self):
        """Merge music, audiobooks, and podcast types into a unified 'audio' group."""
        data = {}
        for k in ("music", "audiobooks", "podcast"):
            entries = self.parent.organized_links.get(k, {})
            for genre, items in entries.items():
                data.setdefault(genre, []).extend(items)
        return data

    def create_button_grid(self, buttons, columns=5):
        """Creates a grid layout for buttons with a dynamic number of rows and columns."""
        grid_frame = tk.Frame(self, bg="black")
        grid_frame.pack(expand=True, fill="both")

        rows = (len(buttons) + columns - 1) // columns  # Calculate required rows
        for i, (text, command, speak_text) in enumerate(buttons):
            row, col = divmod(i, columns)
            btn = tk.Button(
                grid_frame,
                text=text,
                font=("Arial Black", 36),
                bg="light blue",
                fg="black",
                activebackground="yellow",
                activeforeground="black",
                command=lambda c=command, s=speak_text: self.on_select(c, s),
            )
            btn.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            self.buttons.append(btn)  # Add button to scanning list

        for i in range(rows):
            grid_frame.rowconfigure(i, weight=1)
        for j in range(columns):
            grid_frame.columnconfigure(j, weight=1)

    def on_select(self, command, speak_text):
        """Handle button selection with scanning."""
        command()
        if speak_text:
            speak(speak_text)

    def coming_soon(self):
        """Notify that this feature is coming soon."""
        speak("This feature is coming soon")


# Import moved to top of file


class GamesPage(MenuFrame):
    """Games menu that auto‑populates from Python scripts inside ./games."""

    GAMES_DIR = os.path.join(os.path.dirname(__file__), "games")

    def __init__(self, parent):
        super().__init__(parent, "Games")
        self.parent = parent

        # Build button list dynamically: Back + discovered games
        buttons = [("Back", lambda: parent.show_frame(EntertainmentMenuPage), "Back")]
        buttons.extend(self._discover_games())

        self.create_button_grid(buttons)

    # ───────────────────────── helpers ──────────────────────────
    def _discover_games(self):
        """Return a list of (label, command, speak_text) tuples for each game script."""
        games = []

        if not os.path.isdir(self.GAMES_DIR):
            print(f"[GamesPage] Folder not found: {self.GAMES_DIR}")
            return games

        for file in sorted(os.listdir(self.GAMES_DIR)):
            # Only include Python scripts; skip dunders and non‑py files
            if not file.endswith(".py") or file.startswith("__"):
                continue

            script_path = os.path.join(self.GAMES_DIR, file)
            title = self._filename_to_title(file)
            cmd = partial(self.open_game, script_path, title)
            games.append((title, cmd, title))

        return games

    @staticmethod
    def _filename_to_title(filename):
        """Convert "tic_tac_toe.py" → "Tic Tac Toe"."""
        base = os.path.splitext(filename)[0]
        return base.replace("_", " ").title()

    # ───────────────────────── UI helpers ───────────────────────
    def create_button_grid(self, buttons, columns=3):
        grid = tk.Frame(self, bg="black")
        grid.pack(expand=True, fill="both")

        self.buttons = []
        rows = (len(buttons) + columns - 1) // columns

        for i, (text, command, speak_text) in enumerate(buttons):
            r, c = divmod(i, columns)
            btn = tk.Button(
                grid,
                text=text,
                font=("Arial Black", 36),
                bg="light blue",
                fg="black",
                activebackground="yellow",
                activeforeground="black",
                command=lambda c=command, s=speak_text: self.on_select(c, s),
            )
            btn.grid(row=r, column=c, sticky="nsew", padx=10, pady=10)
            self.buttons.append(btn)

        for r in range(rows):
            grid.rowconfigure(r, weight=1)
        for c in range(columns):
            grid.columnconfigure(c, weight=1)

    # ───────────────────────── actions ──────────────────────────
    def open_game(self, script_path, title):
        try:
            print(f"[GamesPage] Launching: {title} → {script_path}")
            subprocess.Popen(
                [sys.executable, script_path], cwd=os.path.dirname(script_path)
            )
            self.parent.destroy()  # Close main app so game runs fullscreen
        except Exception as e:
            print(f"[GamesPage] Failed to open {title}: {e}")
            speak("Unable to launch the selected game.")


# Imports moved to top of file
from tkinter.font import Font


class LibraryMenu(MenuFrame):
    def __init__(self, parent, data, level, parent_key=None):
        """
        data:
          - For level "genre": a dict mapping genre → list of entries.
          - For level "final": a list of entries (each with a "title" key).
        level:
          - "genre" for the first level (choose a genre)
          - "final" for the final step (choose a show)
        parent_key:
          - For "genre": (optional) a type (e.g. "movies")
          - For "final": the chosen genre name
        """
        self.data = data
        self.level = level
        self.parent_key = parent_key
        self.page = 0  # current page index
        self.page_size = 7  # show 7 selection buttons per page

        # Set the window title based on the level.
        if self.level == "genre":
            title = f"Select Genre{(' (' + parent_key.capitalize() + ')') if parent_key else ''}"
        elif self.level == "final":
            title = f"Select Show ({parent_key})"
        else:
            title = "Library"
        super().__init__(parent, title)

        # Use a container frame for our grid.
        self.container = tk.Frame(self, bg="black")
        self.container.pack(expand=True, fill="both")
        self.reload_buttons()

    def adjust_font_size(self, button, max_width=250, min_font_size=18):
        button.update_idletasks()  # Update widget geometry
        text = button.cget("text")
        # Use the persistent font family and weight
        font_family = "Arial Black"
        font_size = 32

        while font_size >= min_font_size:
            test_font = Font(family=font_family, size=font_size)
            if test_font.measure(text) <= max_width:
                break
            font_size -= 2

        # Update the persistent font or create a new one with the same family and desired size.
        new_font = Font(family=font_family, size=font_size)
        button.config(font=new_font)

    def adjust_all_buttons(self):
        """Call adjust_font_size on each button in the current menu."""
        for btn in self.buttons:
            self.adjust_font_size(
                btn,
                max_width=250,
                min_font_size=18,
            )

    def reload_buttons(self):
        # Clear the container.
        for widget in self.container.winfo_children():
            widget.destroy()

        button_list = []

        # Determine the Back button command.
        # If we're not on the first page, the Back button will go to the previous page;
        # otherwise, it returns to the previous (Entertainment) menu.
        if self.page > 0:
            back_command = self.previous_page
        else:

            def back_command():
                return self.parent.show_previous_menu()

        back_btn = tk.Button(
            self.container,
            text="Back",
            font=("Arial Black", 36),
            bg="light blue",
            fg="black",
            command=back_command,
            wraplength=700,  # Allow wrapping into two lines if needed
            justify="center",
        )
        button_list.append(back_btn)

        # Build the keys list based on the current level.
        if self.level == "genre":
            keys = sorted(self.data.keys())
        elif self.level == "final":
            keys = sorted(entry["title"] for entry in self.data)
        else:
            keys = []

        # Determine the slice for the current page.
        start = self.page * self.page_size
        end = start + self.page_size
        page_keys = keys[start:end]

        for key in page_keys:
            btn = tk.Button(
                self.container,
                text=key,
                font=("Arial Black", 36),
                bg="light blue",
                fg="black",
                command=lambda k=key: self.on_select(k),
                wraplength=700,  # Allow wrapping to use two lines
                justify="center",
            )
            button_list.append(btn)

        # If there are more keys beyond this page, add a Next button.
        if end < len(keys):
            next_btn = tk.Button(
                self.container,
                text="Next",
                font=("Arial Black", 36),
                bg="light blue",
                fg="black",
                command=self.next_page,
                wraplength=700,
                justify="center",
            )
            button_list.append(next_btn)

        # Arrange all buttons in a grid (using 3 columns).
        num_cols = 3
        num_buttons = len(button_list)
        num_rows = (num_buttons + num_cols - 1) // num_cols

        for idx, btn in enumerate(button_list):
            row = idx // num_cols
            col = idx % num_cols
            btn.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)

        for r in range(num_rows):
            self.container.grid_rowconfigure(r, weight=1)
        for c in range(num_cols):
            self.container.grid_columnconfigure(c, weight=1)

        # Save the new button list for scanning.
        self.buttons = button_list

        # Update the parent's scanning state (after a short delay to allow the UI to update).
        self.after(50, self.update_scanning)
        # After a short delay, adjust the font sizes on all buttons.
        self.after(100, self.adjust_all_buttons)

    def update_scanning(self):
        self.parent.buttons = self.buttons
        self.parent.current_button_index = 0
        self.parent.highlight_button(0)

    def next_page(self):
        """Advance to the next page and reload the buttons."""
        self.page += 1
        self.reload_buttons()

    def previous_page(self):
        """Go back one page and reload the buttons (if not on the first page)."""
        if self.page > 0:
            self.page -= 1
            self.reload_buttons()
        else:
            self.parent.show_previous_menu()

    def on_select(self, key):
        """
        Dispatch the selection based on the current level:
          - For "genre": directly show a final menu listing all shows in that genre.
          - For "final": locate the matching entry and open its URL.
        """
        if self.level == "genre":
            # Instead of grouping entries by their first letter, directly show the list of shows.
            new_data = self.data[
                key
            ]  # This is a list of entries for the selected genre.
            self.parent.show_frame(
                lambda p: LibraryMenu(p, new_data, "final", parent_key=key)
            )
        elif self.level == "final":
            # Find the entry with a matching title and open its link.
            for entry in self.data:
                if entry["title"] == key:
                    self.open_link(entry)
                    break


# Run the App
if __name__ == "__main__":
    app = App()
    app.mainloop()
