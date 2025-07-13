import tkinter as tk
import pyttsx3
import random
import time
import threading
import queue
import subprocess
import os
import win32gui
import ctypes
import pygame

# Initialize pygame, mixer, and TTS engine
pygame.init()
pygame.mixer.init()  # For sound effects
tts_engine = pyttsx3.init()

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ---------------- Load Sound Effects ----------------
baseball_bg = pygame.mixer.Sound(os.path.join("..", "soundfx", "baseballbg.wav"))
baseball_hit = pygame.mixer.Sound(os.path.join("..", "soundfx", "baseballhit.wav"))
homerun_sound = pygame.mixer.Sound(os.path.join("..", "soundfx", "homerun.wav"))

# Play ambience on loop (-1 loops indefinitely)
baseball_bg.play(-1)

def get_window_handle():
    try:
        info = pygame.display.get_wm_info()
        return info.get("window", None)  # Use .get() to prevent KeyError
    except Exception as e:
        print(f"Error getting window handle: {e}")
        return None

def monitor_focus():
    while True:
        time.sleep(0.5)
        hwnd = get_window_handle()
        if hwnd is None:
            print("Window handle not available. Skipping focus adjustment.")
            continue
        fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd != fg_hwnd:
            force_focus()

def send_esc_key():
    ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)
    print("ESC key sent to close Start Menu.")

def is_start_menu_open():
    hwnd = win32gui.GetForegroundWindow()
    class_name = win32gui.GetClassName(hwnd)
    return class_name in ["Shell_TrayWnd", "Windows.UI.Core.CoreWindow"]

def monitor_start_menu():
    while True:
        time.sleep(0.5)
        try:
            if is_start_menu_open():
                print("Start Menu detected. Closing it now.")
                send_esc_key()
        except Exception as e:
            print(f"Error in monitor_start_menu: {e}")

threading.Thread(target=monitor_focus, daemon=True).start()
threading.Thread(target=monitor_start_menu, daemon=True).start()

class BaseballGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Ben's Baseball Game")
        self.screen_width = root.winfo_screenwidth()
        self.screen_height = root.winfo_screenheight()
        self.root.geometry(f"{self.screen_width}x{self.screen_height}")
        self.root.state("zoomed")
        self.base_scale = min(self.screen_width / 800, self.screen_height / 600)
        self.diamond_side = min(self.screen_width, self.screen_height) * 0.4
        self.root.attributes("-fullscreen", True)

        # Persistent top frame for window controls (Close/Minimize)
        self.top_frame = tk.Frame(self.root, bg="lightgray")
        self.top_frame.pack(side="top", fill="x")
        minimize_btn = tk.Button(self.top_frame, text="_", command=self.minimize_game, font=("Arial", 12))
        minimize_btn.pack(side="right", padx=5, pady=5)
        close_btn = tk.Button(self.top_frame, text="X", command=self.close_game, font=("Arial", 12))
        close_btn.pack(side="right", padx=5, pady=5)        

        # Teams: Top half, you bat (red); Bottom half, you pitch (computer bats, blue)
        self.home_team = "Blue"   # computer defends in bottom half
        self.away_team = "Red"    # you bat in top half

        self.engine = pyttsx3.init()
        self.tts_queue = queue.Queue()
        threading.Thread(target=self._tts_worker, daemon=True).start()
        self.reset_game_state()

        self.extended_pitch_locations = [
            "Inside Left", "Inside Center", "Inside Right",
            "Top Corner Left", "Top Corner Right", "Top Center",
            "Bottom Corner Left", "Bottom Corner Right", "Bottom Center",
            "Outside"
        ]
        self.current_mode = "main_menu"
        self.selection_index = 0
        self.menu_options = []
        self.menu_text_items = []
        self.last_return_press_time = None

        self.root.bind("<KeyPress-Return>", self.on_return_press)
        self.root.bind("<KeyRelease-Return>", self.on_return_release)
        self.root.bind("<KeyRelease-space>", self.on_space_release)
        self.setup_main_menu()

    def reset_game_state(self):
        self.current_inning = 1
        self.half = "top"  # "top": you bat; "bottom": you pitch.
        self.outs = 0
        self.score = {self.home_team: 0, self.away_team: 0}
        # Use "user" for your runners; "comp" for computer's runners.
        self.bases = {"first": None, "second": None, "third": None}
        self.current_balls = 0
        self.current_strikes = 0
        self.first_pitch = True

    def force_focus(self):
        try:
            # Update window tasks to ensure the window is fully created
            self.root.update_idletasks()
            hwnd = self.root.winfo_id()
            if hwnd:
                self.root.iconify()
                self.root.deiconify()
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            else:
                print("Window handle not available. Skipping focus adjustment.")
        except Exception as e:
            print(f"Error forcing focus: {e}")

    def close_game(self):
        self.root.destroy()
    
    def minimize_game(self):
        self.root.iconify()

    def _tts_worker(self):
        while True:
            text = self.tts_queue.get()
            self.tts_playing = True
            self.engine.say(text)
            self.engine.runAndWait()
            self.tts_playing = False
            self.tts_queue.task_done()

    def speak(self, text):
        self.tts_queue.put(text)

    def clear_screen(self):
        # Only destroy widgets that are not the persistent top frame.
        for widget in self.root.winfo_children():
            if widget != self.top_frame:
                widget.destroy()

    def wait_for_tts_and_show_swing(self):
        if getattr(self, "tts_playing", False):
            self.root.after(100, self.wait_for_tts_and_show_swing)
        else:
            self.show_swing_menu()

    def wait_for_tts_and_show_pitch(self):
        if getattr(self, "tts_playing", False):
            self.root.after(100, self.wait_for_tts_and_show_pitch)
        else:
            self.show_pitch_menu()

    # ---------- Main Menu Setup ----------
    def setup_main_menu(self):
        self.current_mode = "main_menu"
        self.clear_screen()
        self.canvas = tk.Canvas(self.root, width=self.screen_width,
                                height=self.screen_height, bg="green")
        self.canvas.pack(fill="both", expand=True)
        cx = self.screen_width / 2
        cy = self.screen_height / 2
        ds = self.diamond_side

        title_font = ("Arial", int(50 * self.base_scale), "bold")
        self.canvas.create_text(cx, 50 * self.base_scale, text="Ben's Baseball Game",
                                font=title_font, fill="white")
        # Draw diamond outline
        home_pt = (cx, cy + ds / 2)
        first_pt = (cx + ds / 2, cy)
        second_pt = (cx, cy - ds / 2)
        third_pt = (cx - ds / 2, cy)
        self.canvas.create_polygon([home_pt, first_pt, second_pt, third_pt],
                                    outline="white", fill="", width=3)
        # Draw bases at diamond corners (using same shapes as in-game)
        self.draw_menu_bases()

        self.menu_options = ["Play Game", "Exit Game"]
        self.selection_index = 0
        self.menu_text_items = []
        opt_font = ("Arial", int(25 * self.base_scale))
        for i, opt in enumerate(self.menu_options):
            y_pos = cy + ds / 2 + 50 * self.base_scale + i * 40 * self.base_scale
            txt = self.canvas.create_text(cx, y_pos, text=opt, font=opt_font, fill="black")
            self.menu_text_items.append(txt)
        self.highlight_menu_option()
        self.root.after(100, lambda: self.speak("Ben's Baseball Game"))

    def draw_menu_bases(self):
        # Place the bases exactly at the diamond corners.
        cx = self.screen_width / 2
        cy = self.screen_height / 2
        ds = self.diamond_side  # use diamond_side so corners match the outline
        field_coords = {
            "home":   (cx, cy + ds / 2),
            "first":  (cx + ds / 2, cy),
            "second": (cx, cy - ds / 2),
            "third":  (cx - ds / 2, cy)
        }
        bs = ds * 0.1  # base size
        # Home base as a polygon (same as game)
        half = bs / 2
        roof = bs / 2
        pts = [field_coords["home"][0] - half, field_coords["home"][1] + half,
               field_coords["home"][0] + half, field_coords["home"][1] + half,
               field_coords["home"][0] + half, field_coords["home"][1] - half,
               field_coords["home"][0],          field_coords["home"][1] - half - roof,
               field_coords["home"][0] - half, field_coords["home"][1] - half]
        self.canvas.create_polygon(pts, outline="white", fill="white", width=3, tags="menu_base")
        # First, second, third as rectangles.
        for base in ["first", "second", "third"]:
            x, y = field_coords[base]
            self.canvas.create_rectangle(x - bs/2, y - bs/2, x + bs/2, y + bs/2,
                                         fill="white", outline="white", tags="menu_base")

    def highlight_menu_option(self):
        for i, item in enumerate(self.menu_text_items):
            color = "yellow" if i == self.selection_index else "black"
            self.canvas.itemconfig(item, fill=color)

    def on_space_release(self, event):
        if self.current_mode in ["main_menu", "pause_menu"]:
            self.selection_index = (self.selection_index + 1) % len(self.menu_options)
            self.highlight_menu_option()
            self.speak(self.menu_options[self.selection_index])

 # ---------- Modified Return Key Handlers ----------
    def on_return_press(self, event):
        """ Starts timing when Return is pressed. """
        if self.last_return_press_time is None:
            self.last_return_press_time = time.time()

        # Schedule a check to see if the key is still being held
        self.root.after(100, self.check_for_pause)

    def check_for_pause(self):
        """ Checks if the key has been held for 5 seconds and pauses the game. """
        if self.last_return_press_time is not None:
            hold_duration = time.time() - self.last_return_press_time
            if hold_duration >= 5:  # 5-second threshold
                self.show_pause_menu()
                self.last_return_press_time = None  # Reset
            else:
                # Keep checking every 100ms while the key is held
                self.root.after(100, self.check_for_pause)

    def on_return_release(self, event):
        hold_duration = time.time() - self.last_return_press_time if self.last_return_press_time else 0
        self.last_return_press_time = None  # Reset after detection

        if self.current_mode == "main_menu":
            self.handle_main_menu_selection()
        elif self.current_mode in ["gameplay"]:
            if hold_duration >= 5:  # Ensure 5-second press triggers pause
                self.show_pause_menu()

    def handle_main_menu_selection(self):
        sel = self.menu_options[self.selection_index]
        if sel == "Play Game":
            self.reset_game_state()
            self.start_gameplay()
        elif sel == "Exit Game":
            try:
                # Try to restore the main app window first
                hwnd = win32gui.FindWindow(None, "Accessible Menu")
                if hwnd:
                    # Restore the window from minimized state
                    win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
                    win32gui.SetForegroundWindow(hwnd)
                else:
                    # If window not found, launch the main app
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    comm_v9_path = os.path.join(current_dir, "..", "comm-v9.py")
                    subprocess.Popen(["python", comm_v9_path])
            except Exception as e:
                print("Failed to restore main app:", e)
            self.root.quit()
            quit()
              
    def show_pause_menu(self):
        # Save the current mode (which might be "batting_selection" or "pitch_selection")
        self.previous_mode = self.current_mode
        self.current_mode = "pause_menu"
        self.pause_window = tk.Toplevel(self.root)
        self.pause_window.title("Pause Menu")
        self.pause_window.attributes("-fullscreen", True)
        self.pause_window.configure(bg="darkgray")
        self.pause_window.transient(self.root)
        self.pause_window.grab_set()  # make it modal

        title = tk.Label(self.pause_window, text="Paused", font=("Arial", int(50 * self.base_scale)), bg="darkgray", fg="white")
        title.pack(pady=50)

        self.pause_options = ["Continue Game", "Main Menu"]
        self.pause_buttons = []
        self.pause_index = -1  # No auto-selection

        for opt in self.pause_options:
            btn = tk.Button(self.pause_window, text=opt,
                            font=("Arial", int(30 * self.base_scale)),
                            relief="raised", bd=5,
                            command=lambda o=opt: self.pause_menu_select(o))
            btn.pack(pady=20, fill="x")
            self.pause_buttons.append(btn)

        self.pause_window.bind("<KeyRelease-space>", self.on_pause_space)
        self.pause_window.bind("<KeyRelease-Return>", self.on_pause_return)
        self.pause_window.focus_force()

    def on_pause_space(self, event):
        """ Navigate the pause menu without auto-highlighting on open. """
        if self.pause_index == -1:
            self.pause_index = 0  # Start selection when space is first pressed
        else:
            self.pause_index = (self.pause_index + 1) % len(self.pause_buttons)
        
        self.update_pause_highlight()
        self.speak(self.pause_buttons[self.pause_index]['text'])

    def update_pause_highlight(self):
        """ Updates the highlighted button in the pause menu. """
        for i, btn in enumerate(self.pause_buttons):
            btn.config(bg="yellow" if i == self.pause_index else "SystemButtonFace")

    def on_pause_return(self, event):
        """ Prevents selection if no option has been highlighted. """
        if self.pause_index != -1:
            self.pause_buttons[self.pause_index].invoke()

    def pause_menu_select(self, selection):
        try:
            self.pause_window.grab_release()
        except Exception as e:
            print("Error releasing grab:", e)
        self.pause_window.destroy()

        if selection == "Continue Game":
            # Clean up any lingering interactive frames
            if hasattr(self, "swing_frame") and self.swing_frame.winfo_exists():
                self.swing_frame.destroy()
            if hasattr(self, "pitch_frame") and self.pitch_frame.winfo_exists():
                self.pitch_frame.destroy()

            # Resume game: clear any obsolete menus and continue the game loop.
            self.current_mode = "gameplay"
            self.continue_game()  # Or call the appropriate function to resume
        elif selection == "Main Menu":
            self.setup_main_menu()

    # ---------- Gameplay Setup & Drawing ----------
    def setup_gameplay_screen(self):
        self.clear_screen()
        self.canvas = tk.Canvas(self.root, width=self.screen_width,
                                height=self.screen_height, bg="green")
        self.canvas.pack(fill="both", expand=True)
        self.draw_field()
        self.draw_scoreboard()

    def start_gameplay(self):
        self.current_mode = "gameplay"
        self.setup_gameplay_screen()
        self.half = "top"  # start with you batting
        self.root.after(1000, self.next_play)

    def draw_field(self):
        cx = self.screen_width / 2
        cy = self.screen_height / 2 + 20 * self.base_scale
        ds = self.diamond_side * 1.3
        self.game_diamond_side = ds
        self.field_coords = {
            "home": (cx, cy + ds / 2),
            "first": (cx + ds / 2, cy),
            "second": (cx, cy - ds / 2),
            "third": (cx - ds / 2, cy)
        }
        self.canvas.create_polygon([self.field_coords["home"],
                                     self.field_coords["first"],
                                     self.field_coords["second"],
                                     self.field_coords["third"]],
                                    outline="white", fill="", width=3)
        self.draw_bases()
        box_size = ds * 0.25
        self.pitchers_box = (cx - box_size / 2, cy - box_size / 2, cx + box_size / 2, cy + box_size / 2)
        self.canvas.create_rectangle(*self.pitchers_box, outline="white", width=3)
        self.pitchers_box_center = (cx, cy)
        def ext_line(p1, p2, factor=1.5):
            return (p1[0] + factor * (p2[0] - p1[0]), p1[1] + factor * (p2[1] - p1[1]))
        self.canvas.create_line(self.field_coords["home"][0], self.field_coords["home"][1],
                                *ext_line(self.field_coords["home"], self.field_coords["first"]),
                                fill="white", width=2)
        self.canvas.create_line(self.field_coords["home"][0], self.field_coords["home"][1],
                                *ext_line(self.field_coords["home"], self.field_coords["third"]),
                                fill="white", width=2)

    def draw_bases(self):
        ds = self.game_diamond_side
        bs = ds * 0.1
        for b in ["home", "first", "second", "third"]:
            x, y = self.field_coords[b]
            if b == "home":
                half = bs / 2
                roof = bs / 2
                pts = [x - half, y + half, x + half, y + half, x + half, y - half, x, y - half - roof, x - half, y - half]
                self.canvas.create_polygon(pts, outline="white", fill="white", width=3, tags="base")
            else:
                col = "white"
                if self.bases[b]:
                    col = "red" if self.bases[b] == "user" else "blue"
                self.canvas.create_rectangle(x - bs/2, y - bs/2, x + bs/2, y + bs/2,
                                             fill=col, tags="base")

    def draw_scoreboard(self):
        # Clear any previous scoreboard items.
        self.canvas.delete("scoreboard")
        
        # Top-center text: Inning and Outs.
        cx = self.screen_width / 2
        top_text = f"INNING: {self.half.upper()} {self.current_inning}       OUTS: {self.outs}/3"
        self.canvas.create_text(cx, 30 * self.base_scale, 
                                text=top_text, 
                                font=("Arial", int(24 * self.base_scale), "bold"), 
                                fill="white", 
                                tags="scoreboard")
        
        # Use 1/5 of the screen width for positioning the side scores.
        left_x = self.screen_width * 0.2
        right_x = self.screen_width * 0.8
        # Place the scores near the top so they aren't blocked by the pitch/swing menus.
        score_y = 130 * self.base_scale  # adjust this value as needed
        
        # Use a large font: about 300% larger than before.
        score_font = ("Arial", int(108 * self.base_scale), "bold")
        
        # Draw player's score (red) on the left.
        self.canvas.create_text(left_x, score_y, 
                                text=str(self.score[self.away_team]), 
                                font=score_font, 
                                fill="red", 
                                tags="scoreboard")
        # Draw computer's score (blue) on the right.
        self.canvas.create_text(right_x, score_y, 
                                text=str(self.score[self.home_team]), 
                                font=score_font, 
                                fill="blue", 
                                tags="scoreboard")


    def update_batter_counter_display(self):
        txt = f"Strikes: {self.current_strikes}/3   Balls: {self.current_balls}/4"
        font = ("Arial", int(18 * self.base_scale))
        self.canvas.delete("batter_counter")
        self.canvas.create_text(self.screen_width - 150 * self.base_scale, self.screen_height - 100 * self.base_scale,
                                text=txt, font=font, fill="white", tags="batter_counter")

    def reset_batter_counter(self):
        self.current_strikes = 0
        self.current_balls = 0
        self.update_batter_counter_display()

    def announce_half_inning(self):
        ann = f"Top of the {self.ordinal(self.current_inning)} inning." if self.half == "top" else f"Bottom of the {self.ordinal(self.current_inning)} inning."
        outs_txt = {0: "zero outs", 1: "one out", 2: "two outs", 3: "three outs"}[self.outs]
        self.speak(f"{ann} And {outs_txt}.")
        # Immediately redraw the bases so they appear at the start.
        self.draw_bases()
        self.first_pitch = False
        self.root.after(2000, self.next_play)

    def ordinal(self, n):
        return {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth",
                6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth"}.get(n, str(n))

    def next_play(self):
        # Clear previous animation elements.
        self.canvas.delete("ball_marker")
        self.canvas.delete("blue_line")
        self.canvas.delete("pitch_marker")
        if self.first_pitch:
            self.announce_half_inning()
            return
        if self.outs >= 3:
            self.end_half_inning()
        else:
            if self.half == "top":
                self.start_batting_phase()
            else:
                self.start_pitching_phase()

    # ---------- Top Half: Player Bats (Computer Pitches) ----------
    def start_batting_phase(self):
        self.current_mode = "batting_selection"
        self.canvas.delete("pitch_marker")
        self.canvas.delete("blue_line")
        self.simulate_computer_pitch()
        self.speak("Pitcher throws ball.")
        # Wait until TTS finishes before showing swing options.
        self.wait_for_tts_and_show_swing()

    def simulate_computer_pitch(self):
        self.selected_pitch_type = random.choice(["Fastball", "Curveball", "Slider", "Knuckleball", "Changeup"])
        self.selected_pitch_location = random.choice(self.extended_pitch_locations)

    def draw_pitch_marker(self, location, color="white"):
        x1, y1, x2, y2 = self.pitchers_box
        box_w = x2 - x1
        center = self.pitchers_box_center
        offsets = {"Inside": (-box_w * 0.15, 0),
                   "Middle": (0, 0),
                   "Outside": (box_w * 0.15, 0)}
        off = offsets.get(location, (0, 0))
        new_cx = center[0] + off[0]
        new_cy = center[1] + off[1]
        r = 10 * self.base_scale
        self.canvas.delete("pitch_marker")
        self.canvas.create_oval(new_cx - r, new_cy - r, new_cx + r, new_cy + r,
                                outline=color, width=2, tags="pitch_marker")

    def show_swing_menu(self):
        # Destroy any existing swing menu before creating a new one.
        if hasattr(self, "swing_frame") and self.swing_frame.winfo_exists():
            self.swing_frame.destroy()

        self.swing_frame = tk.Frame(self.root, bg="lightgray")
        self.swing_frame.place(relx=0.05, rely=0.40, relwidth=0.2, relheight=0.5)
        # Base options for swinging.
        self.menu_options = ["Normal Swing", "Power Swing", "Hold", "Bunt"]
        if self.bases.get("first") and not self.bases.get("second"):
            self.menu_options.append("Steal 2nd Base")
        if self.bases.get("second"):
            self.menu_options.append("Steal 3rd Base")
        
        self.swing_buttons = []
        self.swing_index = -1
        for opt in self.menu_options:
            btn = tk.Button(self.swing_frame, text=opt,
                            font=("Arial", int(18 * self.base_scale)),
                            relief="raised", bd=2,
                            command=lambda o=opt: self.process_batting_selection(o))
            btn.pack(pady=5, fill="x")
            self.swing_buttons.append(btn)
        self.update_swing_highlight()
        # Force focus so its key bindings are active.
        self.swing_frame.focus_force()
        self.swing_frame.bind("<KeyRelease-space>", self.on_swing_space)
        self.swing_frame.bind("<KeyRelease-Return>", self.on_swing_return)

    def update_swing_highlight(self):
        for i, btn in enumerate(self.swing_buttons):
            btn.config(bg="yellow" if i == self.swing_index else "SystemButtonFace")

    def on_swing_space(self, event):
        self.swing_index = (self.swing_index + 1) % len(self.swing_buttons)
        self.update_swing_highlight()
        self.speak(self.swing_buttons[self.swing_index]['text'])

    def on_swing_return(self, event):
        self.swing_buttons[self.swing_index].invoke()

    def process_batting_selection(self, selected):
        self.selected_swing = selected
        self.swing_frame.destroy()
        self.canvas.delete("pitch_marker")
        terminal = False

        if selected in ["Steal 2nd Base", "Steal 3rd Base"]:
            if selected == "Steal 2nd Base":
                if random.uniform(0, 100) < 25:
                    outcome = "Steal Success"
                    self.bases["second"] = "user"
                    self.bases["first"] = None
                else:
                    outcome = "Steal Failed"
                    self.outs += 1
                    self.bases["first"] = None
            else:
                if random.uniform(0, 100) < 15:
                    outcome = "Steal Success"
                    self.bases["third"] = "user"
                    self.bases["second"] = None
                else:
                    outcome = "Steal Failed"
                    self.outs += 1
                    self.bases["second"] = None
            self.speak("Steal " + ("successful." if outcome == "Steal Success" else "failed. Runner is out."))
            terminal = True
        elif selected == "Bunt":
            outcome = random.choices(["Single", "Ground Out"], weights=[30, 70], k=1)[0]
            terminal = True
            if outcome == "Single":
                self.update_bases("Single", batter="user")
            elif outcome == "Ground Out":
                self.outs += 1
        else:
            if selected == "Hold":
                outcome = "Ball" if self.selected_pitch_location == "Outside" else ("Ball" if random.uniform(0, 100) <= 60 else "Strike")
            elif selected == "Power Swing":
                if self.selected_pitch_type == "Fastball":
                    outcome = self.weighted_choice({"Strike": 60, "Pop Fly Out": 30, "HR": 10})
                else:
                    outcome = self.weighted_choice({"Strike": 40, "HR": 10, "Pop Fly Out": 20, "Double": 15, "Foul": 15})
            else:
                outcome = self.simulate_batting(selected, self.selected_pitch_type)
            
            if outcome == "HR":
                outcome = "Home Run"
            
            terminal = outcome in ["Single", "Double", "Triple", "Home Run", "Walk", "Strike Out", "Pop Fly Out", "Ground Out"]
            
            if outcome == "Foul":
                if self.current_strikes < 2:
                    self.current_strikes += 1
                    self.speak(f"Foul. Strike {self.current_strikes}.")
                else:
                    self.speak("Foul.")
                self.update_batter_counter_display()
                baseball_hit.play()  # Play hit sound for foul
            elif outcome == "Strike":
                self.current_strikes += 1
                self.speak(f"Strike {self.current_strikes}.")
                self.update_batter_counter_display()
                self.draw_pitch_marker(self.selected_pitch_location, color="red")  # Ensure red indicator shows
                if self.current_strikes == 3:
                    outcome = "Strike Out"
                    self.outs += 1
                    terminal = True
            elif outcome == "Ball":
                self.current_balls += 1
                self.speak(f"Ball {self.current_balls}.")
                self.update_batter_counter_display()
                if self.current_balls == 4:
                    outcome = "Walk"
                    terminal = True
            elif outcome in ["Pop Fly Out", "Ground Out"]:
                self.outs += 1
                baseball_hit.play()  # Play hit sound for ground out & pop fly
                terminal = True
            elif outcome in ["Single", "Double", "Triple", "Home Run", "Walk"]:
                if outcome == "Walk":
                    self.update_bases("Single", batter="user")
                else:
                    self.update_bases(outcome, batter="user")
                terminal = True

        if outcome in ["Single", "Double", "Triple"]:
            baseball_hit.play()  # Play sound for any normal hit
        elif outcome == "Home Run":
            homerun_sound.play()  # Play the home run sound

        self.speak(f"Result of your swing: {outcome}.")
        if terminal:
            self.reset_batter_counter()
            if self.outs >= 3:
                self.animate_ball_landing(outcome, lambda: self.end_half_inning())
            else:
                self.animate_ball_landing(outcome, lambda: self.finish_update(outcome))
        else:
            self.root.after(1500, self.continue_at_bat)

    def simulate_batting(self, swing, pitch):
        choices = {"Strike": 40, "Foul": 10, "Pop Fly Out": 10, "Ground Out": 15,
                   "Single": 20, "Double": 4, "Triple": 1, "HR": 0.5}
        return self.weighted_choice(choices)

    def weighted_choice(self, choices):
        tot = sum(choices.values())
        r = random.uniform(0, tot)
        cum = 0
        for outcome, weight in choices.items():
            cum += weight
            if r <= cum:
                return outcome
        return "Strike"

    def update_bases(self, outcome, batter):
        if outcome == "Single":
            # If there's a runner on third, they score.
            if self.bases["third"]:
                self.score[self.away_team if self.half=="top" else self.home_team] += 1
            # Shift runners: third gets runner from second, second gets runner from first.
            self.bases["third"] = self.bases["second"]
            self.bases["second"] = self.bases["first"]
            # Batter takes first base.
            self.bases["first"] = batter
        elif outcome == "Double":
            if self.bases["third"]:
                self.score[self.away_team if self.half=="top" else self.home_team] += 1
            if self.bases["second"]:
                self.score[self.away_team if self.half=="top" else self.home_team] += 1
            self.bases["third"] = self.bases["first"]
            self.bases["first"] = None
            self.bases["second"] = batter
        elif outcome == "Triple":
            for base in ["first", "second", "third"]:
                if self.bases[base]:
                    self.score[self.away_team if self.half=="top" else self.home_team] += 1
                    self.bases[base] = None
            self.bases["third"] = batter
        elif outcome == "Home Run":
            runs = 1  # Batter scores.
            for base in ["first", "second", "third"]:
                if self.bases[base]:
                    runs += 1
                    self.bases[base] = None
            if self.half=="top":
                self.score[self.away_team] += runs
            else:
                self.score[self.home_team] += runs
        elif outcome == "Walk":
            # For a walk, simply place the batter on first.
            self.bases["first"] = batter

    def animate_ball_landing(self, outcome, callback):
        # Outcomes that shouldn't animate
        no_animation = {"Strike", "Strike Out", "Ball", "Pitch Hit", "Steal Success", "Steal Failed", "Walk"}
        if outcome in no_animation:
            callback()
            return

        start = self.field_coords["home"]

        if outcome == "Foul":
            margin = 20
            ds = self.game_diamond_side
            home = self.field_coords["home"]
            first = self.field_coords["first"]
            third = self.field_coords["third"]
            cy = self.field_coords["first"][1]
            region = random.choice(["left", "right", "behind"])
            if region == "left":
                end_x = random.randint(0, int(third[0] - margin))
                end_y = random.randint(int(cy - ds/2), int(cy + ds/2))
            elif region == "right":
                end_x = random.randint(int(first[0] + margin), self.screen_width)
                end_y = random.randint(int(cy - ds/2), int(cy + ds/2))
            else:
                end_y = random.randint(int(home[1] + margin), self.screen_height)
                end_x = random.randint(int(third[0]), int(first[0]))
            end = (end_x, end_y)
        elif outcome == "Pop Fly Out":
            x1, y1, x2, y2 = self.pitchers_box
            while True:
                end = (random.randint(int(self.field_coords["third"][0]), int(self.field_coords["first"][0])),
                    random.randint(int(self.field_coords["second"][1]), int(self.field_coords["home"][1])))
                if not (x1 <= end[0] <= x2 and y1 <= end[1] <= y2):
                    break
        elif outcome in {"Ground Out", "Double Play"}:
            # Instead of a random offset, we use the diamond's infield line.
            # For a ground out, the ball flies from home directly to first base.
            end = self.field_coords["first"]
        elif outcome == "Home Run":
            cx = (self.field_coords["first"][0] + self.field_coords["third"][0]) // 2
            cy = (self.field_coords["first"][1] + self.field_coords["third"][1]) // 2
            end = (cx, cy - int(0.4 * min(self.screen_width, self.screen_height)))
        else:
            # For Single, Double, Triple, etc.
            cx = (self.field_coords["first"][0] + self.field_coords["third"][0]) // 2
            cy = (self.field_coords["first"][1] + self.field_coords["third"][1]) // 2
            end = (cx, cy - int(0.15 * min(self.screen_width, self.screen_height)))

        # Draw a blue line for the flight path.
        self.canvas.create_line(start[0], start[1], end[0], end[1],
                                fill="blue", width=2, tags="blue_line")
        # Create a white ball at the start.
        ball = self.canvas.create_oval(start[0]-5, start[1]-5, start[0]+5, start[1]+5,
                                    fill="white", outline="")
        steps = 20
        dx = (end[0] - start[0]) / steps
        dy = (end[1] - start[1]) / steps

        def animate(step):
            if step < steps:
                self.canvas.move(ball, dx, dy)
                self.root.after(50, lambda: animate(step+1))
            else:
                self.canvas.delete(ball)
                # For a pop fly out, display a red X at the endpoint.
                if outcome == "Pop Fly Out":
                    self.canvas.create_text(end[0], end[1], text="X",
                                            font=("Arial", int(30 * self.base_scale)),
                                            fill="red", tags="ball_marker")
                callback()
        animate(0)

    def update_game_after_play(self, outcome):
        self.canvas.delete("ball_marker")
        self.canvas.delete("pitch_marker")
        if outcome in {"Ground Out", "Strike Out", "Pop Fly Out", "Steal Failed", "Double Play"}:
            if outcome == "Pop Fly Out":
                x1, y1, x2, y2 = self.pitchers_box
                while True:
                    rx = random.randint(int(self.field_coords["third"][0]), int(self.field_coords["first"][0]))
                    ry = random.randint(int(self.field_coords["second"][1]), int(self.field_coords["home"][1]))
                    if not (x1 <= rx <= x2 and y1 <= ry <= y2):
                        break
                self.canvas.create_text(rx, ry, text="X", font=("Arial", int(30 * self.base_scale)),
                                        fill="red", tags="ball_marker")
            elif outcome == "Ground Out":
                fx, fy = self.field_coords["first"]
                self.canvas.create_text(fx + 10, fy, text="X", font=("Arial", int(30 * self.base_scale)),
                                        fill="red", tags="ball_marker")
            self.outs += 1
        if outcome in {"Strike", "Strike Out"}:
            self.draw_pitch_marker(self.selected_pitch_location, color="red")
        elif outcome in {"Ball", "Pitch Hit"}:
            self.draw_pitch_marker(self.selected_pitch_location, color="white")
        self.canvas.delete("base")
        self.draw_bases()
        self.canvas.delete("scoreboard")
        self.draw_scoreboard()
        self.root.after(random.randint(4000, 7000), self.continue_game)

    def continue_game(self):
        if self.outs >= 3:
            self.end_half_inning()
        else:
            if self.half == "top":
                self.start_batting_phase()
            else:
                self.start_pitching_phase()

    def continue_at_bat(self):
        if self.half == "top":
            self.root.after(1000, self.start_batting_phase)
        else:
            self.root.after(1000, self.start_pitching_phase)

    # ---------- Bottom Half: Player Pitches (Computer Bats) ----------
    # Remove pitch location selection; the pitch location is now chosen randomly.
    def start_pitching_phase(self):
        self.current_mode = "pitch_selection"
        self.canvas.delete("pitch_marker")
        self.canvas.delete("blue_line")
        # Destroy any existing pitch frame
        if hasattr(self, 'pitch_frame'):
            self.pitch_frame.destroy()
        self.speak("Choose your pitch.")
        self.wait_for_tts_and_show_pitch()

    def show_pitch_menu(self):
        # Destroy any existing pitch menu before creating a new one.
        if hasattr(self, "pitch_frame") and self.pitch_frame.winfo_exists():
            self.pitch_frame.destroy()

        self.pitch_frame = tk.Frame(self.root, bg="lightgray")
        self.pitch_frame.place(relx=0.05, rely=0.45, relwidth=0.2, relheight=0.6)
        self.menu_options = ["Fastball", "Curveball", "Slider", "Knuckleball", "Changeup"]
        self.pitch_buttons = []
        self.pitch_index = -1
        for opt in self.menu_options:
            btn = tk.Button(self.pitch_frame, text=opt,
                            font=("Arial", int(18 * self.base_scale)),
                            relief="raised", bd=2,
                            command=lambda o=opt: self.process_pitch_selection(o))
            btn.pack(pady=5, fill="x")
            self.pitch_buttons.append(btn)
        self.update_pitch_highlight()
        self.pitch_frame.focus_force()  # Ensure the pitch menu grabs focus
        self.pitch_frame.bind("<KeyRelease-space>", self.on_pitch_space)
        self.pitch_frame.bind("<KeyRelease-Return>", self.on_pitch_return)

    def update_pitch_highlight(self):
        for i, btn in enumerate(self.pitch_buttons):
            btn.config(bg="yellow" if i == self.pitch_index else "SystemButtonFace")

    def on_pitch_space(self, event):
        self.pitch_index = (self.pitch_index + 1) % len(self.pitch_buttons)
        self.update_pitch_highlight()
        self.speak(self.pitch_buttons[self.pitch_index]['text'])

    def on_pitch_return(self, event):
        self.pitch_buttons[self.pitch_index].invoke()

    def process_pitch_selection(self, selected):
        self.selected_pitch_type = selected
        self.pitch_frame.destroy()
        # Instead of letting the player choose pitch location, choose it randomly.
        self.selected_pitch_location = random.choice(["Inside", "Middle", "Outside"])
        self.draw_pitch_marker(self.selected_pitch_location, color="white")
        self.speak(f"Pitch: {self.selected_pitch_type} {self.selected_pitch_location}.")
        self.process_pitch(self.selected_pitch_type, self.selected_pitch_location)

    def process_pitch(self, pitch_type, pitch_location):
        if self.half != "bottom":
            return

        if hasattr(self, 'pitch_frame'):
            self.pitch_frame.destroy()

        fatigue = 0
        if pitch_type == "Fastball":
            strike, ball, hit_prob = (80, 10, 10)
        elif pitch_type == "Curveball":
            strike, ball, hit_prob = (65, 10, 25)
        elif pitch_type == "Slider":
            strike, ball, hit_prob = (70, 10, 20)
        elif pitch_type == "Knuckleball":
            strike, ball, hit_prob = (65, 15, 25)
        elif pitch_type == "Changeup":
            strike, ball, hit_prob = (58, 12, 32)
        else:
            strike, ball, hit_prob = (60, 10, 30)
        
        hit_prob += fatigue
        total = strike + ball + hit_prob
        r = random.uniform(0, total)

        if r <= strike:
            outcome = "Strike"
        elif r <= strike + ball:
            outcome = "Ball"
        else:
            # Updated hit_choices to include pop fly outs and ground outs
            hit_choices = {
                "Single": 20,
                "Double": 4,
                "Triple": 1,
                "HR": 0.5,
                "Pop Fly Out": 10,
                "Ground Out": 10
            }
            outcome = self.weighted_choice(hit_choices)
            if outcome == "HR":
                outcome = "Home Run"

        if outcome == "Strike":
            self.draw_pitch_marker(pitch_location, color="red")
        else:
            self.draw_pitch_marker(pitch_location, color="white")

        if outcome == "Foul":
            if self.current_strikes < 2:
                self.current_strikes += 1
                self.speak(f"Computer batter foul. Strike {self.current_strikes}.")
            else:
                self.speak("Computer batter foul.")
            self.update_batter_counter_display()
            baseball_hit.play()  # Play hit sound for foul
            self.root.after(500, self.wait_for_tts_and_show_pitch)
            return
        elif outcome == "Strike":
            self.current_strikes += 1
            self.speak(f"Computer batter strike {self.current_strikes}.")
            self.update_batter_counter_display()
            if self.current_strikes < 3:
                self.root.after(500, self.wait_for_tts_and_show_pitch)
                return
            else:
                outcome = "Strike Out"
                self.outs += 1
        elif outcome == "Ball":
            self.current_balls += 1
            self.speak(f"Computer batter ball {self.current_balls}.")
            self.update_batter_counter_display()
            if self.current_balls < 4:
                self.root.after(500, self.wait_for_tts_and_show_pitch)
                return
            else:
                outcome = "Walk"
                self.update_bases("Single", batter="comp")
        elif outcome in ["Pop Fly Out", "Ground Out"]:
            self.outs += 1
            baseball_hit.play()  # Play hit sound for ground out & pop fly
        elif outcome in ["Single", "Double", "Triple", "Home Run"]:
            self.update_bases(outcome, batter="comp")

        self.reset_batter_counter()

        def after_anim():
            self.finish_update(outcome)
            self.speak(f"Result of computer batter: {outcome}.")

        if outcome in ["Single", "Double", "Triple"]:
            baseball_hit.play()  # Play sound for any normal hit
        elif outcome == "Home Run":
            homerun_sound.play()  # Play home run sound

        allowed = {"Single", "Double", "Triple", "Home Run", "Foul", "Pop Fly Out"}
        if outcome in allowed:
            self.animate_ball_landing(outcome, after_anim)
        else:
            after_anim()

    def update_game_after_play(self, outcome):
        self.canvas.delete("ball_marker")
        self.canvas.delete("pitch_marker")
        if outcome in {"Ground Out", "Strike Out", "Pop Fly Out", "Steal Failed", "Double Play"}:
            if outcome == "Pop Fly Out":
                x1, y1, x2, y2 = self.pitchers_box
                while True:
                    rx = random.randint(int(self.field_coords["third"][0]), int(self.field_coords["first"][0]))
                    ry = random.randint(int(self.field_coords["second"][1]), int(self.field_coords["home"][1]))
                    if not (x1 <= rx <= x2 and y1 <= ry <= y2):
                        break
                self.canvas.create_text(rx, ry, text="X", font=("Arial", int(30 * self.base_scale)),
                                        fill="red", tags="ball_marker")
            elif outcome == "Ground Out":
                fx, fy = self.field_coords["first"]
                self.canvas.create_text(fx + 10, fy, text="X", font=("Arial", int(30 * self.base_scale)),
                                        fill="red", tags="ball_marker")
            self.outs += 1
        if outcome in {"Strike", "Strike Out"}:
            self.draw_pitch_marker(self.selected_pitch_location, color="red")
        elif outcome in {"Ball", "Pitch Hit"}:
            self.draw_pitch_marker(self.selected_pitch_location, color="white")
        self.canvas.delete("base")
        self.draw_bases()
        self.canvas.delete("scoreboard")
        self.draw_scoreboard()
        self.root.after(random.randint(4000, 7000), self.continue_game)

    def finish_update(self, outcome):
        # Clear temporary animation elements.
        self.canvas.delete("blue_line")
        self.canvas.delete("ball_marker")
        self.canvas.delete("pitch_marker")
        self.canvas.delete("base")
        self.draw_bases()
        self.canvas.delete("scoreboard")
        self.draw_scoreboard()
        # If 3 or more outs, switch inning immediately.
        if self.outs >= 3:
            self.root.after(2000, self.end_half_inning)
        else:
            # Otherwise, schedule the next plate appearance.
            if self.half == "top":
                self.root.after(2000, self.start_batting_phase)
            else:
                self.root.after(2000, self.start_pitching_phase)

    def continue_game(self):
        if self.outs >= 3:
            self.end_half_inning()
        else:
            if self.half == "top":
                self.start_batting_phase()
            else:
                self.start_pitching_phase()

    def continue_at_bat(self):
        if self.half == "top":
            self.root.after(1000, self.start_batting_phase)
        else:
            self.root.after(1000, self.start_pitching_phase)

    def end_half_inning(self):
        """Handles switching between innings and detecting end of game conditions."""
        self.speak(f"Half inning over with {self.outs} outs.")
        self.outs = 0
        self.bases = {"first": None, "second": None, "third": None}
        self.canvas.delete("base")
        self.canvas.delete("ball_marker")
        self.canvas.delete("blue_line")

        # END GAME CHECK: If it's the bottom of the 9th inning, determine the result
        if self.current_inning == 9 and self.half == "bottom":
            if self.score[self.home_team] > self.score[self.away_team]:
                # Home team (computer) wins
                self.end_game()
                return
            elif self.score[self.home_team] == self.score[self.away_team]:
                # Game is tied: go to extra innings
                self.current_inning += 1
                self.half = "top"
                self.first_pitch = True
                self.canvas.delete("scoreboard")
                self.draw_scoreboard()
                self.root.after(1000, self.next_play)
                return
            else:
                # Away team (player) wins
                self.end_game()
                return

        # CONTINUE GAME: Otherwise, switch between top/bottom of innings
        if self.half == "top":
            self.half = "bottom"
        else:
            self.half = "top"
            self.current_inning += 1

        self.first_pitch = True
        self.canvas.delete("scoreboard")
        self.draw_scoreboard()
        self.root.after(500, self.next_play)

    def end_game(self):
        """Ends the game and displays the winner before returning to the main menu."""
        self.clear_screen()

        # Determine the winner
        if self.score[self.away_team] > self.score[self.home_team]:
            result_text = "YOU WON!"
            result_color = "green"
        else:
            result_text = "YOU LOST!"
            result_color = "red"

        # Display final screen
        self.canvas = tk.Canvas(self.root, width=self.screen_width, height=self.screen_height, bg="black")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.create_text(self.screen_width / 2, self.screen_height / 2,
                                text=result_text, font=("Arial", int(80 * self.base_scale), "bold"),
                                fill=result_color)

        # Speak the result
        self.speak(result_text)

        # Return to the main menu after 5 seconds
        self.root.after(5000, self.setup_main_menu)

if __name__ == "__main__":
    root = tk.Tk()
    game = BaseballGame(root)
    # Delay force_focus to allow the window to be fully created
    root.after(1000, game.force_focus)
    root.mainloop()