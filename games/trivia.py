import tkinter as tk
from tkinter import Font
import random
import time
import subprocess
import pyttsx3
import threading
import ctypes
import win32gui
import sys
import os
import pandas as pd

class TriviaGame(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Trivia Game for Ben")
        self.attributes("-fullscreen", True)
        self.configure(bg="black")
        
        # Initialize TTS
        self.tts_engine = pyttsx3.init()
        self.tts_queue = []
        self.tts_lock = threading.Lock()
        self.tts_thread = threading.Thread(target=self.play_speak_queue, daemon=True)
        self.tts_thread.start()
        
        # Focus and Start Menu monitoring threads
        self.monitor_focus_thread = threading.Thread(target=self.monitor_focus, daemon=True)
        self.monitor_focus_thread.start()
        self.monitor_start_menu_thread = threading.Thread(target=self.monitor_start_menu, daemon=True)
        self.monitor_start_menu_thread.start()
        
        # Load trivia data
        self.trivia_data = self.load_trivia_questions_excel()
        
        # Window controls
        self.create_window_controls()
        
        # Start with topic selection
        self.show_topic_selection()
        
        # Key bindings
        self.bind("<KeyPress-space>", self.on_space_press)
        self.bind("<KeyRelease-space>", self.on_space_release)
        self.bind("<KeyPress-Return>", self.on_return_press)
        self.bind("<KeyRelease-Return>", self.on_return_release)
        self.focus_set()
        
        # Space bar monitoring
        self.space_press_time = None
        self.space_long_hold_id = None
        self.scanning_backward = False
        self.return_press_time = None
        self.return_long_hold_id = None
        
        # Current interface state
        self.buttons = []
        self.current_button_index = 0
        self.current_screen = "topics"
        
    def create_window_controls(self):
        top_frame = tk.Frame(self, bg="lightgray")
        top_frame.pack(side="top", fill="x")
        minimize_btn = tk.Button(top_frame, text="_", command=self.iconify, font=("Arial", 12))
        minimize_btn.pack(side="right", padx=5, pady=5)
        close_btn = tk.Button(top_frame, text="X", command=self.on_exit, font=("Arial", 12))
        close_btn.pack(side="right", padx=5, pady=5)
    
    def monitor_focus(self):
        while True:
            try:
                time.sleep(0.1)
                hwnd = win32gui.FindWindow(None, "Trivia Game for Ben")
                if hwnd and win32gui.GetForegroundWindow() != hwnd:
                    self.after(10, self.force_focus)
            except:
                pass
    
    def force_focus(self):
        try:
            hwnd = win32gui.FindWindow(None, "Trivia Game for Ben")
            if hwnd:
                win32gui.SetForegroundWindow(hwnd)
        except:
            pass
    
    def is_start_menu_open(self):
        try:
            hwnd = win32gui.FindWindow("DV2ControlHost", None)
            return hwnd is not None
        except:
            return False
    
    def monitor_start_menu(self):
        while True:
            try:
                if self.is_start_menu_open():
                    self.send_esc_key()
                time.sleep(0.1)
            except:
                pass
    
    def send_esc_key(self):
        try:
            ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)
        except:
            pass
    
    def speak(self, text):
        with self.tts_lock:
            self.tts_queue.append(text)
    
    def play_speak_queue(self):
        while True:
            try:
                if self.tts_queue:
                    with self.tts_lock:
                        text = self.tts_queue.pop(0)
                    self.tts_engine.say(text)
                    self.tts_engine.runAndWait()
                time.sleep(0.1)
            except:
                pass
    
    def load_trivia_questions_excel(self):
        """Load trivia questions from Excel file"""
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(project_root, "data", "trivia_questions.xlsx")
            df = pd.read_excel(path)
            trivia_dict = {}
            for _, row in df.iterrows():
                topic = row['Topic']
                question_data = {
                    "question": row['Question'],
                    "choices": [row['Choice1'], row['Choice2'], row['Choice3'], row['Choice4']],
                    "correct": int(row['Correct'])
                }
                trivia_dict.setdefault(topic, []).append(question_data)
            return trivia_dict
        except Exception as e:
            print(f"Error loading trivia questions: {e}")
            return {}
    
    def show_topic_selection(self):
        """Show topic selection screen"""
        self.current_screen = "topics"
        self.clear_screen()
        
        # Title
        title_label = tk.Label(self, text="Trivia Topics", font=("Arial Black", 48), 
                              fg="white", bg="black")
        title_label.pack(pady=20)
        
        # Topic buttons
        all_topics = list(self.trivia_data.keys())
        topics = random.sample(all_topics, min(8, len(all_topics)))
        
        self.create_topic_buttons(topics)
        
        self.speak("Trivia Topics")
    
    def create_topic_buttons(self, topics):
        """Create buttons for topic selection"""
        button_frame = tk.Frame(self, bg="black")
        button_frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Add Back button
        buttons_data = [("Back", self.on_exit)]
        for topic in topics:
            buttons_data.append((topic, lambda t=topic: self.start_game(t)))
        
        self.buttons = []
        rows = (len(buttons_data) + 2) // 3
        for i, (text, command) in enumerate(buttons_data):
            row, col = divmod(i, 3)
            btn = tk.Button(button_frame, text=text, font=("Arial Black", 32),
                           bg="light blue", fg="black", command=command,
                           wraplength=300)
            btn.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            self.buttons.append(btn)
        
        # Configure grid weights
        for i in range(rows):
            button_frame.rowconfigure(i, weight=1)
        for j in range(3):
            button_frame.columnconfigure(j, weight=1)
        
        self.current_button_index = 0
        self.highlight_button(self.current_button_index)
    
    def start_game(self, topic):
        """Start trivia game for selected topic"""
        self.current_screen = "game"
        self.topic = topic
        self.all_questions = self.trivia_data.get(topic, [])
        
        if len(self.all_questions) >= 10:
            self.game_questions = random.sample(self.all_questions, 10)
        else:
            self.game_questions = self.all_questions
        
        self.current_question_index = 0
        self.show_game_screen()
    
    def show_game_screen(self):
        """Show the game screen"""
        self.clear_screen()
        
        # Load trivia image
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            image_path = os.path.join(project_root, "images", "trivia.png")
            self.photo = tk.PhotoImage(file=image_path)
            image_label = tk.Label(self, image=self.photo, bg="black")
            image_label.pack(pady=10)
        except:
            pass
        
        # Question label
        self.question_label = tk.Label(self, text="", font=("Arial", 28),
                                      bg="black", fg="white", wraplength=800)
        self.question_label.pack(pady=20, fill=tk.X)
        
        # Button frame
        button_frame = tk.Frame(self, bg="black")
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)
        
        # Back button
        self.back_button = tk.Button(button_frame, text="Back", font=("Arial", 32),
                                    bg="light blue", fg="black", command=self.show_topic_selection)
        self.back_button.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.BOTH)
        
        # Answer buttons
        self.answer_buttons = []
        for i in range(4):
            btn = tk.Button(button_frame, text="", font=("Arial", 32),
                           bg="light blue", fg="black", command=lambda i=i: self.check_answer(i))
            btn.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.BOTH)
            self.answer_buttons.append(btn)
        
        self.buttons = [self.back_button] + self.answer_buttons
        self.current_button_index = 0
        self.highlight_button(self.current_button_index)
        
        self.speak(f"Trivia: {self.topic}")
        self.after(2000, self.display_question)
    
    def display_question(self):
        """Display current question"""
        if self.current_question_index >= len(self.game_questions):
            self.end_game()
            return
        
        question = self.game_questions[self.current_question_index]
        self.question_label.config(text=question['question'])
        self.after(100, lambda: self.speak(question['question']))
        
        # Shuffle answer choices
        pairs = [(choice, i == question['correct']) for i, choice in enumerate(question['choices'])]
        random.shuffle(pairs)
        shuffled_choices = [p[0] for p in pairs]
        self.shuffled_correct = next(i for i, p in enumerate(pairs) if p[1])
        
        for i, btn in enumerate(self.answer_buttons):
            if i < len(shuffled_choices):
                btn.config(text=shuffled_choices[i], state=tk.NORMAL, bg="light blue", fg="black")
                self.adjust_font_size(btn)
            else:
                btn.config(text="", state=tk.DISABLED)
        
        self.current_button_index = 0
        self.highlight_button(self.current_button_index)
    
    def adjust_font_size(self, button, max_width=250, min_font_size=12):
        """Adjust font size to fit button"""
        button.update_idletasks()
        text = button.cget("text")
        font_family = "Arial"
        font_size = 32
        
        while font_size >= min_font_size:
            test_font = Font(family=font_family, size=font_size)
            text_width = test_font.measure(text)
            if text_width <= max_width:
                break
            font_size -= 2
        
        button.config(font=(font_family, font_size))
    
    def check_answer(self, selected_index):
        """Check if selected answer is correct"""
        if selected_index == self.shuffled_correct:
            result_text = "Correct!"
            self.answer_buttons[selected_index].config(bg="green")
        else:
            result_text = "Incorrect!"
            self.answer_buttons[selected_index].config(bg="red")
            self.answer_buttons[self.shuffled_correct].config(bg="green")
        
        self.speak(result_text)
        self.after(2000, self.next_question)
    
    def next_question(self):
        """Move to next question"""
        self.current_question_index += 1
        if self.current_question_index < len(self.game_questions):
            self.display_question()
        else:
            self.end_game()
    
    def end_game(self):
        """End the game"""
        self.question_label.config(text="End of Trivia Game. Press Back to return.")
        for btn in self.answer_buttons:
            btn.config(text="", state=tk.DISABLED)
        self.buttons = [self.back_button]
        self.current_button_index = 0
        self.highlight_button(self.current_button_index)
        self.speak("End of Trivia Game. Press Back to return.")
    
    def clear_screen(self):
        """Clear the screen"""
        for widget in self.winfo_children():
            if widget.winfo_class() != "Frame" or widget.cget("bg") != "lightgray":
                widget.destroy()
    
    def highlight_button(self, index):
        """Highlight the current button"""
        for i, btn in enumerate(self.buttons):
            if i == index:
                btn.config(bg="yellow", fg="black")
            else:
                btn.config(bg="light blue", fg="black")
    
    def on_space_press(self, event):
        """Handle space key press"""
        if self.space_press_time is None:
            self.space_press_time = time.time()
            self.space_long_hold_id = self.after(3000, self.space_long_hold)
            if not self.scanning_backward:
                self.move_scan_forward()
    
    def on_space_release(self, event):
        """Handle space key release"""
        if self.space_long_hold_id:
            self.after_cancel(self.space_long_hold_id)
            self.space_long_hold_id = None
        self.space_press_time = None
        self.scanning_backward = False
    
    def space_long_hold(self):
        """Handle long space hold"""
        self.scanning_backward = True
        self.move_scan_backward()
        self.after(200, self.space_long_hold)
    
    def move_scan_forward(self):
        """Move scan forward"""
        if self.buttons:
            self.current_button_index = (self.current_button_index + 1) % len(self.buttons)
            self.highlight_button(self.current_button_index)
    
    def move_scan_backward(self):
        """Move scan backward"""
        if self.buttons:
            self.current_button_index = (self.current_button_index - 1) % len(self.buttons)
            self.highlight_button(self.current_button_index)
    
    def on_return_press(self, event):
        """Handle return key press"""
        if self.return_press_time is None:
            self.return_press_time = time.time()
            self.return_long_hold_id = self.after(6000, self.return_long_hold)
    
    def on_return_release(self, event):
        """Handle return key release"""
        if self.return_long_hold_id:
            self.after_cancel(self.return_long_hold_id)
            self.return_long_hold_id = None
        
        # Short press - select button
        if self.return_press_time and time.time() - self.return_press_time < 6:
            self.select_button()
        
        self.return_press_time = None
    
    def return_long_hold(self):
        """Handle long return hold - pause menu"""
        self.show_pause_menu()
    
    def select_button(self):
        """Select current button"""
        if self.buttons and 0 <= self.current_button_index < len(self.buttons):
            self.buttons[self.current_button_index].invoke()
    
    def show_pause_menu(self):
        """Show pause menu"""
        pause_window = tk.Toplevel(self)
        pause_window.title("Pause Menu")
        pause_window.geometry("400x300")
        pause_window.configure(bg="black")
        
        tk.Label(pause_window, text="Game Paused", font=("Arial", 24), 
                fg="white", bg="black").pack(pady=20)
        
        tk.Button(pause_window, text="Continue", font=("Arial", 18),
                 command=pause_window.destroy).pack(pady=10)
        
        tk.Button(pause_window, text="Exit Game", font=("Arial", 18),
                 command=lambda: [pause_window.destroy(), self.on_exit()]).pack(pady=10)
    
    def on_exit(self):
        """Exit the game and return to main app"""
        self.destroy()
        try:
            # Get the main app window and restore it
            self.restore_main_app()
        except Exception as e:
            print(f"Failed to restore main app: {e}")
    
    def restore_main_app(self):
        """Restore the main application window"""
        try:
            # Find the main app window
            hwnd = win32gui.FindWindow(None, "Accessible Menu")
            if hwnd:
                # Restore the window from minimized state
                win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
                win32gui.SetForegroundWindow(hwnd)
            else:
                # If window not found, launch the main app
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                script_path = os.path.join(project_root, "comm-v9.py")
                subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            print(f"Error restoring main app: {e}")

if __name__ == "__main__":
    app = TriviaGame()
    app.mainloop()