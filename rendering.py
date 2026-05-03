# rendering.py

import cv2
import numpy as np

from config  import (ROAD_X, ROAD_Y, ROAD_HALF_WIDTH, MAP_WIDTH, MAP_HEIGHT,
                     SCREEN_WIDTH, SIM_HEIGHT, LANDMARKS, PARKING_LOTS)
from traffic import AgentType


# Sprite creation

def create_car_sprite(width=36, height=22, body_color=None):
    img = np.zeros((height, width, 4), dtype=np.uint8)
    bc  = (*(body_color or (50, 50, 220)), 255)
    wc  = (200, 200, 255, 255)
    tc  = (30, 30, 30, 255)
    lc  = (0, 255, 255, 255)
    brc = (0, 0, 255, 255)
    cv2.rectangle(img, (4, 6),       (width-4, height-6),  bc,  -1)
    cv2.rectangle(img, (4, 6),       (width-4, height-6),  (30, 30, 180, 255), 2)
    cv2.rectangle(img, (22, 8),      (32, 16),              wc,  -1)
    cv2.rectangle(img, (14, 7),      (24, 17),              bc,  -1)
    for cx, cy in [(8, 6), (width-8, 6), (8, height-6), (width-8, height-6)]:
        cv2.circle(img, (cx, cy), 3, tc, -1)
    cv2.circle(img, (width-4, 8),        2, lc,  -1)
    cv2.circle(img, (width-4, height-8), 2, lc,  -1)
    cv2.circle(img, (4, 8),              2, brc, -1)
    cv2.circle(img, (4, height-8),       2, brc, -1)
    return img


def rotate_sprite(sprite, angle):
    h, w    = sprite.shape[:2]
    center  = (w // 2, h // 2)
    M       = cv2.getRotationMatrix2D(center, -angle, 1.0)
    cos_a   = np.abs(M[0, 0])
    sin_a   = np.abs(M[0, 1])
    new_w   = int(h * sin_a + w * cos_a)
    new_h   = int(h * cos_a + w * sin_a)
    M[0, 2] += new_w / 2 - center[0]
    M[1, 2] += new_h / 2 - center[1]
    rotated = cv2.warpAffine(sprite, M, (new_w, new_h),
                             borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(0, 0, 0, 0))
    return rotated, (new_w // 2, new_h // 2)


def draw_sprite_on_image(bg, sprite, x, y, shadow=False):
    h, w = sprite.shape[:2]
    y1   = int(y - h // 2)
    x1   = int(x - w // 2)
    y2, x2 = y1 + h, x1 + w

    if shadow:
        sy1, sx1 = y1 + 4, x1 + 4
        sy2, sx2 = y2 + 4, x2 + 4
        if sy1 >= 0 and sx1 >= 0 and sy2 < bg.shape[0] and sx2 < bg.shape[1]:
            alpha = sprite[:, :, 3] / 255.0 * 0.3
            for c in range(3):
                bg[sy1:sy2, sx1:sx2, c] = (
                    (1 - alpha) * bg[sy1:sy2, sx1:sx2, c]
                )

    sly1, slx1 = 0, 0
    sly2, slx2 = h, w
    if y1 < 0:  sly1 = -y1;  y1 = 0
    if x1 < 0:  slx1 = -x1;  x1 = 0
    if y2 > bg.shape[0]:
        sly2 = h - (y2 - bg.shape[0]); y2 = bg.shape[0]
    if x2 > bg.shape[1]:
        slx2 = w - (x2 - bg.shape[1]); x2 = bg.shape[1]

    sprite = sprite[sly1:sly2, slx1:slx2]
    if sprite.shape[0] == 0 or sprite.shape[1] == 0:
        return
    h2, w2 = sprite.shape[:2]
    y2, x2 = y1 + h2, x1 + w2

    alpha = sprite[:, :, 3] / 255.0
    for c in range(3):
        bg[y1:y2, x1:x2, c] = (
            alpha * sprite[:, :, c] + (1 - alpha) * bg[y1:y2, x1:x2, c]
        )


# Vehicle drawing

def draw_vehicle(img, vehicle, cam_x, cam_y, is_player=False):
    if is_player:
        sx, sy = SCREEN_WIDTH // 2, SIM_HEIGHT // 2
    else:
        sx = SCREEN_WIDTH // 2 + int(vehicle.x - cam_x)
        sy = SIM_HEIGHT  // 2 + int(vehicle.y - cam_y)

    if not (0 < sx < SCREEN_WIDTH and 0 < sy < SIM_HEIGHT):
        return

    sprite, _ = rotate_sprite(create_car_sprite(36, 22, vehicle.color), vehicle.angle)
    draw_sprite_on_image(img, sprite, sx, sy, shadow=True)

    if vehicle.agent_type != AgentType.HUMAN:
        cv2.putText(img, str(vehicle.id), (sx - 5, sy - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    if vehicle.waiting_at_light:
        cv2.circle(img, (sx, sy - 30), 4, (0, 0, 255), -1)
    elif vehicle.in_queue:
        cv2.circle(img, (sx - 8, sy - 30), 3, (0, 255, 255), -1)

    if vehicle.vehicle_ahead:
        ax = SCREEN_WIDTH // 2 + int(vehicle.vehicle_ahead.x - cam_x)
        ay = SIM_HEIGHT  // 2 + int(vehicle.vehicle_ahead.y - cam_y)
        if 0 < ax < SCREEN_WIDTH and 0 < ay < SIM_HEIGHT:
            cv2.line(img, (sx, sy), (ax, ay), (255, 255, 0), 1)


# Traffic light drawing

def draw_traffic_light(img, light, cam_x, cam_y):
    from traffic import TrafficLightState
    sx = SCREEN_WIDTH // 2 + int(light.x - cam_x)
    sy = SIM_HEIGHT  // 2 + int(light.y - cam_y)
    if not (0 < sx < SCREEN_WIDTH and 0 < sy < SIM_HEIGHT):
        return

    cv2.line(img, (sx, sy), (sx, sy - 30), (80, 80, 80), 3)
    cv2.rectangle(img, (sx - 8, sy - 45), (sx + 8, sy - 25), (40, 40, 40), -1)

    color = (0, 255, 0)
    if light.state == TrafficLightState.RED:
        color = (0, 0, 255)
    elif light.state == TrafficLightState.YELLOW:
        color = (0, 255, 255)
    cv2.circle(img, (sx, sy - 35), 5, color, -1)

    if light.queue_length > 0:
        cv2.putText(img, str(light.queue_length), (sx + 10, sy - 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)


# Building icons

def create_building_icon(building_type, width=60, height=50):
    icon = np.zeros((height, width, 4), dtype=np.uint8)
    palette = {
        "gas":        ((0, 100, 200, 255),   (255, 255, 255, 255)),
        "school":     ((200, 200, 50, 255),  (50, 50, 50, 255)),
        "home":       ((150, 100, 50, 255),  (100, 50, 0, 255)),
        "park":       ((100, 200, 100, 255), (0, 100, 0, 255)),
        "restaurant": ((50, 150, 50, 255),   (255, 200, 0, 255)),
        "mall":       ((200, 100, 200, 255), (100, 50, 100, 255)),
        "hospital":   ((255, 255, 255, 255), (0, 0, 255, 255)),
        "bank":       ((200, 150, 50, 255),  (255, 255, 0, 255)),
        "police":     ((100, 50, 150, 255),  (255, 255, 255, 255)),
        "fire":       ((50, 50, 200, 255),   (255, 255, 255, 255)),
        "library":    ((150, 50, 150, 255),  (200, 200, 255, 255)),
        "airport":    ((150, 150, 150, 255), (100, 100, 100, 255)),
        "stadium":    ((50, 50, 150, 255),   (200, 200, 200, 255)),
    }
    bc, dc = palette.get(building_type, ((150, 150, 150, 255), (100, 100, 100, 255)))
    cv2.rectangle(icon, (5, 10),  (width-5, height-5), bc, -1)
    cv2.rectangle(icon, (5, 10),  (width-5, height-5), (30, 30, 30, 255), 2)
    cv2.rectangle(icon, (3, 5),   (width-3, 12),        (40, 40, 40, 255), -1)
    cx, cy = width // 2, height // 2
    if building_type == "gas":
        cv2.rectangle(icon, (cx-8, 18), (cx+8, 38), dc, -1)
        cv2.line(icon, (cx, 18), (cx, 12), dc, 3)
    elif building_type == "hospital":
        cv2.rectangle(icon, (cx-3, cy-5), (cx+3, cy+8), dc, -1)
        cv2.rectangle(icon, (cx-8, cy-3), (cx+8, cy+3), dc, -1)
    elif building_type == "school":
        cv2.line(icon, (cx, 15), (cx, 35), dc, 2)
        cv2.rectangle(icon, (cx, 15), (cx+10, 22), dc, -1)
    elif building_type == "home":
        pts = np.array([[5, 10], [cx, 2], [width-5, 10]], np.int32)
        cv2.fillPoly(icon, [pts], dc)
    elif building_type == "restaurant":
        cv2.line(icon, (cx-5, 20), (cx-5, 35), dc, 2)
        cv2.line(icon, (cx+5, 20), (cx+5, 35), dc, 2)
    elif building_type == "park":
        cv2.circle(icon, (cx, 25), 8, dc, -1)
        cv2.rectangle(icon, (cx-2, 33), (cx+2, 40), (100, 50, 0, 255), -1)
    return icon


# Map generation

def create_map():
    img = np.ones((MAP_HEIGHT, MAP_WIDTH, 3), dtype=np.uint8)
    img[:] = (70, 130, 70)
    rw         = ROAD_HALF_WIDTH
    road_color = (40, 40, 40)
    line_color = (0, 160, 255)

    for x in ROAD_X:
        cv2.rectangle(img, (x - rw, 0), (x + rw, MAP_HEIGHT), road_color, -1)
        for y in range(0, MAP_HEIGHT, 80):
            cv2.line(img, (x, y), (x, min(y + 40, MAP_HEIGHT)), line_color, 3)

    for y in ROAD_Y:
        cv2.rectangle(img, (0, y - rw), (MAP_WIDTH, y + rw), road_color, -1)
        for x in range(0, MAP_WIDTH, 80):
            cv2.line(img, (x, y), (min(x + 40, MAP_WIDTH), y), line_color, 3)

    icons = {ltype: create_building_icon(ltype, 60, 50)
             for ltype in {l["type"] for l in LANDMARKS}}

    for lm in LANDMARKS:
        x, y   = lm["pos"]
        icon   = icons.get(lm["type"], icons["home"])
        ih, iw = icon.shape[:2]
        x1, y1 = x - iw // 2, y - ih // 2
        if x1 >= 0 and y1 >= 0 and x1 + iw < MAP_WIDTH and y1 + ih < MAP_HEIGHT:
            alpha = icon[:, :, 3] / 255.0
            for c in range(3):
                img[y1:y1+ih, x1:x1+iw, c] = (
                    alpha * icon[:, :, c] +
                    (1 - alpha) * img[y1:y1+ih, x1:x1+iw, c]
                )
        cv2.putText(img, lm["name"][:12], (x - 45, y + ih // 2 + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # Parking lots
    for lm in LANDMARKS:
        name = lm["name"]
        if name not in PARKING_LOTS:
            continue
        spot = PARKING_LOTS[name]["spot"]
        drwy = PARKING_LOTS[name]["driveway"]
        sx, sy = int(spot[0]), int(spot[1])
        dx, dy = int(drwy[0]), int(drwy[1])
        # Parking area box
        cv2.rectangle(img, (sx - 20, sy - 15), (sx + 20, sy + 15), (160, 160, 160), -1)
        cv2.rectangle(img, (sx - 20, sy - 15), (sx + 20, sy + 15), (100, 100, 100),  1)
        # Driveway connector line
        cv2.line(img, (sx, sy), (dx, dy), (130, 130, 130), 3)
        # Parking spot line markings
        for offset in [-8, 0, 8]:
            if abs(sx - dx) > abs(sy - dy):  # horizontal driveway
                cv2.line(img, (sx + offset, sy - 15), (sx + offset, sy + 15), (200, 200, 200), 1)
            else:
                cv2.line(img, (sx - 20, sy + offset), (sx + 20, sy + offset), (200, 200, 200), 1)

    return img
