import ctypes
import math
import os
import subprocess
import sys
import threading
import time

import pygame
import pyttsx3
import win32gui

# Initialize pygame, mixer, and TTS engine
pygame.init()
pygame.mixer.init()  # For sound effects
tts_engine = pyttsx3.init()
tts_engine.setProperty("rate", 150)

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ---------------- Load Sound Effects ----------------
# Relative paths: game lives in "games" folder, sound effects in "../soundfx/"
putt_sound = pygame.mixer.Sound(os.path.join("..", "soundfx", "putt.wav"))
areyoutoogoodforyourhome_sound = pygame.mixer.Sound(
    os.path.join("..", "soundfx", "areyoutoogoodforyourhome.wav")
)
golfballwhacker_sound = pygame.mixer.Sound(
    os.path.join("..", "soundfx", "golfballwhacker.wav")
)
golfrequires_sound = pygame.mixer.Sound(
    os.path.join("..", "soundfx", "golfrequires.wav")
)
in_hole_sound = pygame.mixer.Sound(os.path.join("..", "soundfx", "in-hole.wav"))
jackass_sound = pygame.mixer.Sound(os.path.join("..", "soundfx", "jackass.wav"))
youwillnot_sound = pygame.mixer.Sound(os.path.join("..", "soundfx", "youwillnot.wav"))
timetogohome_sound = pygame.mixer.Sound(
    os.path.join("..", "soundfx", "timetogohome.wav")
)
tapperoo_sound = pygame.mixer.Sound(os.path.join("..", "soundfx", "tapperoo.wav"))
happylearned_sound = pygame.mixer.Sound(
    os.path.join("..", "soundfx", "happylearned.wav")
)
plentymore_sound = pygame.mixer.Sound(os.path.join("..", "soundfx", "plentymore.wav"))
splash_sound = pygame.mixer.Sound(os.path.join("..", "soundfx", "splash.wav"))
ambience_sound = pygame.mixer.Sound(os.path.join("..", "soundfx", "ambience.wav"))

# Play ambience on loop (-1 loops indefinitely)
ambience_sound.play(-1)

# ---------------- Global Variables ----------------
VIRTUAL_WIDTH = 1200
VIRTUAL_HEIGHT = 800

virtual_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT))
screen = pygame.display.set_mode(
    (pygame.display.Info().current_w, pygame.display.Info().current_h),
    pygame.FULLSCREEN,
)
pygame.display.set_caption("Mini Golf")

WIDTH, HEIGHT = VIRTUAL_WIDTH, VIRTUAL_HEIGHT  # Virtual resolution for game logic
BALL_SPEED = WIDTH

BORDER_THICKNESS = 50
BASE_BALL_RADIUS = 45
BASE_HOLE_RADIUS = 45
FRICTION = 0.9875
ANGLE_SPEED = 5
MAX_POWER = 3
PAUSE_HOLD_TIME = 6000

# Colors
WHITE = (255, 255, 255)
GREEN = (0, 128, 0)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
GREY = (50, 50, 50)
DARK_RED = (150, 0, 0)
BLUE = (0, 0, 255)
SAND = (194, 178, 128)

# Global game state variables
ball_x = 0
ball_y = 0
hole_x, hole_y = 0, 0
ball_velocity = [0, 0]
can_shoot = True
stroke_count = 0
strokes_this_level = 0  # Stroke count for current level

# For deferring stroke-specific sound effects
pending_stroke_sound = None  # Will store the stroke number (2, 3, or 4)

# Aiming
angle = 0
rotate_direction = 1
rotating = False
power = 0
charging = False

# For detecting long-press on Return (Enter)
return_key_hold_start = None
pause_triggered = False

# Level variables
current_level = 1
TOTAL_LEVELS = 9
current_hole_radius = BASE_HOLE_RADIUS

# Hazards
# current_walls can be either axis-aligned (tuple) or rotated (dict with keys "rect" and "angle")
current_walls = []
current_waters = []
current_sands = []

# Font for text
font = pygame.font.Font(None, 36)
clock = pygame.time.Clock()

# Global flag for main menu first load
first_main_menu = True


# --- TTS and Utility Functions ---
def speak(text):
    tts_engine.say(text)
    tts_engine.runAndWait()


def clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))


def circle_rect_collision(cx, cy, radius, rx, ry, rw, rh):
    closest_x = clamp(cx, rx, rx + rw)
    closest_y = clamp(cy, ry, ry + rh)
    distance = math.hypot(cx - closest_x, cy - closest_y)
    return distance < radius


def bounce_off_hazard_wall(cx, cy, vel, radius, rect):
    # Axis-aligned wall collision detection.
    rx, ry, rw, rh = rect
    if not circle_rect_collision(cx, cy, radius, rx, ry, rw, rh):
        return cx, cy
    closest_x = clamp(cx, rx, rx + rw)
    closest_y = clamp(cy, ry, ry + rh)
    dx = cx - closest_x
    dy = cy - closest_y
    dist = math.hypot(dx, dy)
    if dist == 0:
        dx, dy = 1, 0
        dist = 1
    n_x, n_y = dx / dist, dy / dist
    penetration = radius - dist
    cx += n_x * penetration
    cy += n_y * penetration
    dot = vel[0] * n_x + vel[1] * n_y
    vel[0] = (vel[0] - 2 * dot * n_x) * 0.8
    vel[1] = (vel[1] - 2 * dot * n_y) * 0.8
    return cx, cy


def bounce_off_rotated_wall(cx, cy, vel, radius, wall):
    r = wall["rect"]
    angle_rad = math.radians(wall.get("angle", 0))
    # Translate circle center to wall's local coordinate system
    cx_local = math.cos(-angle_rad) * (cx - r.centerx) - math.sin(-angle_rad) * (
        cy - r.centery
    )
    cy_local = math.sin(-angle_rad) * (cx - r.centerx) + math.cos(-angle_rad) * (
        cy - r.centery
    )
    half_w = r.width / 2
    half_h = r.height / 2
    # Axis aligned rectangle in local coordinates: from -half_w to half_w, -half_h to half_h
    closest_x = clamp(cx_local, -half_w, half_w)
    closest_y = clamp(cy_local, -half_h, half_h)
    dx = cx_local - closest_x
    dy = cy_local - closest_y
    dist = math.hypot(dx, dy)
    if dist >= radius:
        return cx, cy  # No collision
    if dist == 0:
        dx, dy = 1, 0
        dist = 1
    penetration = radius - dist
    n_local_x = dx / dist
    n_local_y = dy / dist
    cx_local += n_local_x * penetration
    cy_local += n_local_y * penetration
    # Convert back to global coordinates
    cx_new = math.cos(angle_rad) * cx_local - math.sin(angle_rad) * cy_local + r.centerx
    cy_new = math.sin(angle_rad) * cx_local + math.cos(angle_rad) * cy_local + r.centery
    # Reflect velocity
    vx_local = math.cos(-angle_rad) * vel[0] - math.sin(-angle_rad) * vel[1]
    vy_local = math.sin(-angle_rad) * vel[0] + math.cos(-angle_rad) * vel[1]
    dot = vx_local * n_local_x + vy_local * n_local_y
    vx_local = (vx_local - 2 * dot * n_local_x) * 0.8
    vy_local = (vy_local - 2 * dot * n_local_y) * 0.8
    vel[0] = math.cos(angle_rad) * vx_local - math.sin(angle_rad) * vy_local
    vel[1] = math.sin(angle_rad) * vx_local + math.cos(angle_rad) * vy_local
    return cx_new, cy_new


def announce_level(level):
    if level in [1, 3, 7]:
        pass
    else:
        speak(f"Level {level}")


# --- Level Loading and Reset Functions ---
def load_level(level):
    global ball_x, ball_y, hole_x, hole_y, current_hole_radius
    global ball_velocity, can_shoot, rotating, power, charging, angle, rotate_direction
    global current_walls, current_waters, current_sands, strokes_this_level, current_level, pending_stroke_sound

    play_x0 = BORDER_THICKNESS
    play_y0 = BORDER_THICKNESS
    play_width = WIDTH - 2 * BORDER_THICKNESS
    play_height = HEIGHT - 2 * BORDER_THICKNESS

    if level == 1:
        ball_vert_pct = 0.2
        hole_vert_pct = 0.8
        ball_x = play_x0 + BASE_BALL_RADIUS + 10
        ball_y = (
            play_y0
            + BASE_BALL_RADIUS
            + ball_vert_pct * (play_height - 2 * BASE_BALL_RADIUS)
        )
        hole_x = play_x0 + play_width - BASE_HOLE_RADIUS - 10
        hole_y = (
            play_y0
            + BASE_HOLE_RADIUS
            + hole_vert_pct * (play_height - 2 * BASE_BALL_RADIUS)
        )
        current_walls = []
        current_waters = []
        current_sands = []
        current_hole_radius = BASE_HOLE_RADIUS
    elif level == 2:
        # Example: axis-aligned wall as tuple
        current_walls = [(489, 279, 120, 240)]
        current_waters = []
        current_sands = []
        ball_x, ball_y = (112, 372)
        hole_x, hole_y = (1068, 398)
        current_hole_radius = BASE_HOLE_RADIUS
    elif level == 3:
        current_walls = [(503, 509, 120, 240)]
        current_waters = []
        current_sands = [
            (343, 110, 100, 60),
            (343, 50, 100, 60),
            (343, 169, 100, 60),
            (343, 228, 100, 60),
            (443, 198, 150, 90),
            (443, 108, 150, 90),
            (443, 50, 150, 90),
        ]
        ball_x, ball_y = (133, 617)
        hole_x, hole_y = (976, 159)
        current_hole_radius = BASE_HOLE_RADIUS
    elif level == 4:
        current_walls = [
            (902, 590, 80, 160),
            (725, 50, 80, 160),
            (316, 215, 120, 240),
        ]
        current_waters = [
            (425, 50, 150, 90),
            (575, 50, 150, 90),
            (752, 659, 150, 90),
            (602, 659, 150, 90),
            (453, 659, 150, 90),
        ]
        current_sands = [
            (1100, 281, 50, 30),
            (1100, 309, 50, 30),
            (1100, 337, 50, 30),
            (1100, 367, 50, 30),
            (1100, 397, 50, 30),
            (1052, 383, 50, 30),
            (1052, 353, 50, 30),
            (1051, 325, 50, 30),
            (1051, 296, 50, 30),
            (1022, 311, 50, 30),
            (1015, 338, 50, 30),
            (1023, 365, 50, 30),
        ]
        ball_x, ball_y = (180, 656)
        hole_x, hole_y = (1001, 157)
        current_hole_radius = BASE_HOLE_RADIUS
    elif level == 5:
        current_walls = [(352, 492, 50, 100), (402, 444, 50, 100), (451, 392, 50, 100)]
        current_waters = [(999, 51, 150, 90), (999, 139, 150, 90), (999, 225, 150, 90)]
        current_sands = [
            (448, 50, 50, 30),
            (461, 79, 50, 30),
            (487, 107, 50, 30),
            (497, 50, 50, 30),
            (511, 77, 50, 30),
            (502, 128, 50, 30),
            (528, 143, 50, 30),
            (552, 115, 50, 30),
        ]
        ball_x, ball_y = (254, 397)
        hole_x, hole_y = (666, 515)
        current_hole_radius = BASE_HOLE_RADIUS
    elif level == 6:
        current_walls = [
            (589, 49, 120, 240),
            (378, 510, 120, 240),
            (199, 322, 50, 100),
            (149, 372, 50, 100),
            (247, 263, 50, 100),
        ]
        current_waters = [
            (999, 51, 150, 90),
            (999, 139, 150, 90),
            (999, 225, 150, 90),
            (709, 50, 150, 90),
            (851, 50, 150, 90),
        ]
        current_sands = [
            (685, 691, 100, 60),
            (706, 633, 100, 60),
            (783, 690, 100, 60),
            (806, 630, 100, 60),
            (766, 575, 100, 60),
            (805, 521, 100, 60),
            (864, 577, 100, 60),
            (883, 635, 100, 60),
            (931, 691, 100, 60),
            (879, 691, 100, 60),
        ]
        ball_x, ball_y = (209, 128)
        hole_x, hole_y = (908, 213)
        current_hole_radius = BASE_HOLE_RADIUS
    elif level == 7:
        current_walls = [
            (454, 589, 80, 160),
            (474, 50, 80, 160),
            (474, 209, 80, 160),
            (749, 510, 120, 240),
        ]
        current_waters = [
            (324, 49, 150, 90),
            (554, 49, 150, 90),
            (701, 49, 150, 90),
            (850, 49, 150, 90),
            (1000, 49, 150, 90),
            (869, 720, 50, 30),
            (919, 720, 50, 30),
            (966, 720, 50, 30),
            (1013, 720, 50, 30),
            (1060, 720, 50, 30),
            (1100, 720, 50, 30),
        ]
        current_sands = [
            (50, 692, 100, 60),
            (147, 691, 100, 60),
            (237, 693, 100, 60),
            (81, 644, 100, 60),
            (176, 641, 100, 60),
            (143, 600, 100, 60),
            (1101, 190, 50, 30),
            (1101, 218, 50, 30),
            (1101, 248, 50, 30),
            (1101, 277, 50, 30),
            (1102, 304, 50, 30),
            (1058, 216, 50, 30),
            (1057, 246, 50, 30),
            (1059, 274, 50, 30),
            (1027, 241, 50, 30),
            (1064, 300, 50, 30),
            (1039, 270, 50, 30),
            (1049, 293, 50, 30),
            (1101, 332, 50, 30),
            (1077, 321, 50, 30),
        ]
        ball_x, ball_y = (157, 192)
        hole_x, hole_y = (1034, 655)
        current_hole_radius = BASE_HOLE_RADIUS
    elif level == 8:
        current_walls = [
            (295, 258, 120, 240),
            (726, 450, 120, 240),
            (410, 258, 50, 100),
            (455, 258, 50, 100),
            (501, 258, 50, 100),
            (540, 258, 50, 100),
        ]
        current_waters = [
            (96, 467, 50, 30),
            (146, 467, 50, 30),
            (196, 467, 50, 30),
            (245, 467, 50, 30),
            (51, 467, 50, 30),
            (1001, 50, 150, 90),
            (1001, 138, 150, 90),
            (1001, 224, 150, 90),
            (1001, 310, 150, 90),
            (1001, 395, 150, 90),
            (1001, 482, 150, 90),
            (1001, 570, 150, 90),
            (1001, 660, 150, 90),
        ]
        current_sands = [
            (767, 50, 100, 60),
            (781, 103, 100, 60),
            (804, 148, 100, 60),
            (832, 181, 100, 60),
            (872, 205, 100, 60),
            (902, 233, 100, 60),
            (863, 50, 100, 60),
            (865, 104, 100, 60),
            (901, 50, 100, 60),
            (902, 109, 100, 60),
            (902, 181, 100, 60),
            (903, 146, 100, 60),
            (49, 99, 50, 30),
            (49, 129, 50, 30),
            (49, 70, 50, 30),
            (49, 48, 50, 30),
            (97, 49, 50, 30),
            (147, 49, 50, 30),
            (178, 49, 50, 30),
            (79, 74, 50, 30),
            (66, 98, 50, 30),
            (108, 64, 50, 30),
            (340, 690, 100, 60),
            (433, 691, 100, 60),
            (367, 655, 100, 60),
            (426, 661, 100, 60),
            (393, 633, 50, 30),
            (417, 619, 50, 30),
            (438, 634, 50, 30),
            (462, 642, 50, 30),
        ]
        ball_x, ball_y = (160, 352)
        hole_x, hole_y = (159, 656)
        current_hole_radius = BASE_HOLE_RADIUS
    elif level == 9:
        current_walls = [
            (361, 50, 80, 160),
            (361, 210, 80, 160),
            (439, 270, 50, 100),
            (489, 270, 50, 100),
            (539, 270, 50, 100),
            (589, 270, 50, 100),
            (639, 270, 50, 100),
            (634, 552, 50, 100),
            (634, 651, 50, 100),
            (831, 137, 50, 100),
            (947, 362, 50, 100),
            (820, 503, 50, 100),
            (309, 546, 50, 100),
        ]
        current_waters = [
            (50, 720, 50, 30),
            (98, 720, 50, 30),
            (144, 720, 50, 30),
            (194, 720, 50, 30),
            (244, 720, 50, 30),
            (293, 720, 50, 30),
            (341, 720, 50, 30),
            (391, 720, 50, 30),
            (440, 720, 50, 30),
            (489, 720, 50, 30),
            (536, 720, 50, 30),
            (585, 720, 50, 30),
            (949, 719, 50, 30),
            (999, 719, 50, 30),
            (899, 719, 50, 30),
            (850, 719, 50, 30),
            (440, 212, 100, 60),
            (440, 154, 100, 60),
        ]
        current_sands = [
            (50, 228, 100, 60),
            (50, 288, 100, 60),
            (50, 347, 100, 60),
            (50, 406, 100, 60),
            (1050, 631, 100, 60),
            (1050, 691, 100, 60),
            (1050, 572, 100, 60),
            (1050, 109, 100, 60),
            (1050, 50, 100, 60),
            (1050, 169, 100, 60),
            (1050, 229, 100, 60),
        ]
        ball_x, ball_y = (226, 124)
        hole_x, hole_y = (491, 103)

    ball_velocity = [0, 0]
    can_shoot = True
    rotating = False
    power = 0
    charging = False
    angle = 0
    rotate_direction = 1

    strokes_this_level = 0
    pending_stroke_sound = None

    if level == 1:
        golfrequires_sound.play()
    elif level == 3:
        timetogohome_sound.play()
    elif level == 7:
        youwillnot_sound.play()

    announce_level(level)


def reset_game_state():
    global stroke_count, current_level
    stroke_count = 0
    current_level = 1
    load_level(current_level)


def end_game_screen(strokes):
    message = f"Congratulations, you finished in {strokes} strokes!"
    speak(message)
    end_font = pygame.font.Font(None, 72)
    display_time = 3000
    start_ticks = pygame.time.get_ticks()
    while pygame.time.get_ticks() - start_ticks < display_time:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        virtual_surface.fill(GREEN)
        text_surface = end_font.render(message, True, WHITE)
        text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        virtual_surface.blit(text_surface, text_rect)
        scaled_surface = pygame.transform.scale(virtual_surface, screen.get_size())
        screen.blit(scaled_surface, (0, 0))
        pygame.display.flip()
    menu()
    reset_game_state()


def draw_text(text, font, color, x, y):
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=(x, y))
    virtual_surface.blit(text_surface, text_rect)


def get_window_handle():
    info = pygame.display.get_wm_info()
    return info["window"]


def force_focus():
    hwnd = get_window_handle()
    try:
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"Error forcing focus: {e}")


def monitor_focus():
    while True:
        time.sleep(0.5)
        hwnd = get_window_handle()
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


def menu():
    global first_main_menu
    menu_running = True
    selected_option = 0
    title_font = pygame.font.Font(None, 72)
    button_font = pygame.font.Font(None, 48)

    if first_main_menu:
        golfballwhacker_sound.play()
        first_main_menu = False

    while menu_running:
        virtual_surface.fill(GREEN)
        pygame.draw.circle(
            virtual_surface, WHITE, (WIDTH // 3, HEIGHT // 2), BASE_BALL_RADIUS
        )
        pygame.draw.circle(
            virtual_surface, BLACK, (2 * WIDTH // 3, HEIGHT // 2), BASE_HOLE_RADIUS
        )
        draw_text("Mini Golf", title_font, WHITE, WIDTH // 2, HEIGHT // 4)
        play_color = RED if selected_option == 0 else WHITE
        exit_color = RED if selected_option == 1 else WHITE
        draw_text("Play", button_font, play_color, WIDTH // 2, HEIGHT // 2)
        draw_text("Exit", button_font, exit_color, WIDTH // 2, HEIGHT // 2 + 60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    selected_option = 1 - selected_option
                    speak("Play" if selected_option == 0 else "Exit")
                elif event.key == pygame.K_RETURN:
                    if selected_option == 0:
                        menu_running = False
                    else:
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        comm_v9_path = os.path.join(current_dir, "..", "comm-v9.py")
                        subprocess.Popen(["python", comm_v9_path])
                        pygame.quit()
                        sys.exit()
        scaled_surface = pygame.transform.scale(virtual_surface, screen.get_size())
        screen.blit(scaled_surface, (0, 0))
        pygame.display.flip()


def pause_menu():
    global power, charging, rotating, return_key_hold_start, pause_triggered
    power = 0
    charging = False
    rotating = False
    pause_running = True
    selected_option = None
    pause_font = pygame.font.Font(None, 48)
    speak("Paused")
    pygame.event.clear(pygame.KEYDOWN)
    pygame.event.clear(pygame.KEYUP)
    while pause_running:
        virtual_surface.fill(GREEN)
        draw_text("Pause Menu", font, WHITE, WIDTH // 2, HEIGHT // 4)
        continue_color = (
            WHITE
            if selected_option is None
            else (RED if selected_option == 0 else WHITE)
        )
        main_menu_color = (
            WHITE
            if selected_option is None
            else (RED if selected_option == 1 else WHITE)
        )
        draw_text("Continue Game", pause_font, continue_color, WIDTH // 2, HEIGHT // 2)
        draw_text(
            "Main Menu", pause_font, main_menu_color, WIDTH // 2, HEIGHT // 2 + 60
        )
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    if selected_option is None:
                        selected_option = 0
                    else:
                        selected_option = 1 - selected_option
                    speak("Continue Game" if selected_option == 0 else "Main Menu")
                elif event.key == pygame.K_RETURN:
                    if selected_option is None:
                        pass
                    elif selected_option == 0:
                        pause_running = False
                    else:
                        pause_running = False
                        speak("Main menu")
                        reset_game_state()
                        menu()
        scaled_surface = pygame.transform.scale(virtual_surface, screen.get_size())
        screen.blit(scaled_surface, (0, 0))
        pygame.display.flip()


menu()
reset_game_state()

running = True
while running:
    dt = clock.tick(60) / 1000
    virtual_surface.fill(GREEN)
    BALL_SPEED = WIDTH

    ball_x = max(
        BORDER_THICKNESS + BASE_BALL_RADIUS,
        min(WIDTH - BORDER_THICKNESS - BASE_BALL_RADIUS, ball_x),
    )
    ball_y = max(
        BORDER_THICKNESS + BASE_BALL_RADIUS,
        min(HEIGHT - BORDER_THICKNESS - BASE_BALL_RADIUS, ball_y),
    )

    pygame.draw.rect(virtual_surface, GREY, (0, 0, WIDTH, BORDER_THICKNESS))
    pygame.draw.rect(
        virtual_surface, GREY, (0, HEIGHT - BORDER_THICKNESS, WIDTH, BORDER_THICKNESS)
    )
    pygame.draw.rect(virtual_surface, GREY, (0, 0, BORDER_THICKNESS, HEIGHT))
    pygame.draw.rect(
        virtual_surface, GREY, (WIDTH - BORDER_THICKNESS, 0, BORDER_THICKNESS, HEIGHT)
    )

    # Draw walls: check if rotated or axis-aligned
    for wall in current_walls:
        if isinstance(wall, dict):

            def draw_rotated_wall(wall):
                r = wall["rect"]
                angle = wall.get("angle", 0)
                temp_surface = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
                temp_surface.fill(DARK_RED)
                rotated_surface = pygame.transform.rotate(temp_surface, angle)
                new_rect = rotated_surface.get_rect(center=r.center)
                virtual_surface.blit(rotated_surface, new_rect)

            draw_rotated_wall(wall)
        else:
            pygame.draw.rect(virtual_surface, DARK_RED, wall)
    for water in current_waters:
        pygame.draw.rect(virtual_surface, BLUE, water)
    for sand in current_sands:
        pygame.draw.rect(virtual_surface, SAND, sand)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if return_key_hold_start is None:
                    return_key_hold_start = pygame.time.get_ticks()
                if can_shoot:
                    charging = True
                    power = 0
            elif event.key == pygame.K_SPACE and can_shoot:
                rotating = True
                rotate_direction *= -1
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_RETURN:
                if pause_triggered:
                    pause_triggered = False
                elif return_key_hold_start is not None:
                    hold_duration = pygame.time.get_ticks() - return_key_hold_start
                    if hold_duration < PAUSE_HOLD_TIME and can_shoot:
                        putt_sound.play()
                        ball_velocity[0] = (
                            math.cos(math.radians(angle))
                            * BALL_SPEED
                            * (power / MAX_POWER)
                        )
                        ball_velocity[1] = (
                            math.sin(math.radians(angle))
                            * BALL_SPEED
                            * (power / MAX_POWER)
                        )
                        charging = False
                        power = 0
                        can_shoot = False
                        stroke_count += 1
                        strokes_this_level += 1
                        if strokes_this_level in [2, 3, 4]:
                            pending_stroke_sound = strokes_this_level
                return_key_hold_start = None
            elif event.key == pygame.K_SPACE:
                rotating = False

    if return_key_hold_start is not None:
        if pygame.time.get_ticks() - return_key_hold_start >= PAUSE_HOLD_TIME:
            return_key_hold_start = None
            pause_triggered = True
            pause_menu()

    if rotating:
        angle += rotate_direction * ANGLE_SPEED * dt
        angle %= 360
    if charging:
        power = min(power + dt, MAX_POWER)

    ball_x += ball_velocity[0] * dt
    ball_y += ball_velocity[1] * dt
    ball_velocity[0] *= FRICTION
    ball_velocity[1] *= FRICTION

    if (
        ball_x - BASE_BALL_RADIUS < BORDER_THICKNESS
        or ball_x + BASE_BALL_RADIUS > WIDTH - BORDER_THICKNESS
    ):
        ball_velocity[0] *= -0.8
    if (
        ball_y - BASE_BALL_RADIUS < BORDER_THICKNESS
        or ball_y + BASE_BALL_RADIUS > HEIGHT - BORDER_THICKNESS
    ):
        ball_velocity[1] *= -0.8

    for wall in current_walls:
        if isinstance(wall, dict):
            ball_x, ball_y = bounce_off_rotated_wall(
                ball_x, ball_y, ball_velocity, BASE_BALL_RADIUS, wall
            )
        else:
            ball_x, ball_y = bounce_off_hazard_wall(
                ball_x, ball_y, ball_velocity, BASE_BALL_RADIUS, wall
            )

    hit_water = False
    for water in current_waters:
        if circle_rect_collision(ball_x, ball_y, BASE_BALL_RADIUS, *water):
            hit_water = True
            break
    if hit_water:
        splash_sound.play()  # Play splash.wav when ball lands in water hazard
        stroke_count += 1
        load_level(current_level)

    for sand in current_sands:
        if circle_rect_collision(ball_x, ball_y, BASE_BALL_RADIUS, *sand):
            ball_velocity[0] *= 0.7
            ball_velocity[1] *= 0.7

    if math.hypot(ball_x - hole_x, ball_y - hole_y) < current_hole_radius:
        pending_stroke_sound = None
        if current_level == TOTAL_LEVELS:
            plentymore_sound.play()
        elif strokes_this_level == 1:
            happylearned_sound.play()
        else:
            in_hole_sound.play()
        pygame.time.delay(500)
        if current_level < TOTAL_LEVELS:
            current_level += 1
            load_level(current_level)
        else:
            end_game_screen(stroke_count)

    if can_shoot and pending_stroke_sound is not None:
        if pending_stroke_sound == 2:
            tapperoo_sound.play()
        elif pending_stroke_sound == 3:
            areyoutoogoodforyourhome_sound.play()
        elif pending_stroke_sound == 4:
            jackass_sound.play()
        pending_stroke_sound = None

    if abs(ball_velocity[0]) < 0.1 and abs(ball_velocity[1]) < 0.1:
        ball_velocity = [0, 0]
        can_shoot = True

    pygame.draw.circle(
        virtual_surface, BLACK, (int(hole_x), int(hole_y)), current_hole_radius
    )
    pygame.draw.circle(
        virtual_surface, WHITE, (int(ball_x), int(ball_y)), BASE_BALL_RADIUS
    )
    if can_shoot or rotating:
        aim_x = ball_x + math.cos(math.radians(angle)) * 500
        aim_y = ball_y + math.sin(math.radians(angle)) * 500
        pygame.draw.line(virtual_surface, WHITE, (ball_x, ball_y), (aim_x, aim_y), 25)
    power_color = (
        (0, 255, 0)
        if power < MAX_POWER * 0.33
        else (255, 255, 0) if power < MAX_POWER * 0.66 else (255, 0, 0)
    )
    pygame.draw.rect(
        virtual_surface,
        power_color,
        (WIDTH // 3, HEIGHT - 50, int((WIDTH // 3) * (power / MAX_POWER)), 60),
    )
    pygame.draw.rect(
        virtual_surface, WHITE, (WIDTH // 3, HEIGHT - 50, WIDTH // 3, 60), 2
    )
    stroke_text = font.render(f"Strokes: {stroke_count}", True, WHITE)
    virtual_surface.blit(stroke_text, (WIDTH // 2 - 50, 10))
    level_text = font.render(f"Level: {current_level}/{TOTAL_LEVELS}", True, WHITE)
    virtual_surface.blit(level_text, (10, 10))

    scaled_surface = pygame.transform.scale(virtual_surface, screen.get_size())
    screen.blit(scaled_surface, (0, 0))
    pygame.display.flip()

pygame.quit()
