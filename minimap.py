# minimap.py

import cv2
import numpy as np

from config import (ROAD_X, ROAD_Y, ROAD_HALF_WIDTH,
                    MAP_WIDTH, MAP_HEIGHT, SCREEN_WIDTH, SIM_HEIGHT,
                    LANDMARKS)
from traffic import AgentType


# Minimap dimensions
MM_W   = 200
MM_H   = int(MM_W * MAP_HEIGHT / MAP_WIDTH)
MM_X   = SCREEN_WIDTH - MM_W - 10 # top-right corner
MM_Y   = 10
BORDER = 2

# Scale factors
SX = MM_W / MAP_WIDTH
SY = MM_H / MAP_HEIGHT


def _sim_to_mm(x: float, y: float):
    return int(x * SX), int(y * SY)


# Pre-render the static minimap
def build_minimap_base() -> np.ndarray:
    base = np.zeros((MM_H, MM_W, 3), dtype=np.uint8)
    base[:] = (30, 60, 30)   # dark grass

    # Roads
    road_col = (55, 55, 55)
    rw_x = max(1, int(ROAD_HALF_WIDTH * SX))
    rw_y = max(1, int(ROAD_HALF_WIDTH * SY))
    for rx in ROAD_X:
        mx, _ = _sim_to_mm(rx, 0)
        cv2.rectangle(base, (mx - rw_x, 0), (mx + rw_x, MM_H), road_col, -1)
    for ry in ROAD_Y:
        _, my = _sim_to_mm(0, ry)
        cv2.rectangle(base, (0, my - rw_y), (MM_W, my + rw_y), road_col, -1)

    # Landmark dots
    type_colors = {
        "home":       (100, 150, 255),
        "gas":        (50,  200, 255),
        "school":     (200, 200,  50),
        "restaurant": (50,  200,  50),
        "mall":       (200, 100, 200),
        "hospital":   (255, 255, 255),
        "bank":       (200, 180,  50),
        "police":     (150,  80, 200),
        "fire":       (50,   50, 220),
        "library":    (180,  80, 180),
        "airport":    (180, 180, 180),
        "stadium":    (80,   80, 200),
        "park":       (80,  200,  80),
    }
    for lm in LANDMARKS:
        mx, my = _sim_to_mm(*lm["pos"])
        col    = type_colors.get(lm["type"], (150, 150, 150))
        cv2.rectangle(base, (mx - 2, my - 2), (mx + 2, my + 2), col, -1)

    return base


def draw_minimap(frame: np.ndarray,
                 base: np.ndarray,
                 vehicles: list,
                 player_vehicle,
                 cam_x: float,
                 cam_y: float):
    mm = base.copy()

    # Vehicle dots
    dot_colors = {
        AgentType.HUMAN:         (50,  50, 220),  # blue
        AgentType.AI_RANDOM:     (50,  50, 220),
        AgentType.AI_EFFICIENT:  (50, 220,  50),  # green
        AgentType.AI_AGGRESSIVE: (220, 220, 50),  # yellow
    }
    for v in vehicles:
        mx, my = _sim_to_mm(v.x, v.y)
        if not (0 <= mx < MM_W and 0 <= my < MM_H):
            continue
        if v.agent_type == AgentType.HUMAN:
            # Player: white dot with blue ring
            cv2.circle(mm, (mx, my), 4, (255, 255, 255), -1)
            cv2.circle(mm, (mx, my), 4, (50, 50, 220), 1)
        elif v.agent_type == AgentType.AI_RANDOM:
            cv2.circle(mm, (mx, my), 2, (220, 80, 80), -1)
        elif v.agent_type == AgentType.AI_EFFICIENT:
            cv2.circle(mm, (mx, my), 2, (80, 220, 80), -1)
        else:
            cv2.circle(mm, (mx, my), 2, (220, 220, 80), -1)

    # Destination marker
    if player_vehicle.current_destination:
        dx, dy = _sim_to_mm(*player_vehicle.current_destination)
        if 0 <= dx < MM_W and 0 <= dy < MM_H:
            cv2.drawMarker(mm, (dx, dy), (0, 255, 255),
                           cv2.MARKER_CROSS, 6, 1)

    # Viewport rectangle
    vx1, vy1 = _sim_to_mm(cam_x - SCREEN_WIDTH // 2, cam_y - SIM_HEIGHT // 2)
    vx2, vy2 = _sim_to_mm(cam_x + SCREEN_WIDTH // 2, cam_y + SIM_HEIGHT // 2)
    vx1 = max(0, min(MM_W - 1, vx1))
    vy1 = max(0, min(MM_H - 1, vy1))
    vx2 = max(0, min(MM_W - 1, vx2))
    vy2 = max(0, min(MM_H - 1, vy2))
    cv2.rectangle(mm, (vx1, vy1), (vx2, vy2), (255, 255, 255), 1)

    # Border background
    bx1, by1 = MM_X - BORDER, MM_Y - BORDER
    bx2, by2 = MM_X + MM_W + BORDER, MM_Y + MM_H + BORDER

    # Dark background behind minimap
    cv2.rectangle(frame, (bx1, by1), (bx2, by2), (15, 15, 15), -1)
    cv2.rectangle(frame, (bx1, by1), (bx2, by2), (80, 80, 80), 1)

    # Paste minimap onto frame
    frame[MM_Y:MM_Y + MM_H, MM_X:MM_X + MM_W] = mm

    # "MAP" label
    cv2.putText(frame, "MAP", (MM_X + 2, MM_Y + MM_H + 13),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (140, 140, 140), 1)

    # Compass N indicator
    cv2.putText(frame, "N", (MM_X + MM_W - 12, MM_Y + 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)
    cv2.arrowedLine(frame,
                    (MM_X + MM_W - 8, MM_Y + 22),
                    (MM_X + MM_W - 8, MM_Y + 14),
                    (200, 200, 200), 1, tipLength=0.5)
