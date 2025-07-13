import pygame
import random
import time
import threading
import pyttsx3
import queue
from copy import deepcopy
import os
import subprocess
import sys
import math
import ctypes
import win32gui

# Initialize the mixer (only once)
pygame.mixer.init()

# Determine the path to the soundfx folder.
sound_folder = os.path.join(os.path.dirname(__file__), "..", "soundfx")

# Load sound effects and set them to full volume.
hit_tower_sound = pygame.mixer.Sound(os.path.join(sound_folder, "hittower.wav"))
hit_tower_sound.set_volume(1.0)
tower_shoot_sound = pygame.mixer.Sound(os.path.join(sound_folder, "towershoot.wav"))
tower_shoot_sound.set_volume(1.0)
enemy_destroyed_sound = pygame.mixer.Sound(os.path.join(sound_folder, "enemydestroyed.wav"))
enemy_destroyed_sound.set_volume(1.0)

# Load bomb and laser beam sound effects.
bomb_sound = pygame.mixer.Sound(os.path.join(sound_folder, "bomb.wav"))
bomb_sound.set_volume(1.0)
laserbeam_sound = pygame.mixer.Sound(os.path.join(sound_folder, "laserbeam.wav"))
laserbeam_sound.set_volume(1.0)

# Load Enemy Projectiles
enemy_projectiles = []

# Load and play background music.
tower_mid_path = os.path.join(sound_folder, "tower.wav")
pygame.mixer.music.load(tower_mid_path)
pygame.mixer.music.set_volume(1)  # This only affects the music channel.
pygame.mixer.music.play(-1)

# Initialize TTS (separate from pygame mixer)
engine = pyttsx3.init()
engine.setProperty('volume', 1.0)
tts_queue = queue.Queue()
def tts_worker():
    while True:
        text = tts_queue.get()
        if text is None:
            break
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print("TTS error:", e)
        tts_queue.task_done()

tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()

def speak(text):
    tts_queue.put(text)

# ------------------------------ #
#   Pygame Initialization        #
# ------------------------------ #
pygame.init()
INFO = pygame.display.Info()
SCREEN_WIDTH = INFO.current_w
SCREEN_HEIGHT = INFO.current_h
# Use a resizable window so that OS window controls appear.
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Ben's Tower Defense")
clock = pygame.time.Clock()

def handle_resize(event):
    global SCREEN_WIDTH, SCREEN_HEIGHT, screen, TOWER_X, TOWER_Y
    SCREEN_WIDTH, SCREEN_HEIGHT = event.w, event.h
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    TOWER_X = SCREEN_WIDTH // 2 - TOWER_SIZE // 2
    TOWER_Y = SCREEN_HEIGHT - 180

# ------------------------------ #
#         Global Variables       #
# ------------------------------ #
# Initially, maximum tower health is the same as TOWER_MAX_HP.
ROUND_DURATION = 150            # 2.5 minutes per level
TOWER_MAX_HP = 100
max_tower_hp = TOWER_MAX_HP

# These globals will be reset for a fresh game:
wave_number = 1
points = 200                    # Starting points
tower_hp = TOWER_MAX_HP
enemies = []
tower_projectiles = []
tower_units = []
game_time_start = time.time()
last_spawn_time = {"small": 0, "medium": 0, "large": 0, "extra_large": 0, "boss": 0}
tower_last_unit_spawn_time = time.time()
shield_hp = 0  # Shield starts with 0 HP
max_shield_hp = 0
shield_active = False

# Tower parameters – 150x150 (3× larger)
TOWER_SIZE = 150  
TOWER_X = SCREEN_WIDTH // 2 - TOWER_SIZE // 2
TOWER_Y = SCREEN_HEIGHT - 180  # Damage zone starts at TOWER_Y

# We'll use a global list for towers.
towers = []

# For pause detection:
return_hold_start = None
restart_requested = False

# Global variables for the laser beam:
laser_active = True
laser_start_time = time.time()
laser_hit_enemies = set()
last_laser_time = time.time()  # Tracks when the laser last fired

# --- Global Bomb Variables (add these near your other globals) ---
bomb_duration = 2.0        # Shockwave lasts 2 seconds.
bomb_damage = 6            # Damage dealt by the bomb.
bomb_last_time = time.time()  # Time when the bomb was last dropped.
bomb_active = False        # Whether the bomb effect is active.
bomb_hit_enemies = set()   # Enemies already damaged by the current bomb drop.

# --- Enemy Focus ---

focused_enemy = None

# ------------------------------ #
#    Custom Window Controls      #
# ------------------------------ #
def draw_window_controls():
    button_width = 40
    button_height = 30
    gap = 5
    close_rect = pygame.Rect(SCREEN_WIDTH - button_width - gap, gap, button_width, button_height)
    min_rect = pygame.Rect(SCREEN_WIDTH - 2*button_width - 2*gap, gap, button_width, button_height)
    pygame.draw.rect(screen, (200, 0, 0), close_rect)
    pygame.draw.rect(screen, (0, 200, 0), min_rect)
    font = pygame.font.Font(None, 36)
    close_text = font.render("X", True, (255,255,255))
    min_text = font.render("_", True, (255,255,255))
    screen.blit(close_text, (close_rect.x + (button_width - close_text.get_width())/2, close_rect.y + (button_height - close_text.get_height())/2))
    screen.blit(min_text, (min_rect.x + (button_width - min_text.get_width())/2, min_rect.y + (button_height - min_text.get_height())/2))
    return close_rect, min_rect

# ------------------------------ #
#         Tower Class            #
# ------------------------------ #
class Tower:
    def __init__(self, x, y, size=TOWER_SIZE):
        self.x = x
        self.y = y
        self.size = size

# ------------------------------ #
#      Bomb Effect Function      #
# ------------------------------ #
def drop_bomb_effect():
    global bomb_active, bomb_start_time, bomb_hit_enemies
    # Define the bomb's center. (Here, we choose the center of the screen.)
    bomb_center = (SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
    elapsed = time.time() - bomb_start_time
    # Determine the current radius of the shockwave.
    max_radius = 1500  # Adjust as desired.
    current_radius = (elapsed / bomb_duration) * max_radius
    # Draw an expanding circle outline (shockwave) in dark orange.
    dark_orange = (255, 140, 0)
    pygame.draw.circle(screen, dark_orange, (int(bomb_center[0]), int(bomb_center[1])), int(current_radius), 5)
    
    # Damage detection: for each enemy, if its distance from bomb_center is less than current_radius and
    # it has not already been hit by this bomb, then apply damage.
    for enemy in enemies[:]:
        distance = math.hypot(enemy.x - bomb_center[0], enemy.y - bomb_center[1])
        if distance < current_radius:
            if enemy not in bomb_hit_enemies:
                enemy.hp -= bomb_damage
                bomb_hit_enemies.add(enemy)
                if enemy.hp <= 0:
                    enemies.remove(enemy)
                    enemy_destroyed_sound.play()
    # Deactivate the bomb effect after bomb_duration seconds.
    if elapsed >= bomb_duration:
        bomb_active = False

# ------------------------------ #
#   Laser Beam Function  #
# ------------------------------ #

def draw_laser_beams():
    global laser_active, laser_start_time, laser_hit_enemies
    # Choose the "middle" tower: by horizontal distance to SCREEN_WIDTH/2.
    if not towers:
        return
    main_tower = min(towers, key=lambda t: abs((t.x + t.size/2) - SCREEN_WIDTH/2))
    tower_center_x = main_tower.x + main_tower.size/2

    # Define vertical region for the laser effect:
    # It should extend from the bottom of the timer bar (say, y = 70)
    # down to the top of the gray damage zone (TOWER_Y).
    y_top = 70
    y_bottom = TOWER_Y

    # Calculate progress parameter over 3 seconds (0 <= t <= 1).
    progress = (time.time() - laser_start_time) / 3.0
    if progress > 1:
        progress = 1

    # Animate the horizontal positions of two beams:
    # At progress=0, both beams start at tower_center_x.
    # At progress=1, left beam reaches a left boundary (e.g. 50) and right beam reaches a right boundary.
    left_bound = 50
    right_bound = SCREEN_WIDTH - 50
    left_beam_x = tower_center_x - progress * (tower_center_x - left_bound)
    right_beam_x = tower_center_x + progress * (right_bound - tower_center_x)
    beam_thickness = 10

    # Draw the two vertical beams (from y_top to y_bottom).
    pygame.draw.line(screen, (0, 0, 255), (left_beam_x, y_top), (left_beam_x, y_bottom), beam_thickness)
    pygame.draw.line(screen, (0, 0, 255), (right_beam_x, y_top), (right_beam_x, y_bottom), beam_thickness)

    # Damage detection: For enemies in this vertical region, if their x is within tolerance of either beam, subtract 1 hp.
    tolerance = beam_thickness / 2 + 5
    for enemy in enemies[:]:
        if y_top <= enemy.y <= y_bottom:
            if abs(enemy.x - left_beam_x) < tolerance or abs(enemy.x - right_beam_x) < tolerance:
                if enemy not in laser_hit_enemies:
                    enemy.hp -= 1
                    laser_hit_enemies.add(enemy)
                    if enemy.hp <= 0:
                        enemies.remove(enemy)
                        enemy_destroyed_sound.play()
        
# ------------------------------ #
#   Tower Projectile Functions   #
# ------------------------------ #
def get_tower_projectile_cooldown():
    upgrade = buy_menu_options[0]["purchased"]
    if upgrade >= 1:
        return max(1, 10 - 2 * (upgrade - 1))
    return None

def get_tower_projectile_damage():
    power = buy_menu_options[1]["purchased"]
    return 1 + power

class TowerProjectile:
    def __init__(self, start_x, start_y, target_x, target_y, damage):
        self.x = start_x
        self.y = start_y
        self.damage = damage
        dx = target_x - start_x
        dy = target_y - start_y
        dist = (dx**2 + dy**2)**0.5
        if dist == 0:
            self.vx, self.vy = 0, 0
        else:
            speed = 15  # pixels per frame
            self.vx = speed * dx / dist
            self.vy = speed * dy / dist
        self.radius = 5
    def move(self):
        self.x += self.vx
        self.y += self.vy
    def draw(self):
        pygame.draw.circle(screen, (0,0,0), (int(self.x), int(self.y)), self.radius)

def fire_tower_projectile():
    global tower_last_projectile_time, tower_projectiles, focused_enemy
    cooldown = get_tower_projectile_cooldown()
    if cooldown is None:
        return
    current_time = time.time()
    if current_time - tower_last_projectile_time >= cooldown:
        if enemies:
            # If there is no focused enemy or the focused enemy is no longer alive, select the one with the highest HP.
            if focused_enemy is None or focused_enemy not in enemies:
                focused_enemy = max(enemies, key=lambda e: e.hp)
            # Fire from every tower at the focused enemy.
            for tower in towers:
                tower_center_x = tower.x + tower.size / 2
                tower_center_y = tower.y + tower.size / 2
                damage = get_tower_projectile_damage()
                proj = TowerProjectile(tower_center_x, tower_center_y, focused_enemy.x, focused_enemy.y, damage)
                tower_projectiles.append(proj)
            tower_last_projectile_time = current_time
            tower_shoot_sound.play()

def update_tower_projectiles():
    global tower_projectiles, enemies
    for proj in tower_projectiles[:]:
        proj.move()
        proj.draw()
        if proj.x < 0 or proj.x > SCREEN_WIDTH or proj.y < 0 or proj.y > SCREEN_HEIGHT:
            tower_projectiles.remove(proj)
            continue
        for enemy in enemies[:]:
            size_map = {"small": 10, "medium": 15, "large": 20, "extra_large": 25, "boss": 75}
            enemy_radius = size_map[enemy.etype]
            dx = enemy.x - proj.x
            dy = enemy.y - proj.y
            if (dx*dx + dy*dy)**0.5 < enemy_radius + proj.radius:
                enemy.hp -= proj.damage
                if enemy.hp <= 0:
                    enemies.remove(enemy)
                    enemy_destroyed_sound.play()
                if proj in tower_projectiles:
                    tower_projectiles.remove(proj)
                break

# ------------------------------ #
#       Shield Function          #
# ------------------------------ #


def draw_shield():
    if shield_active and shield_hp > 0:
        print(f"DEBUG: Shield is being drawn with HP {shield_hp}")
        shield_y = TOWER_Y - 10
        pygame.draw.line(screen, (0, 0, 255), (0, shield_y), (SCREEN_WIDTH, shield_y), 10)

def check_shield_damage():
    global shield_hp, tower_hp, shield_active
    for enemy in enemies[:]:
        if enemy.y >= TOWER_Y:  # Enemy reaches tower
            if shield_active and shield_hp > 0:
                shield_hp -= enemy.damage  # Absorb damage with shield
                print(f"DEBUG: Shield absorbing damage. Remaining HP: {shield_hp}")
                if shield_hp <= 0:
                    shield_hp = 0
                    shield_active = False
                    speak("Shield broken")
                enemies.remove(enemy)
                hit_tower_sound.play()
            else:
                tower_hp = max(0, tower_hp - enemy.damage)
                print(f"DEBUG: Tower took damage. Remaining HP: {tower_hp}")
                enemies.remove(enemy)
                hit_tower_sound.play()


# ------------------------------ #
#       Healing Tower Function   #
# ------------------------------ #

# Healing upgrade: key 9 in buy_menu_options.
healing_intervals = {0: None, 1: 10, 2: 5, 3: 2}  # Level 1: heal every 10s, Level 2: every 5s, Level 3: every 2s
last_heal_time = time.time()  # initialize the timer

def heal_tower():
    global tower_hp, last_heal_time
    healing_level = buy_menu_options[9]["purchased"]
    if healing_level > 0:
        interval = healing_intervals[healing_level]
        if time.time() - last_heal_time >= interval:
            tower_hp = min(max_tower_hp, tower_hp + 10)
            last_heal_time = time.time()  # Update the global timer
    return last_heal_time

# ------------------------------ #
#       Tower Unit Functions     #
# ------------------------------ #

def get_unit_spawn_interval():
    base_interval = 10
    freq_upgrade = buy_menu_options[4]["purchased"]
    return max(1, base_interval - 2 * freq_upgrade)

def get_unit_spawn_count():
    n = buy_menu_options[3]["purchased"]
    if n > 0:
        return 2 ** (n - 1)
    return 0

# --- Tower Unit Class Update ---
class TowerUnit:
    def __init__(self, start_x, start_y, damage=1):
        self.x = start_x
        self.y = start_y
        self.damage = damage
        self.speed = 20 / 60  
        self.radius = 10
        self.target = None
        self.locked_target = None
        self.random_direction = None  # For random wandering

    def update_target(self, enemy_list):
        """Updates target using absolute distance from the unit's current position."""
        if not enemy_list:
            self.target = None
            return
        self.target = min(enemy_list, key=lambda enemy: math.hypot(enemy.x - self.x, enemy.y - self.y))

        # Define weights for each enemy type.
        weights = {
            "small": 1.5,      # small enemies are deprioritized
            "medium": 1.0,     # medium enemies use their actual distance
            "large": 1.2,      # large enemies are a bit less attractive
            "extra_large": 1.0,
            "boss": 0.8,       # boss is considered more urgent to target
        }

        # Define a helper function to calculate weighted distance.
        def weighted_distance(enemy):
            base_distance = math.hypot(enemy.x - self.x, enemy.y - self.y)
            weight = weights.get(enemy.etype, 1.0)
            return base_distance * weight

        # Choose the enemy with the smallest weighted distance.
        self.target = min(enemy_list, key=weighted_distance)

    def move(self):
        if self.target is None:
            # No target assigned: move in a random direction.
            if self.random_direction is None:
                angle = random.uniform(0, 2 * math.pi)
                self.random_direction = (math.cos(angle), math.sin(angle))
            self.x += self.speed * self.random_direction[0]
            self.y += self.speed * self.random_direction[1]
        else:
            # Clear any random movement once a target exists.
            self.random_direction = None
            dx = self.target.x - self.x
            dy = self.target.y - self.y
            dist = math.hypot(dx, dy)
            if dist > 0:
                self.x += self.speed * dx / dist
                self.y += self.speed * dy / dist

    def draw(self):
        pygame.draw.circle(screen, (0, 0, 255), (int(self.x), int(self.y)), self.radius)


def update_tower_units():
    global tower_units, enemies

    # If there are no enemies, clear targets so units will wander.
    if not enemies:
        for unit in tower_units:
            unit.target = None
        return

    # STEP 1: Initial unique assignment for units that have not been locked yet.
    # Create a copy of the enemy list to track which enemies have been assigned.
    available_enemies = enemies.copy()
    random.shuffle(available_enemies)  # randomize order so assignment isn’t predictable
    for unit in tower_units:
        if not hasattr(unit, "locked_target") or unit.locked_target is None:
            # Look for the closest enemy from the available pool.
            if available_enemies:
                candidate = min(available_enemies, key=lambda e: math.hypot(e.x - unit.x, e.y - unit.y))
                unit.locked_target = candidate
                unit.target = candidate
                available_enemies.remove(candidate)
            else:
                # No unique enemy available: set target to None (unit will wander until a new enemy appears)
                unit.locked_target = None
                unit.target = None

    # STEP 2: For any unit whose current target is missing or dead, choose the absolute closest enemy.
    for unit in tower_units:
        if unit.target is None or unit.target not in enemies or unit.target.hp <= 0:
            unit.locked_target = None  # Clear previous lock
            sorted_candidates = sorted(enemies, key=lambda e: math.hypot(e.x - unit.x, e.y - unit.y))
            unit.target = sorted_candidates[0] if sorted_candidates else None

    # STEP 3: Resolve conflicts if multiple units are targeting the same enemy.
    # For each enemy, if more than one unit is targeting it, only the unit closest to the enemy should keep it.
    enemy_to_units = {}
    for unit in tower_units:
        if unit.target is not None:
            enemy_to_units.setdefault(unit.target, []).append(unit)

    for enemy, units in enemy_to_units.items():
        if len(units) > 1:
            # Sort units by their distance to this enemy.
            units_sorted = sorted(units, key=lambda u: math.hypot(u.x - enemy.x, u.y - enemy.y))
            # The closest unit keeps this target.
            for u in units_sorted[1:]:
                # Try to assign an alternative candidate.
                sorted_candidates = sorted(enemies, key=lambda e: math.hypot(e.x - u.x, e.y - u.y))
                new_target = None
                for cand in sorted_candidates:
                    # Accept cand if either it’s not targeted by any unit or if the unit u is closer than any other unit already targeting cand.
                    conflict = False
                    for other in tower_units:
                        if other is not u and other.target == cand:
                            if math.hypot(other.x - cand.x, other.y - cand.y) < math.hypot(u.x - cand.x, u.y - cand.y):
                                conflict = True
                                break
                    if not conflict:
                        new_target = cand
                        break
                u.target = new_target  # May be None if no candidate found.

    # STEP 4: Finally, move each unit toward its assigned target and check for collision.
    for unit in tower_units[:]:
        unit.move()
        unit.draw()
        if unit.target:
            dx = unit.target.x - unit.x
            dy = unit.target.y - unit.y
            if math.hypot(dx, dy) < (unit.radius + unit.target.radius):
                unit.target.hp -= unit.damage
                if unit.target.hp <= 0 and unit.target in enemies:
                    enemies.remove(unit.target)
                    enemy_destroyed_sound.play()
                if unit in tower_units:
                    tower_units.remove(unit)

# ------------------------------ #
#   Enemy Spawn Parameters       #
# ------------------------------ #
spawn_intervals = {
    "small":       [8,4,2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    "medium":      [0,0,0,8,6,4,4,3,3,3,3,3,3,3,2,2,2,2,2,2],
    "large":       [0,0,0,0,60,45,30,25,20,15,15,15,15,15,15,15,12,10,10,9],
    "extra_large": [0,0,0,0,0,0,0,0,60,45,30,30,30,25,25,25,20,20,20,15],
    "boss":        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,60,45,30]
}
quantities = {
    "small":       [1,1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,3,3,3,4],
    "medium":      [0,0,0,1,1,1,1,1,1,1,1,1,1,2,2,2,3,3,3,4],
    "large":       [0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,2,2,3],
    "extra_large": [0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,2,2],
    "boss":        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1]
}
last_spawn_time = {etype: 0 for etype in spawn_intervals}

class Enemy:
    def __init__(self, etype, hp, speed, damage):
        self.etype = etype
        self.hp = hp
        self.speed = speed / 60  
        self.damage = damage
        self.x = random.randint(0, SCREEN_WIDTH - 20)
        self.y = 80
        size_map = {"small": 10, "medium": 15, "large": 20, "extra_large": 25, "boss": 75}
        self.radius = size_map[etype]
        if self.etype == "extra_large":
            self.last_shot_time = time.time()  # Initialize shooting timer for extra-large enemies

    def move(self):
        self.y += self.speed  # Move enemy downward

        # Check for collision with tower units
        for unit in tower_units[:]:
            dx = unit.x - self.x
            dy = unit.y - self.y
            distance = math.hypot(dx, dy)

            if distance < (self.radius + unit.radius):  # Collision detected
                self.hp -= 1  # Inflict 1 HP damage on the enemy
                if self.hp <= 0:
                    enemies.remove(self)
                    enemy_destroyed_sound.play()

                if unit in tower_units:  # Ensure unit is removed
                    tower_units.remove(unit)
                break  # Stop checking further

    def draw(self):
        """ Draw enemies with distinct colors and shapes """
        size_map = {"small": 10, "medium": 15, "large": 20, "extra_large": 25, "boss": 75}
        color_map = {
            "small": (255, 0, 0),          # Red
            "medium": (255, 165, 0),       # Orange
            "large": (255, 0, 0),          # Red (Triangular)
            "extra_large": (128, 0, 128),  # Purple
            "boss": (139, 0, 0)            # Dark Red
        }

        if self.etype == "large":  # Draw triangle
            points = [
                (int(self.x), int(self.y - size_map[self.etype])),
                (int(self.x - size_map[self.etype]), int(self.y + size_map[self.etype])),
                (int(self.x + size_map[self.etype]), int(self.y + size_map[self.etype])),
            ]
            pygame.draw.polygon(screen, color_map[self.etype], points)
        
        elif self.etype == "boss":  # Draw square
            pygame.draw.rect(screen, color_map[self.etype], 
                            (int(self.x - size_map[self.etype] // 2), int(self.y - size_map[self.etype] // 2),
                            size_map[self.etype], size_map[self.etype]))

        else:  # Draw circle for small, medium, and extra_large
            pygame.draw.circle(screen, color_map[self.etype], (int(self.x), int(self.y)), size_map[self.etype])

    def shoot(self):
            """ Extra Large Enemies shoot projectiles at the tower or tower units """
            if self.etype != "extra_large":
                return  # Only extra_large enemies shoot

            global enemy_projectiles  # Ensure we use the correct list

            current_time = time.time()
            if current_time - self.last_shot_time >= 2.0:  # Fire every 2 seconds
                self.last_shot_time = current_time
                if tower_units:
                    target = min(tower_units, key=lambda unit: math.hypot(unit.x - self.x, unit.y - self.y))
                else:
                    target = Tower(TOWER_X + TOWER_SIZE // 2, TOWER_Y)

                enemy_projectiles.append(EnemyProjectile(self.x, self.y, target.x, target.y, damage=2))

def spawn_enemies():
    global last_spawn_time, enemies
    current_time = time.time()
    for etype in spawn_intervals:
        interval = spawn_intervals[etype][wave_number - 1]
        qty = quantities[etype][wave_number - 1]
        if interval > 0 and (current_time - last_spawn_time[etype] >= interval):
            for _ in range(qty):
                if etype == "small":
                    enemies.append(Enemy("small", 1, 10, 1))
                elif etype == "medium":
                    enemies.append(Enemy("medium", 3, 15, 3))
                elif etype == "large":
                    enemies.append(Enemy("large", 5, 20, 5))
                elif etype == "extra_large":
                    enemies.append(Enemy("extra_large", 10, 4, 10))
                elif etype == "boss":
                    enemies.append(Enemy("boss", 100, 4, 100))
            last_spawn_time[etype] = current_time

# ------------------------------ #
#       Enemy Projectiles        #
# ------------------------------ #

class EnemyProjectile:
    def __init__(self, start_x, start_y, target_x, target_y, damage=2):
        self.x = start_x
        self.y = start_y
        self.damage = damage
        self.radius = 6
        speed = 8  # Speed of projectile

        # Calculate movement direction
        dx = target_x - start_x
        dy = target_y - start_y
        dist = math.hypot(dx, dy)

        if dist == 0:
            self.vx, self.vy = 0, 0
        else:
            self.vx = speed * dx / dist
            self.vy = speed * dy / dist

    def move(self):
        """ Move the projectile """
        self.x += self.vx
        self.y += self.vy

    def draw(self):
        """ Draw the projectile """
        pygame.draw.circle(screen, (200, 50, 50), (int(self.x), int(self.y)), self.radius)
    
def update_enemy_projectiles():
    global enemy_projectiles, tower_hp, shield_hp, shield_active
    for proj in enemy_projectiles[:]:
        proj.move()
        proj.draw()

        # Remove the projectile if it goes off-screen.
        if proj.x < 0 or proj.x > SCREEN_WIDTH or proj.y < 0 or proj.y > SCREEN_HEIGHT:
            enemy_projectiles.remove(proj)
            continue

        # When the projectile reaches the tower's damage zone:
        if proj.y >= TOWER_Y:
            if shield_active and shield_hp > 0:
                # Projectile hits the shield instead of the tower.
                shield_hp = max(0, shield_hp - proj.damage)
                if shield_hp == 0:
                    shield_active = False
                    speak("Shield broken")
                enemy_projectiles.remove(proj)
            else:
                # No shield active, so damage the tower.
                tower_hp = max(0, tower_hp - proj.damage)
                enemy_projectiles.remove(proj)

# ------------------------------ #
#       Pause Menu Function      #
# ------------------------------ #
def pause_menu():
    global restart_requested
    pause_active = True
    options = ["Continue", "Main Menu"]
    # Start with no option highlighted.
    selected = None  
    menu_font = pygame.font.Font(None, 60)
    title_font = pygame.font.Font(None, 80)
    # Do not announce any option until a selection is made.
    pause_start = time.time()
    
    while pause_active:
        screen.fill((0, 0, 0))
        title = title_font.render("Paused", True, (255, 255, 255))
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 150))
        
        # Render each option. If 'selected' is None, no option is highlighted.
        for i, option in enumerate(options):
            if selected is not None and i == selected:
                color = (0, 255, 0)  # Highlight color
            else:
                color = (200, 200, 200)
            text = menu_font.render(option, True, color)
            screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, 300 + i * 70))
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            # Wait for the spacebar to be released before selecting anything.
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE and selected is None:
                    selected = 0
                    speak(options[selected])
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if selected is not None:
                        # Cycle through the options when SPACE is pressed after the first release.
                        selected = (selected + 1) % len(options)
                        speak(options[selected])
                elif event.key == pygame.K_RETURN:
                    if selected is not None:
                        speak(options[selected])
                        if options[selected] == "Continue":
                            pause_active = False
                        elif options[selected] == "Main Menu":
                            restart_requested = True
                            return  # Exit pause_menu immediately.
        
        pygame.display.flip()
        clock.tick(30)
    return time.time() - pause_start

# ------------------------------ #
#       Game Over Function       #
# ------------------------------ #

def game_over():
    over_font = pygame.font.Font(None, 100)
    screen.fill((0,0,0))
    text = over_font.render("You Lose", True, (255,0,0))
    screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, SCREEN_HEIGHT//2 - text.get_height()//2))
    pygame.display.flip()
    time.sleep(5)
    reset_game_state()
    main_menu()

def game_won():
    win_font = pygame.font.Font(None, 100)
    screen.fill((0, 0, 0))
    text = win_font.render("You Won!", True, (0, 255, 0))
    screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, SCREEN_HEIGHT//2 - text.get_height()//2))
    pygame.display.flip()
    time.sleep(5)
    reset_game_state()
    main_menu()

# ------------------------------ #
#         UI Functions           #
# ------------------------------ #
def draw_timer_bar():
    bar_width, bar_height = SCREEN_WIDTH - 100, 20
    bar_x, bar_y = 50, 50
    elapsed = time.time() - game_time_start
    remaining_ratio = max(0, 1 - elapsed / ROUND_DURATION)
    pygame.draw.rect(screen, (50,50,50), (bar_x, bar_y, bar_width, bar_height))
    pygame.draw.rect(screen, (0,0,255), (bar_x, bar_y, int(bar_width * remaining_ratio), bar_height))

# --- Health Bar Update ---
def draw_health_bar():
    bar_width, bar_height = SCREEN_WIDTH - 100, 40
    bar_x, bar_y = 50, 20
    # Use max_tower_hp instead of TOWER_MAX_HP.
    if tower_hp > max_tower_hp * 0.66:
        color = (0,255,0)
    elif tower_hp > max_tower_hp * 0.33:
        color = (255,255,0)
    else:
        color = (255,0,0)
    pygame.draw.rect(screen, (50,50,50), (bar_x, bar_y, bar_width, bar_height))
    pygame.draw.rect(screen, color, (bar_x, bar_y, int(bar_width * (tower_hp / max_tower_hp)), bar_height))
    health_font = pygame.font.SysFont(None, 36, bold=True)
    hp_text = health_font.render(f"{tower_hp}", True, (0,0,0))
    screen.blit(hp_text, (bar_x + (bar_width - hp_text.get_width()) // 2,
                          bar_y + (bar_height - hp_text.get_height()) // 2))

def draw_damage_zone():
    zone_rect = pygame.Rect(0, TOWER_Y, SCREEN_WIDTH, SCREEN_HEIGHT - TOWER_Y)
    pygame.draw.rect(screen, (80,80,80), zone_rect)

# ------------------------------ #
#       Buy Menu (Grid Layout)   #
# ------------------------------ #
initial_buy_menu_options = [
        {"name": "Add Tower Projectile", "cost": 200, "max": 6, "purchased": 0},
        {"name": "Increase Projectile Power", "cost": 300, "max": 3, "purchased": 0},
        {"name": "Recover Tower Health", "cost": 50, "max": 2, "purchased": 0},
        {"name": "Add Units", "cost": 200, "max": 2, "purchased": 0},
        {"name": "Increase Unit Frequency", "cost": 300, "max": 2, "purchased": 0},
        {"name": "Extra Tower", "cost": 1500, "max": 2, "purchased": 0},
        {"name": "Buy Bomb", "cost": 2000, "max": 1, "purchased": 0},
        {"name": "Upgrade Bomb Frequency", "cost": 3000, "max": 1, "purchased": 0},
        {"name": "Laser Beam", "cost": 1200, "max": 1, "purchased": 0},
        {"name": "Add Healing", "cost": 750, "max": 3, "purchased": 0},  
        {"name": "Add Shield", "cost": 1000, "max": 1, "purchased": 0},
        {"name": "Upgrade Shield", "cost": 1500, "max": 3, "purchased": 0}
    ]

buy_menu_options = deepcopy(initial_buy_menu_options)
bottom_buttons = ["Start Level", "Main Menu"]

def buy_menu():
    global selected_buy_index, points, wave_number, max_tower_hp, tower_hp, shield_hp, shield_active, max_shield_hp

    def get_selectable_indices():
        selectable = []
        for i, item in enumerate(buy_menu_options):
            available = (item["purchased"] < item["max"] and item["cost"] <= points)
            # For "Increase Projectile Power" (index 1) require at least one Tower Projectile purchased.
            if i == 1 and buy_menu_options[0]["purchased"] < 1:
                available = False
            # "Recover Tower Health" is only available if tower_hp is less than max_tower_hp.
            if i == 2 and tower_hp >= max_tower_hp:
                available = False
            # "Increase Unit Frequency" (index 4) only available if "Add Units" (index 3) has been purchased.
            if i == 4 and buy_menu_options[3]["purchased"] < 1:
                available = False
            # Disable "Upgrade Shield" (index 11) until "Add Shield" (index 10) is purchased.
            if i == 11 and buy_menu_options[10]["purchased"] < 1:
                available = False
            if available:
                selectable.append(i)
        for j in range(len(bottom_buttons)):
            selectable.append(len(buy_menu_options) + j)
        return selectable

    # Dynamic Layout Calculation
    total_items = len(buy_menu_options)
    columns = 3  # Keep 3 columns
    rows = math.ceil(total_items / columns)  # Determine rows automatically

    top_margin = SCREEN_HEIGHT * 0.1         # 10% of screen height
    bottom_margin = SCREEN_HEIGHT * 0.15       # 15% reserved for bottom buttons
    side_margin = SCREEN_WIDTH * 0.05          # 5% of screen width
    gap_x = SCREEN_WIDTH * 0.02                # 2% horizontal spacing
    gap_y = SCREEN_HEIGHT * 0.02               # 2% vertical spacing

    button_area_height = SCREEN_HEIGHT - (top_margin + bottom_margin)
    button_width = (SCREEN_WIDTH - 2 * side_margin - (columns - 1) * gap_x) / columns
    button_height = (button_area_height - (rows - 1) * gap_y) / rows

    bottom_box_height = SCREEN_HEIGHT * 0.12
    bottom_button_width = (SCREEN_WIDTH - 2 * side_margin - gap_x) / 2

    # Dynamically adjust font size based on button size
    max_text_size = min(button_height // 3, 30)
    menu_font = pygame.font.Font(None, max_text_size)
    title_font = pygame.font.Font(None, int(SCREEN_HEIGHT * 0.07))

    in_buy = True
    selectable_indices = get_selectable_indices()
    if not selectable_indices:
        selectable_indices = list(range(len(buy_menu_options), len(buy_menu_options) + len(bottom_buttons)))
    selected_buy_index = selectable_indices[0]

    def announce():
        if selected_buy_index < len(buy_menu_options):
            speak(buy_menu_options[selected_buy_index]["name"])
        else:
            speak(bottom_buttons[selected_buy_index - len(buy_menu_options)])

    announce()

    while in_buy:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.VIDEORESIZE:
                handle_resize(event)
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                close_rect, min_rect = draw_window_controls()
                if close_rect.collidepoint(mouse_pos):
                    pygame.quit()
                    exit()
                if min_rect.collidepoint(mouse_pos):
                    pygame.display.iconify()

        # Update font sizes on resize
        menu_font = pygame.font.Font(None, min(button_height // 3, 30))
        title_font = pygame.font.Font(None, int(SCREEN_HEIGHT * 0.07))

        screen.fill((0, 0, 0))

        # Draw Title and Points
        title = title_font.render(f"Buy Menu - Level {wave_number}", True, (255, 255, 255))
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT * 0.02))
        points_text = menu_font.render(f"Points: {points}", True, (255, 255, 0))
        screen.blit(points_text, (SCREEN_WIDTH // 2 - points_text.get_width() // 2, SCREEN_HEIGHT * 0.08))

        # Draw Buy Menu Buttons
        start_x = side_margin
        start_y = top_margin
        for i, item in enumerate(buy_menu_options):
            col = i % columns
            row = i // columns
            x = start_x + col * (button_width + gap_x)
            y = start_y + row * (button_height + gap_y)
            rect = pygame.Rect(x, y, button_width, button_height)
            pygame.draw.rect(screen, (255, 255, 255), rect, 5)

            available = (item["purchased"] < item["max"] and item["cost"] <= points)
            if i == 1 and buy_menu_options[0]["purchased"] < 1:
                available = False
            if i == 2 and tower_hp >= max_tower_hp:
                available = False
            fill_color = (0, 255, 0) if (available and i == selected_buy_index) else (200, 200, 200)
            if not available:
                fill_color = (100, 100, 100)
            pygame.draw.rect(screen, fill_color, rect)

            text = menu_font.render(f"{item['name']} ({item['cost']} pts)", True, (0, 0, 0))
            text_rect = text.get_rect(center=rect.center)
            screen.blit(text, text_rect)

        # Draw Bottom Buttons
        bottom_y = SCREEN_HEIGHT - bottom_margin
        for j, btn in enumerate(bottom_buttons):
            x = side_margin + j * (bottom_button_width + gap_x)
            rect = pygame.Rect(x, bottom_y, bottom_button_width, bottom_box_height)
            pygame.draw.rect(screen, (255, 255, 255), rect, 5)
            fill_color = (0, 255, 0) if (len(buy_menu_options) + j) == selected_buy_index else (200, 200, 200)
            pygame.draw.rect(screen, fill_color, rect)
            text = menu_font.render(btn, True, (0, 0, 0))
            text_rect = text.get_rect(center=rect.center)
            screen.blit(text, text_rect)

        selectable_indices = get_selectable_indices()
        if selected_buy_index not in selectable_indices:
            selected_buy_index = selectable_indices[0]
            announce()

        for event in events:
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    idx = selectable_indices.index(selected_buy_index)
                    idx = (idx + 1) % len(selectable_indices)
                    selected_buy_index = selectable_indices[idx]
                    announce()
                elif event.key == pygame.K_RETURN:
                    if selected_buy_index >= len(buy_menu_options):
                        btn = bottom_buttons[selected_buy_index - len(buy_menu_options)]
                        speak(btn)
                        if btn == "Start Level":
                            in_buy = False
                        elif btn == "Main Menu":
                            reset_game_state()
                            main_menu()
                    else:
                        item = buy_menu_options[selected_buy_index]
                        # If the selected item is "Recover Tower Health" (assumed to be index 2)
                        if selected_buy_index == 2:
                            if tower_hp < max_tower_hp:
                                heal_amount = min(50, max_tower_hp - tower_hp)
                                tower_hp += heal_amount
                                speak(f"Recovered {heal_amount} HP. Current HP: {tower_hp}")
                                item["purchased"] += 1
                                points -= item["cost"]
                            # Gray out if tower is fully healed
                            if tower_hp >= max_tower_hp:
                                item["purchased"] = item["max"]
                        else:
                            if item["purchased"] < item["max"] and points >= item["cost"]:
                                points -= item["cost"]
                                item["purchased"] += 1
                                speak(f"Purchased {item['name']}")
                            if item["name"] == "Add Shield":
                                shield_active = True
                                shield_hp = 50
                                max_shield_hp = 50
                                print(f"DEBUG: Shield purchased! shield_active={shield_active}, shield_hp={shield_hp}")
                                speak("Shield activated")
                            elif item["name"] == "Upgrade Shield":
                                if shield_active:
                                    max_shield_hp += 25  # Increase max shield HP
                                    shield_hp = max_shield_hp  # Fully restore shield on upgrade
                                    print(f"DEBUG: Shield upgraded! New max HP: {max_shield_hp}, current HP: {shield_hp}")
                                    speak(f"Shield upgraded to {max_shield_hp} HP")
                                else:
                                    speak("You need to buy the shield first!")

        pygame.display.flip()
        clock.tick(30)

# ------------------------------ #
#       Game Level Loop          #
# ------------------------------ #
def game_level():
    global game_time_start, tower_hp, enemies, points, tower_projectiles, tower_units
    global tower_last_projectile_time, return_hold_start, towers, last_laser_time, tower_last_unit_spawn_time
    global laser_active, laser_start_time, laser_hit_enemies
    global bomb_last_time, bomb_active, bomb_start_time, bomb_hit_enemies
    global last_heal_time, shield_hp, shield_active, max_shield_hp

    # Announce current level and reset timers
    speak(f"Level {wave_number}")
    game_time_start = time.time()
    last_heal_time = time.time()  # Reset healing timer at level start
    for etype in last_spawn_time:
        last_spawn_time[etype] = time.time()
    enemies = []
    tower_projectiles = []
    tower_units = []
    tower_last_unit_spawn_time = time.time()
    return_hold_start = None

    # *** RESET SHIELD AT THE START OF EACH LEVEL ***
    # If the player purchased "Add Shield" (index 10), then the shield is enabled.
    # Its maximum HP is 50 plus 25 for each "Upgrade Shield" purchase (index 11).
    if buy_menu_options[10]["purchased"] >= 1:
        shield_active = True
        max_shield_hp = 50 + 25 * buy_menu_options[11]["purchased"]
        shield_hp = max_shield_hp
        print(f"DEBUG: Shield reset for new level: shield_active={shield_active}, shield_hp={shield_hp}")
    else:
        shield_active = False
        shield_hp = 0
        max_shield_hp = 0

    # Set up towers based on the Extra Tower upgrade.
    towers = [Tower(TOWER_X, TOWER_Y)]
    margin = 20
    if buy_menu_options[5]["purchased"] >= 1:
        towers.append(Tower(TOWER_X + TOWER_SIZE + margin, TOWER_Y))
    if buy_menu_options[5]["purchased"] >= 2:
        towers.insert(0, Tower(TOWER_X - TOWER_SIZE - margin, TOWER_Y))
    
    last_laser_time = time.time()
    laser_active = False
    laser_hit_enemies = set()
    
    # Reset bomb timer.
    bomb_last_time = time.time()
    bomb_active = False
    bomb_hit_enemies = set()
    
    level_running = True

    while level_running:
        # Process events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.VIDEORESIZE:
                handle_resize(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if return_hold_start is None:
                        return_hold_start = time.time()
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_RETURN:
                    return_hold_start = None
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                close_rect, min_rect = draw_window_controls()
                if close_rect.collidepoint(mouse_pos):
                    pygame.quit()
                    exit()
                if min_rect.collidepoint(mouse_pos):
                    pygame.display.iconify()

        if return_hold_start is not None and (time.time() - return_hold_start >= 3):
            pause_duration = pause_menu()
            if restart_requested:
                return  # Exit game_level if a restart was requested
            game_time_start += pause_duration
            return_hold_start = None
            last_heal_time = heal_tower()

        # Call healing every frame
        last_heal_time = heal_tower()

        # Bomb Activation
        if buy_menu_options[6]["purchased"] >= 1:
            interval = 120
            if buy_menu_options[7]["purchased"] >= 1:
                interval = 60
            if time.time() - bomb_last_time >= interval:
                bomb_active = True
                bomb_start_time = time.time()
                bomb_hit_enemies = set()
                bomb_last_time = time.time()
                bomb_sound.play()

        # Laser Activation
        if buy_menu_options[8]["purchased"] >= 1:
            if not laser_active and (time.time() - last_laser_time >= 30):
                laser_active = True
                laser_start_time = time.time()
                laser_hit_enemies = set()
                laserbeam_sound.play()

        # Clear the screen.
        screen.fill((255, 255, 255))
        
        # Draw UI elements.
        draw_health_bar()
        draw_timer_bar()
        draw_damage_zone()
        if shield_active and shield_hp > 0:
            draw_shield()

        # Draw towers.
        for tower in towers:
            pygame.draw.rect(screen, (0, 0, 255), (tower.x, tower.y, tower.size, tower.size))
        
        # Spawn and draw enemies.
        spawn_enemies()
        for enemy in enemies:
            enemy.move()
            enemy.shoot()  # Extra-large enemies fire projectiles
            enemy.draw()
        check_shield_damage()

        # Update and draw projectiles.
        fire_tower_projectile()
        update_tower_projectiles()
        update_enemy_projectiles()
        
        # Spawn and update tower units.
        if time.time() - tower_last_unit_spawn_time >= get_unit_spawn_interval():
            count = get_unit_spawn_count()
            if count > 0:
                for tower in towers:
                    tower_center_x = tower.x + tower.size / 2
                    tower_center_y = tower.y + tower.size / 2
                    for _ in range(count):
                        tower_units.append(TowerUnit(tower_center_x, tower_center_y))
            tower_last_unit_spawn_time = time.time()
        update_tower_units()

        # Draw laser beam if active.
        if laser_active:
            draw_laser_beams()
            if time.time() - laser_start_time >= 3:
                laser_active = False
                last_laser_time = time.time()

        # Draw bomb effect if active.
        if bomb_active:
            drop_bomb_effect()
        
        draw_window_controls()
        pygame.display.flip()
        clock.tick(60)

        if tower_hp <= 0:
            game_over()
            return
        if time.time() - game_time_start >= ROUND_DURATION:
            level_running = False

    base_points = 100
    multiplier = 100 * wave_number
    bonus = 100 if tower_hp == max_tower_hp else 0
    level_points = base_points + multiplier + bonus
    points += level_points
    speak(f"Level complete. You earned {level_points} points.")

# ------------------------------ #
#       Reset Game State         #
# ------------------------------ #

def reset_game_state():
    global wave_number, points, tower_hp, max_tower_hp, enemies, tower_projectiles, tower_units, last_spawn_time, buy_menu_options, towers, tower_last_projectile_time, shield_hp, max_shield_hp, shield_active
    wave_number = 1
    points = 200
    tower_hp = TOWER_MAX_HP
    max_tower_hp = TOWER_MAX_HP
    enemies = []
    tower_projectiles = []
    tower_units = []
    last_spawn_time = {etype: time.time() for etype in spawn_intervals}
    tower_last_projectile_time = time.time()
    towers = [Tower(TOWER_X, TOWER_Y)]
    shield_active = False
    shield_hp = 0
    max_shield_hp = 0
    # Reset the buy menu options as needed...
    buy_menu_options = deepcopy(initial_buy_menu_options)

    initial = [
        {"name": "Add Tower Projectile", "cost": 150, "max": 6, "purchased": 0},
        {"name": "Increase Projectile Power", "cost": 250, "max": 3, "purchased": 0},
        {"name": "Recover Tower Health", "cost": 50, "max": 2, "purchased": 0},
        {"name": "Add Units", "cost": 200, "max": 3, "purchased": 0},
        {"name": "Increase Unit Frequency", "cost": 300, "max": 2, "purchased": 0},
        {"name": "Extra Tower", "cost": 1500, "max": 2, "purchased": 0},
        {"name": "Buy Bomb", "cost": 2000, "max": 1, "purchased": 0},
        {"name": "Upgrade Bomb Frequency", "cost": 5000, "max": 1, "purchased": 0},
        {"name": "Laser Beam", "cost": 1200, "max": 1, "purchased": 0},
        {"name": "Add Healing", "cost": 750, "max": 3, "purchased": 0},  
        {"name": "Add Shield", "cost": 1000, "max": 1, "purchased": 0},
        {"name": "Upgrade Shield", "cost": 2000, "max": 3, "purchased": 0}
    ]

    buy_menu_options = deepcopy(initial)

# ------------------------------ #
#          Force Focus           #
# ------------------------------ #


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

# ------------------------------ #
#           Main Menu            #
# ------------------------------ #

def close_game():
    # Try to restore the main app window first
    try:
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
    pygame.quit()
    exit()

def main_menu():
    # A full reset of game state – wave_number resets to 1.
    reset_game_state()
    menu_options = ["Play Game", "Exit Game"]
    selected = 0
    menu_font = pygame.font.Font(None, 60)
    title_font = pygame.font.Font(None, 120)
    speak(menu_options[selected])
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                close_game()  # Use the new close_game() function
            if event.type == pygame.VIDEORESIZE:
                handle_resize(event)
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    selected = (selected + 1) % len(menu_options)
                    speak(menu_options[selected])
                elif event.key == pygame.K_RETURN:
                    speak(menu_options[selected])
                    if menu_options[selected] == "Play Game":
                        return  # Exit main_menu() and start level 1
                    elif menu_options[selected] == "Exit Game":
                        close_game()  # Call close_game() when exiting
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                close_rect, min_rect = draw_window_controls()
                if close_rect.collidepoint(mouse_pos):
                    close_game()  # Ensure comm-v9.py launches on window close
                if min_rect.collidepoint(mouse_pos):
                    pygame.display.iconify()

        screen.fill((0, 0, 0))
        title = title_font.render("Ben's Tower Defense", True, (255, 255, 255))
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))
        for i, option in enumerate(menu_options):
            color = (0, 255, 0) if i == selected else (200, 200, 200)
            text = menu_font.render(option, True, color)
            screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 300 + i * 80))
        draw_window_controls()
        pygame.display.flip()
        clock.tick(30)

def main():
    global restart_requested, wave_number
    while True:
        # Always show the main menu (which resets game state, including wave_number to 1)
        main_menu()  # main_menu() should call reset_game_state() internally
        wave_number = 1  # Ensure we start at level 1

        # Run levels until the win condition (e.g., level > 20)
        while wave_number <= 20:
            buy_menu()
            game_level()
            if restart_requested:
                # If the player restarts during a level, break to return to the main menu.
                restart_requested = False
                break
            wave_number += 1

        # If we've passed level 20, the player has won.
        if wave_number > 20:
            game_won()

if __name__ == "__main__":
    main()