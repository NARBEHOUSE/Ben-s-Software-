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


class TicTacToeGame(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tic Tac Toe for Ben")
        self.attributes("-fullscreen", True)
        self.configure(bg="blue")  # Overall background is blue

        # Top frame for close and minimize buttons (always visible)
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

        # Initialize TTS engine and a lock for thread-safety.
        self.tts_engine = pyttsx3.init()
        self.tts_lock = threading.Lock()

        # Scanning state variables:
        self.current_mode = (
            None  # Modes: "main_menu", "game", "pause", "game_over_menu"
        )
        # For main menu and pause menus:
        self.menu_buttons = []
        self.menu_scan_index = 0
        self.pause_buttons = []
        self.pause_scan_index = 0
        self.pause_just_opened = False
        self.game_over_buttons = []
        self.game_over_scan_index = 0
        # For game board scanning (by button order, row-major):
        self.game_board_order = []  # List of (r, c) positions
        self.game_board_scan_index = 0

        # Key hold timing variables:
        self.space_press_time = None
        self.spacebar_held = False
        self.space_backward_active = False
        self.space_backwards_timer_id = None
        self.return_press_time = None
        self.return_held = False
        self.return_pause_timer_id = None
        self.pause_triggered = False

        # Game state variables:
        self.board = {}  # Mapping (r, c) -> "", "X", or "O"
        self.buttons = {}  # Mapping (r, c) -> Button widget
        self.current_turn = "X"  # X always starts; in single-player mode the starting turn will be randomized.
        self.game_mode = None  # "single" or "two"

        # Container frame for switching between screens:
        self.container = tk.Frame(self, bg="blue")
        self.container.pack(expand=True, fill="both")
        self.current_frame = None

        self.monitor_focus_thread = threading.Thread(
            target=self.monitor_focus, daemon=True
        )
        self.monitor_focus_thread.start()

        self.monitor_start_menu_thread = threading.Thread(
            target=self.monitor_start_menu, daemon=True
        )
        self.monitor_start_menu_thread.start()

        # Bind scanning keys:
        self.bind("<KeyPress-space>", self.on_space_press)
        self.bind("<KeyRelease-space>", self.on_space_release)
        self.bind("<KeyPress-Return>", self.on_return_press)
        self.bind("<KeyRelease-Return>", self.on_return_release)

        self.show_main_menu()

    # ---------------- Monitor Focus & Close Start Menu-------------

    def monitor_focus(self):
        """Ensure this application stays in focus."""
        while True:
            time.sleep(0.5)  # Check every 500ms
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd != self.winfo_id():
                    self.force_focus()
            except Exception as e:
                print(f"Focus monitoring error: {e}")

    def force_focus(self):
        """Force this application to the foreground."""
        try:
            self.iconify()
            self.deiconify()
            ctypes.windll.user32.SetForegroundWindow(self.winfo_id())
        except Exception as e:
            print(f"Error forcing focus: {e}")

    def send_esc_key(self):
        """Send the ESC key to close the Start Menu."""
        ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)  # ESC key down
        ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)  # ESC key up
        print("ESC key sent to close Start Menu.")

    def is_start_menu_open(self):
        """Check if the Start Menu is currently open and focused."""
        hwnd = (
            win32gui.GetForegroundWindow()
        )  # Get the handle of the active (focused) window
        class_name = win32gui.GetClassName(
            hwnd
        )  # Get the class name of the active window
        return class_name in ["Shell_TrayWnd", "Windows.UI.Core.CoreWindow"]

    def monitor_start_menu(self):
        """Continuously check and close the Start Menu if it is open."""
        while True:
            try:
                if self.is_start_menu_open():
                    print("Start Menu detected. Closing it now.")
                    self.send_esc_key()
            except Exception as e:
                print(f"Error in monitor_start_menu: {e}")
            time.sleep(0.5)  # Adjust frequency as needed

    # --- TTS Methods (with lock) ---
    def say_text(self, text):
        threading.Thread(target=self._speak, args=(text,)).start()

    def _speak(self, text):
        with self.tts_lock:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()

    # --- Helper for Creating Buttons with TTS (for menus/pauses) ---
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

    # --- Main Menu ---
    def show_main_menu(self):
        self.current_mode = "main_menu"
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = tk.Frame(self.container, bg="blue")
        self.current_frame.pack(expand=True, fill="both")
        title = tk.Label(
            self.current_frame,
            text="TIC TAC TOE",
            font=("Arial Black", 60),
            bg="blue",
            fg="white",
        )
        title.pack(pady=20)
        self.menu_buttons = []
        btn = self.create_tts_button(
            self.current_frame, "Single Player", lambda: self.start_game("single")
        )
        self.menu_buttons.append(btn)
        btn = self.create_tts_button(
            self.current_frame, "2-Player", lambda: self.start_game("two")
        )
        self.menu_buttons.append(btn)
        btn = self.create_tts_button(self.current_frame, "Exit", self.on_exit)
        self.menu_buttons.append(btn)
        self.menu_scan_index = 0
        self.update_menu_scan_highlight()

    def update_menu_scan_highlight(self):
        for idx, btn in enumerate(self.menu_buttons):
            if idx == self.menu_scan_index:
                btn.config(bg="yellow", activebackground="yellow")
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

    def start_game(self, mode):
        self.game_mode = mode
        self.current_mode = "game"
        if self.current_frame:
            self.current_frame.destroy()
        # Set board background based on mode.
        if mode == "single":
            board_bg = "#ffcccc"  # light red
        else:
            board_bg = "#ccccff"  # light blue
        self.current_frame = tk.Frame(self.container, bg=board_bg)
        self.current_frame.pack(expand=True, fill="both")
        board_frame = tk.Frame(self.current_frame, bg=board_bg)
        board_frame.pack(expand=True, fill="both")
        self.rows, self.cols = 3, 3
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        cell_width = screen_width // self.cols
        cell_height = screen_height // self.rows
        self.board = {}
        self.buttons = {}
        self.game_board_order = []
        for r in range(self.rows):
            for c in range(self.cols):
                self.board[(r, c)] = ""
                # Create a cell frame with a solid border.
                cell_frame = tk.Frame(
                    board_frame,
                    width=cell_width,
                    height=cell_height,
                    bg=board_bg,
                    bd=2,
                    relief="solid",
                )
                cell_frame.grid(row=r, column=c)
                cell_frame.grid_propagate(False)
                # Create a button that is slightly smaller than the cell so the border is visible.
                btn = tk.Button(
                    cell_frame,
                    text="",
                    font=("Arial", 96),
                    bg="dark gray",
                    fg="black",
                    activebackground="dark gray",
                    command=partial(self.select_cell, r, c),
                )
                btn.place(
                    relx=0.5,
                    rely=0.5,
                    anchor="center",
                    width=cell_width - 4,
                    height=cell_height - 4,
                )
                self.buttons[(r, c)] = btn
                self.game_board_order.append((r, c))
        # For single-player mode, randomly decide who starts.
        if mode == "single":
            self.current_turn = random.choice(["X", "O"])
        else:
            self.current_turn = "X"
        if mode == "single" and self.current_turn == "O":
            self.after(1000, self.computer_move)
        elif self.current_turn == "X":
            self.say_text("your turn")
        self.game_board_scan_index = 0
        self.update_game_board_scan_highlight()

    def update_game_board_scan_highlight(self):
        for idx, pos in enumerate(self.game_board_order):
            btn = self.buttons[pos]
            # Determine the cell's default color based on its state.
            if self.board[pos] == "X":
                default_color = "red"
            elif self.board[pos] == "O":
                default_color = "blue"
            else:
                default_color = "dark gray"
            # If this cell is the one being scanned, override its color with yellow.
            if idx == self.game_board_scan_index:
                btn.config(
                    bg="yellow", relief="raised", bd=5, activebackground="yellow"
                )
            else:
                btn.config(
                    bg=default_color,
                    relief="flat",
                    bd=0,
                    activebackground=default_color,
                )

    def move_game_board_scan_forward(self):
        self.game_board_scan_index = (self.game_board_scan_index + 1) % len(
            self.game_board_order
        )
        self.update_game_board_scan_highlight()

    def move_game_board_scan_backward(self):
        self.game_board_scan_index = (self.game_board_scan_index - 1) % len(
            self.game_board_order
        )
        self.update_game_board_scan_highlight()

    def select_cell(self, r, c):
        # In single-player mode, only allow the X player (human) to make a move.
        if self.game_mode == "single" and self.current_turn != "X":
            return  # Not allowed in single-player mode.
        if self.board[(r, c)] != "":
            return  # Cell already marked.

        # Mark the cell with the current turn's symbol.
        self.board[(r, c)] = self.current_turn

        # Set tile background based on the current turn.
        if self.current_turn == "X":
            tile_color = "red"
        else:
            tile_color = "blue"
        self.buttons[(r, c)].config(
            text=self.current_turn,
            fg="black",
            font=("Arial", 72),
            bg=tile_color,
            activebackground=tile_color,
        )

        # Check for a win or tie.
        result = self.check_win()
        if result is not None:
            self.game_over_menu(result)
            return

        # Switch turns.
        if self.current_turn == "X":
            self.current_turn = "O"
        else:
            self.current_turn = "X"

        # In single-player mode, if it's the computer's turn, schedule its move.
        if self.game_mode == "single" and self.current_turn == "O":
            self.after(1000, self.computer_move)
        elif self.current_turn == "X":
            self.say_text("your turn")

    def computer_move(self):
        empty_cells = [(r, c) for (r, c), v in self.board.items() if v == ""]
        if not empty_cells:
            return
        r, c = random.choice(empty_cells)
        self.board[(r, c)] = "O"
        # For O, set the tile background to blue.
        self.buttons[(r, c)].config(
            text="O", fg="black", font=("Arial", 72), bg="blue", activebackground="blue"
        )
        result = self.check_win()
        if result is not None:
            self.game_over_menu(result)
            return
        self.current_turn = "X"
        self.say_text("your turn")

    def check_win(self):
        b = self.board
        # Check rows
        for r in range(3):
            if b[(r, 0)] != "" and b[(r, 0)] == b[(r, 1)] == b[(r, 2)]:
                return b[(r, 0)]
        # Check columns
        for c in range(3):
            if b[(0, c)] != "" and b[(0, c)] == b[(1, c)] == b[(2, c)]:
                return b[(0, c)]
        # Check diagonals
        if b[(0, 0)] != "" and b[(0, 0)] == b[(1, 1)] == b[(2, 2)]:
            return b[(0, 0)]
        if b[(0, 2)] != "" and b[(0, 2)] == b[(1, 1)] == b[(2, 0)]:
            return b[(0, 2)]
        # Check tie
        if all(b[(r, c)] != "" for r in range(3) for c in range(3)):
            return "Tie"
        return None

    def game_over_menu(self, result):
        self.current_mode = "game_over_menu"
        for widget in self.current_frame.winfo_children():
            widget.destroy()
        if result == "Tie":
            msg = "It's a tie!"
        else:
            msg = f"Player {result} wins!"
        self.say_text(msg)
        result_label = tk.Label(
            self.current_frame,
            text=msg,
            font=("Arial Black", 42),
            fg="purple",
            bg="yellow",
        )
        result_label.place(relx=0.5, rely=0.3, anchor="center")
        question = tk.Label(
            self.current_frame,
            text="Play again?",
            font=("Arial", 36),
            fg="black",
            bg="yellow",
        )
        question.place(relx=0.5, rely=0.5, anchor="center")
        self.say_text("Would you like to play again?")
        self.game_over_buttons = []
        btn_yes = self.create_tts_button(
            self.current_frame, "Yes", lambda: self.restart_game(), font_size=36
        )
        self.game_over_buttons.append(btn_yes)
        btn_no = self.create_tts_button(
            self.current_frame, "No", self.show_main_menu, font_size=36
        )
        self.game_over_buttons.append(btn_no)
        self.game_over_scan_index = 0
        self.update_game_over_scan_highlight()

    def update_game_over_scan_highlight(self):
        for idx, btn in enumerate(self.game_over_buttons):
            if idx == self.game_over_scan_index:
                btn.config(bg="yellow", activebackground="yellow")
            else:
                btn.config(bg="gray", activebackground="gray")
        if self.game_over_buttons:
            self.say_text(
                self.game_over_buttons[self.game_over_scan_index].cget("text")
            )

    def move_game_over_scan_forward(self):
        self.game_over_scan_index = (self.game_over_scan_index + 1) % len(
            self.game_over_buttons
        )
        self.update_game_over_scan_highlight()

    def move_game_over_scan_backward(self):
        self.game_over_scan_index = (self.game_over_scan_index - 1) % len(
            self.game_over_buttons
        )
        self.update_game_over_scan_highlight()

    def restart_game(self):
        self.start_game(self.game_mode)

    # --- Pause Menu ---
    def show_pause_screen(self):
        self.current_mode = "pause"
        self.return_held = False
        self.return_press_time = None
        self.pause_just_opened = True
        self.pause_frame = tk.Frame(self.current_frame, bg="black")
        self.pause_frame.place(relx=0.5, rely=0.5, anchor="center")
        label = tk.Label(
            self.pause_frame,
            text="Pause Menu",
            font=("Arial", 40),
            fg="white",
            bg="black",
        )
        label.pack(pady=20)
        self.pause_buttons = []
        btn = self.create_tts_button(
            self.pause_frame, "Continue Game", self.continue_game, font_size=36
        )
        self.pause_buttons.append(btn)
        btn = self.create_tts_button(
            self.pause_frame, "Return to Menu", self.show_main_menu, font_size=36
        )
        self.pause_buttons.append(btn)
        btn = self.create_tts_button(
            self.pause_frame, "Exit", self.on_exit, font_size=36
        )
        self.pause_buttons.append(btn)
        self.pause_scan_index = 0
        self.update_pause_menu_scan_highlight()

    def update_pause_menu_scan_highlight(self):
        for idx, btn in enumerate(self.pause_buttons):
            if idx == self.pause_scan_index:
                btn.config(bg="yellow", activebackground="yellow")
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

    # --- Key Event Handlers ---
    def on_space_press(self, event):
        if self.current_mode not in ("game", "main_menu", "pause", "game_over_menu"):
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
                self.move_game_board_scan_backward()
            elif self.current_mode == "main_menu":
                self.move_menu_scan_backward()
            elif self.current_mode == "pause":
                self.move_pause_menu_scan_backward()
            elif self.current_mode == "game_over_menu":
                self.move_game_over_scan_backward()
            self.space_backwards_timer_id = self.after(2000, self.space_long_hold)

    def on_space_release(self, event):
        if self.current_mode not in ("game", "main_menu", "pause", "game_over_menu"):
            return
        duration = time.time() - self.space_press_time if self.space_press_time else 0
        if self.space_backwards_timer_id:
            self.after_cancel(self.space_backwards_timer_id)
            self.space_backwards_timer_id = None
        self.spacebar_held = False
        if not self.space_backward_active and 0.1 <= duration < 3:
            if self.current_mode == "game":
                self.move_game_board_scan_forward()
            elif self.current_mode == "main_menu":
                self.move_menu_scan_forward()
            elif self.current_mode == "pause":
                self.move_pause_menu_scan_forward()
            elif self.current_mode == "game_over_menu":
                self.move_game_over_scan_forward()
        self.space_backward_active = False

    def on_return_press(self, event):
        if self.current_mode not in ("game", "main_menu", "pause", "game_over_menu"):
            return
        if self.return_held:
            return
        self.return_press_time = time.time()
        self.return_held = True
        if self.current_mode == "game":
            self.return_pause_timer_id = self.after(6000, self.return_long_hold)

    def return_long_hold(self):
        if self.return_held:
            self.pause_triggered = True
            self.show_pause_screen()

    def on_return_release(self, event):
        if self.current_mode not in ("game", "main_menu", "pause", "game_over_menu"):
            return
        duration = time.time() - self.return_press_time if self.return_press_time else 0
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
                # In game mode, selecting the scanned cell:
                pos = self.game_board_order[self.game_board_scan_index]
                self.select_cell(pos[0], pos[1])
        elif self.current_mode == "main_menu":
            self.return_held = False
            self.menu_buttons[self.menu_scan_index].invoke()
        elif self.current_mode == "pause":
            self.return_held = False
            self.pause_buttons[self.pause_scan_index].invoke()
        elif self.current_mode == "game_over_menu":
            self.return_held = False
            self.game_over_buttons[self.game_over_scan_index].invoke()

    def move_game_board_scan_forward(self):
        self.game_board_scan_index = (self.game_board_scan_index + 1) % len(
            self.game_board_order
        )
        self.update_game_board_scan_highlight()

    def move_game_board_scan_backward(self):
        self.game_board_scan_index = (self.game_board_scan_index - 1) % len(
            self.game_board_order
        )
        self.update_game_board_scan_highlight()

    def on_exit(self):
        self.destroy()
        try:
            # Get the parent directory (root folder of the project)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            script_path = os.path.join(project_root, "Comm-v9.py")
            subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            print("Failed to launch Comm-v9.py:", e)


if __name__ == "__main__":
    app = TicTacToeGame()
    app.mainloop()
