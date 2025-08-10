# streaming_library.py

import os
import sys
import threading
import tkinter as tk
from tkinter.font import Font
import pandas as pd
import json
import pyttsx3
import queue
from collections import defaultdict
import time
import subprocess
import pyautogui
import win32gui
import win32con
import win32api
import platform

# --- SETTINGS ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LAST_WATCHED_FILE = os.path.join(DATA_DIR, "last_watched.json")
EXCEL_PATH = os.path.join(DATA_DIR, "shows.xlsx")
BUTTONS_PER_PAGE = 7
GRID_COLS = 3
CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"

# --- TTS ---
tts_engine = pyttsx3.init()
tts_queue = queue.Queue()

def tts_worker():
    while True:
        text = tts_queue.get()
        if text is None:
            break
        tts_engine.say(text)
        tts_engine.runAndWait()

tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()

def speak(text):
    tts_queue.put(text)

# --- DATA LOAD ---
def load_last_watched():
    if os.path.exists(LAST_WATCHED_FILE):
        try:
            with open(LAST_WATCHED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_last_watched(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LAST_WATCHED_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_links():
    try:
        df = pd.read_excel(EXCEL_PATH)
    except Exception as e:
        print(f"[ERROR] Failed to read {EXCEL_PATH}: {e}")
        return {}
    links = df.to_dict(orient="records")
    organized = defaultdict(lambda: defaultdict(list))
    for entry in links:
        t = entry.get("type", "misc").lower()
        genre = entry.get("genre", "misc").lower()
        organized[t][genre].append(entry)
    for t in organized:
        for genre in organized[t]:
            organized[t][genre].sort(key=lambda e: e.get("title", ""))
    return organized

# --- STREAMING PLATFORM HANDLERS ---
def open_in_chrome(show_name, url, persistent=True):
    if persistent:
        last = load_last_watched()
        if show_name in last:
            url = last[show_name]
    args = [
        CHROME_PATH,
        "--start-fullscreen",
        url
    ]
    try:
        subprocess.Popen(args, shell=False)
        print(f"[LAUNCH] Chrome → {url}")
    except Exception as e:
        print(f"[ERROR] launching Chrome: {e}")

def open_and_click(show_name, url, x_offset=0, y_offset=0):
    open_in_chrome(show_name, url, persistent=False)
    time.sleep(5)
    hwnd = win32gui.GetForegroundWindow()
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    screen_width, screen_height = pyautogui.size()
    click_x = (screen_width // 2) + x_offset
    click_y = (screen_height // 2) + y_offset
    pyautogui.click(click_x, click_y)
    time.sleep(2)

def open_pluto(show_name, pluto_url):
    open_in_chrome(show_name, pluto_url)
    time.sleep(7)
    hwnd = win32gui.GetForegroundWindow()
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(6)
    pyautogui.press('m')
    time.sleep(2)
    pyautogui.press('f')
    print("Pluto.TV interaction complete.")

def open_spotify(playlist_url):
    if not os.path.exists(CHROME_PATH):
        os.startfile(playlist_url)
    else:
        args = [
            CHROME_PATH,
            "--autoplay-policy=no-user-gesture-required",
            "--start-fullscreen",
            playlist_url
        ]
        subprocess.Popen(args)
    time.sleep(12)
    pyautogui.click((752, 665))
    time.sleep(2)
    pyautogui.hotkey('alt', 's')
    print("[DEBUG] Sent Alt+S to shuffle.")

def open_youtube(youtube_url, show_name):
    open_in_chrome(show_name, youtube_url, persistent=False)
    time.sleep(5)
    pyautogui.press('f')
    print("Sent keys: f")

def open_plex_movies(plex_url, show_name):
    open_in_chrome(show_name, plex_url, persistent=False)
    time.sleep(7)
    pyautogui.press('x')
    time.sleep(2)
    pyautogui.press('enter')
    time.sleep(2)
    pyautogui.press('p')
    print("Sent keys: x, enter, p.")

def open_plex(plex_url, show_name):
    open_in_chrome(show_name, plex_url, persistent=True)
    time.sleep(7)
    pyautogui.press('x')
    time.sleep(2)
    pyautogui.press('enter')
    time.sleep(2)
    pyautogui.press('p')
    print("Sent keys: x, enter, p.")

# --- OVERLAY PLAYER CONTROLS ---
HOTKEYS = {
    "netflix": {
        "play_pause": lambda: pyautogui.press('space'),
        "rewind": lambda: pyautogui.press('left'),
        "fast_forward": lambda: pyautogui.press('right'),
        "next_episode": lambda: pyautogui.press('n'),
        "prev_episode": lambda: pyautogui.hotkey('shift', 'p'),
    },
    "hulu": {
        "play_pause": lambda: pyautogui.press('space'),
        "rewind": lambda: pyautogui.press('j'),
        "fast_forward": lambda: pyautogui.press('l'),
        "next_episode": lambda: pyautogui.press('n'),
        "prev_episode": lambda: pyautogui.hotkey('shift', 'p'),
    },
    "disney": {
        "play_pause": lambda: pyautogui.press('space'),
        "rewind": lambda: pyautogui.press('left'),
        "fast_forward": lambda: pyautogui.press('right'),
        "next_episode": lambda: pyautogui.press('n'),
        "prev_episode": lambda: pyautogui.hotkey('shift', 'p'),
    },
    "plex": {
        "play_pause": lambda: pyautogui.press('space'),
        "rewind": lambda: pyautogui.press('left'),
        "fast_forward": lambda: pyautogui.press('right'),
        "next_episode": lambda: pyautogui.press('n'),
        "prev_episode": lambda: pyautogui.press('p'),
    },
    "youtube": {
        "play_pause": lambda: pyautogui.press('k'),
        "rewind": lambda: pyautogui.press('j'),
        "fast_forward": lambda: pyautogui.press('l'),
        "next_episode": lambda: pyautogui.hotkey('shift', 'n'),
        "prev_episode": lambda: pyautogui.hotkey('shift', 'p'),
    },
    "amazon": {
        "play_pause": lambda: pyautogui.press('space'),
        "rewind": lambda: pyautogui.press('left'),
        "fast_forward": lambda: pyautogui.press('right'),
        "next_episode": lambda: pyautogui.press('n'),
        "prev_episode": lambda: pyautogui.hotkey('shift', 'p'),
    },
    "spotify": {
        "play_pause": lambda: pyautogui.press('space'),
        "next_episode": lambda: pyautogui.hotkey('ctrl', 'right'),
        "prev_episode": lambda: pyautogui.hotkey('ctrl', 'left'),
        "rewind": lambda: pyautogui.hotkey('ctrl', 'left'),
        "fast_forward": lambda: pyautogui.hotkey('ctrl', 'right'),
    }
}

def get_platform_from_url(url):
    url = url.lower()
    if "netflix" in url:
        return "netflix"
    if "plex" in url:
        return "plex"
    if "youtube" in url or "youtu.be" in url:
        return "youtube"
    if "amazon" in url:
        return "amazon"
    if "hulu" in url:
        return "hulu"
    if "pluto" in url:
        return "pluto"
    if "spotify" in url:
        return "spotify"
    if "disney" in url:
        return "disney"
    return "generic"

def close_chrome():
    if platform.system() == "Windows":
        os.system("taskkill /IM chrome.exe /F")
    else:
        os.system("pkill chrome")

def focus_chrome():
    def enum_windows_callback(hwnd, hwnds):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            text = win32gui.GetWindowText(hwnd).lower()
            if "chrome" in text:
                hwnds.append(hwnd)
    hwnds = []
    win32gui.EnumWindows(enum_windows_callback, hwnds)
    if hwnds:
        win32gui.ShowWindow(hwnds[0], win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnds[0])
        time.sleep(0.1)

class StreamingControllerOverlay(tk.Toplevel):
    def __init__(self, stream_url, main_window, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform = get_platform_from_url(stream_url)
        self.main_window = main_window
        self.title("Streaming Controls")
        self.configure(bg="black")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(self.calc_geometry())

        self.buttons = []
        self.current_index = 0
        self.selection_enabled = True
        self.debounce = False

        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.create_controls()
        self.bind_events()
        self.after(100, self.force_top)
        self.after(300, self.focus_set)

    def calc_geometry(self):
        w, h = self.winfo_screenwidth(), self.winfo_screenheight()
        bar_height = int(h * 0.12)  # 12% of screen height
        return f"{w}x{bar_height}+0+{h-bar_height}"

    def force_top(self):
        self.lift()
        self.focus_force()
        self.after(500, self.force_top)

    def bind_events(self):
        self.bind("<KeyRelease-space>", self.scan_forward)
        self.bind("<KeyRelease-Return>", self.select_button)

    def create_controls(self):
        labels = [
            ("Play/Pause", self.play_pause),
            ("Previous", self.prev_episode),
            ("Rewind", self.rewind),
            ("Fast Forward", self.fast_forward),
            ("Next", self.next_episode),
            ("Exit", self.on_exit)
        ]
        frame = tk.Frame(self, bg="black")
        frame.pack(expand=True, fill="both")
        self.buttons = []
        for i, (label, command) in enumerate(labels):
            btn = tk.Button(
                frame, text=label, font=("Arial", 20, "bold"), width=9, height=1,
                bg="#002B36" if label!="Exit" else "#900",
                fg="white", activebackground="#B58900" if label!="Exit" else "#E03",
                activeforeground="black", command=command,
                relief="raised", bd=3
            )
            btn.grid(row=0, column=i, padx=7, pady=7, sticky="nsew")
            self.buttons.append(btn)
        for c in range(len(labels)):
            frame.grid_columnconfigure(c, weight=1)
        self.current_index = 0
        self.highlight_button(0)

    def highlight_button(self, index):
        for i, btn in enumerate(self.buttons):
            if i == index:
                btn.config(bg="#FFDC00" if btn['text']!="Exit" else "#FA8072", fg="black")
            else:
                btn.config(bg="#002B36" if btn['text']!="Exit" else "#900", fg="white")
        self.update_idletasks()
        text = self.buttons[index].cget("text")
        print(f"[TTS] Speaking: {text}")
        speak(text)

    def scan_forward(self, event=None):
        if self.debounce: return
        self.debounce = True
        self.current_index = (self.current_index + 1) % len(self.buttons)
        self.after(10, lambda: self.highlight_button(self.current_index))
        self.after(250, self.reset_debounce)

    def select_button(self, event=None):
        if self.debounce: return
        self.debounce = True
        self.buttons[self.current_index].invoke()
        self.after(400, self.reset_debounce)

    def reset_debounce(self):
        self.debounce = False

    def play_pause(self):
        self.send_hotkey("play_pause")
        speak("Play Pause")

    def prev_episode(self):
        self.send_hotkey("prev_episode")
        speak("Previous")

    def rewind(self):
        self.send_hotkey("rewind")
        speak("Rewind")

    def fast_forward(self):
        self.send_hotkey("fast_forward")
        speak("Fast Forward")

    def next_episode(self):
        self.send_hotkey("next_episode")
        speak("Next")

    def on_exit(self):
        close_chrome()
        self.after(400, self.destroy)
        self.after(600, self.restore_main_app)

    def restore_main_app(self):
        if self.main_window:
            self.main_window.deiconify()
            self.main_window.lift()
            self.main_window.focus_force()
            self.main_window.selection_enabled = True
            self.main_window.current_index = 0
            if self.main_window.current_buttons:
                self.main_window.highlight_button(0)
            self.main_window.bind_events()
            self.main_window.focus_set()

    def send_hotkey(self, action):
        plat = self.platform
        if plat in HOTKEYS and action in HOTKEYS[plat]:
            focus_chrome()
            time.sleep(0.1)
            HOTKEYS[plat][action]()

# --- DISPATCH LOGIC ---
def dispatch_stream(entry, main_window):
    title = entry.get("title", "Untitled")
    url = entry.get("url", "")
    content_type = entry.get("type", "shows").lower()
    last = load_last_watched()
    last[title] = url
    save_last_watched(last)

    main_window.selection_enabled = False  # Prevent background scanning

    if content_type == "shows":
        if "plex.tv" in url:
            open_plex(url, title)
        elif "youtube.com" in url or "youtu.be" in url:
            open_youtube(url, title)
        elif "paramountplus.com/live-tv" in url:
            open_and_click(title, url)
        elif "pluto.tv" in url:
            open_pluto(title, url)
        elif "amazon.com" in url:
            open_and_click(title, url)
        else:
            open_in_chrome(title, url)
    elif content_type == "live":
        if "paramountplus.com/live-tv" in url:
            open_and_click(title, url)
        elif "pluto.tv" in url:
            open_pluto(title, url)
        elif "youtube.com" in url or "youtu.be" in url:
            open_youtube(url, title)
        elif "amazon.com" in url:
            open_and_click(title, url)
        else:
            open_in_chrome(title, url)
    elif content_type == "movies":
        if "plex.tv" in url:
            open_plex_movies(url, title)
        elif "amazon.com" in url:
            open_and_click(title, url)
        else:
            open_in_chrome(title, url, persistent=False)
    elif content_type == "music":
        if "spotify.com" in url:
            open_spotify(url)
        else:
            open_in_chrome(title, url, persistent=False)
    elif content_type == "audiobooks":
        if "plex.tv" in url:
            open_plex_movies(url, title)
        else:
            open_in_chrome(title, url, persistent=False)
    else:
        open_in_chrome(title, url, persistent=False)

    overlay = StreamingControllerOverlay(url, main_window)
    overlay.grab_set()
    overlay.mainloop()

# --- MAIN APP ---
class StreamingLibraryApp(tk.Tk):
    def __init__(self, data):
        super().__init__()
        self.title("Streaming Library")
        self.geometry("960x540")
        self.attributes("-fullscreen", True)
        self.configure(bg="black")
        self.data = data
        self.stack = []
        self.current_buttons = []
        self.current_index = 0
        self.selection_enabled = True
        self.page = 0
        self.show_main_menu()
        self.bind_events()

    def bind_events(self):
        self.bind("<KeyRelease-space>", self.scan_forward)
        self.bind("<KeyRelease-Return>", self.select_button)

    def scan_forward(self, event=None):
        if not self.selection_enabled or not self.current_buttons:
            return
        self.selection_enabled = False
        self.current_index = (self.current_index + 1) % len(self.current_buttons)
        self.after(10, lambda: self.highlight_button(self.current_index))
        self.after(250, self.enable_selection)

    def select_button(self, event=None):
        if self.selection_enabled and self.current_buttons:
            self.selection_enabled = False
            self.current_buttons[self.current_index].invoke()
            self.after(400, self.enable_selection)

    def enable_selection(self):
        self.selection_enabled = True

    def highlight_button(self, index):
        for i, btn in enumerate(self.current_buttons):
            if i == index:
                btn.config(bg="yellow", fg="black")
            else:
                btn.config(bg="light blue", fg="black")
        self.update_idletasks()
        text = self.current_buttons[index].cget("text")
        print(f"[TTS] Speaking: {text}")
        speak(text)

    def show_main_menu(self):
        self.stack = []
        self.show_grid_menu(
            title="Streaming Library",
            options=list(self.data.keys()),
            on_select=self.show_genre_menu
        )

    def show_genre_menu(self, content_type):
        self.stack.append(self.show_main_menu)
        genres = list(self.data[content_type].keys())
        self.show_grid_menu(
            title=f"{content_type.capitalize()} Genres",
            options=genres,
            on_select=lambda g: self.show_titles_menu(content_type, g)
        )

    def show_titles_menu(self, content_type, genre):
        self.stack.append(lambda: self.show_genre_menu(content_type))
        entries = self.data[content_type][genre]
        titles = [entry.get("title", "Untitled") for entry in entries]
        self.show_grid_menu(
            title=f"{genre.capitalize()} {content_type.capitalize()}",
            options=titles,
            on_select=lambda t: self.handle_title_selection(content_type, genre, t)
        )

    def handle_title_selection(self, content_type, genre, title):
        entries = self.data[content_type][genre]
        entry = next((e for e in entries if e.get("title") == title), None)
        if entry:
            dispatch_stream(entry, self)

    def show_grid_menu(self, title, options, on_select):
        self.page = getattr(self, 'page', 0)
        total_pages = (len(options) + BUTTONS_PER_PAGE - 1) // BUTTONS_PER_PAGE
        start = self.page * BUTTONS_PER_PAGE
        end = start + BUTTONS_PER_PAGE
        page_options = options[start:end]

        for widget in self.winfo_children():
            widget.destroy()

        tk.Label(self, text=title, font=("Arial Black", 36), fg="white", bg="black").pack(pady=20)

        grid = tk.Frame(self, bg="black")
        grid.pack(expand=True, fill="both")
        self.current_buttons = []

        # Back button (always first)
        btn = tk.Button(grid, text="Back", font=("Arial Black", 24), bg="orange", fg="black", command=self.go_back)
        btn.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.current_buttons.append(btn)

        # Main options
        for i, opt in enumerate(page_options):
            row, col = divmod(i + 1, GRID_COLS)
            btn = tk.Button(
                grid, text=opt, font=("Arial Black", 24), bg="light blue", fg="black",
                command=lambda o=opt: on_select(o)
            )
            btn.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            self.current_buttons.append(btn)

        # Next button (if more pages)
        if end < len(options):
            row, col = divmod(BUTTONS_PER_PAGE + 1, GRID_COLS)
            next_btn = tk.Button(
                grid, text="Next", font=("Arial Black", 24), bg="light blue", fg="black",
                command=self.next_page
            )
            next_btn.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            self.current_buttons.append(next_btn)

        total = len(self.current_buttons)
        rows = (total + GRID_COLS - 1) // GRID_COLS
        for r in range(rows):
            grid.rowconfigure(r, weight=1)
        for c in range(GRID_COLS):
            grid.columnconfigure(c, weight=1)

        self.current_index = 0
        self.selection_enabled = True
        self.after(50, lambda: self.highlight_button(self.current_index))
        self.bind_events()
        self.focus_force()

    def next_page(self):
        self.page += 1
        self.current_buttons[1].invoke()

    def go_back(self):
        self.page = 0
        if self.stack:
            back_func = self.stack.pop()
            back_func()
        else:
            self.destroy()

# --- MAIN ---
if __name__ == "__main__":
    data = load_links()
    if data:
        app = StreamingLibraryApp(data)
        app.mainloop()
    else:
        print("No data to display.")
