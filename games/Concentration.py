import ctypes
from functools import partial
import os
import random
import subprocess
import sys
import threading
import time
import tkinter as tk

import pyttsx3
import win32gui


class MemoryGame(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Memory Game for Ben")
        self.attributes("-fullscreen", True)  # Fullscreen window
        self.configure(bg="red")  # Overall background is red

        # Focus and Start Menu monitoring threads
        self.monitor_focus_thread = threading.Thread(
            target=self.monitor_focus, daemon=True
        )
        self.monitor_focus_thread.start()
        self.monitor_start_menu_thread = threading.Thread(
            target=self.monitor_start_menu, daemon=True
        )
        self.monitor_start_menu_thread.start()

        # Initialize TTS engine
        self.tts_engine = pyttsx3.init()
        self.tts_lock = threading.Lock()

        # Player mode state
        self.two_player_mode = False
        self.current_player = 1
        self.match_colors = {
            1: "green",
            2: "#FF00FF",
        }  # Player 1: green, Player 2: pink

        # Mapping from card symbol to a spoken name
        self.symbol_names = {
            "●": "circle",
            "■": "square",
            "▲": "triangle",
            "◆": "diamond",
            "★": "star",
            "☀": "sun",
            "☂": "umbrella",
            "♣": "club",
            "♠": "spade",
            "♥": "heart",
            "♦": "diamond",
            "☯": "yin yang",
            "☮": "peace",
            "✿": "flower",
            "☘": "clover",
            "⚽": "soccer ball",
            "☕": "coffee",
            "✈": "airplane",
        }

        # Top frame for window controls
        top_frame = tk.Frame(self, bg="lightgray")
        top_frame.pack(side="top", fill="x")
        minimize_btn = tk.Button(
            top_frame, text="_", command=self.iconify, font=("Arial", 12)
        )
        minimize_btn.pack(side="right", padx=5, pady=5)
        close_btn = tk.Button(
            top_frame, text="X", command=self.on_exit, font=("Arial", 12)
        )
        close_btn.pack(side="right", padx=5, pady=5)

        # Container frame for switching screens
        self.container = tk.Frame(self, bg="red")
        self.container.pack(expand=True, fill="both")
        self.current_frame = None

        # Scanning state
        self.current_mode = None
        self.scan_mode = "row"
        self.current_row = 0
        self.current_col = 0
        self.menu_buttons = []
        self.menu_scan_index = 0
        self.pause_buttons = []
        self.pause_scan_index = 0
        self.pause_just_opened = False
        self.space_press_time = None
        self.spacebar_held = False
        self.space_backward_active = False
        self.space_backwards_timer_id = None
        self.return_press_time = None
        self.return_held = False
        self.return_pause_timer_id = None
        self.pause_triggered = False

        # Game state
        self.buttons = {}
        self.rows = 0
        self.cols = 0
        self.inactive_cell = False
        self.first_selection = None
        self.busy = False
        self.matched_pairs = 0
        self.start_time = 0

        # Key bindings
        self.bind("<KeyPress-space>", self.on_space_press)
        self.bind("<KeyRelease-space>", self.on_space_release)
        self.bind("<KeyPress-Return>", self.on_return_press)
        self.bind("<KeyRelease-Return>", self.on_return_release)

        # Show player mode menu first
        self.show_player_mode_menu()

    # Monitoring focus and start menu
    def monitor_focus(self):
        while True:
            time.sleep(0.5)
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd != self.winfo_id():
                    self.force_focus()
            except Exception as e:
                print(f"Focus monitoring error: {e}")

    def force_focus(self):
        try:
            self.iconify()
            self.deiconify()
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception as e:
            print(f"Error forcing focus: {e}")

    def send_esc_key(self):
        ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)

    def is_start_menu_open(self):
        hwnd = win32gui.GetForegroundWindow()
        class_name = win32gui.GetClassName(hwnd)
        return class_name in ["Shell_TrayWnd", "Windows.UI.Core.CoreWindow"]

    def monitor_start_menu(self):
        while True:
            try:
                if self.is_start_menu_open():
                    self.send_esc_key()
            except Exception as e:
                print(f"Error in monitor_start_menu: {e}")
            time.sleep(0.5)

    # TTS helper methods
    def say_text(self, text):
        threading.Thread(target=self._speak, args=(text,)).start()

    def _speak(self, text):
        with self.tts_lock:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()

    def create_tts_button(self, parent, text, command, font_size=36, pady=10):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Arial", font_size),
            bg="gray",
            activebackground="gray",
        )
        btn.pack(pady=pady)
        btn.bind("<Enter>", lambda e: self.say_text(text))
        return btn

    # ------- Main Menus -------
    def show_player_mode_menu(self):
        self.current_mode = "main_menu"
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = tk.Frame(self.container, bg="red")
        self.current_frame.pack(expand=True, fill="both")
        title = tk.Label(
            self.current_frame,
            text="CONCENTRATION",
            font=("Arial Black", 60),
            bg="red",
            fg="white",
        )
        title.pack(pady=20)
        self.menu_buttons = []
        btn = self.create_tts_button(
            self.current_frame, "Single Player", lambda: self.select_player_mode(False)
        )
        self.menu_buttons.append(btn)
        btn = self.create_tts_button(
            self.current_frame, "Two Player", lambda: self.select_player_mode(True)
        )
        self.menu_buttons.append(btn)
        btn = self.create_tts_button(self.current_frame, "Exit", self.on_exit)
        self.menu_buttons.append(btn)
        self.menu_scan_index = 0
        self.update_menu_scan_highlight()

    def select_player_mode(self, two_player):
        self.two_player_mode = two_player
        self.show_difficulty_menu()

    def show_difficulty_menu(self):
        self.current_mode = "main_menu"
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = tk.Frame(self.container, bg="red")
        self.current_frame.pack(expand=True, fill="both")
        title = tk.Label(
            self.current_frame,
            text="SELECT DIFFICULTY",
            font=("Arial Black", 60),
            bg="red",
            fg="white",
        )
        title.pack(pady=20)
        self.menu_buttons = []
        btn = self.create_tts_button(
            self.current_frame, "Easy", lambda: self.start_game("easy")
        )
        self.menu_buttons.append(btn)
        btn = self.create_tts_button(
            self.current_frame, "Medium", lambda: self.start_game("medium")
        )
        self.menu_buttons.append(btn)
        btn = self.create_tts_button(
            self.current_frame, "Hard", lambda: self.start_game("hard")
        )
        self.menu_buttons.append(btn)
        btn = self.create_tts_button(
            self.current_frame, "Back", self.show_player_mode_menu
        )
        self.menu_buttons.append(btn)
        self.menu_scan_index = 0
        self.update_menu_scan_highlight()

    def update_menu_scan_highlight(self):
        for idx, btn in enumerate(self.menu_buttons):
            if idx == self.menu_scan_index:
                btn.config(bg="white", activebackground="white")
            else:
                btn.config(bg="gray", activebackground="gray")
        if self.menu_buttons:
            self.say_text(self.menu_buttons[self.menu_scan_index].cget("text"))

    def move_menu_scan_forward(self):
        self.menu_scan_index = (self.menu_scan_index + 1) % len(self.menu_buttons)
        self.update_menu_scan_highlight()

    def move_menu_scan_backward(self):
        self.menu_scan_index = (self.menu_scan_index - 1) % len(self.menu_buttons)
        self.update_menu_scan_highlight()

    # ------- Pause Menu -------
    def show_pause_screen(self):
        self.current_mode = "pause"
        self.return_held = False
        self.pause_just_opened = True
        self.pause_frame = tk.Frame(self.current_frame, bg="black")
        self.pause_frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            self.pause_frame,
            text="Pause Menu",
            font=("Arial", 40),
            fg="white",
            bg="black",
        ).pack(pady=20)
        self.pause_buttons = []
        btn = self.create_tts_button(
            self.pause_frame, "Continue Game", self.continue_game
        )
        self.pause_buttons.append(btn)
        btn = self.create_tts_button(
            self.pause_frame, "Return to Menu", self.return_to_menu
        )
        self.pause_buttons.append(btn)
        btn = self.create_tts_button(self.pause_frame, "Exit", self.on_exit)
        self.pause_buttons.append(btn)
        self.pause_scan_index = 0
        self.update_pause_menu_scan_highlight()

    def update_pause_menu_scan_highlight(self):
        for idx, btn in enumerate(self.pause_buttons):
            if idx == self.pause_scan_index:
                btn.config(bg="white", activebackground="white")
            else:
                btn.config(bg="gray", activebackground="gray")
        if self.pause_buttons:
            self.say_text(self.pause_buttons[self.pause_scan_index].cget("text"))

    def move_pause_menu_scan_forward(self):
        self.pause_scan_index = (self.pause_scan_index + 1) % len(self.pause_buttons)
        self.update_pause_menu_scan_highlight()

    def move_pause_menu_scan_backward(self):
        self.pause_scan_index = (self.pause_scan_index - 1) % len(self.pause_buttons)
        self.update_pause_menu_scan_highlight()

    def continue_game(self):
        self.pause_frame.destroy()
        self.current_mode = "game"

    def return_to_menu(self):
        self.pause_frame.destroy()
        self.show_player_mode_menu()

    # ------- Game Setup -------
    def start_game(self, difficulty):
        self.current_mode = "game"
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.scan_mode = "row"
        self.current_frame = tk.Frame(self.container, bg="red")
        self.current_frame.pack(expand=True, fill="both")
        grid_frame = tk.Frame(self.current_frame, bg="red")
        grid_frame.pack(expand=False)
        if difficulty == "easy":
            self.rows, self.cols = 4, 4
        elif difficulty == "medium":
            self.rows, self.cols = 4, 5
        else:
            self.rows, self.cols = 6, 5
        total_cells = self.rows * self.cols
        if total_cells % 2 != 0:
            active_cells = total_cells - 1
            self.inactive_cell = True
            inactive_index = random.randint(0, total_cells - 1)
        else:
            active_cells = total_cells
            self.inactive_cell = False
            inactive_index = None
        num_pairs = active_cells // 2
        card_designs = [
            ("●", "blue"),
            ("■", "red"),
            ("▲", "lime"),
            ("◆", "purple"),
            ("★", "gold"),
            ("☀", "yellow"),
            ("☂", "cyan"),
            ("♣", "lime"),
            ("♠", "black"),
            ("♥", "red"),
            ("♦", "orange"),
            ("☯", "black"),
            ("☮", "purple"),
            ("✿", "violet"),
            ("☘", "lime"),
            ("⚽", "black"),
            ("☕", "brown"),
            ("✈", "navy"),
        ]
        random.shuffle(card_designs)
        selected_designs = card_designs[:num_pairs]
        cards = selected_designs * 2
        random.shuffle(cards)
        self.buttons = {}
        self.first_selection = None
        self.busy = False
        self.matched_pairs = 0
        self.start_time = time.time()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        cell_width = screen_width // self.cols
        cell_height = screen_height // self.rows
        card_index = 0
        for r in range(self.rows):
            for c in range(self.cols):
                cell_frame = tk.Frame(
                    grid_frame, width=cell_width, height=cell_height, bg="red"
                )
                cell_frame.grid(row=r, column=c)
                cell_frame.grid_propagate(False)
                cell_idx = r * self.cols + c
                if self.inactive_cell and cell_idx == inactive_index:
                    lbl = tk.Label(cell_frame, text="", bg="gray", relief="sunken")
                    lbl.place(
                        relx=0.5,
                        rely=0.5,
                        anchor="center",
                        width=cell_width,
                        height=cell_height,
                    )
                else:
                    symbol, color = cards[card_index]
                    card_index += 1
                    btn = tk.Button(
                        cell_frame,
                        text="",
                        font=("Arial", 48),
                        bg="dark gray",
                        fg="black",
                        activebackground="dark gray",
                        bd=2,
                        relief="solid",
                        command=partial(self.reveal_card, r, c),
                    )
                    btn.place(
                        relx=0.5,
                        rely=0.5,
                        anchor="center",
                        width=cell_width,
                        height=cell_height,
                    )
                    self.buttons[(r, c)] = {
                        "button": btn,
                        "value": (symbol, color),
                        "revealed": False,
                        "matched": False,
                    }
        self.current_row, self.current_col = 0, 0
        # Announce first turn
        if self.two_player_mode:
            self.current_player = 1
            self.say_text("Player One's Turn")
        self.update_scan_highlight()

    # ------- Scanning -------
    def update_scan_highlight(self):
        for (r, c), info in self.buttons.items():
            btn = info["button"]
            if info.get("matched"):
                if self.two_player_mode and info.get("matched_by") in self.match_colors:
                    default_color = self.match_colors[info.get("matched_by")]
                else:
                    default_color = "green"
            else:
                default_color = "dark gray"
            if self.scan_mode == "row":
                if r == self.current_row:
                    btn.config(bg="white", activebackground="white")
                else:
                    btn.config(bg=default_color, activebackground=default_color)
            elif r == self.current_row and c == self.current_col:
                btn.config(bg="white", activebackground="white")
            else:
                btn.config(bg=default_color, activebackground=default_color)

    def move_scan_forward(self):
        if self.scan_mode == "row":
            self.current_row = (self.current_row + 1) % self.rows
        else:
            next_col = self.current_col
            for _ in range(self.cols):
                next_col = (next_col + 1) % self.cols
                if (self.current_row, next_col) in self.buttons:
                    self.current_col = next_col
                    break
        self.update_scan_highlight()

    def move_scan_backward(self):
        if self.scan_mode == "row":
            self.current_row = (self.current_row - 1) % self.rows
        else:
            next_col = self.current_col
            for _ in range(self.cols):
                next_col = (next_col - 1) % self.cols
                if (self.current_row, next_col) in self.buttons:
                    self.current_col = next_col
                    break
        self.update_scan_highlight()

    # ------- Key Handlers -------
    def on_space_press(self, event):
        if self.current_mode not in ("game", "main_menu", "pause"):
            return
        if self.spacebar_held:
            return
        self.space_press_time = time.time()
        self.spacebar_held = True
        self.space_backward_active = False
        self.space_backwards_timer_id = self.after(3000, self.space_long_hold)

    def space_long_hold(self):
        if self.spacebar_held:
            self.space_backward_active = True
            if self.current_mode == "game":
                self.move_scan_backward()
            elif self.current_mode == "main_menu":
                self.move_menu_scan_backward()
            else:
                self.move_pause_menu_scan_backward()
            self.space_backwards_timer_id = self.after(2000, self.space_long_hold)

    def on_space_release(self, event):
        if self.current_mode not in ("game", "main_menu", "pause"):
            return
        duration = time.time() - (self.space_press_time or 0)
        if self.space_backwards_timer_id:
            self.after_cancel(self.space_backwards_timer_id)
            self.space_backwards_timer_id = None
        self.spacebar_held = False
        if not self.space_backward_active and 0.1 <= duration < 3:
            if self.current_mode == "game":
                self.move_scan_forward()
            elif self.current_mode == "main_menu":
                self.move_menu_scan_forward()
            else:
                self.move_pause_menu_scan_forward()
        self.space_backward_active = False

    def on_return_press(self, event):
        if self.current_mode not in ("game", "main_menu", "pause"):
            return
        if self.return_held:
            return
        self.return_press_time = time.time()
        self.return_held = True
        if self.current_mode == "game":
            self.return_pause_timer_id = self.after(3000, self.return_long_hold)

    def return_long_hold(self):
        if self.return_held:
            self.pause_triggered = True
            self.show_pause_screen()

    def on_return_release(self, event):
        if self.current_mode not in ("game", "main_menu", "pause"):
            return
        duration = time.time() - (self.return_press_time or 0)
        if self.current_mode == "pause" and self.pause_just_opened:
            self.pause_just_opened = False
            self.return_held = False
            return
        if self.current_mode == "game":
            if self.return_pause_timer_id:
                self.after_cancel(self.return_pause_timer_id)
                self.return_pause_timer_id = None
            self.return_held = False
            if self.pause_triggered:
                self.pause_triggered = False
                return
            if 0.1 <= duration < 3:
                if self.scan_mode == "row":
                    self.scan_mode = "col"
                    for col in range(self.cols):
                        if (self.current_row, col) in self.buttons:
                            self.current_col = col
                            break
                    self.update_scan_highlight()
                else:
                    self.reveal_card(self.current_row, self.current_col)
                    self.scan_mode = "row"
                    self.update_scan_highlight()
        elif self.current_mode == "main_menu":
            self.return_held = False
            self.menu_buttons[self.menu_scan_index].invoke()
        else:
            self.return_held = False
            self.pause_buttons[self.pause_scan_index].invoke()

    # ------- Game Logic -------
    def reveal_card(self, r, c):
        if self.busy:
            return
        card_info = self.buttons.get((r, c))
        if not card_info or card_info.get("matched") or card_info.get("revealed"):
            return
        symbol, color = card_info["value"]
        card_info["button"].config(text=symbol, fg=color, font=("Arial", 172))
        card_info["revealed"] = True
        self.say_text(f"{color} {self.symbol_names.get(symbol, symbol)}")
        if self.first_selection is None:
            self.first_selection = (r, c)
        else:
            fr, fc = self.first_selection
            first_card = self.buttons.get((fr, fc))
            if first_card and first_card["value"] == card_info["value"]:
                # Match!
                match_color = (
                    self.match_colors[self.current_player]
                    if self.two_player_mode
                    else "green"
                )
                for card in (first_card, card_info):
                    card["matched"] = True
                    if self.two_player_mode:
                        card["matched_by"] = self.current_player
                self.matched_pairs += 1
                self.after(100, lambda: self.say_text("that's a match!"))
                first_card["button"].config(
                    bg=match_color, activebackground=match_color
                )
                card_info["button"].config(bg=match_color, activebackground=match_color)
                self.first_selection = None
                if self.two_player_mode:
                    # Player gets another turn after a match
                    self.say_text(f"Player {self.current_player}'s Turn")
                if self.matched_pairs == len(self.buttons) // 2:
                    elapsed = time.time() - self.start_time
                    self.show_win_message(elapsed)
            else:
                self.busy = True
                self.after(1000, self.hide_cards, (fr, fc), (r, c))
                self.first_selection = None

    def hide_cards(self, pos1, pos2):
        for pos in (pos1, pos2):
            card = self.buttons.get(pos)
            if card:
                card["button"].config(text="", font=("Arial", 48))
                card["revealed"] = False
        self.busy = False
        if self.two_player_mode:
            # Switch turn
            self.current_player = 2 if self.current_player == 1 else 1
            self.say_text(f"Player {self.current_player}'s Turn")

    def show_win_message(self, elapsed):
        for widget in self.current_frame.winfo_children():
            widget.destroy()
        win_msg = f"Congratulations! You won in {elapsed:.2f} seconds!"
        self.say_text(win_msg)
        tk.Label(
            self.current_frame,
            text=win_msg,
            font=("Arial Black", 42),
            fg="purple",
            bg="yellow",
        ).place(relx=0.5, rely=0.5, anchor="center")
        self.after(5000, self.show_player_mode_menu)

    def on_exit(self):
        self.destroy()
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            script_path = os.path.join(project_root, "Comm-v9.py")
            subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            print("Failed to launch Comm-v9.py:", e)


if __name__ == "__main__":
    app = MemoryGame()
    app.mainloop()
