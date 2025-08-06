import math
import sys

import pygame

pygame.init()

# ---------------- Constants ----------------
GAME_WIDTH, GAME_HEIGHT = 1200, 800  # Fixed dimensions for the golf game area
PALETTE_WIDTH = 220  # Extra width for the palette on the left
SCREEN_WIDTH = GAME_WIDTH + PALETTE_WIDTH
SCREEN_HEIGHT = GAME_HEIGHT

BORDER_THICKNESS = 50
BASE_BALL_RADIUS = 45
BASE_HOLE_RADIUS = 45

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (200, 200, 200)
DARK_GREY = (50, 50, 50)
GREEN = (0, 128, 0)
BLUE = (0, 0, 255)
RED = (255, 0, 0)
SAND = (194, 178, 128)

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Golf Level Editor")
clock = pygame.time.Clock()

# ---------------- Hazard Definitions ----------------
# Hazard pieces for water, wall, and sand.
hazard_defs = {
    "water_small": {"type": "water", "size": (50, 30), "color": BLUE},
    "water_medium": {"type": "water", "size": (100, 60), "color": BLUE},
    "water_large": {"type": "water", "size": (150, 90), "color": BLUE},
    "wall_small": {"type": "wall", "size": (50, 100), "color": DARK_GREY},
    "wall_medium": {"type": "wall", "size": (80, 160), "color": DARK_GREY},
    "wall_large": {"type": "wall", "size": (120, 240), "color": DARK_GREY},
    "sand_small": {"type": "sand", "size": (50, 30), "color": SAND},
    "sand_medium": {"type": "sand", "size": (100, 60), "color": SAND},
    "sand_large": {"type": "sand", "size": (150, 90), "color": SAND},
}
# ---------------- Palette Setup ----------------
palette_items = []
padding = 10
y_offset = padding
font = pygame.font.SysFont(None, 24)

# Add hazard pieces.
for key, defs in hazard_defs.items():
    text = font.render(key, True, BLACK)
    text_rect = text.get_rect(topleft=(padding, y_offset))
    preview_rect = pygame.Rect(PALETTE_WIDTH - 70, y_offset, 50, 50)
    palette_items.append(
        {
            "name": key,
            "def": defs,
            "text": text,
            "text_rect": text_rect,
            "preview_rect": preview_rect,
        }
    )
    y_offset += max(text_rect.height, preview_rect.height) + padding

# Next, add items for "ball" and "hole"
for key, _label, size, color in [
    ("ball", "ball", (40, 40), WHITE),
    ("hole", "hole", (40, 40), BLACK),
]:
    text = font.render(key, True, BLACK)
    text_rect = text.get_rect(topleft=(padding, y_offset))
    preview_rect = pygame.Rect(PALETTE_WIDTH - 70, y_offset, 50, 50)
    palette_items.append(
        {
            "name": key,
            "def": {"type": key, "size": size, "color": color},
            "text": text,
            "text_rect": text_rect,
            "preview_rect": preview_rect,
        }
    )
    y_offset += max(text_rect.height, preview_rect.height) + padding


# ---------------- Game Layout Functions ----------------
def get_playable_area():
    """
    Returns the area (rectangle) inside the outer walls of the game.
    The game area is drawn starting at x = PALETTE_WIDTH.
    """
    play_x0 = PALETTE_WIDTH + BORDER_THICKNESS
    play_y0 = BORDER_THICKNESS
    play_width = GAME_WIDTH - 2 * BORDER_THICKNESS
    play_height = GAME_HEIGHT - 2 * BORDER_THICKNESS
    return play_x0, play_y0, play_width, play_height


# Global ball and hole positions.
def get_default_positions():
    play_x0, play_y0, play_width, play_height = get_playable_area()
    ball_vert_pct = 0.2
    hole_vert_pct = 0.8
    ball_x = PALETTE_WIDTH + BORDER_THICKNESS + BASE_BALL_RADIUS + 10
    ball_y = (
        play_y0
        + BASE_BALL_RADIUS
        + int(ball_vert_pct * (play_height - 2 * BASE_BALL_RADIUS))
    )
    hole_x = PALETTE_WIDTH + BORDER_THICKNESS + play_width - BASE_HOLE_RADIUS - 10
    hole_y = (
        play_y0
        + BASE_HOLE_RADIUS
        + int(hole_vert_pct * (play_height - 2 * BASE_HOLE_RADIUS))
    )
    return [ball_x, ball_y], [hole_x, hole_y]


ball_pos, hole_pos = get_default_positions()

# ---------------- Placed Hazards ----------------
# Each placed hazard is stored as a dict with keys: 'name', 'rect', 'type', 'color'
placed_hazards = []

# ---------------- Drag/Selection Variables ----------------
selected_object = None  # Can be a hazard (dict) or the string "ball" or "hole"
offset_x, offset_y = 0, 0  # For dragging


# ---------------- Drawing Functions ----------------
def draw_palette():
    pygame.draw.rect(screen, GREY, (0, 0, PALETTE_WIDTH, SCREEN_HEIGHT))
    for item in palette_items:
        pygame.draw.rect(screen, BLACK, item["preview_rect"], 2)
        screen.blit(item["text"], item["text_rect"])


def draw_game_area():
    # Draw game area background
    game_area_rect = pygame.Rect(PALETTE_WIDTH, 0, GAME_WIDTH, GAME_HEIGHT)
    pygame.draw.rect(screen, GREEN, game_area_rect)
    # Draw outer walls
    pygame.draw.rect(
        screen, GREY, (PALETTE_WIDTH, 0, GAME_WIDTH, BORDER_THICKNESS)
    )  # Top wall
    pygame.draw.rect(
        screen,
        GREY,
        (PALETTE_WIDTH, GAME_HEIGHT - BORDER_THICKNESS, GAME_WIDTH, BORDER_THICKNESS),
    )  # Bottom wall
    pygame.draw.rect(
        screen, GREY, (PALETTE_WIDTH, 0, BORDER_THICKNESS, GAME_HEIGHT)
    )  # Left wall
    pygame.draw.rect(
        screen,
        GREY,
        (
            PALETTE_WIDTH + GAME_WIDTH - BORDER_THICKNESS,
            0,
            BORDER_THICKNESS,
            GAME_HEIGHT,
        ),
    )  # Right wall
    # Draw ball and hole at their current positions
    pygame.draw.circle(
        screen, WHITE, (int(ball_pos[0]), int(ball_pos[1])), BASE_BALL_RADIUS
    )
    pygame.draw.circle(
        screen, BLACK, (int(hole_pos[0]), int(hole_pos[1])), BASE_HOLE_RADIUS
    )


def draw_hazards():
    for hazard in placed_hazards:
        pygame.draw.rect(screen, hazard["color"], hazard["rect"])
        if hazard is selected_object:
            pygame.draw.rect(screen, RED, hazard["rect"], 3)


def draw_divider():
    pygame.draw.line(
        screen, BLACK, (PALETTE_WIDTH, 0), (PALETTE_WIDTH, SCREEN_HEIGHT), 2
    )


# ---------------- Output Function ----------------
def print_layout():
    # Define the target game dimensions (should match the game)
    target_game_width = 1200
    target_game_height = 800

    # Calculate scaling factors (if your editor's GAME_WIDTH/HEIGHT differ)
    scale_x = target_game_width / GAME_WIDTH
    scale_y = target_game_height / GAME_HEIGHT

    walls = []
    waters = []
    sands = []
    for hazard in placed_hazards:
        r = hazard["rect"]
        # Remove the PALETTE_WIDTH offset and scale the coordinates.
        export_x = int((r.x - PALETTE_WIDTH) * scale_x)
        export_y = int(r.y * scale_y)
        export_w = int(r.width * scale_x)
        export_h = int(r.height * scale_y)
        tup = f"({export_x}, {export_y}, {export_w}, {export_h})"
        if hazard["type"] == "wall":
            walls.append(tup)
        elif hazard["type"] == "water":
            waters.append(tup)
        elif hazard["type"] == "sand":
            sands.append(tup)

    # Adjust ball and hole positions similarly:
    ball_x_export = int((ball_pos[0] - PALETTE_WIDTH) * scale_x)
    ball_y_export = int(ball_pos[1] * scale_y)
    hole_x_export = int((hole_pos[0] - PALETTE_WIDTH) * scale_x)
    hole_y_export = int(hole_pos[1] * scale_y)

    # Print out the layout in a format that can be pasted directly into the game.
    print("\n# Copy and paste this layout code into your game for a level:")
    print("current_walls = [")
    for w in walls:
        print("    " + w + ",")
    print("]")
    print("current_waters = [")
    for w in waters:
        print("    " + w + ",")
    print("]")
    print("current_sands = [")
    for w in sands:
        print("    " + w + ",")
    print("]")
    print(f"ball_x, ball_y = ({ball_x_export}, {ball_y_export})")
    print(f"hole_x, hole_y = ({hole_x_export}, {hole_y_export})")


# ---------------- Main Editor Loop ----------------
selected_hazard_def = None  # Currently selected palette item definition.

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            sys.exit()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            # Left click (button 1)
            if event.button == 1:
                # If click is in the palette area:
                if mx < PALETTE_WIDTH:
                    for item in palette_items:
                        if item["text_rect"].collidepoint(mx, my) or item[
                            "preview_rect"
                        ].collidepoint(mx, my):
                            selected_hazard_def = item["def"]
                            print(f"Selected {item['name']}")
                            break
                else:
                    # In game area: check if clicking on ball or hole first.
                    dx_ball = mx - ball_pos[0]
                    dy_ball = my - ball_pos[1]
                    dx_hole = mx - hole_pos[0]
                    dy_hole = my - hole_pos[1]
                    if math.hypot(dx_ball, dy_ball) <= BASE_BALL_RADIUS:
                        selected_object = "ball"
                        offset_x = dx_ball
                        offset_y = dy_ball
                    elif math.hypot(dx_hole, dy_hole) <= BASE_HOLE_RADIUS:
                        selected_object = "hole"
                        offset_x = dx_hole
                        offset_y = dy_hole
                    else:
                        # Check if click is on any hazard.
                        hit = False
                        for hazard in placed_hazards:
                            if hazard["rect"].collidepoint(mx, my):
                                selected_object = hazard
                                offset_x = mx - hazard["rect"].x
                                offset_y = my - hazard["rect"].y
                                hit = True
                                break
                        if not hit:
                            # Nothing selected, so if a palette item is chosen, place a new object.
                            if selected_hazard_def:
                                # If the selected type is "ball" or "hole", update global positions.
                                if selected_hazard_def["type"] == "ball":
                                    ball_pos = [mx, my]
                                    print("Ball position updated.")
                                elif selected_hazard_def["type"] == "hole":
                                    hole_pos = [mx, my]
                                    print("Hole position updated.")
                                else:
                                    # Otherwise, create a new hazard.
                                    width, height = selected_hazard_def["size"]
                                    new_rect = pygame.Rect(
                                        mx - width // 2, my - height // 2, width, height
                                    )
                                    placed_hazards.append(
                                        {
                                            "name": next(
                                                k
                                                for k, v in hazard_defs.items()
                                                if v == selected_hazard_def
                                            ),
                                            "rect": new_rect,
                                            "type": selected_hazard_def["type"],
                                            "color": selected_hazard_def["color"],
                                        }
                                    )
                            selected_object = None

            # Right click (button 3) deletes hazards (but not ball/hole)
            elif event.button == 3 and mx >= PALETTE_WIDTH:
                for hazard in placed_hazards:
                    if hazard["rect"].collidepoint(mx, my):
                        placed_hazards.remove(hazard)
                        print(f"Removed {hazard['name']}")
                        break

        elif event.type == pygame.MOUSEBUTTONUP:
            selected_object = None

        elif event.type == pygame.MOUSEMOTION:
            if selected_object:
                mx, my = event.pos
                if selected_object == "ball":
                    ball_pos[0] = mx - offset_x
                    ball_pos[1] = my - offset_y
                elif selected_object == "hole":
                    hole_pos[0] = mx - offset_x
                    hole_pos[1] = my - offset_y
                else:
                    selected_object["rect"].x = mx - offset_x
                    selected_object["rect"].y = my - offset_y

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_s:
                print_layout()
            elif event.key == pygame.K_ESCAPE:
                running = False

    # ---------------- Draw Everything ----------------
    screen.fill(WHITE)
    draw_palette()
    draw_divider()
    draw_game_area()
    draw_hazards()
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
