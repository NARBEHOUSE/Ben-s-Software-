import ctypes
import random
import sys
import threading
import time
import tkinter as tk

import pandas as pd
import win32gui

# Import shared utilities
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])  # Add project root to path
from shared import speak, get_data_dir, get_images_dir

# Path constants using shared utilities
DATA_DIR = get_data_dir()
IMG_DIR = get_images_dir()
TRIVIA_XLSX = DATA_DIR / "trivia_questions.xlsx"
TRIVIA_IMG = IMG_DIR / "trivia.png"


# -------------------- Data ---------------------
def load_trivia():
    data = {}
    try:
        df = pd.read_excel(TRIVIA_XLSX)
        for _, row in df.iterrows():
            topic = row["Topic"]
            q = {
                "question": row["Question"],
                "choices": [row[f"Choice{i}"] for i in range(1, 5)],
                "correct": int(row["Correct"]),
            }
            data.setdefault(topic, []).append(q)
    except Exception as e:
        print("[Trivia] Excel load error", e)
    return data


TRIVIA_DATA = load_trivia()


# ---------------- Base Frame -------------------
class MenuFrame(tk.Frame):
    def __init__(self, parent, title=""):
        super().__init__(parent, bg="black")
        self.parent = parent
        s = parent.ui_scale

        # dynamic fonts
        ctrl_size = max(8, int(12 * s))
        title_size = max(12, int(40 * s))
        max(10, int(32 * s))

        self.buttons = []
        self.cur_idx = -1
        self.space_pressed_time = None

        # Control bar
        bar = tk.Frame(self, bg="gray20")
        bar.pack(fill="x", side="top")
        tk.Button(
            bar,
            text="Minimize",
            command=parent.iconify,
            bg="light blue",
            fg="black",
            font=("Arial", ctrl_size),
        ).pack(side="right", padx=int(4 * s), pady=int(4 * s))
        tk.Button(
            bar,
            text="Close",
            command=parent.quit_to_main,
            bg="red",
            fg="white",
            font=("Arial", ctrl_size),
        ).pack(side="right", padx=int(4 * s), pady=int(4 * s))

        tk.Label(
            self, text=title, font=("Arial", title_size), fg="white", bg="black"
        ).pack(pady=int(20 * s))

        # Key bindings
        self.bind_all("<KeyPress-space>", self.start_hold)
        self.bind_all("<KeyRelease-space>", self.space_released)
        self.bind_all("<KeyRelease-Return>", self.select_btn)
        self.hold_thread = None

    # --------- scanning logic ---------
    def start_hold(self, evt):
        if self.space_pressed_time is None:
            self.space_pressed_time = time.time()
            self.hold_thread = threading.Thread(target=self.monitor_hold, daemon=True)
            self.hold_thread.start()

    def monitor_hold(self):
        while self.space_pressed_time is not None:
            held = time.time() - self.space_pressed_time
            if held >= 5:
                self.cur_idx = (self.cur_idx - 1) % len(self.buttons)
                self.highlight(self.cur_idx)
                time.sleep(1.5)
            else:
                time.sleep(0.1)

    def space_released(self, evt):
        if self.space_pressed_time is None:
            return
        if time.time() - self.space_pressed_time < 5:
            if self.cur_idx == -1:
                self.cur_idx = 0
            else:
                self.cur_idx = (self.cur_idx + 1) % len(self.buttons)
            self.highlight(self.cur_idx)
        self.space_pressed_time = None

    def select_btn(self, evt):
        if 0 <= self.cur_idx < len(self.buttons):
            self.buttons[self.cur_idx].invoke()

    def highlight(self, index):
        for i, b in enumerate(self.buttons):
            b.config(bg="yellow" if i == index else "light blue")
        speak(self.buttons[index]["text"])

    # ---------- grid helper ----------
    def create_button_grid(self, items, columns=3):
        s = self.parent.ui_scale
        grid = tk.Frame(self, bg="black")
        grid.pack(expand=True, fill="both")
        for i, (txt, cmd) in enumerate(items):
            r, c = divmod(i, columns)
            btn = tk.Button(
                grid,
                text=txt,
                command=cmd,
                font=("Arial Black", max(10, int(32 * s))),
                bg="light blue",
                fg="black",
                wraplength=int(600 * s),
                activebackground="yellow",
                activeforeground="black",
            )
            btn.grid(row=r, column=c, sticky="nsew", padx=int(10 * s), pady=int(10 * s))
            self.buttons.append(btn)
        for r in range((len(items) + columns - 1) // columns):
            grid.rowconfigure(r, weight=1)
        for c in range(columns):
            grid.columnconfigure(c, weight=1)


# ---------------- Main App ------------------
class TriviaApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # detect screen size and compute scale
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        BASE_W, BASE_H = 1920, 1080
        scale = min(sw / BASE_W, sh / BASE_H)
        self.ui_scale = scale

        self.title("Trivia Game")
        self.attributes("-fullscreen", True)
        self.configure(bg="black")

        self.frame = None
        self.correct = 0
        self.wrong = 0
        self.show(HomePage)

        # start up our background threads to keep focus and slam the Start Menu shut
        threading.Thread(target=self.monitor_focus, daemon=True).start()
        threading.Thread(target=self.monitor_start_menu, daemon=True).start()

    def show(self, cls, *a):
        if self.frame:
            self.frame.destroy()
        self.frame = cls(self, *a)
        self.frame.pack(expand=True, fill="both")

    def quit_to_main(self):
        from shared import quit_to_main

        quit_to_main(self)

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


# ---------------- Pages ------------------
class HomePage(MenuFrame):
    def __init__(self, app):
        super().__init__(app, "Trivia Game")
        s = app.ui_scale

        if TRIVIA_IMG.exists():
            img = tk.PhotoImage(file=TRIVIA_IMG)
            # auto-scale header image
            w = img.width()
            h = img.height()
            max_w = int(self.winfo_screenwidth() * 0.8)
            max_h = int(self.winfo_screenheight() * 0.3)
            ratio = min(max_w / w, max_h / h, 1.0)
            img = img.subsample(int(1 / ratio), int(1 / ratio))
            tk.Label(self, image=img, bg="black").pack(pady=int(10 * s))
            self.img = img

        self.create_button_grid(
            [
                ("Choose Topic", lambda: app.show(TopicPage)),
                ("Exit Game", app.quit_to_main),
            ],
            1,
        )
        self.after(100, lambda: speak("Trivia Game"))


class TopicPage(MenuFrame):
    def __init__(self, app):
        super().__init__(app, "Select Topic")
        items = [("Back", lambda: app.show(HomePage))]
        items += [
            (t, lambda t=t: app.show(GamePage, t)) for t in sorted(TRIVIA_DATA.keys())
        ]
        self.create_button_grid(items, 3)
        self.after(100, lambda: speak("Select a topic"))


class GamePage(MenuFrame):
    def __init__(self, app, topic):
        super().__init__(app, f"{topic} – 20 Questions")
        self.app = app
        self.topic = topic
        self.qs = random.sample(TRIVIA_DATA[topic], min(20, len(TRIVIA_DATA[topic])))
        self.idx = 0
        s = app.ui_scale

        # header image
        if TRIVIA_IMG.exists():
            img = tk.PhotoImage(file=TRIVIA_IMG)
            w, h = img.width(), img.height()
            max_w = int(self.winfo_screenwidth() * 0.6)
            max_h = int(self.winfo_screenheight() * 0.3)
            ratio = min(max_w / w, max_h / h, 1.0)
            img = img.subsample(int(1 / ratio), int(1 / ratio))
            tk.Label(self, image=img, bg="black").pack(pady=int(5 * s))
            self.img = img

        # question label
        qsize = max(12, int(28 * s))
        self.q_lbl = tk.Label(
            self,
            font=("Arial", qsize),
            fg="white",
            bg="black",
            wraplength=int(1000 * s),
        )
        self.q_lbl.pack(pady=int(20 * s), fill="x")

        # answer buttons grid
        self.ans_f = tk.Frame(self, bg="black")
        self.ans_f.pack()
        self.a_btns = []
        for i in range(4):
            btn = tk.Button(
                self.ans_f,
                font=("Arial", max(10, int(26 * s))),
                width=max(10, int(20 * s)),
                wraplength=int(400 * s),
                bg="light blue",
                fg="black",
                command=lambda i=i: self.pick(i),
            )
            btn.grid(row=0, column=i, padx=int(10 * s), pady=int(10 * s), sticky="nsew")
            self.a_btns.append(btn)
        for c in range(4):
            self.ans_f.columnconfigure(c, weight=1)

        # back button
        back = tk.Button(
            self,
            text="Back",
            font=("Arial", max(10, int(24 * s))),
            bg="light blue",
            fg="black",
            command=lambda: app.show(TopicPage),
        )
        back.pack(pady=int(10 * s))

        self.buttons = [*self.a_btns, back]
        self.cur_idx = -1

        self.stat = tk.Label(
            self, font=("Arial", max(10, int(22 * s))), fg="white", bg="black"
        )
        self.stat.pack()

        self.after(50, self.load_q)

    def load_q(self):
        if self.idx >= len(self.qs):
            self.q_lbl.config(
                text=f"Done! Correct {self.app.correct} Incorrect {self.app.wrong}"
            )
            for b in self.a_btns:
                b.config(state=tk.DISABLED)
            self.buttons = [self.buttons[-1]]  # only Back
            self.cur_idx = -1
            self.buttons[-1].config(text="Back to Main Menu")
            self.stat.config(text="Trivia Complete")
            speak(f"You got {self.app.correct} correct and {self.app.wrong} wrong.")
            return

        q = self.qs[self.idx]
        self.q_lbl.config(text=q["question"])
        self.stat.config(text=f"Question {self.idx+1}/{len(self.qs)}")

        choices = list(enumerate(q["choices"]))
        random.shuffle(choices)
        self.correct_idx = next(
            i for i, (orig, _) in enumerate(choices) if orig == q["correct"]
        )
        for i, (_, text) in enumerate(choices):
            self.a_btns[i].config(text=text, bg="light blue", state=tk.NORMAL)

        self.cur_idx = -1
        self.after(100, lambda: speak(q["question"]))

    def pick(self, i):
        if i == self.correct_idx:
            self.a_btns[i].config(bg="green")
            self.app.correct += 1
            speak("Correct")
        else:
            self.a_btns[i].config(bg="red")
            self.a_btns[self.correct_idx].config(bg="green")
            self.app.wrong += 1
            speak("Incorrect")
        self.after(2000, self.next_q)

    def next_q(self):
        self.idx += 1
        self.load_q()


# ---------------- Launch ------------------
if __name__ == "__main__":
    TriviaApp().mainloop()
