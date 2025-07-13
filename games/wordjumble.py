import os
import tkinter as tk
from tkinter import messagebox
import pandas as pd
import random
import time
import threading
import pyttsx3
import subprocess
import queue
import re
import sys
import ctypes
import win32gui

class WordJumbleGame(tk.Tk):
    def __init__(self):
        super().__init__()
        self.attributes("-fullscreen", True)
        self.title("Bens Jumble Game")

        # Initialize TTS engine and set up a dedicated TTS thread.
        self.tts_engine = pyttsx3.init()
        self.tts_queue = queue.Queue()
        self.tts_thread = threading.Thread(target=self.process_tts_queue, daemon=True)
        self.tts_thread.start()
        self.protocol("WM_DELETE_WINDOW", self.exit_game)

        # Load the Excel file.
        excel_path = os.path.join(os.path.dirname(__file__), "..", "data", "wordjumble.xlsx")
        try:
            self.words_data = pd.read_excel(excel_path)
            self.words_data.columns = self.words_data.columns.str.strip().str.lower()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load {excel_path}: {e}")
            self.destroy()
            return

        # ---------------- Scanning State Variables ----------------
        self.spacebar_held = False
        self.space_press_time = None
        self.space_backward_active = False
        self.space_backwards_timer_id = None

        self.return_held = False
        self.return_press_time = None
        self.return_pause_timer_id = None
        self.pause_triggered = False
        self.pause_just_opened = False

        # For game mode (letter scanning)
        self.letter_buttons = []
        self.scanning_index = None

        # For main menu scanning
        self.menu_buttons = []
        self.menu_scan_index = 0

        # For pause menu scanning
        self.pause_buttons = []
        self.pause_scan_index = 0

        # ---------------- Level and Game State Variables ----------------
        self.current_difficulty = None
        self.selected_word = ""
        self.full_sentence = ""   # Full sentence with the target word (for TTS)
        self.current_selection = ""
        self.original_jumbled_letters = []

        # Level progression settings:
        # Each difficulty has 5 levels defined by (min_length, max_length).
        self.level_ranges = {
            "easy": [(2,2), (3,3), (3,3), (4,4), (4,4)],
            "medium": [(4,4), (5,5), (6,6), (6,6), (6,6)],
            "hard": [(6,6), (7,7), (7,7), (8,8), (8,8)]
        }
        self.level_number = None  # 1 to 5
        self.total_attempts = 0   # Across all words in this session.
        self.total_correct = 0
        self.level_correct = 0    # Incremented only on correct answers.

        # Used words: ensure uniqueness in a session.
        self.used_words = set()

        # Active mode: "main" (main menu), "game", or "pause"
        self.active_menu = None

        self.monitor_focus_thread = threading.Thread(target=self.monitor_focus, daemon=True)
        self.monitor_focus_thread.start()

        self.monitor_start_menu_thread = threading.Thread(target=self.monitor_start_menu, daemon=True)
        self.monitor_start_menu_thread.start()

        # ---------------- Build Screens ----------------
        self.build_main_menu()
        self.build_game_screen()
        self.build_pause_menu()
        self.show_main_menu()

        # Bind key events. (Only spacebar and return keys are used.)
        self.bind("<KeyPress-space>", self.on_space_press)
        self.bind("<KeyRelease-space>", self.on_space_release)
        self.bind("<KeyPress-Return>", self.on_return_press)
        self.bind("<KeyRelease-Return>", self.on_return_release)


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
        hwnd = win32gui.GetForegroundWindow()  # Get the handle of the active (focused) window
        class_name = win32gui.GetClassName(hwnd)  # Get the class name of the active window
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

    # ---------------- TTS Methods ----------------
    def process_tts_queue(self):
        while True:
            text = self.tts_queue.get()
            if text is None:
                break
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()

    def tts_speak(self, text):
        self.tts_queue.put(text)

    # ---------------- Scanning Methods for Game Mode (Letters) ----------------
    def highlight_game_button(self):
        if not self.letter_buttons or self.scanning_index is None:
            return
        for btn in self.letter_buttons:
            btn.config(bg="darkorange", fg="black")
        self.letter_buttons[self.scanning_index].config(bg="white", fg="black")
        letter = self.letter_buttons[self.scanning_index]["text"]
        self.tts_speak(letter)

    def move_game_scan_forward(self):
        if not self.letter_buttons:
            return
        if self.scanning_index is None:
            self.scanning_index = 0
        else:
            self.scanning_index = (self.scanning_index + 1) % len(self.letter_buttons)
        self.highlight_game_button()

    def move_game_scan_backward(self):
        if not self.letter_buttons:
            return
        if self.scanning_index is None:
            self.scanning_index = 0
        else:
            self.scanning_index = (self.scanning_index - 1) % len(self.letter_buttons)
        self.highlight_game_button()

    # ---------------- Scanning Methods for Main Menu ----------------
    def update_menu_scan_highlight(self):
        for idx, btn in enumerate(self.menu_buttons):
            if idx == self.menu_scan_index:
                btn.config(bg="white", fg="black")
            else:
                btn.config(bg="darkorange", fg="black")
        if self.menu_buttons:
            text = self.menu_buttons[self.menu_scan_index].cget("text")
            self.tts_speak(text)

    def move_menu_scan_forward(self):
        self.menu_scan_index = (self.menu_scan_index + 1) % len(self.menu_buttons)
        self.update_menu_scan_highlight()

    def move_menu_scan_backward(self):
        self.menu_scan_index = (self.menu_scan_index - 1) % len(self.menu_buttons)
        self.update_menu_scan_highlight()

    # ---------------- Scanning Methods for Pause Menu ----------------
    def update_pause_scan_highlight(self):
        if self.pause_scan_index is None:
            # Clear highlight from all buttons
            for btn in self.pause_buttons:
                btn.config(bg="darkorange", activebackground="darkorange", fg="black")
            return
        for idx, btn in enumerate(self.pause_buttons):
            if idx == self.pause_scan_index:
                btn.config(bg="white", activebackground="white", fg="black")
            else:
                btn.config(bg="darkorange", activebackground="darkorange", fg="black")
        text = self.pause_buttons[self.pause_scan_index].cget("text")
        self.tts_speak(text)

    def move_pause_scan_forward(self):
        self.pause_scan_index = (self.pause_scan_index + 1) % len(self.pause_buttons)
        self.update_pause_scan_highlight()

    def move_pause_scan_backward(self):
        self.pause_scan_index = (self.pause_scan_index - 1) % len(self.pause_buttons)
        self.update_pause_scan_highlight()

    # ---------------- Key Event Handlers (Spacebar) ----------------
    def on_space_press(self, event):
        if self.active_menu not in ("game", "main", "pause"):
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
            if self.active_menu == "game":
                self.move_game_scan_backward()
            elif self.active_menu == "main":
                self.move_menu_scan_backward()
            elif self.active_menu == "pause":
                self.move_pause_scan_backward()
            self.space_backwards_timer_id = self.after(2000, self.space_long_hold)

    def on_space_release(self, event):
        if self.space_backwards_timer_id:
            self.after_cancel(self.space_backwards_timer_id)
            self.space_backwards_timer_id = None
        self.spacebar_held = False
        duration = time.time() - self.space_press_time if self.space_press_time else 0
        if not self.space_backward_active:
            if 0.1 <= duration < 3:
                if self.active_menu == "game":
                    self.move_game_scan_forward()
                elif self.active_menu == "main":
                    if self.menu_scan_index is None:
                        self.menu_scan_index = 0
                        self.update_menu_scan_highlight()
                    else:
                        self.move_menu_scan_forward()
                elif self.active_menu == "pause":
                    if self.pause_scan_index is None:
                        self.pause_scan_index = 0
                        self.update_pause_scan_highlight()
                    else:
                        self.move_pause_scan_forward()
        self.space_backward_active = False

    # ---------------- Key Event Handlers (Return Key) ----------------
    def on_return_press(self, event):
        if self.active_menu not in ("game", "main", "pause"):
            return
        if self.return_held:
            return
        self.return_press_time = time.time()
        self.return_held = True
        if self.active_menu == "game":
            self.return_pause_timer_id = self.after(3000, self.return_long_hold)

    def return_long_hold(self):
        if self.return_held:
            self.pause_triggered = True
            self.show_pause_menu()

    def on_return_release(self, event):
        duration = time.time() - self.return_press_time if self.return_press_time else 0
        if self.active_menu == "pause" and self.pause_just_opened:
            self.pause_just_opened = False
            self.return_held = False
            return
        if self.active_menu == "game":
            if self.return_pause_timer_id:
                self.after_cancel(self.return_pause_timer_id)
                self.return_pause_timer_id = None
            self.return_held = False
            if self.pause_triggered:
                self.pause_triggered = False
                return
            if 0.1 <= duration < 3:
                if self.scanning_index is not None:
                    self.select_letter(self.scanning_index)
        elif self.active_menu == "main":
            self.return_held = False
            self.menu_buttons[self.menu_scan_index].invoke()
        elif self.active_menu == "pause":
            self.return_held = False
            self.pause_buttons[self.pause_scan_index].invoke()

    # ---------------- Main Menu ----------------
    def build_main_menu(self):
        self.main_menu_frame = tk.Frame(self, bg="darkorange")
        title_label = tk.Label(self.main_menu_frame, text="Ben's Jumble Game", font=("Arial", 48), bg="darkorange", fg="black")
        title_label.pack(pady=50)
        self.menu_buttons = []
        btn_easy = tk.Button(self.main_menu_frame, text="Easy", font=("Arial", 36), bg="darkorange", fg="black",
                             command=lambda: self.start_game("easy"))
        btn_easy.pack(pady=20)
        self.menu_buttons.append(btn_easy)
        btn_medium = tk.Button(self.main_menu_frame, text="Medium", font=("Arial", 36), bg="darkorange", fg="black",
                               command=lambda: self.start_game("medium"))
        btn_medium.pack(pady=20)
        self.menu_buttons.append(btn_medium)
        btn_hard = tk.Button(self.main_menu_frame, text="Hard", font=("Arial", 36), bg="darkorange", fg="black",
                             command=lambda: self.start_game("hard"))
        btn_hard.pack(pady=20)
        self.menu_buttons.append(btn_hard)
        btn_exit = tk.Button(self.main_menu_frame, text="Exit", font=("Arial", 36), bg="darkorange", fg="black",
                             command=self.exit_game)
        btn_exit.pack(pady=20)
        self.menu_buttons.append(btn_exit)
        self.menu_scan_index = None

    def show_main_menu(self):
        self.active_menu = "main"
        self.main_menu_frame.pack(fill="both", expand=True)
        if hasattr(self, "game_frame"):
            self.game_frame.pack_forget()
        if hasattr(self, "pause_menu_frame"):
            self.pause_menu_frame.pack_forget()
        self.menu_scan_index = None
        for btn in self.menu_buttons:
            btn.config(bg="darkorange", fg="black")
        self.tts_speak("Ben's Jumble Game.")

    # ---------------- Game Screen ----------------
    def build_game_screen(self):
        self.game_frame = tk.Frame(self, bg="black", highlightbackground="darkorange", highlightthickness=50)
        self.sentence_label = tk.Label(self.game_frame, text="", font=("Arial", 36), fg="white", bg="black")
        self.sentence_label.pack(pady=30)
        # Make the answer label about 300% larger and bold.
        self.answer_label = tk.Label(self.game_frame, text="", font=("Arial", 128, "bold"), fg="white", bg="black")
        self.answer_label.pack(pady=30)
        # Level indicator at top right.
        self.level_label = tk.Label(self.game_frame, text="", font=("Arial", 24), fg="white", bg="black")
        self.level_label.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
        self.buttons_frame = tk.Frame(self.game_frame, bg="black")
        self.buttons_frame.pack(side="bottom", fill="x", padx=20, pady=20)

    def start_game(self, difficulty):
        self.active_menu = "game"
        self.current_difficulty = difficulty
        # Initialize level if starting fresh.
        if self.level_number is None:
            self.level_number = 1
            self.total_attempts = 0
            self.total_correct = 0
            self.level_correct = 0
            self.used_words = set()

        # Update level indicator.
        self.level_label.config(text=f"Level {self.level_number}")
        self.current_selection = ""
        self.answer_label.config(text=self.current_selection)
        self.show_game_screen()

        # Get the letter range for the current level.
        min_len, max_len = self.level_ranges[difficulty][self.level_number - 1]

        # Filter words by difficulty and letter length.
        filtered = self.words_data[self.words_data["mode"] == difficulty.lower()]
        filtered = filtered[filtered["word"].str.len().between(min_len, max_len)]
        # Exclude words already used.
        available = filtered[~filtered["word"].isin(self.used_words)]
        if available.empty:
            self.used_words = set()
            available = filtered
        row = available.sample(n=1).iloc[0]
        self.used_words.add(row["word"].strip())
        self.selected_word = row["word"].strip()
        self.full_sentence = row["sentence"].strip()
        # For display, replace the target word with underscores.
        if self.selected_word in self.full_sentence:
            display_sentence = self.full_sentence.replace(self.selected_word, "_" * len(self.selected_word))
        else:
            display_sentence = self.full_sentence
        self.sentence_label.config(text=display_sentence)
        # TTS: speak the word then the sentence.
        self.tts_speak("The word is: " + self.selected_word)
        tts_sentence = re.sub(r'_+', self.selected_word, self.full_sentence)
        self.tts_speak(tts_sentence)
        # Create jumbled letter buttons.
        self.jumbled_letters = list(self.selected_word)
        random.shuffle(self.jumbled_letters)
        self.original_jumbled_letters = self.jumbled_letters.copy()
        for widget in self.buttons_frame.winfo_children():
            widget.destroy()
        self.letter_buttons = []
        for letter in self.jumbled_letters:
            btn = tk.Button(self.buttons_frame, text=letter, font=("Arial", 36), bg="darkorange", fg="black")
            btn.pack(side="left", expand=True, fill="both", padx=5, pady=5)
            self.letter_buttons.append(btn)
        self.scanning_index = None

    def show_game_screen(self):
        self.game_frame.pack(fill="both", expand=True)
        self.main_menu_frame.pack_forget()
        if hasattr(self, "pause_menu_frame"):
            self.pause_menu_frame.pack_forget()

    def select_letter(self, index):
        if not self.letter_buttons or index < 0 or index >= len(self.letter_buttons):
            return
        letter = self.letter_buttons[index]["text"]
        self.current_selection += letter
        self.answer_label.config(text=self.current_selection)
        btn = self.letter_buttons.pop(index)
        btn.destroy()
        self.scanning_index = None
        if not self.letter_buttons:
            self.check_answer()

    def check_answer(self):
        self.total_attempts += 1
        if self.current_selection.lower() == self.selected_word.lower():
            self.total_correct += 1
            self.level_correct += 1
            self.tts_speak("Correct")
            if self.level_correct == 5:
                if self.level_number == 5:
                    self.show_final_score()
                else:
                    self.tts_speak("Level complete!")
                    self.level_number += 1
                    self.level_correct = 0
                    self.after(2000, lambda: self.start_game(self.current_difficulty))
            else:
                self.after(1000, lambda: self.start_game(self.current_difficulty))
        else:
            self.tts_speak("Incorrect")
            # Do not reset level progress; allow reattempt of the same word.
            self.after(2000, self.retry_word)

    def retry_word(self):
        # Reset the current word attempt (keeping the same word).
        self.current_selection = ""
        self.answer_label.config(text=self.current_selection)
        # Re-scramble the letters for the same word.
        self.jumbled_letters = list(self.selected_word)
        random.shuffle(self.jumbled_letters)
        self.original_jumbled_letters = self.jumbled_letters.copy()
        for widget in self.buttons_frame.winfo_children():
            widget.destroy()
        self.letter_buttons = []
        for letter in self.jumbled_letters:
            btn = tk.Button(self.buttons_frame, text=letter, font=("Arial", 36), bg="darkorange", fg="black")
            btn.pack(side="left", expand=True, fill="both", padx=5, pady=5)
            self.letter_buttons.append(btn)
        self.scanning_index = None

    def show_final_score(self):
        percentage = (self.total_correct / self.total_attempts * 100) if self.total_attempts > 0 else 0
        if percentage < 50:
            color = "red"
            msg = "Try again"
        elif percentage < 60:
            color = "orange"
            msg = "You can do better"
        elif percentage < 70:
            color = "yellow"
            msg = "Getting better"
        elif percentage < 80:
            color = "green"
            msg = "Pretty good"
        elif percentage < 90:
            color = "light blue"
            msg = "Good job"
        elif percentage < 100:
            color = "light purple"
            msg = "That's really good"
        else:
            color = "magenta"
            msg = "Wow that's perfect! ★★★"
        score_label = tk.Label(self.game_frame, text=f"Score: {percentage:.0f}%", font=("Arial", 48), fg=color, bg="black")
        score_label.place(relx=0.5, rely=0.5, anchor="center")
        self.tts_speak(msg)
        self.after(5000, lambda: (score_label.destroy(), self.reset_all_levels(), self.show_main_menu()))

    def reset_all_levels(self):
        self.level_number = None
        self.total_attempts = 0
        self.total_correct = 0
        self.level_correct = 0

    # ---------------- Pause Menu ----------------
    def build_pause_menu(self):
        self.pause_menu_frame = tk.Frame(self, bg="black")
        pause_label = tk.Label(self.pause_menu_frame, text="Paused", font=("Arial", 48), fg="white", bg="black")
        pause_label.pack(pady=50)
        self.pause_buttons = []
        btn_continue = tk.Button(self.pause_menu_frame, text="Continue", font=("Arial", 36), fg="black", bg="darkorange", command=self.resume_game)
        btn_continue.pack(pady=20)
        self.pause_buttons.append(btn_continue)
        btn_remove = tk.Button(self.pause_menu_frame, text="Remove Letter", font=("Arial", 36), fg="black", bg="darkorange", command=self.remove_last_letter_option)
        btn_remove.pack(pady=20)
        self.pause_buttons.append(btn_remove)
        btn_menu = tk.Button(self.pause_menu_frame, text="Main Menu", font=("Arial", 36), fg="black", bg="darkorange", command=self.return_to_main_menu)
        btn_menu.pack(pady=20)
        self.pause_buttons.append(btn_menu)
        btn_exit = tk.Button(self.pause_menu_frame, text="Exit", font=("Arial", 36), fg="black", bg="darkorange", command=self.exit_game)
        btn_exit.pack(pady=20)
        self.pause_buttons.append(btn_exit)
        self.pause_scan_index = None

    def show_pause_menu(self):
        self.active_menu = "pause"
        self.pause_just_opened = True
        self.game_frame.pack_forget()
        self.pause_menu_frame.pack(fill="both", expand=True)
        self.pause_scan_index = None  # Reset highlight index
        self.update_pause_scan_highlight()  # Clear previous highlight

    def resume_game(self):
        self.pause_menu_frame.pack_forget()
        self.active_menu = "game"
        self.show_game_screen()

    def return_to_main_menu(self):
        self.pause_menu_frame.pack_forget()
        self.active_menu = "main"
        self.show_main_menu()

    def exit_game(self):
        # Terminate TTS thread gracefully by sending termination signal.
        self.tts_queue.put(None)
        # Wait for the TTS thread to finish.
        self.tts_thread.join(timeout=2)
        self.destroy()
        try:
            # Try to restore the main app window first
            hwnd = win32gui.FindWindow(None, "Accessible Menu")
            if hwnd:
                # Restore the window from minimized state
                win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
                win32gui.SetForegroundWindow(hwnd)
            else:
                # If window not found, launch the main app
                current_dir = os.path.dirname(__file__)
                comm_v9_path = os.path.join(current_dir, "..", "comm-v9.py")
                subprocess.Popen([sys.executable, comm_v9_path])
        except Exception as e:
            print("Failed to restore main app:", e)

    # ---------------- Remove Letter Option (via Pause Menu) ----------------
    def remove_last_letter_option(self):
        # Remove the last letter from current_selection and return it to the pool.
        if self.current_selection:
            removed = self.current_selection[-1]
            self.current_selection = self.current_selection[:-1]
            self.answer_label.config(text=self.current_selection)
            btn = tk.Button(self.buttons_frame, text=removed, font=("Arial", 36), bg="darkorange", fg="black")
            btn.pack(side="left", expand=True, fill="both", padx=5, pady=5)
            self.letter_buttons.append(btn)
            self.scanning_index = None
        # Automatically resume game mode.
        self.resume_game()


if __name__ == "__main__":
    app = WordJumbleGame()
    app.mainloop()
