# © 2025 NARBE House – Licensed under CC BY-NC 4.0

import ctypes
import os
import subprocess
import sys
import threading
import time
import tkinter as tk

from keyboard_predictive import get_predictive_suggestions, update_word_usage
import pyttsx3  # For Text-to-Speech functionality
import win32gui


class KeyboardFrameApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Keyboard Application")
        self.geometry("960x540")
        self.attributes("-fullscreen", True)
        self.configure(bg="black")

        self.create_window_controls()
        self.keyboard_frame = KeyboardFrame(self)
        self.keyboard_frame.pack(expand=True, fill="both")

        self.monitor_focus_thread = threading.Thread(
            target=self.monitor_focus, daemon=True
        )
        self.monitor_focus_thread.start()

        self.monitor_start_menu_thread = threading.Thread(
            target=self.monitor_start_menu, daemon=True
        )
        self.monitor_start_menu_thread.start()

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


class KeyboardFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="black")
        self.parent = parent
        self.current_text = tk.StringVar()
        self.current_row_index = 0
        self.current_button_index = 0
        self.in_row_selection_mode = True
        self.spacebar_pressed = False
        self.backward_scanning_active = False
        self.scanning_thread = None
        self.press_time = None  # To record the time when spacebar is pressed
        self.debounce_time = 0.1
        self.toggle_cursor()
        self.tts_trigger_count = 0

        self.tts_engine = pyttsx3.init()  # Initialize TTS engine

        # Initialize current mode
        self.current_mode = "Keyboard"  # Default mode is "Keyboard"

        # Initialize rows and row_titles
        self.row_titles = [
            "Controls",
            "A-B-C-D-E-F",
            "G-H-I-J-K-L",
            "M-N-O-P-Q-R",
            "S-T-U-V-W-X",
            "Y-Z 1 2 3",
            "4 5 6 7 8 9",
            "Predictive Text",
        ]
        self.rows = [
            ["Space", "Del Letter", "Del Word", "Clear", "Layout", "Main"],  # Controls
            ["A", "B", "C", "D", "E", "F"],
            ["G", "H", "I", "J", "K", "L"],
            ["M", "N", "O", "P", "Q", "R"],
            ["S", "T", "U", "V", "W", "X"],
            ["Y", "Z", "0", "1", "2", "3"],
            ["4", "5", "6", "7", "8", "9"],
        ]

        # Define predictive text row
        self.predictive_text_row = [
            "",
            "",
            "",
            "",
            "",
            "",
        ]  # Placeholder for predictive text
        self.rows.append(self.predictive_text_row)  # Append to the rows list

        # Create the layout
        self.create_layout()
        self.bind_keys()
        self.highlight_row(0)  # Start with the first row highlighted
        self.update_predictive_text()  # ✅ Load predictions when the keyboard starts

    def update_predictive_text(self):
        """Dynamically updates the predictive text row in real-time."""
        text = self.current_text.get().strip()
        print(f"DEBUG: Current text input = '{text}'")  # Debugging line

        suggestions = get_predictive_suggestions(text)
        print(f"DEBUG: Predicted suggestions = {suggestions}")  # Debugging line

        # Ensure exactly 6 slots are filled in the predictive text row
        self.predictive_text_row[:] = suggestions + [""] * (6 - len(suggestions))

        # Update the last row dynamically
        if len(self.rows) > 0:
            self.rows[-1] = self.predictive_text_row

        self.create_layout()

    def toggle_cursor(self):
        """Ensures the cursor remains static in the text field."""
        text = self.current_text.get().rstrip("|")  # Remove any existing cursor
        self.current_text.set(text + "|")  # Always keep the cursor at the end

    def create_layout(self):
        """Create the layout for the current mode."""
        # Clear any existing widgets.
        for widget in self.winfo_children():
            widget.destroy()

        # Create the text display bar (row 0).
        self.text_bar_button = tk.Button(
            self,
            textvariable=self.current_text,
            font=("Arial Black", 72),
            bg="light blue",
            command=self.read_text_tts,
            wraplength=1368,  # Adjust this value as needed for your layout
            justify="left",  # This will align wrapped lines to the left
        )
        self.text_bar_button.grid(row=0, column=0, columnspan=6, sticky="nsew")

        # Create buttons for each row.
        self.buttons = []
        for row_index, row_keys in enumerate(self.rows):
            button_row = []
            for col_index, key in enumerate(row_keys):
                # If this is the predictive text row (assumed to be the last row), adjust font size.
                if row_index == len(self.rows) - 1:
                    # For predictive row, use dynamic font sizing based on key length.
                    if not key:
                        # If the key is empty, use a default small size.
                        font_size = 24
                    # Adjust thresholds as desired.
                    elif len(key) <= 5:
                        font_size = 48
                    elif len(key) <= 8:
                        font_size = 36
                    elif len(key) <= 12:
                        font_size = 24
                    else:
                        font_size = 18
                else:
                    # For other rows, use your usual font sizing.
                    font_size = (
                        48
                        if self.current_mode == "Keyboard"
                        else (12 if len(key) > 10 else 24)
                    )
                btn = tk.Button(
                    self,
                    text=key,
                    font=("Arial Bold", font_size),
                    bg="light blue",
                    command=lambda k=key: self.handle_button_press(k),
                )
                btn.grid(
                    row=row_index + 1, column=col_index, sticky="nsew"
                )  # Offset by 1 for the text bar.
                button_row.append(btn)
            self.buttons.append(button_row)

        # Configure the grid so that rows and columns expand evenly.
        for i in range(len(self.rows) + 1):  # Include the text bar row.
            self.grid_rowconfigure(i, weight=1)
        for j in range(6):  # Always 6 columns.
            self.grid_columnconfigure(j, weight=1)

    def create_button(self, text, command):
        """Create a button with dynamic font size based on text length."""
        font_size = 48  # Default font size
        if (
            self.current_mode == "Words" and len(text) > 10
        ):  # Adjust font size for long text
            font_size = 12

        return tk.Button(
            self,
            text=text,
            font=("Arial Bold", font_size),
            bg="light blue",
            command=command,
        )

    def toggle_mode(self):
        """Toggle between Keyboard Mode and Words Mode, preserving the predictive row."""
        if self.current_mode == "Keyboard":
            self.current_mode = "Words"
            self.show_main_menu()  # Display the main Words Mode menu
            self.current_row_index = 0  # Reset to Controls row
            self.in_row_selection_mode = True
            self.toggle_cursor()
            self.highlight_row(0)
        else:
            self.current_mode = "Keyboard"
            # Reset to Keyboard Mode layout but preserve the predictive row
            self.row_titles = [
                "Controls",
                "A-B-C-D-E-F",
                "G-H-I-J-K-L",
                "M-N-O-P-Q-R",
                "S-T-U-V-W-X",
                "Y-Z 0 1 2 3",
                "4 5 6 7 8 9",
                "Predictive Text",
            ]
            # Define the base rows for Keyboard Mode
            base_rows = [
                [
                    "Space",
                    "Del Letter",
                    "Del Word",
                    "Clear",
                    "Layout",
                    "Main",
                ],  # Controls
                ["A", "B", "C", "D", "E", "F"],
                ["G", "H", "I", "J", "K", "L"],
                ["M", "N", "O", "P", "Q", "R"],
                ["S", "T", "U", "V", "W", "X"],
                ["Y", "Z", "0", "1", "2", "3"],
                ["4", "5", "6", "7", "8", "9"],
            ]
            # Keep predictive row updated
            self.rows = [*base_rows, self.predictive_text_row]
            self.create_layout()
            self.update_predictive_text()  # Ensure predictive row is updated
            self.current_row_index = 0  # Highlight Controls row
            self.in_row_selection_mode = True
            self.highlight_row(0)

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

    def bind_keys(self):
        """Bind keys for scanning and selecting."""
        self.bind_all("<KeyPress-space>", self.start_scanning)
        self.bind_all("<KeyRelease-space>", self.stop_scanning)
        self.bind_all("<KeyPress-Return>", self.start_selecting)
        self.bind_all("<KeyRelease-Return>", self.stop_selecting)

    def clear_all_highlights(self):
        """Clears highlights from the text bar and all button rows."""
        # Reset the text bar background.
        self.text_bar_button.config(bg="light blue")
        # Reset each button's background in every row.
        for row in self.buttons:
            for btn in row:
                btn.config(bg="light blue")

    def start_selecting(self, event):
        # Record the time when the Return key is pressed.
        if not hasattr(self, "return_press_time") or self.return_press_time is None:
            self.return_press_time = time.time()
            self.long_press_triggered = False  # Reset the long-press flag.
            print("Return key pressed.")
            # Schedule a callback to check if the key is held for 3 seconds.
            self.after(3000, self.check_long_press)

    def check_long_press(self):
        """
        Called via after() when the Return key has been held for 3 seconds.
        This method clears previous highlights, jumps to the predictive text row,
        highlights that row, and then reads it aloud using TTS.
        """
        if (
            self.return_press_time is not None
            and (time.time() - self.return_press_time) >= 3
        ):
            # Clear any previous highlights.
            self.clear_all_highlights()
            # Assume your predictive text row is the last row.
            predictive_row_index = len(
                self.rows
            )  # Row 0 is text bar; rows 1..N are buttons.
            self.current_row_index = predictive_row_index
            self.in_row_selection_mode = True
            self.highlight_row(self.current_row_index)
            self.long_press_triggered = True
            print("Long press detected: Jumped to predictive text row.")
            # Call TTS on the predictive row.
            self.read_predictive_tts()

    def read_predictive_tts(self):
        """
        Reads each suggestion in the predictive text row aloud.
        """
        for word in self.predictive_text_row:
            if word.strip():  # Skip empty placeholders
                self.tts_engine.say(word.lower())  # lowercase avoids spelling letters
        self.tts_engine.runAndWait()

    def stop_selecting(self, event):
        if hasattr(self, "return_press_time") and self.return_press_time is not None:
            press_duration = time.time() - self.return_press_time
            print(f"Return key released after {press_duration:.2f} seconds.")
            # If a long press was not triggered, handle as a short press.
            if not self.long_press_triggered and press_duration >= 0.1:
                print("Short press detected: Select action triggered.")
                self.select_button()
            # Reset the press time and long-press flag.
            self.return_press_time = None
            self.long_press_triggered = False

    def start_scanning(self, event):
        """Start tracking when the spacebar is pressed."""
        if not self.spacebar_pressed:
            self.spacebar_pressed = True
            self.spacebar_press_time = time.time()  # Record the press time
            print("Spacebar pressed.")

            # Start a thread to monitor backward scanning
            threading.Thread(target=self.monitor_backward_scanning, daemon=True).start()

    def stop_scanning(self, event):
        """Handle the logic when the spacebar is released."""
        if self.spacebar_pressed:
            self.spacebar_pressed = False
            press_duration = time.time() - self.spacebar_press_time
            print(f"Spacebar released after {press_duration:.2f} seconds.")

            # Forward scanning if held between 0.25 and 3 seconds
            if 0.25 <= press_duration <= 3:
                print("Scanning forward by one selection.")
                self.scan_forward()

            # Reset tracking variables
            self.spacebar_press_time = None

    def monitor_backward_scanning(self):
        """Continuously scan backward if the spacebar is held for more than 3 seconds."""
        while self.spacebar_pressed:
            press_duration = time.time() - self.spacebar_press_time

            if press_duration > 3:
                print("Spacebar held for more than 3 seconds. Scanning backward.")
                self.scan_backward()
                time.sleep(1)  # Scan backward every 1 seconds while held

            # Small delay to prevent excessive CPU usage
            time.sleep(0.1)

    def monitor_forward_scanning(self):
        """Monitor the duration of the spacebar press and handle forward scanning."""
        time.sleep(1)  # Wait for 1 second before starting scanning
        if self.spacebar_pressed:
            print("Spacebar held for 1 second. Starting forward scanning.")
            while self.spacebar_pressed:
                self.scan_forward()  # Trigger forward scan
                time.sleep(2)  # Wait for 2 seconds between scans

    def scan_forward(self):
        """Scan forward through rows or buttons."""
        if not self.winfo_exists():
            return

        if self.in_row_selection_mode:
            # Move to the next row, looping back if necessary
            prev_row_index = self.current_row_index
            self.current_row_index = (self.current_row_index + 1) % (
                len(self.rows) + 1
            )  # Include the text bar
            print(f"Scanning forward to row {self.current_row_index}")

            self.highlight_row(self.current_row_index, prev_row_index)
            if self.current_row_index == 0:
                print("Text bar highlighted.")
            else:
                self.speak_row_title(self.current_row_index)
        else:
            # Scan buttons within the current row
            prev_button_index = self.current_button_index
            self.current_button_index = (self.current_button_index + 1) % len(
                self.rows[self.current_row_index - 1]
            )

            if self.current_button_index == 0:  # Button looped back
                self.in_row_selection_mode = True
                self.highlight_row(self.current_row_index)
                self.speak_row_title(self.current_row_index)
            else:
                self.highlight_button(self.current_button_index, prev_button_index)
                self.speak_button_label(self.current_button_index)

    def scan_backward(self):
        """Scan backward through rows or buttons."""
        if not self.winfo_exists():
            return

        if self.in_row_selection_mode:
            # Move to the previous row, looping back if necessary
            prev_row_index = self.current_row_index
            self.current_row_index = (self.current_row_index - 1) % (
                len(self.rows) + 1
            )  # Include the text bar
            print(f"Scanning backward to row {self.current_row_index}")

            self.highlight_row(self.current_row_index, prev_row_index)
            if self.current_row_index == 0:
                print("Text bar highlighted.")
            else:
                self.speak_row_title(self.current_row_index)
        else:
            # Scan buttons within the current row
            prev_button_index = self.current_button_index
            self.current_button_index = (self.current_button_index - 1) % len(
                self.rows[self.current_row_index - 1]
            )

            if (
                self.current_button_index
                == len(self.rows[self.current_row_index - 1]) - 1
            ):  # Button looped back
                self.in_row_selection_mode = True
                self.highlight_row(self.current_row_index)
                self.speak_row_title(self.current_row_index)
            else:
                self.highlight_button(self.current_button_index, prev_button_index)
                self.speak_button_label(self.current_button_index)

    def select_button(self, event=None):
        """Handle selection triggered by the Return key."""
        if self.in_row_selection_mode:
            if self.current_row_index == 0:  # Text bar selected
                self.read_text_tts()  # Play the text
            else:
                # Transition to Button Selection Mode
                self.in_row_selection_mode = False
                self.current_button_index = 0  # Start with the first button in the row

                # Un-highlight the row and highlight the first button
                if self.current_row_index > 0:
                    for button in self.buttons[self.current_row_index - 1]:
                        button.config(bg="light blue")
                    self.highlight_button(self.current_button_index)

                # Speak the first button label
                self.speak_button_label(self.current_button_index)
        else:
            # Perform the action for the selected button
            key = self.rows[self.current_row_index - 1][self.current_button_index]
            self.handle_button_press(key)

            if self.current_mode == "Keyboard":
                # In Alphabet mode, reset to the same row
                self.in_row_selection_mode = True
                self.highlight_row(self.current_row_index)
            elif self.current_mode == "Words":
                if key in self.get_submenus():
                    # If a submenu is selected, reset to the Controls row
                    self.in_row_selection_mode = True
                    self.current_row_index = 0  # Controls row
                    self.highlight_row(0)
                else:
                    # In submenus, reset to the current row
                    self.in_row_selection_mode = True
                    self.highlight_row(self.current_row_index)

    def highlight_row(self, row_index, prev_row_index=None):
        """Highlight the buttons in the current row."""
        if prev_row_index is not None:
            if prev_row_index == 0:  # Un-highlight the text bar
                self.text_bar_button.config(bg="light blue")
            else:
                # Un-highlight the previous row
                for button in self.buttons[prev_row_index - 1]:
                    button.config(bg="light blue")

        if row_index == 0:  # Highlight the text bar
            self.text_bar_button.config(bg="yellow")
        else:
            # Highlight the current row
            for button in self.buttons[row_index - 1]:
                button.config(bg="yellow")
        self.update_idletasks()

    def highlight_button(self, button_index, prev_button_index=None):
        """Highlight the current button and reset the previous button."""
        if prev_button_index is not None:
            self.buttons[self.current_row_index - 1][prev_button_index].config(
                bg="light blue", fg="black"
            )

        self.buttons[self.current_row_index - 1][button_index].config(
            bg="yellow", fg="black"
        )
        self.update_idletasks()

    def speak_row_title(self, row_index):
        """Speak the title of the current row."""
        if row_index == 0:  # Text box row
            title = "Text Box"
        elif row_index == 1:  # Controls row
            title = "Controls"
        else:
            # Adjust the actual row index based on the current mode
            if self.current_mode == "Keyboard":
                # Offset for alphabet keyboard mode (text box + controls rows)
                actual_row_index = row_index - 1
            elif self.current_mode == "Words":
                # Offset for word keyboard mode (text box + controls rows)
                actual_row_index = row_index - 2

            # Check if the actual row index is within bounds
            if 0 <= actual_row_index < len(self.row_titles):
                title = self.row_titles[actual_row_index]
            else:
                title = ""  # No title for rows beyond defined row_titles

        if title:
            print(f"TTS: {title}")  # Debugging line
            self.tts_engine.say(title)
            self.tts_engine.runAndWait()

    def speak_button_label(self, button_index):
        """Speak the label of the current button."""
        label = self.rows[self.current_row_index - 1][button_index]
        # Convert label to lowercase to avoid TTS spelling out short words
        self.tts_engine.say(label.lower())
        self.tts_engine.runAndWait()

    def handle_button_press(self, char):
        # Get the current text without the cursor.
        text = self.current_text.get().rstrip("|")
        if char in self.predictive_text_row:
            if text.endswith(" "):
                new_text = text + char
            else:

                parts = text.rsplit(" ", 1)
                if len(parts) == 1:
                    new_text = char
                else:
                    new_text = parts[0] + " " + char
            self.current_text.set(new_text + " |")
            self.update_predictive_text()
            return  # Exit early since we have handled the predictive suggestion.

        # If we're in Words mode, use volume keys instead of adding text.
        if self.current_mode == "Words":
            if char == "Vol+":
                print("Increasing volume by 6 steps (Words mode).")
                self.change_volume(up=True, steps=6)
                return  # Do not update the text box
            elif char == "Vol-":
                print("Decreasing volume by 6 steps (Words mode).")
                self.change_volume(up=False, steps=6)
                return  # Do not update the text box

        # --- Special Buttons ---
        if char == "Layout":
            self.toggle_mode()
        elif char == "Main":
            self.open_and_exit(
                "comm-v9.py"
            )  # Close current script and open the main script.
        elif char == "Back":
            self.show_main_menu()  # Return to the main Words Mode menu.
        elif char in ["Space", "Del Word", "Clear"]:
            if char == "Space":
                self.current_text.set(text + " |")
            elif char == "Clear":
                self.current_text.set("|")  # Reset text with just the cursor.
            elif char == "Del Word":
                words = text.split()
                self.current_text.set(" ".join(words[:-1]) + " |")

        # --- Keyboard Mode (Normal Letter Buttons) ---
        elif self.current_mode == "Keyboard":
            if char == "Del Letter":
                self.current_text.set(text[:-1] + "|")
            else:
                self.current_text.set(text + char + "|")
                self.update_predictive_text()

        # --- Words Mode (For submenus, etc.) ---
        elif self.current_mode == "Words":
            submenus = self.get_submenus()
            if char in submenus:
                self.show_submenu(char)
            elif char in [word for row in self.rows for word in row]:
                self.current_text.set(text + char + "|")

        # Always update predictive suggestions after handling the button press.
        self.update_predictive_text()

    def change_volume(self, up=True, steps=1):
        """Adjusts system volume using Windows virtual key codes.
        By default it sends one key event; pass steps=6 to move the volume by 6 steps.
        """
        VK_VOLUME_UP = 0xAF
        VK_VOLUME_DOWN = 0xAE
        key = VK_VOLUME_UP if up else VK_VOLUME_DOWN
        for _ in range(steps):
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)  # Key down
            ctypes.windll.user32.keybd_event(key, 0, 2, 0)  # Key up
            time.sleep(0.01)

    def show_submenu(self, submenu_title):
        """Display the submenu for the selected title."""
        submenus = self.get_submenus()
        if submenu_title in submenus:
            submenu = submenus[submenu_title]

            # Update row titles for TTS feedback
            self.row_titles = submenu["row_titles"]

            # Collect words for the 6x6 grid
            words = [
                word for row in submenu["rows"] for word in row
            ]  # Flatten the rows

            # Ensure 36 buttons
            words = words[:36] + [""] * (36 - len(words))

            # Create a 6x6 grid, first row for controls
            self.rows = [
                ["Back", "Del Word", "Clear", "Vol+", "Vol-", "Main"],  # Controls row
                words[:6],  # Row 1
                words[6:12],  # Row 2
                words[12:18],  # Row 3
                words[18:24],  # Row 4
                words[24:30],  # Row 5
                words[30:36],  # Row 6
                ["", "", "", "", "", ""],
            ]
            self.create_layout()

    def open_and_exit(self, script_name):
        """Open a new Python script in the parent directory and close the current application."""
        try:
            # Get the directory that contains the current file, then its parent directory.
            parent_dir = os.path.dirname(os.path.dirname(__file__))
            script_path = os.path.join(parent_dir, script_name)
            subprocess.Popen([sys.executable, script_path])
            self.parent.destroy()
        except Exception as e:
            print(f"Failed to open script {script_name}: {e}")

    def read_text_tts(self):
        """Reads the current text with TTS and tracks word usage after 3 triggers."""
        text = self.current_text.get().strip()
        if text:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
            self.tts_trigger_count += 1  # Increment counter

            if self.tts_trigger_count >= 3:
                update_word_usage(text)  # Update Ben's word frequency
                self.tts_trigger_count = 0  # Reset counter

    def show_main_menu(self):
        """Display the main Words Mode menu with a 6x6 grid of submenu titles."""
        self.get_submenus()

        # Categorized row titles for TTS feedback
        self.row_titles = [
            "General References",  # Row 1
            "Daily Life",  # Row 2
            "Education and Nature",  # Row 3
            "Emotions and Actions",  # Row 4
            "Practical and Everyday Living",  # Row 5
            "Shows and TV",  # Row 6
            "Predictive Text",  # Row 7 Predictive Text
        ]

        # Collect submenu titles for the 6x6 grid
        submenu_titles = [
            # General References (6 titles)
            "Common Phrases/Needs",
            "Pronouns",
            "Adjectives",
            "Time/Days Reference",
            "Location Reference",
            "Family & Proper Names",
            # Daily Life (6 titles)
            "Forming Questions",
            "Health & Body",
            "Clothing & Accessories",
            "Weather & Seasons",
            "Adjectives",
            "Entertainment",
            # Education and Nature (6 titles)
            "Numbers & Math",
            "Transportation",
            "Work & Tools",
            "School & Learning",
            "Animals",
            "Nature",
            # Emotions and Actions (6 titles)
            "Emotions & Feelings",
            "Travel & Vacations",
            "Holidays & Celebrations",
            "Shopping & Money",
            "Technology & Media",
            "Verbs & Actions",
            "Predictive Text"
            # Practical and Everyday Living (6 titles)
            "Household",
            "Sports & Activities",
            "Hobbies & Interests",
            "Jobs & Professions",
            "Colors",
            "People & Titles",
            # Shows and TV (6 titles)
            "Simpsons/Futurama",
            "Family Guy/American Dad",
            "South Park",
            "Dragon Ball Universe",
            "Drake & Josh/iCarly/Victorious",
            "Rugrats/Spongebob",
        ]

        # Ensure 36 buttons
        submenu_titles = submenu_titles[:36] + [""] * (36 - len(submenu_titles))

        # Create a 6x6 grid
        self.rows = [
            ["Layout", "Del Word", "Clear", "Vol+", "Vol-", "Main"],  # Controls
            submenu_titles[:6],  # Row 1
            submenu_titles[6:12],  # Row 2
            submenu_titles[12:18],  # Row 3
            submenu_titles[18:24],  # Row 4
            submenu_titles[24:30],  # Row 5
            submenu_titles[30:36],  # Row 6
            ["", "", "", "", "", ""],
        ]
        # Reset scanning to start at the Controls row
        self.current_row = 1  # Set highlight to start on Controls row
        self.create_layout()

    def get_submenus(self):
        return {
            "row_titles": [
                "General References",
                "Daily Life",
                "Education and Nature",
                "Emotions and Actions",
                "Practical and Technology",
                "Shows and TV",
                "Predictive Text",
            ],
            "Common Phrases/Needs": {  # Add the rest of your hierarchical data here
                "row_titles": [
                    "Frequent Needs",
                    "Basic Actions",
                    "Communication",
                    "Work",
                    "Play",
                    "Feelings",
                    "Predictive Text",
                ],
                "rows": [
                    ["SUCTION", "PAIN", "SICK", "BED", "CHAIR", "TIRED"],
                    ["DO", "MAKE", "GET", "TAKE", "GIVE", "PUT"],
                    ["TALK", "ASK", "TELL", "LISTEN", "SPEAK", "SAY"],
                    ["BUILD", "FIX", "CLEAN", "WRITE", "PLAN", "WORK"],
                    ["PLAY", "LAUGH", "DANCE", "SING", "DRAW", "COOK"],
                    ["LOVE", "HATE", "NEED", "FEEL", "WANT", "SMILE"],
                ],
            },
            "Pronouns": {
                "row_titles": [
                    "Subject",
                    "Subject 2",
                    "Possessive",
                    "Reflexive",
                    "Demonstrative",
                    "Interrogative",
                    "Predictive Text",
                ],
                "rows": [
                    ["I", "YOU", "HE", "SHE", "IT", "WE"],
                    ["ME", "YOU", "HIM", "HER", "IT", "US"],
                    ["MY", "YOUR", "HIS", "HER", "ITS", "OUR"],
                    ["MYSELF", "YOURSELF", "HIMSELF", "HERSELF", "ITSELF", "OURSELVES"],
                    ["THIS", "THAT", "THESE", "THOSE", "HERE", "THERE"],
                    ["WHO", "WHAT", "WHICH", "WHOSE", "WHOM", "WHY"],
                ],
            },
            "Adjectives": {
                "row_titles": [
                    "Size",
                    "Help & Actions",
                    "Comfort & Temperature",
                    "Distance & Position",
                    "Speed & Difficulty",
                    "Appearance & Condition",
                    "Predictive Text",
                ],
                "rows": [
                    ["BIG", "SMALL", "TALL", "SHORT", "LONG", "TINY"],
                    ["QUICK", "EASY", "DIFFICULT", "HEAVY", "LIGHT", "STRONG"],
                    ["SOFT", "HARD", "FLUFFY", "WARM", "COLD", "COMFORTABLE"],
                    ["FAR", "CLOSE", "HIGH", "LOW", "DEEP", "SHALLOW"],
                    ["FAST", "SLOW", "NEW", "OLD", "YOUNG", "WEAK"],
                    ["BEAUTIFUL", "UGLY", "CLEAN", "DIRTY", "QUIET", "LOUD"],
                ],
            },
            "Time/Days Reference": {
                "row_titles": [
                    "Times of Day",
                    "Days of Week",
                    "Months",
                    "Seasons",
                    "Time Units",
                    "Relative Time",
                    "Predictive Text",
                ],
                "rows": [
                    ["MORNING", "AFTERNOON", "EVENING", "NIGHT", "MIDNIGHT", "NOON"],
                    ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "WEEKEND"],
                    ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE"],
                    ["SUMMER", "WINTER", "SPRING", "AUTUMN", "RAINY", "DRY"],
                    ["HOUR", "MINUTE", "SECOND", "DAY", "WEEK", "MONTH"],
                    ["NOW", "SOON", "LATER", "TOMORROW", "YESTERDAY", "TODAY"],
                ],
            },
            "Location Reference": {
                "row_titles": [
                    "Home",
                    "School",
                    "Outdoors",
                    "Public",
                    "Travel",
                    "Other",
                    "Predictive Text",
                ],
                "rows": [
                    ["KITCHEN", "BATHROOM", "BEDROOM", "LIVING ROOM", "GARAGE", "YARD"],
                    ["CLASSROOM", "OFFICE", "LIBRARY", "GYM", "HOUSE", "CAFETERIA"],
                    ["PARK", "BEACH", "MOUNTAIN", "FOREST", "TRAIL", "FIELD"],
                    ["STORE", "MARKET", "HOSPITAL", "POLICE", "MALL", "AIRPORT"],
                    ["CAR", "BUS", "TRAIN", "PLANE", "BOAT", "BIKE"],
                    ["CITY", "VILLAGE", "ISLAND", "HOTEL", "CAMP", "FARM"],
                ],
            },
            "People & Titles": {
                "row_titles": [
                    "Family",
                    "Friends",
                    "Helpers",
                    "Titles",
                    "Generic Names",
                    "Other",
                    "Predictive Text",
                ],
                "rows": [
                    ["MOM", "DAD", "SISTER", "BROTHER", "GRANDMA", "GRANDPA"],
                    ["FRIEND", "BUDDY", "NEIGHBOR", "CLASSMATE", "BESTIE", "PAL"],
                    ["DOCTOR", "NURSE", "TEACHER", "COACH", "THERAPIST", "HELPER"],
                    ["MR.", "MRS.", "MISS", "DR.", "SIR", "MA’AM"],
                    ["GUY", "GIRL", "BOY", "KID", "PERSON", "SOMEONE"],
                    ["BOSS", "COWORKER", "CLIENT", "OFFICER", "DRIVER", "VISITOR"],
                ],
            },
            "Forming Questions": {
                "row_titles": [
                    "Basic",
                    "Clarification",
                    "Personal",
                    "Descriptive",
                    "Decision-Making",
                    "Other",
                    "Predictive Text",
                ],
                "rows": [
                    ["WHO", "WHAT", "WHERE", "WHEN", "WHY", "HOW"],
                    ["WHICH", "WHOSE", "HOW MANY", "HOW MUCH", "HOW LONG", "WHY NOT"],
                    [
                        "ARE YOU",
                        "CAN YOU",
                        "DO YOU",
                        "WILL YOU",
                        "WOULD YOU",
                        "COULD YOU",
                    ],
                    ["DESCRIBE", "EXPLAIN", "DEFINE", "SHOW ME", "TELL ME", "REPEAT"],
                    ["THIS?", "THAT?", "HERE?", "THERE?", "RIGHT?", "WRONG?"],
                    [
                        "IS IT?",
                        "WAS IT?",
                        "SHOULD IT?",
                        "COULD IT?",
                        "WOULD IT?",
                        "WILL IT?",
                    ],
                ],
            },
            "Health & Body": {
                "row_titles": [
                    "Body Parts",
                    "Senses",
                    "Physical States",
                    "Illnesses",
                    "Treatments",
                    "Medical Tools",
                    "Predictive Text",
                ],
                "rows": [
                    ["HEAD", "FACE", "NECK", "ARM", "LEG", "HAND"],
                    ["EYES", "EARS", "NOSE", "MOUTH", "SKIN", "HAIR"],
                    ["TIRED", "HUNGRY", "THIRSTY", "COLD", "HOT", "SICK"],
                    ["FEVER", "COUGH", "PAIN", "INJURY", "ALLERGY", "FLU"],
                    ["MEDICINE", "THERAPY", "BANDAGE", "REST", "ICE PACK", "INJECTION"],
                    [
                        "STETHOSCOPE",
                        "THERMOMETER",
                        "SYRINGE",
                        "WHEELCHAIR",
                        "CRUTCH",
                        "IV",
                    ],
                ],
            },
            "Clothing & Accessories": {
                "row_titles": [
                    "Tops",
                    "Bottoms",
                    "Outerwear",
                    "Footwear",
                    "Accessories",
                    "Seasonal",
                    "Predictive Text",
                ],
                "rows": [
                    ["SHIRT", "T-SHIRT", "BLOUSE", "TANK TOP", "SWEATER", "HOODIE"],
                    ["PANTS", "JEANS", "SHORTS", "SKIRT", "LEGGINGS", "TROUSERS"],
                    ["COAT", "JACKET", "BLAZER", "RAINCOAT", "PONCHO", "VEST"],
                    ["SHOES", "BOOTS", "SANDALS", "SNEAKERS", "HEELS", "SLIPPERS"],
                    ["HAT", "GLOVES", "SCARF", "BELT", "WATCH", "SUNGLASSES"],
                    [
                        "SWIMSUIT",
                        "SNOW BOOTS",
                        "WINTER COAT",
                        "THERMALS",
                        "FLIP FLOPS",
                        "RAIN BOOTS",
                    ],
                ],
            },
            "Weather & Seasons": {
                "row_titles": [
                    "General Weather",
                    "Seasons",
                    "Precipitation",
                    "Sky Conditions",
                    "Wind",
                    "Temperature",
                    "Predictive Text",
                ],
                "rows": [
                    ["SUNNY", "CLOUDY", "RAINY", "SNOWY", "FOGGY", "STORMY"],
                    ["SPRING", "SUMMER", "AUTUMN", "WINTER", "SEASON", "HOLIDAY"],
                    ["RAIN", "SNOW", "HAIL", "DRIZZLE", "SLEET", "DOWNPOUR"],
                    ["CLEAR", "OVERCAST", "CLOUDY", "BRIGHT", "DARK", "RAINBOW"],
                    ["WINDY", "BREEZY", "GUSTY", "CALM", "HURRICANE", "TORNADO"],
                    ["HOT", "COLD", "WARM", "COOL", "FREEZING", "BOILING"],
                ],
            },
            "Food & Drink": {
                "row_titles": [
                    "Fruits",
                    "Vegetables",
                    "Proteins",
                    "Carbs",
                    "Snacks",
                    "Drinks",
                    "Predictive Text",
                ],
                "rows": [
                    ["APPLE", "BANANA", "ORANGE", "PEACH", "GRAPE", "MANGO"],
                    ["CARROT", "BROCCOLI", "POTATO", "LETTUCE", "ONION", "PEPPER"],
                    ["CHICKEN", "BEEF", "FISH", "EGG", "TOFU", "PORK"],
                    ["BREAD", "RICE", "PASTA", "CEREAL", "BAGEL", "TORTILLA"],
                    ["CHIPS", "COOKIE", "CANDY", "CAKE", "POPCORN", "PRETZEL"],
                    ["WATER", "JUICE", "MILK", "TEA", "COFFEE", "SODA"],
                ],
            },
            "Colors": {
                "row_titles": [
                    "Primary Colors",
                    "Secondary Colors",
                    "Neutrals",
                    "Pastels",
                    "Brights",
                    "Dark Shades",
                    "Predictive Text",
                ],
                "rows": [
                    ["RED", "BLUE", "YELLOW", "GREEN", "PURPLE", "ORANGE"],
                    ["PINK", "BROWN", "GRAY", "BLACK", "WHITE", "BEIGE"],
                    ["GOLD", "SILVER", "BRONZE", "CHARCOAL", "IVORY", "CREAM"],
                    ["LAVENDER", "PEACH", "MINT", "CORAL", "TEAL", "MAROON"],
                    ["SCARLET", "CRIMSON", "TURQUOISE", "AMBER", "MAGENTA", "CYAN"],
                    ["NAVY", "INDIGO", "OLIVE", "TAN", "VIOLET", "LILAC"],
                ],
            },
            "Numbers & Math": {
                "row_titles": [
                    "Single Digits",
                    "Teens",
                    "Tens",
                    "Large Numbers",
                    "Fractions",
                    "Math Symbols",
                    "Predictive Text",
                ],
                "rows": [
                    ["ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX"],
                    ["SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE"],
                    [
                        "THIRTEEN",
                        "FOURTEEN",
                        "FIFTEEN",
                        "SIXTEEN",
                        "SEVENTEEN",
                        "EIGHTEEN",
                    ],
                    ["HUNDRED", "THOUSAND", "MILLION", "BILLION", "TRILLION", "ZERO"],
                    ["HALF", "QUARTER", "THIRD", "EIGHTH", "TENTH", "WHOLE"],
                    ["PLUS", "MINUS", "TIMES", "DIVIDE", "EQUALS", "PERCENT"],
                ],
            },
            "Transportation": {
                "row_titles": [
                    "Land",
                    "Water",
                    "Air",
                    "Public",
                    "Emergency",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    ["CAR", "TRUCK", "BIKE", "MOTORCYCLE", "BUS", "TRAIN"],
                    ["BOAT", "SHIP", "CANOE", "FERRY", "SUBMARINE", "KAYAK"],
                    ["PLANE", "HELICOPTER", "JET", "GLIDER", "DRONE", "BALLOON"],
                    ["TAXI", "SUBWAY", "TRAM", "METRO", "RIDE SHARE", "TROLLEY"],
                    [
                        "AMBULANCE",
                        "FIRE TRUCK",
                        "POLICE CAR",
                        "RESCUE BOAT",
                        "PATROL",
                        "HELICOPTER",
                    ],
                    ["SCOOTER", "SKATEBOARD", "HOVERBOARD", "SEGWAY", "RV", "ATV"],
                ],
            },
            "Work & Tools": {
                "row_titles": [
                    "Household",
                    "Construction",
                    "Garden",
                    "Office",
                    "Mechanical",
                    "Power Tools",
                    "Predictive Text",
                ],
                "rows": [
                    ["BROOM", "MOP", "VACUUM", "BUCKET", "SOAP", "DUSTER"],
                    ["HAMMER", "SCREWDRIVER", "WRENCH", "SAW", "DRILL", "TAPE"],
                    ["SHOVEL", "RAKE", "HOE", "PRUNERS", "TROWEL", "HOSE"],
                    ["PEN", "PENCIL", "PAPER", "ERASER", "STAPLER", "TAPE"],
                    ["WRENCH", "RATCHET", "CLAMP", "SOCKET", "JACK", "HEX KEY"],
                    [
                        "CORDLESS DRILL",
                        "CHAINSAW",
                        "SANDER",
                        "GRINDER",
                        "ROUTER",
                        "IMPACT DRIVER",
                    ],
                ],
            },
            "School & Learning": {
                "row_titles": [
                    "Subjects",
                    "Supplies",
                    "People",
                    "Places",
                    "Activities",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    ["MATH", "SCIENCE", "HISTORY", "ENGLISH", "ART", "MUSIC"],
                    ["PENCIL", "ERASER", "NOTEBOOK", "MARKER", "RULER", "GLUE"],
                    [
                        "TEACHER",
                        "STUDENT",
                        "PRINCIPAL",
                        "COUNSELOR",
                        "COACH",
                        "LIBRARIAN",
                    ],
                    [
                        "CLASSROOM",
                        "LIBRARY",
                        "OFFICE",
                        "GYM",
                        "CAFETERIA",
                        "PLAYGROUND",
                    ],
                    [
                        "TEST",
                        "QUIZ",
                        "HOMEWORK",
                        "PROJECT",
                        "PRESENTATION",
                        "ASSIGNMENT",
                    ],
                    ["CHALK", "BOARD", "TEXTBOOK", "COMPUTER", "TABLET", "PRINTER"],
                ],
            },
            "Entertainment": {
                "row_titles": [
                    "Movies",
                    "TV Shows",
                    "Games",
                    "Books",
                    "Music",
                    "Events",
                    "Predictive Text",
                ],
                "rows": [
                    ["COMEDY", "DRAMA", "HORROR", "ACTION", "ROMANCE", "SCI-FI"],
                    ["CARTOON", "SERIES", "SITCOM", "REALITY", "NEWS", "DOCUMENTARY"],
                    ["VIDEO GAME", "BOARD GAME", "CARDS", "CHESS", "TRIVIA", "PUZZLE"],
                    ["NOVEL", "MYSTERY", "BIOGRAPHY", "FANTASY", "POETRY", "COMICS"],
                    ["SONG", "ALBUM", "ARTIST", "BAND", "PLAYLIST", "CONCERT"],
                    ["THEATER", "FESTIVAL", "CIRCUS", "PARADE", "SHOW", "PARTY"],
                ],
            },
            "Animals": {
                "row_titles": [
                    "Pets",
                    "Farm Animals",
                    "Wild Animals",
                    "Birds",
                    "Reptiles",
                    "Aquatic",
                    "Predictive Text",
                ],
                "rows": [
                    ["DOG", "CAT", "BIRD", "FISH", "HAMSTER", "RABBIT"],
                    ["COW", "HORSE", "PIG", "CHICKEN", "SHEEP", "GOAT"],
                    ["LION", "TIGER", "ELEPHANT", "BEAR", "WOLF", "DEER"],
                    ["PARROT", "EAGLE", "OWL", "CROW", "SEAGULL", "SPARROW"],
                    ["SNAKE", "LIZARD", "TURTLE", "CROCODILE", "IGUANA", "GECKO"],
                    ["SHARK", "DOLPHIN", "WHALE", "OCTOPUS", "SEAL", "CRAB"],
                ],
            },
            "Nature": {
                "row_titles": [
                    "Landforms",
                    "Water",
                    "Sky",
                    "Plants",
                    "Weather",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    ["MOUNTAIN", "VALLEY", "HILL", "CANYON", "DESERT", "PLATEAU"],
                    ["RIVER", "LAKE", "OCEAN", "STREAM", "POND", "WATERFALL"],
                    ["SUN", "MOON", "STARS", "CLOUDS", "RAINBOW", "SKY"],
                    ["TREE", "FLOWER", "GRASS", "CACTUS", "BUSH", "SHRUB"],
                    ["RAIN", "SNOW", "FOG", "HAIL", "WIND", "STORM"],
                    ["SAND", "ROCK", "DIRT", "SOIL", "ICE", "LAVA"],
                ],
            },
            "Family & Proper Names": {
                "row_titles": [
                    "Immediate Family",
                    "Friends",
                    "Extended Family",
                    "Pet Names",
                    "Common Names",
                    "Other",
                    "Predictive Text",
                ],
                "rows": [
                    ["MOM", "DAD", "BROTHER", "SISTER", "GRANDMA", "GRANDPA"],
                    ["FRIEND", "BUDDY", "PAL", "NEIGHBOR", "BESTIE", "CLASSMATE"],
                    ["UNCLE", "AUNT", "COUSIN", "NIECE", "NEPHEW", "GUARDIAN"],
                    ["RUSH", "TRIXIE", "JAZZ", "DAISY", "PEPPER", "LIVINGSTON"],
                    ["ALLEN", "LAUREN", "BRYAN", "ARI", "JAKE", "NANCY"],
                    ["JARED", "ALEXA", "MATTHEW", "MARISSA", "BLAKE", "LEO"],
                ],
            },
            "Emotions & Feelings": {
                "row_titles": [
                    "Positive",
                    "Negative",
                    "Neutral",
                    "Intense",
                    "Mild",
                    "Physical States",
                    "Predictive Text",
                ],
                "rows": [
                    ["JOYFUL", "EXCITED", "GRATEFUL", "PROUD", "HOPEFUL", "OPTIMISTIC"],
                    ["ANGRY", "FRUSTRATED", "LONELY", "WORRIED", "ASHAMED", "SAD"],
                    ["OKAY", "FINE", "CALM", "CONTENT", "NEUTRAL", "MEH"],
                    [
                        "SHOCKED",
                        "OVERWHELMED",
                        "ANXIOUS",
                        "TERRIFIED",
                        "EAGER",
                        "ELATED",
                    ],
                    ["ANNOYED", "BORED", "CONFUSED", "SHY", "JEALOUS", "SCARED"],
                    ["TIRED", "HUNGRY", "THIRSTY", "HOT", "COLD", "SICK"],
                ],
            },
            "Travel & Vacations": {
                "row_titles": [
                    "Transportation",
                    "Lodging",
                    "Activities",
                    "Essentials",
                    "Documents",
                    "Destinations",
                    "Predictive Text",
                ],
                "rows": [
                    ["CAR", "BUS", "TRAIN", "PLANE", "BIKE", "BOAT"],
                    ["HOTEL", "HOSTEL", "MOTEL", "RESORT", "CABIN", "AIRBNB"],
                    [
                        "HIKING",
                        "CAMPING",
                        "FISHING",
                        "SKIING",
                        "SIGHTSEEING",
                        "SWIMMING",
                    ],
                    ["BACKPACK", "SNACKS", "WATER", "CAMERA", "MAP", "SUITCASE"],
                    ["PASSPORT", "VISA", "ID", "TICKET", "GUIDEBOOK", "RESERVATION"],
                    ["BEACH", "MOUNTAIN", "CITY", "FOREST", "ISLAND", "VILLAGE"],
                ],
            },
            "Holidays & Celebrations": {
                "row_titles": [
                    "Winter Holidays",
                    "Spring Holidays",
                    "Summer Holidays",
                    "Fall Holidays",
                    "Festivals",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    ["CHRISTMAS", "NEW YEAR", "HANUKKAH", "KWANZAA", "DIWALI", "EID"],
                    ["EASTER", "PASSOVER", "PURIM", "RAMADAN", "EARTH DAY", "LENT"],
                    [
                        "INDEPENDENCE DAY",
                        "FATHER'S DAY",
                        "MOTHER'S DAY",
                        "LABOR DAY",
                        "BASTILLE",
                        "MEMORIAL DAY",
                    ],
                    [
                        "HALLOWEEN",
                        "THANKSGIVING",
                        "HARVEST",
                        "VETERANS",
                        "OKTOBERFEST",
                        "COLUMBUS",
                    ],
                    [
                        "BIRTHDAY",
                        "ANNIVERSARY",
                        "GRADUATION",
                        "PARADE",
                        "CONCERT",
                        "PARTY",
                    ],
                    ["FAIR", "CIRCUS", "SHOW", "FIREWORKS", "FESTIVAL", "WEDDING"],
                ],
            },
            "Shopping & Money": {
                "row_titles": [
                    "General Shopping",
                    "Groceries",
                    "Clothing",
                    "Electronics",
                    "Furniture",
                    "Other",
                    "Predictive Text",
                ],
                "rows": [
                    ["MALL", "STORE", "SHOP", "CART", "BAG", "CHECKOUT"],
                    ["BREAD", "EGGS", "MILK", "CHEESE", "FRUIT", "VEGETABLES"],
                    ["SHOES", "SHIRT", "PANTS", "JACKET", "HAT", "SCARF"],
                    ["PHONE", "TABLET", "TV", "CAMERA", "LAPTOP", "SPEAKER"],
                    ["DESK", "CHAIR", "TABLE", "BED", "CABINET", "COUCH"],
                    ["CASH", "CARD", "COUPON", "RECEIPT", "SALE", "BARCODE"],
                ],
            },
            "Technology & Media": {
                "row_titles": [
                    "Devices",
                    "Components",
                    "Networks",
                    "Software",
                    "Accessories",
                    "Other",
                    "Predictive Text",
                ],
                "rows": [
                    ["PHONE", "TABLET", "MONITOR", "CAMERA", "LAPTOP", "DESKTOP"],
                    ["CPU", "GPU", "RAM", "SSD", "BATTERY", "CHARGER"],
                    ["WIFI", "ROUTER", "SERVER", "CLOUD", "ETHERNET", "BLUETOOTH"],
                    ["APP", "BROWSER", "GAME", "TOOL", "WEBSITE", "EDITOR"],
                    ["KEYBOARD", "MOUSE", "SPEAKER", "DOCK", "MICROPHONE", "CABLE"],
                    ["MUSIC", "VIDEO", "PHOTO", "PODCAST", "STREAM", "PLAYLIST"],
                ],
            },
            "Verbs & Actions": {
                "row_titles": [
                    "General Actions",
                    "Movement",
                    "Speech",
                    "Work",
                    "Play",
                    "Emotion",
                    "Predictive Text",
                ],
                "rows": [
                    ["BEGIN", "CREATE", "DISCOVER", "SOLVE", "TRY", "ACHIEVE"],
                    ["LEAP", "CRAWL", "SLIDE", "SPIN", "KICK", "GLIDE"],
                    ["DEBATE", "NARRATE", "DECLARE", "REPEAT", "MUTTER", "EXCLAIM"],
                    ["ANALYZE", "ASSEMBLE", "CALCULATE", "DESIGN", "PROGRAM", "DRAFT"],
                    ["SKETCH", "BUILD", "EXPLORE", "INVENT", "ROLEPLAY", "COMPETE"],
                    ["ADMIRE", "FORGIVE", "COMFORT", "ENCOURAGE", "PONDER", "WONDER"],
                ],
            },
            "Household": {
                "row_titles": [
                    "Rooms",
                    "Appliances",
                    "Furniture",
                    "Cleaning Supplies",
                    "Decorations",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    ["PANTRY", "ATTIC", "BASEMENT", "CLOSET", "HALLWAY", "BALCONY"],
                    ["STOVE", "BLENDER", "FREEZER", "KETTLE", "TOASTER", "AIR FRYER"],
                    ["ARMCHAIR", "STOOL", "BOOKSHELF", "HAMMOCK", "CRIB", "BENCH"],
                    [
                        "DUSTPAN",
                        "CLEANING CLOTH",
                        "BRUSH",
                        "SQUEEGEE",
                        "CLEANER",
                        "DISINFECTANT",
                    ],
                    [
                        "CANDLE",
                        "PHOTO FRAME",
                        "PLANT POT",
                        "WALL ART",
                        "CLOCK",
                        "SHELF",
                    ],
                    [
                        "LADDER",
                        "TOOLBOX",
                        "REMOTE",
                        "THERMOSTAT",
                        "POWER STRIP",
                        "DOORBELL",
                    ],
                ],
            },
            "Sports & Activities": {
                "row_titles": [
                    "Team Sports",
                    "Individual Sports",
                    "Outdoor Activities",
                    "Indoor Activities",
                    "Water Sports",
                    "Other Activities",
                    "Predictive Text",
                ],
                "rows": [
                    [
                        "CRICKET",
                        "RUGBY",
                        "SOFTBALL",
                        "LACROSSE",
                        "FIELD HOCKEY",
                        "ULTIMATE FRISBEE",
                    ],
                    [
                        "BADMINTON",
                        "FENCING",
                        "JUDO",
                        "TAEKWONDO",
                        "TRACK",
                        "FIGURE SKATING",
                    ],
                    [
                        "ROCK CLIMBING",
                        "ORIENTEERING",
                        "GEOCACHING",
                        "TRAIL RUNNING",
                        "STARGAZING",
                        "BIRDWATCHING",
                    ],
                    [
                        "POOL",
                        "TABLE TENNIS",
                        "FOOSBALL",
                        "MARTIAL ARTS",
                        "POTTERY",
                        "BAKING",
                    ],
                    [
                        "SNORKELING",
                        "KAYAKING",
                        "CANOEING",
                        "SCUBA DIVING",
                        "WATER SKIING",
                        "WAKEBOARDING",
                    ],
                    [
                        "SNOWSHOEING",
                        "ICE SKATING",
                        "SURFING",
                        "PARKOUR",
                        "CURLING",
                        "ZUMBA",
                    ],
                ],
            },
            "Hobbies & Interests": {
                "row_titles": [
                    "Arts & Crafts",
                    "Music",
                    "Gardening",
                    "Collecting",
                    "Technology",
                    "Games",
                    "Predictive Text",
                ],
                "rows": [
                    [
                        "ORIGAMI",
                        "CALLIGRAPHY",
                        "WEAVING",
                        "WOODWORKING",
                        "EMBROIDERY",
                        "QUILTING",
                    ],
                    ["HARMONICA", "BASS", "KEYBOARD", "FLUTE", "SAXOPHONE", "VIOLA"],
                    [
                        "HERBS",
                        "VEGETABLES",
                        "FLOWERS",
                        "FRUIT TREES",
                        "SUCCULENTS",
                        "VINES",
                    ],
                    [
                        "VINTAGE ITEMS",
                        "TOYS",
                        "ROCKS",
                        "ARTIFACTS",
                        "MEMORABILIA",
                        "POSTCARDS",
                    ],
                    [
                        "DRONES",
                        "VR",
                        "AI PROJECTS",
                        "HOME AUTOMATION",
                        "CODING CHALLENGES",
                        "DATA VISUALIZATION",
                    ],
                    [
                        "RPGS",
                        "SIMULATIONS",
                        "MYSTERY GAMES",
                        "PARTY GAMES",
                        "ESCAPE ROOMS",
                        "WORD GAMES",
                    ],
                ],
            },
            "Jobs & Professions": {
                "row_titles": [
                    "Medical",
                    "Education",
                    "Technology",
                    "Trades",
                    "Creative",
                    "Service",
                    "Predictive Text",
                ],
                "rows": [
                    [
                        "OPTOMETRIST",
                        "RADIOLOGIST",
                        "PHARMACIST",
                        "VETERINARIAN",
                        "ORTHODONTIST",
                        "MIDWIFE",
                    ],
                    [
                        "DEAN",
                        "SUBSTITUTE",
                        "ASSISTANT",
                        "RESEARCHER",
                        "SPECIALIST",
                        "TRAINER",
                    ],
                    [
                        "ARCHITECT",
                        "DEVELOPER",
                        "SYSADMIN",
                        "DATA SCIENTIST",
                        "CRYPTOGRAPHER",
                        "AI ENGINEER",
                    ],
                    [
                        "PLASTERER",
                        "BRICKLAYER",
                        "BLACKSMITH",
                        "LANDSCAPER",
                        "PLUMBER",
                        "ROOFER",
                    ],
                    [
                        "CARTOONIST",
                        "ANIMATOR",
                        "SET DESIGNER",
                        "SCREENWRITER",
                        "COMPOSER",
                        "LYRICIST",
                    ],
                    [
                        "BARBER",
                        "BUTCHER",
                        "TAILOR",
                        "RECEPTIONIST",
                        "COURIER",
                        "WAITSTAFF",
                    ],
                ],
            },
            "Simpsons/Futurama": {
                "row_titles": [
                    "Main Characters",
                    "Supporting Characters",
                    "Antagonists",
                    "Secondary Characters",
                    "Iconic Items/Places",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    [
                        "HOMER",
                        "MARGE",
                        "BART",
                        "LISA",
                        "MAGGIE",
                        "MILHOUSE",
                    ],  # MAIN CHARACTERS
                    [
                        "BENDER",
                        "FRY",
                        "LEELA",
                        "ZOIDBERG",
                        "PROFESSOR",
                        "AMY",
                    ],  # SUPPORTING CHARACTERS
                    [
                        "MR. BURNS",
                        "SMITHERS",
                        "MOE",
                        "BARNEY",
                        "LENNY",
                        "CARL",
                    ],  # ANTAGONISTS
                    [
                        "KRUSTY",
                        "APU",
                        "COMIC BOOK GUY",
                        "RALPH",
                        "NELSON",
                        "SKINNER",
                    ],  # SECONDARY CHARACTERS
                    [
                        "ROBOT DEVIL",
                        "HERMES",
                        "SCRUFFY",
                        "KIF",
                        "ZAPP",
                        "MOM",
                    ],  # ICONIC ITEMS/PLACES
                    [
                        "ITCHY",
                        "SCRATCHY",
                        "FUTURAMA SHIP",
                        "NIBBLER",
                        "HYPNOTOAD",
                        "SLURM",
                    ],  # Miscellaneous
                ],
            },
            "Family Guy/American Dad": {
                "row_titles": [
                    "Main Characters",
                    "Supporting Characters",
                    "Antagonists",
                    "Secondary Characters",
                    "Iconic Items/Places",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    [
                        "PETER",
                        "LOIS",
                        "STEWIE",
                        "BRIAN",
                        "CHRIS",
                        "MEG",
                    ],  # MAIN CHARACTERS
                    [
                        "QUAGMIRE",
                        "CLEVELAND",
                        "JOE",
                        "MORT",
                        "DR. HARTMAN",
                        "HERBERT",
                    ],  # SUPPORTING CHARACTERS
                    [
                        "STAN",
                        "FRANCINE",
                        "STEVE",
                        "ROGER",
                        "HAYLEY",
                        "KLAUS",
                    ],  # ANTAGONISTS
                    [
                        "CHRIS",
                        "PRINCIPAL SHEPHERD",
                        "NEIL",
                        "CONSUELA",
                        "SEAMUS",
                        "TRICIA",
                    ],  # SECONDARY CHARACTERS
                    [
                        "THE CHICKEN",
                        "DEATH",
                        "ANGELA",
                        "BRUCE",
                        "JILLIAN",
                        "TOM TUCKER",
                    ],  # ICONIC ITEMS/PLACES
                    [
                        "RICKY SPANISH",
                        "BULLOCK",
                        "GREG",
                        "TERRY",
                        "BARRY",
                        "SNOT",
                    ],  # Miscellaneous
                ],
            },
            "South Park": {
                "row_titles": [
                    "Main Characters",
                    "Supporting Characters",
                    "Antagonists",
                    "Secondary Characters",
                    "Iconic Items/Places",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    [
                        "CARTMAN",
                        "STAN",
                        "KYLE",
                        "KENNY",
                        "BUTTERS",
                        "WENDY",
                    ],  # MAIN CHARACTERS
                    [
                        "RANDY",
                        "SHARON",
                        "SHELLY",
                        "MR. GARRISON",
                        "MR. MACKEY",
                        "CHEF",
                    ],  # SUPPORTING CHARACTERS
                    [
                        "TOKEN",
                        "JIMMY",
                        "TIMMY",
                        "CRAIG",
                        "TWEEK",
                        "CLYDE",
                    ],  # ANTAGONISTS
                    [
                        "TERRANCE",
                        "PHILLIP",
                        "PC PRINCIPAL",
                        "SATAN",
                        "MR. HANKEY",
                        "BIG GAY AL",
                    ],  # SECONDARY CHARACTERS
                    [
                        "MAYOR",
                        "DR. MEPHESTO",
                        "PRINCIPAL VICTORIA",
                        "LEMMIWINKS",
                        "IKE",
                        "PIP",
                    ],  # ICONIC ITEMS/PLACES
                    [
                        "MANBEARPIG",
                        "CARTMAN'S MOM",
                        "STARVIN' MARVIN",
                        "MS. CHOKSONDIK",
                        "NATHAN",
                        "SCOTT TENORMAN",
                    ],  # Miscellaneous
                ],
            },
            "Dragon Ball Universe": {
                "row_titles": [
                    "Main Characters",
                    "Supporting Characters",
                    "Antagonists",
                    "Secondary Characters",
                    "Iconic Items/Places",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    [
                        "GOKU",
                        "VEGETA",
                        "PICCOLO",
                        "KRILLIN",
                        "BULMA",
                        "TRUNKS",
                    ],  # MAIN CHARACTERS
                    [
                        "FRIEZA",
                        "CELL",
                        "MAJIN BUU",
                        "GOHAN",
                        "CHI-CHI",
                        "YAMCHA",
                    ],  # SUPPORTING CHARACTERS
                    [
                        "TIEN",
                        "CHIAOTZU",
                        "ANDROID 18",
                        "ANDROID 17",
                        "MASTER ROSHI",
                        "VIDEL",
                    ],  # ANTAGONISTS
                    [
                        "BEERUS",
                        "WHIS",
                        "JIREN",
                        "ZENO",
                        "RADITZ",
                        "NAPPA",
                    ],  # SECONDARY CHARACTERS
                    [
                        "GOTEN",
                        "BARDOCK",
                        "KAME HOUSE",
                        "KORIN",
                        "KAMI",
                        "DENDE",
                    ],  # ICONIC ITEMS/PLACES
                    [
                        "DRAGON BALLS",
                        "NIMBUS",
                        "FUSION",
                        "SPIRIT BOMB",
                        "ULTRA INSTINCT",
                        "SAIYAN",
                    ],  # Miscellaneous
                ],
            },
            "Drake & Josh/iCarly/Victorious": {
                "row_titles": [
                    "Main Characters",
                    "Supporting Characters",
                    "Antagonists",
                    "Secondary Characters",
                    "Iconic Items/Places",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    [
                        "DRAKE",
                        "JOSH",
                        "MEGAN",
                        "WALTER",
                        "AUDREY",
                        "CRAZY STEVE",
                    ],  # MAIN CHARACTERS
                    [
                        "CARLY",
                        "SAM",
                        "FREDDIE",
                        "SPENCER",
                        "GIBBY",
                        "NEVEL",
                    ],  # SUPPORTING CHARACTERS
                    ["TORI", "ANDRE", "JADE", "BECK", "CAT", "ROBBIE"],  # ANTAGONISTS
                    [
                        "HELEN",
                        "MRS. BENSON",
                        "TRINA",
                        "SINJIN",
                        "LANE",
                        "SOCKO",
                    ],  # SECONDARY CHARACTERS
                    [
                        "PECK",
                        "SHAMPOO HAT",
                        "MOVIE THEATER",
                        "ICARLY SHOW",
                        "PEAR PHONE",
                        "SMOOTHIE",
                    ],  # ICONIC ITEMS/PLACES
                    [
                        "HOLLYWOOD ARTS",
                        "SPAGHETTI TACOS",
                        "PUPPETS",
                        "SPENCER'S SCULPTURES",
                        "MOOD APP",
                        "GROOVY SMOOTHIE",
                    ],  # Miscellaneous
                ],
            },
            "Rugrats/Spongebob": {
                "row_titles": [
                    "Main Characters",
                    "Supporting Characters",
                    "Antagonists",
                    "Secondary Characters",
                    "Iconic Items/Places",
                    "Miscellaneous",
                    "Predictive Text",
                ],
                "rows": [
                    [
                        "TOMMY",
                        "CHUCKIE",
                        "PHIL",
                        "LIL",
                        "ANGELICA",
                        "DIL",
                    ],  # MAIN CHARACTERS
                    [
                        "STU",
                        "DIDI",
                        "GRANDPA",
                        "SPIKE",
                        "SUSIE",
                        "KIMI",
                    ],  # SUPPORTING CHARACTERS
                    [
                        "SPONGEBOB",
                        "PATRICK",
                        "SQUIDWARD",
                        "MR. KRABS",
                        "SANDY",
                        "PLANKTON",
                    ],  # ANTAGONISTS
                    [
                        "GARY",
                        "KAREN",
                        "BUBBLE BUDDY",
                        "MERMAID MAN",
                        "BARNACLE BOY",
                        "FLYING DUTCHMAN",
                    ],  # SECONDARY CHARACTERS
                    [
                        "JELLYFISH",
                        "KRUSTY KRAB",
                        "CHUM BUCKET",
                        "GOOFY GOOBER",
                        "PINEAPPLE",
                        "LAGOON",
                    ],  # ICONIC ITEMS/PLACES
                    [
                        "REPTAR",
                        "PICKLES",
                        "ANGELICA'S DOLL",
                        "RUGRATS ADVENTURES",
                        "TIDE POOL",
                        "BIKINI BOTTOM",
                    ],  # Miscellaneous
                ],
            },
        }


if __name__ == "__main__":
    app = KeyboardFrameApp()
    app.mainloop()
