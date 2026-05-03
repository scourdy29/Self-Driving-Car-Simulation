# weather.py

import cv2
import numpy as np
import random
from enum import Enum

from config import SCREEN_WIDTH, SIM_HEIGHT, MAP_WIDTH, MAP_HEIGHT


class WeatherState(Enum):
    CLEAR       = "Clear"
    RAIN        = "Rain"
    HEAVY_RAIN  = "Heavy Rain"
    NIGHT       = "Night"


# Speed multipliers
SPEED_MULTIPLIERS = {
    WeatherState.CLEAR:      1.0,
    WeatherState.RAIN:       0.75,
    WeatherState.HEAVY_RAIN: 0.50,
    WeatherState.NIGHT:      0.85,
}

# How far ahead vehicles can "see"
VISIBILITY = {
    WeatherState.CLEAR:      1.0,
    WeatherState.RAIN:       0.80,
    WeatherState.HEAVY_RAIN: 0.55,
    WeatherState.NIGHT:      0.70,
}


class WeatherSystem:

    # Transition probabilities per tick
    _TRANSITION_INTERVAL = 30 * 60 * 3   # every ~3 minutes at 30fps

    def __init__(self):
        self.state        = WeatherState.CLEAR
        self._tick        = 0
        self._rain_drops  = []
        self._base_speeds = {}

        self._init_rain()

    # Public API

    def cycle(self):
        states = list(WeatherState)
        idx    = states.index(self.state)
        self.state = states[(idx + 1) % len(states)]
        self._init_rain()
        return self.state.value

    def update(self):
        self._tick += 1
        self._update_rain()

    def apply_overlay(self, img: np.ndarray):
        if self.state == WeatherState.RAIN:
            self._draw_rain(img, density=0.4)
            self._draw_tint(img, color=(180, 180, 220), alpha=0.08)
        elif self.state == WeatherState.HEAVY_RAIN:
            self._draw_rain(img, density=1.0)
            self._draw_tint(img, color=(130, 130, 190), alpha=0.18)
            self._draw_fog(img, alpha=0.12)
        elif self.state == WeatherState.NIGHT:
            self._draw_tint(img, color=(10, 10, 40), alpha=0.55)

    def apply_to_vehicles(self, vehicles: list):
        mult = SPEED_MULTIPLIERS[self.state]
        for v in vehicles:
            vid = v.id
            # When Clear, always refresh the stored base
            if self.state == WeatherState.CLEAR or vid not in self._base_speeds:
                self._base_speeds[vid] = v.max_speed
            v.max_speed = self._base_speeds[vid] * mult

    def draw_hud(self, img: np.ndarray):
        icons = {
            WeatherState.CLEAR:      ("   CLEAR", (255, 220, 80)),
            WeatherState.RAIN:       ("    RAIN", (140, 180, 255)),
            WeatherState.HEAVY_RAIN: ("HVY RAIN", (80, 100, 220)),
            WeatherState.NIGHT:      ("   NIGHT", (180, 140, 255)),
        }
        label, color = icons[self.state]

        # Background pill
        x0, y0 = SCREEN_WIDTH - 160, 8
        cv2.rectangle(img, (x0, y0), (x0 + 150, y0 + 28), (20, 20, 20), -1)
        cv2.rectangle(img, (x0, y0), (x0 + 150, y0 + 28), color, 1)

        # Weather icon
        cx, cy = x0 + 18, y0 + 14
        if self.state == WeatherState.CLEAR:
            cv2.circle(img, (cx, cy), 8, (0, 220, 255), -1)
        elif self.state in (WeatherState.RAIN, WeatherState.HEAVY_RAIN):
            cv2.ellipse(img, (cx, cy - 2), (9, 6), 0, 180, 360, (180, 180, 255), -1)
            n = 3 if self.state == WeatherState.RAIN else 5
            for i in range(n):
                rx = cx - 6 + i * 3
                cv2.line(img, (rx, cy + 4), (rx - 2, cy + 9), (100, 150, 255), 1)
        elif self.state == WeatherState.NIGHT:
            pts = np.array([[cx-6,cy],[cx,cy-8],[cx+4,cy-4],[cx+8,cy+2],[cx+2,cy+7]], np.int32)
            cv2.fillPoly(img, [pts], (200, 180, 100))

        cv2.putText(img, label, (x0 + 32, y0 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1)

        # Speed modifier label
        mult = SPEED_MULTIPLIERS[self.state]
        if mult < 1.0:
            cv2.putText(img, f"Spd x{mult:.0%}", (x0, y0 + 44),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)

        # Night: draw headlight cones for all nearby vehicles

    def draw_headlights(self, img: np.ndarray, vehicles: list, cam_x: float, cam_y: float):
        if self.state != WeatherState.NIGHT:
            return
        import math
        for v in vehicles:
            sx = SCREEN_WIDTH // 2 + int(v.x - cam_x)
            sy = SIM_HEIGHT   // 2 + int(v.y - cam_y)
            if not (0 < sx < SCREEN_WIDTH and 0 < sy < SIM_HEIGHT):
                continue
            rad    = math.radians(v.angle)
            length = 70
            spread = math.radians(25)
            for offset in [-spread, 0, spread]:
                ex = int(sx + length * math.cos(rad + offset))
                ey = int(sy + length * math.sin(rad + offset))
                cv2.line(img, (sx, sy), (ex, ey), (40, 40, 100), 1)
            # Bright headlight dot
            hx = int(sx + 18 * math.cos(rad))
            hy = int(sy + 18 * math.sin(rad))
            cv2.circle(img, (hx, hy), 4, (200, 200, 100), -1)

    # Internal helpers

    def _init_rain(self):
        self._rain_drops = [
            [random.randint(0, SCREEN_WIDTH),
             random.randint(0, SIM_HEIGHT),
             random.randint(8, 16),
             random.uniform(6, 14)]
            for _ in range(400)
        ]

    def _update_rain(self):
        if self.state not in (WeatherState.RAIN, WeatherState.HEAVY_RAIN):
            return
        for drop in self._rain_drops:
            drop[1] += drop[3]   # y += speed
            if drop[1] > SIM_HEIGHT:
                drop[0] = random.randint(0, SCREEN_WIDTH)
                drop[1] = random.randint(-20, 0)

    def _draw_rain(self, img: np.ndarray, density: float):
        n = int(len(self._rain_drops) * density)
        for drop in self._rain_drops[:n]:
            x, y, length, _ = drop
            x1, y1 = int(x), int(y)
            x2, y2 = int(x - length * 0.3), int(y + length)
            if 0 <= x1 < SCREEN_WIDTH and 0 <= y1 < SIM_HEIGHT:
                cv2.line(img, (x1, y1), (x2, y2), (180, 200, 255), 1)

    def _draw_tint(self, img: np.ndarray, color: tuple, alpha: float):
        overlay = np.full_like(img, color, dtype=np.uint8)
        dst = np.empty_like(img)
        cv2.addWeighted(overlay, alpha, img, 1.0 - alpha, 0, dst)
        np.copyto(img, dst)

    def _draw_fog(self, img: np.ndarray, alpha: float):
        h, w = img.shape[:2]
        rows   = np.abs(np.arange(h) - h // 2) / (h // 2)   # 0 at centre, 1 at edges
        mask   = (rows * alpha).astype(np.float32)[:, np.newaxis, np.newaxis]
        overlay = np.full_like(img, (200, 210, 230), dtype=np.float32)
        blended = img.astype(np.float32) * (1.0 - mask) + overlay * mask
        np.copyto(img, np.clip(blended, 0, 255).astype(np.uint8))
