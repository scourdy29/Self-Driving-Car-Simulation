import cv2
import numpy as np
from datetime import datetime
import re
import sys
import random
import sqlite3
import os
import hashlib
import math
from collections import deque
from enum import Enum

# Database setup
DB_PATH = "ai_driver.db"

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            landmark_name TEXT,
            pos_x REAL,
            pos_y REAL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, name)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            landmark_name TEXT,
            pos_x REAL,
            pos_y REAL,
            visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            frequency INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preferences (
            user_id INTEGER,
            pref_key TEXT,
            pref_value TEXT,
            PRIMARY KEY (user_id, pref_key),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_user_exists(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def register_user(username, password):
    if not username or not password:
        return False, "Username and password required", None
    if len(username) < 3:
        return False, "Username must be at least 3 characters", None
    if len(password) < 4:
        return False, "Password must be at least 4 characters", None
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username: letters, numbers, underscores only", None
    if check_user_exists(username):
        return False, f"Username '{username}' already exists", None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        hashed_pw = hash_password(password)
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
        user_id = cursor.lastrowid
        conn.commit()
        return True, "Registration successful", user_id
    except Exception as e:
        return False, f"Database error: {str(e)}", None
    finally:
        conn.close()

def authenticate_user(username, password):
    if not username or not password:
        return None
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    if result and result[1] == hash_password(password):
        return result[0]
    return None

def get_or_create_user(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def add_favorite(user_id, name, landmark_name, pos_x, pos_y, category="general"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO favorites (user_id, name, landmark_name, pos_x, pos_y, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, name.lower(), landmark_name, pos_x, pos_y, category))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding favorite: {e}")
        return False
    finally:
        conn.close()

def get_favorite(user_id, name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT landmark_name, pos_x, pos_y FROM favorites 
        WHERE user_id = ? AND name = ?
    ''', (user_id, name.lower()))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"landmark_name": result[0], "x": result[1], "y": result[2]}
    return None

def add_to_history(user_id, landmark_name, pos_x, pos_y):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, frequency FROM history 
        WHERE user_id = ? AND landmark_name = ?
    ''', (user_id, landmark_name))
    result = cursor.fetchone()
    if result:
        cursor.execute('''
            UPDATE history SET frequency = ?, visited_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (result[1] + 1, result[0]))
    else:
        cursor.execute('''
            INSERT INTO history (user_id, landmark_name, pos_x, pos_y)
            VALUES (?, ?, ?, ?)
        ''', (user_id, landmark_name, pos_x, pos_y))
    conn.commit()
    conn.close()

# ==================== REALISTIC TRAFFIC SYSTEM ====================

class AgentType(Enum):
    HUMAN = "human"
    AI_RANDOM = "ai_random"
    AI_EFFICIENT = "ai_efficient"
    AI_AGGRESSIVE = "ai_aggressive"

class TrafficLightState(Enum):
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"

class TrafficLight:
    def __init__(self, x, y, orientation, id):
        self.x = x
        self.y = y
        self.orientation = orientation
        self.id = id
        self.state = TrafficLightState.GREEN
        self.timer = random.randint(0, 300)
        self.green_duration = 150
        self.yellow_duration = 30
        self.red_duration = 120
        self.queue_length = 0
        self.waiting_vehicles = []
        self.adaptive_mode = True
        
    def update(self, vehicles, all_lights, dt=1):
        self.waiting_vehicles = []
        for v in vehicles:
            if v.state == "driving" and v.waiting_at_light and v.target_light == self:
                self.waiting_vehicles.append(v.id)
                
        self.queue_length = len(self.waiting_vehicles)
        
        if not self.adaptive_mode:
            self._fixed_timing_update()
            return
            
        self.timer += dt
        self._state_machine_update()
        
    def _state_machine_update(self):
        cycle_pos = self.timer % (self.green_duration + self.yellow_duration + self.red_duration)
        if cycle_pos < self.green_duration:
            new_state = TrafficLightState.GREEN
        elif cycle_pos < self.green_duration + self.yellow_duration:
            new_state = TrafficLightState.YELLOW
        else:
            new_state = TrafficLightState.RED
            
        if new_state != self.state:
            self.state = new_state
            
    def _fixed_timing_update(self):
        cycle_pos = self.timer % 300
        if cycle_pos < 150:
            self.state = TrafficLightState.GREEN
        else:
            self.state = TrafficLightState.RED

class VehicleAgent:
    def __init__(self, x, y, agent_type=AgentType.AI_RANDOM, vehicle_id=0, color=None):
        self.id = vehicle_id
        self.x = float(x)
        self.y = float(y)
        self.angle = random.choice([0, 90, 180, 270])
        self.speed = 0.0
        self.max_speed = 5.0 if agent_type != AgentType.AI_AGGRESSIVE else 6.5
        self.agent_type = agent_type
        
        # Visual properties
        if color is None:
            if agent_type == AgentType.HUMAN:
                self.color = (50, 50, 220)
            elif agent_type == AgentType.AI_RANDOM:
                self.color = (220, 50, 50)
            elif agent_type == AgentType.AI_EFFICIENT:
                self.color = (50, 220, 50)
            else:
                self.color = (220, 220, 50)
        else:
            self.color = color
            
        # Navigation
        self.current_destination = None
        self.destination_name = None
        self.path = []
        self.waypoint_idx = 0
        self.state = "idle"
        self.stuck_counter = 0
        self.last_pos = (x, y)
        
        # Per-type driving personality
        if agent_type == AgentType.AI_AGGRESSIVE:
            self.max_speed          = 6.5
            self.following_distance = 45    # tailgates
            self.comfortable_decel  = 0.25
            self.max_decel          = 0.7
            self.acceleration       = 0.20
        elif agent_type == AgentType.AI_EFFICIENT:
            self.max_speed          = 4.2
            self.following_distance = 85
            self.comfortable_decel  = 0.10
            self.max_decel          = 0.35
            self.acceleration       = 0.09
        elif agent_type == AgentType.AI_RANDOM:
            self.max_speed          = random.uniform(3.5, 5.5)
            self.following_distance = random.randint(55, 90)
            self.comfortable_decel  = 0.13
            self.max_decel          = 0.45
            self.acceleration       = random.uniform(0.08, 0.15)
        else:
            self.max_speed          = 5.0
            self.following_distance = 70
            self.comfortable_decel  = 0.15
            self.max_decel          = 0.4
            self.acceleration       = 0.1
        self.desired_speed = self.max_speed
        self.lane_offset   = 18

        # Traffic state
        self.waiting_at_light = False
        self.target_light = None
        self.wait_time = 0
        self.total_wait_time = 0
        self.in_queue = False
        self.vehicle_ahead = None

        # Tire tracks
        self.tire_tracks = []

        # Park at destination before despawning
        self.behavior_timer  = 0
        self.park_duration   = random.randint(60, 240)   # 2–8 s at 30 fps
        
        # Boundaries
        self.bounds = {'min_x': 50, 'max_x': MAP_WIDTH - 50, 'min_y': 50, 'max_y': MAP_HEIGHT - 50}
        
    def set_destination(self, dest_name, dest_pos, original_pos=None):
        self.destination_name = dest_name
        self.current_destination = dest_pos
        self.original_goal = original_pos or dest_pos
        self.state = "driving"
        self.path = []
        self.waypoint_idx = 0
        self.speed = 0
        self.waiting_at_light = False
        self.in_queue = False
        
        # Face toward destination initially
        dx = dest_pos[0] - self.x
        dy = dest_pos[1] - self.y
        if abs(dx) > abs(dy):
            self.angle = 0 if dx > 0 else 180
        else:
            self.angle = 90 if dy > 0 else 270
        
        # Snap to lane if off road
        if not is_on_road(self.x, self.y):
            self._snap_to_lane()
        
    def update(self, world_map, traffic_lights, all_vehicles, dt=1):
        # Enforce boundaries
        self._enforce_boundaries()
        
        # Update tire tracks
        if self.speed > 0.5:
            self.tire_tracks.append((self.x, self.y, self.angle, 1.0))
            if len(self.tire_tracks) > 40:
                self.tire_tracks.pop(0)
        self.tire_tracks = [(x, y, a, o*0.95) for x, y, a, o in self.tire_tracks if o > 0.05]
        
        # AI destination selection
        if self.agent_type != AgentType.HUMAN and self.state == "idle":
            self._ai_select_destination(world_map)
        
        # Main navigation
        if self.state == "driving" and self.current_destination:
            self._navigate_realistic(all_vehicles, traffic_lights)
        
        self._check_stuck()
        
        if self.waiting_at_light:
            self.wait_time += dt
            self.total_wait_time += dt
            
    def _enforce_boundaries(self):
        self.x = max(self.bounds['min_x'], min(self.bounds['max_x'], self.x))
        self.y = max(self.bounds['min_y'], min(self.bounds['max_y'], self.y))
        
        if not is_on_road(self.x, self.y):
            self.x, self.y = snap_to_road(self.x, self.y)
            
    def _ai_select_destination(self, world_map):
        # First-frame initialisation of idle delay counter
        if not hasattr(self, '_idle_delay'):
            self._idle_delay = random.randint(0, 45)

        if self._idle_delay > 0:
            self._idle_delay -= 1
            return

        if not LANDMARKS:
            return

        if self.agent_type == AgentType.AI_EFFICIENT:
            # Pick closest landmark
            target = min(LANDMARKS, key=lambda l:
                math.sqrt((l["pos"][0] - self.x)**2 + (l["pos"][1] - self.y)**2))

        elif self.agent_type == AgentType.AI_AGGRESSIVE:
            dists = [math.sqrt((l["pos"][0]-self.x)**2 + (l["pos"][1]-self.y)**2)
                     for l in LANDMARKS]
            total = sum(dists) or 1
            weights = [d / total for d in dists]
            target = random.choices(LANDMARKS, weights=weights, k=1)[0]

        else:   # AI_RANDOM
            target = random.choice(LANDMARKS)

        dest_pos = get_drop_off_point(target["pos"][0], target["pos"][1])
        self.set_destination(target["name"], dest_pos, target["pos"])
        # Reset idle delay for next arrival
        self._idle_delay = random.randint(30, 120)
                
    def _navigate_realistic(self, all_vehicles, traffic_lights):
        # Check arrival
        if self.current_destination:
            dist_to_dest = math.sqrt((self.x - self.current_destination[0])**2 + 
                                     (self.y - self.current_destination[1])**2)
            if dist_to_dest < 25:
                self.state = "arrived"
                self.speed = 0
                self.waiting_at_light = False
                return
        
        # Path planning
        if not self.path or self.waypoint_idx >= len(self.path):
            self.path = find_grid_path((self.x, self.y), self.current_destination)
            self.waypoint_idx = 0

        if not self.path:
            self.state = "idle"
            self.speed = 0
            return
            
        if self.waypoint_idx >= len(self.path):
            self.waypoint_idx = len(self.path) - 1
            
        wx, wy = self.path[self.waypoint_idx]
        wp_dist = math.sqrt((wx - self.x)**2 + (wy - self.y)**2)

        advance_radius = 20 if self.waypoint_idx == len(self.path) - 1 else 30
        if wp_dist < advance_radius and self.waypoint_idx + 1 < len(self.path):
            self.waypoint_idx += 1
            wx, wy = self.path[self.waypoint_idx]

        # Find vehicle ahead
        vehicle_ahead = self._find_vehicle_ahead(all_vehicles)
        self.vehicle_ahead = vehicle_ahead
        
        # Check traffic light
        light_ahead, dist_to_light = self._check_light_ahead(traffic_lights)
        
        # Calculate target speed
        target_speed = self.max_speed
        
        # Vehicle ahead constraint
        if vehicle_ahead:
            dist = math.sqrt((vehicle_ahead.x - self.x)**2 + (vehicle_ahead.y - self.y)**2)
            safe_gap = 38   # stop before touching

            if dist <= safe_gap:
                target_speed = 0
            elif dist < self.following_distance:
                # Smoothly scale from 0 up to other car's speed
                ratio = (dist - safe_gap) / (self.following_distance - safe_gap)
                target_speed = vehicle_ahead.speed * max(0.0, min(1.0, ratio))
            # else: target_speed stays at max_speed

            self.in_queue = (dist < self.following_distance)
        else:
            self.in_queue = False
            
        # Traffic light constraint
        self.waiting_at_light = False
        if light_ahead and dist_to_light < 150:
            if light_ahead.state == TrafficLightState.RED:
                if dist_to_light < 80:
                    target_speed = 0
                    self.waiting_at_light = True
                    self.target_light = light_ahead
                else:
                    target_speed = min(target_speed, dist_to_light / 40)
            elif light_ahead.state == TrafficLightState.YELLOW and dist_to_light < 100:
                target_speed = min(target_speed, dist_to_light / 30)
                
        # Cornering speed
        if self.waypoint_idx < len(self.path):
            angle_to_wp = math.degrees(math.atan2(wy - self.y, wx - self.x))
            angle_diff = abs(angle_to_wp - self.angle)
            while angle_diff > 180:
                angle_diff = 360 - angle_diff
            
            if angle_diff > 60:
                target_speed = min(target_speed, 2.0)
            elif angle_diff > 30:
                target_speed = min(target_speed, 3.5)
        
        # Apply acceleration/deceleration
        if target_speed < self.speed:
            if vehicle_ahead:
                vdist = math.sqrt((vehicle_ahead.x - self.x)**2 + (vehicle_ahead.y - self.y)**2)
                # Scale braking force: gentle far away, maximum when very close
                t = max(0.0, 1.0 - (vdist - 35) / 50.0)   # 0 at 85px, 1 at 35px
                decel = self.comfortable_decel + t * (self.max_decel - self.comfortable_decel)
            else:
                # Braking for light or corner — use max_decel so we actually stop
                decel = self.max_decel
            self.speed = max(target_speed, self.speed - decel)
        else:
            self.speed = min(target_speed, self.speed + self.acceleration)
            
        self.speed = max(0, min(self.speed, self.max_speed))
        
        # Update lane offset from current heading, then steer
        self._update_lane_direction(wx, wy)

        # Steering toward waypoint
        self._steer_toward(wx, wy)
        
        # Move forward
        if self.speed > 0.1:
            rad = math.radians(self.angle)
            new_x = self.x + self.speed * math.cos(rad)
            new_y = self.y + self.speed * math.sin(rad)
            
            if is_on_road(new_x, new_y):
                self.x, self.y = new_x, new_y
            else:
                # Try sliding along road
                if is_on_road(new_x, self.y):
                    self.x = new_x
                elif is_on_road(self.x, new_y):
                    self.y = new_y
                else:
                    self.speed *= 0.5
                    self.x, self.y = snap_to_road(self.x, self.y)

    def _find_vehicle_ahead(self, all_vehicles):
        closest_ahead = None
        min_dist = float('inf')

        for other in all_vehicles:
            if other.id == self.id:
                continue

            dx = other.x - self.x
            dy = other.y - self.y
            dist = math.sqrt(dx**2 + dy**2)

            if dist > 120 or dist < 1:
                continue

            bearing = math.degrees(math.atan2(dy, dx))
            b_diff  = bearing - self.angle
            while b_diff >  180: b_diff -= 360
            while b_diff < -180: b_diff += 360

            if abs(b_diff) > 30:
                continue   # outside forward cone

            # For moving cars also check they are going the same direction.
            # Stopped/slow cars (speed < 0.5) are always treated as obstacles.
            if other.speed > 0.5:
                h_diff = other.angle - self.angle
                while h_diff >  180: h_diff -= 360
                while h_diff < -180: h_diff += 360
                if abs(h_diff) > 100:
                    continue   # oncoming or crossing traffic — ignore

            if dist < min_dist:
                min_dist = dist
                closest_ahead = other

        return closest_ahead

    def _check_light_ahead(self, traffic_lights):
        best_light = None
        best_dist  = float('inf')

        for light in traffic_lights:
            dx = light.x - self.x
            dy = light.y - self.y
            dist = math.sqrt(dx**2 + dy**2)

            if dist > 180 or dist < 20:
                continue

            angle_to_light = math.degrees(math.atan2(dy, dx))
            diff = angle_to_light - self.angle
            while diff >  180: diff -= 360
            while diff < -180: diff += 360

            if abs(diff) < 30 and dist < best_dist:
                best_dist  = dist
                best_light = light

        return best_light, best_dist

    def _steer_toward(self, wx, wy):
        dx = wx - self.x
        dy = wy - self.y
        if abs(dx) < 1 and abs(dy) < 1:
            return

        target_angle = math.degrees(math.atan2(dy, dx))

        steer = target_angle - self.angle
        while steer > 180:  steer -= 360
        while steer < -180: steer += 360

        max_turn = 5.0
        self.angle += max(-max_turn, min(max_turn, steer * 0.4))
        while self.angle >= 360: self.angle -= 360
        while self.angle < 0:    self.angle += 360

    def _get_lane_target(self, wx, wy):
        LANE_W = 18
        heading_rad = math.radians(self.angle)
        ch = math.cos(heading_rad)
        sh = math.sin(heading_rad)
        if abs(ch) >= abs(sh):
            road_y = min(ROAD_Y, key=lambda ry: abs(ry - self.y))
            return wx, road_y + (LANE_W if ch > 0 else -LANE_W)
        else:
            road_x = min(ROAD_X, key=lambda rx: abs(rx - self.x))
            return road_x + (LANE_W if sh > 0 else -LANE_W), wy

    def _update_lane_direction(self, wx, wy):
        LANE_W = 18
        heading_rad = math.radians(self.angle)
        ch = math.cos(heading_rad)
        sh = math.sin(heading_rad)
        self.lane_offset = LANE_W if (abs(ch) >= abs(sh) and ch > 0) or \
                                     (abs(sh) > abs(ch) and sh > 0) else -LANE_W
            
    def _check_stuck(self):
        current_pos = (self.x, self.y)
        moved = math.sqrt((current_pos[0] - self.last_pos[0])**2 +
                          (current_pos[1] - self.last_pos[1])**2)

        # Don't count as stuck while stopped at a red light
        if moved < 0.1 and self.state == "driving" and not self.waiting_at_light:
            self.stuck_counter += 1
            if self.stuck_counter > 120:
                if self.agent_type != AgentType.HUMAN:
                    # Teleport to a clear intersection and pick a fresh destination
                    self._unstick()
                else:
                    self.x, self.y = snap_to_road(self.x, self.y)
                self.stuck_counter = 0
        else:
            self.stuck_counter = 0

        self.last_pos = current_pos

    def _unstick(self):
        """Teleport this AI car to a random clear intersection and restart."""
        for _ in range(20):
            rx = random.choice(ROAD_X)
            ry = random.choice(ROAD_Y)
            if not any(v.id != self.id and
                       math.sqrt((v.x-rx)**2 + (v.y-ry)**2) < 80
                       for v in _all_vehicles_ref):
                self.x, self.y = float(rx), float(ry)
                break
        else:
            self.x = float(random.choice(ROAD_X))
            self.y = float(random.choice(ROAD_Y))
        self.speed = 0
        self.path  = []
        self.waypoint_idx = 0
        self.state = "idle"
        self._idle_delay = random.randint(5, 20)

    def _snap_to_lane(self):
        """Snap car to the correct lane on whichever road it's currently on."""
        self._update_lane_direction(self.x, self.y)
        nearest_x = min(ROAD_X, key=lambda rx: abs(rx - self.x))
        nearest_y = min(ROAD_Y, key=lambda ry: abs(ry - self.y))
        if abs(self.x - nearest_x) <= abs(self.y - nearest_y):
            self.x = nearest_x + self.lane_offset
        else:
            self.y = nearest_y + self.lane_offset

def draw_vehicle(img, vehicle, car_x, car_y, is_player=False):
    if is_player:
        scr_x = SCREEN_WIDTH // 2
        scr_y = SIM_HEIGHT // 2
    else:
        scr_x = SCREEN_WIDTH//2 + int(vehicle.x - car_x)
        scr_y = SIM_HEIGHT//2 + int(vehicle.y - car_y)
    
    if not (0 < scr_x < SCREEN_WIDTH and 0 < scr_y < SIM_HEIGHT):
        return
        
    sprite = create_car_sprite(36, 22, vehicle.color)
    rotated, _ = rotate_sprite(sprite, vehicle.angle)
    draw_sprite_on_image(img, rotated, scr_x, scr_y, shadow=True)
    
    if vehicle.agent_type != AgentType.HUMAN:
        cv2.putText(img, f"{vehicle.id}", (scr_x-5, scr_y-20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)
    
    if vehicle.waiting_at_light:
        cv2.circle(img, (scr_x, scr_y-30), 4, (0,0,255), -1)
    elif vehicle.in_queue:
        cv2.circle(img, (scr_x-8, scr_y-30), 3, (0,255,255), -1)
        
    if vehicle.vehicle_ahead:
        ahead_x = SCREEN_WIDTH//2 + int(vehicle.vehicle_ahead.x - car_x)
        ahead_y = SIM_HEIGHT//2 + int(vehicle.vehicle_ahead.y - car_y)
        if 0 < ahead_x < SCREEN_WIDTH and 0 < ahead_y < SIM_HEIGHT:
            cv2.line(img, (scr_x, scr_y), (ahead_x, ahead_y), (255,255,0), 1)

def create_car_sprite(width=40, height=24, body_color=None):
    car_img = np.zeros((height, width, 4), dtype=np.uint8)
    
    if body_color is None:
        body_color = (50, 50, 220, 255)
    else:
        body_color = (*body_color, 255)
        
    window_color = (200, 200, 255, 255)
    tire_color = (30, 30, 30, 255)
    light_color = (0, 255, 255, 255)
    brake_color = (0, 0, 255, 255)
    
    cv2.rectangle(car_img, (4, 6), (width-4, height-6), body_color, -1)
    cv2.rectangle(car_img, (4, 6), (width-4, height-6), (30, 30, 180, 255), 2)
    cv2.rectangle(car_img, (22, 8), (32, 16), window_color, -1)
    cv2.rectangle(car_img, (14, 7), (24, 17), body_color, -1)
    cv2.circle(car_img, (8, 6), 3, tire_color, -1)
    cv2.circle(car_img, (width-8, 6), 3, tire_color, -1)
    cv2.circle(car_img, (8, height-6), 3, tire_color, -1)
    cv2.circle(car_img, (width-8, height-6), 3, tire_color, -1)
    cv2.circle(car_img, (width-4, 8), 2, light_color, -1)
    cv2.circle(car_img, (width-4, height-8), 2, light_color, -1)
    cv2.circle(car_img, (4, 8), 2, brake_color, -1)
    cv2.circle(car_img, (4, height-8), 2, brake_color, -1)
    
    return car_img

def snap_to_road(x, y):
    nearest_x = min(ROAD_X, key=lambda rx: abs(rx - x))
    nearest_y = min(ROAD_Y, key=lambda ry: abs(ry - y))
    
    if abs(nearest_x - x) <= abs(nearest_y - y):
        return (nearest_x, y)
    else:
        return (x, nearest_y)

def is_on_road(x, y):
    for rx in ROAD_X:
        if abs(x - rx) <= ROAD_HALF_WIDTH:
            return True
    for ry in ROAD_Y:
        if abs(y - ry) <= ROAD_HALF_WIDTH:
            return True
    return False

def get_drop_off_point(landmark_x, landmark_y):
    # Distance to each candidate road line
    best_v_road = min(ROAD_X, key=lambda rx: abs(rx - landmark_x))
    best_h_road = min(ROAD_Y, key=lambda ry: abs(ry - landmark_y))

    dist_to_v = abs(best_v_road - landmark_x)
    dist_to_h = abs(best_h_road - landmark_y)

    if dist_to_v <= dist_to_h:
        # Closest road is vertical — park on it, align Y with the landmark
        side_offset = 20 if landmark_x > best_v_road else -20
        road_x = best_v_road + side_offset
        # Clamp road_y to stay within the map; no snapping to intersections
        road_y = max(50, min(MAP_HEIGHT - 50, landmark_y))
        return (road_x, road_y)
    else:
        # Closest road is horizontal
        side_offset = 20 if landmark_y > best_h_road else -20
        road_y = best_h_road + side_offset
        road_x = max(50, min(MAP_WIDTH - 50, landmark_x))
        return (road_x, road_y)
def find_grid_path(start, goal):
    LANE_W = 18
    sx, sy = start
    gx, gy = goal

    # Nearest road grid lines for start and goal
    start_rx = min(ROAD_X, key=lambda rx: abs(rx - sx))
    start_ry = min(ROAD_Y, key=lambda ry: abs(ry - sy))
    goal_rx  = min(ROAD_X, key=lambda rx: abs(rx - gx))
    goal_ry  = min(ROAD_Y, key=lambda ry: abs(ry - gy))

    raw = []  

    # Start at current position
    raw.append((sx, sy, 0, 0))

    # Enter the road grid: slide to nearest intersection
    cur_x, cur_y = start_rx, start_ry

    # Decide horizontal-first or vertical-first
    h_dist = abs(goal_rx - start_rx)
    v_dist = abs(goal_ry - start_ry)

    if h_dist >= v_dist:
        # Horizontal leg first
        dx_sign = 1 if goal_rx >= cur_x else -1
        xs = sorted([x for x in ROAD_X
                     if min(cur_x, goal_rx) <= x <= max(cur_x, goal_rx)])
        if dx_sign < 0: xs = xs[::-1]
        for x in xs:
            raw.append((x, cur_y, dx_sign, 0))
        cur_x = goal_rx

        # Vertical leg
        dy_sign = 1 if goal_ry >= cur_y else -1
        ys = sorted([y for y in ROAD_Y
                     if min(cur_y, goal_ry) <= y <= max(cur_y, goal_ry)])
        if dy_sign < 0: ys = ys[::-1]
        for y in ys:
            raw.append((cur_x, y, 0, dy_sign))
        cur_y = goal_ry
    else:
        # Vertical leg
        dy_sign = 1 if goal_ry >= cur_y else -1
        ys = sorted([y for y in ROAD_Y
                     if min(cur_y, goal_ry) <= y <= max(cur_y, goal_ry)])
        if dy_sign < 0: ys = ys[::-1]
        for y in ys:
            raw.append((cur_x, y, 0, dy_sign))
        cur_y = goal_ry

        # Horizontal leg
        dx_sign = 1 if goal_rx >= cur_x else -1
        xs = sorted([x for x in ROAD_X
                     if min(cur_x, goal_rx) <= x <= max(cur_x, goal_rx)])
        if dx_sign < 0: xs = xs[::-1]
        for x in xs:
            raw.append((x, cur_y, dx_sign, 0))
        cur_x = goal_rx

    # Final destination
    raw.append((gx, gy, 0, 0))

    path = []
    for x, y, dxs, dys in raw:
        if dxs != 0:
            # Horizontal travel: offset Y
            path.append((x, y + LANE_W * dxs))
        elif dys != 0:
            # Vertical travel: offset X
            path.append((x + LANE_W * dys, y))
        else:
            # Start or end
            path.append((x, y))

    filtered = []
    for p in path:
        if not filtered or abs(p[0]-filtered[-1][0]) > 2 or abs(p[1]-filtered[-1][1]) > 2:
            filtered.append(p)

    return filtered

def rotate_sprite(sprite, angle):
    h, w = sprite.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, -angle, 1.0)
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]
    rotated = cv2.warpAffine(sprite, M, (new_w, new_h), 
                            borderMode=cv2.BORDER_CONSTANT,
                            borderValue=(0, 0, 0, 0))
    return rotated, (new_w // 2, new_h // 2)

def draw_sprite_on_image(background, sprite, x, y, shadow=False):
    h, w = sprite.shape[:2]
    y1, y2 = int(y - h//2), int(y - h//2) + h
    x1, x2 = int(x - w//2), int(x - w//2) + w
    
    if shadow:
        shadow_offset = 4
        shadow_y1, shadow_y2 = y1 + shadow_offset, y2 + shadow_offset
        shadow_x1, shadow_x2 = x1 + shadow_offset, x2 + shadow_offset
        if shadow_y1 >= 0 and shadow_x1 >= 0 and shadow_y2 < background.shape[0] and shadow_x2 < background.shape[1]:
            alpha = sprite[:, :, 3] / 255.0 * 0.3
            for c in range(3):
                background[shadow_y1:shadow_y2, shadow_x1:shadow_x2, c] = (
                    (1 - alpha) * background[shadow_y1:shadow_y2, shadow_x1:shadow_x2, c]
                )
    
    if y1 < 0 or y2 > background.shape[0] or x1 < 0 or x2 > background.shape[1]:
        sprite_y1, sprite_y2 = 0, h
        sprite_x1, sprite_x2 = 0, w
        
        if y1 < 0:
            sprite_y1 = -y1
            y1 = 0
        if y2 > background.shape[0]:
            sprite_y2 = h - (y2 - background.shape[0])
            y2 = background.shape[0]
        if x1 < 0:
            sprite_x1 = -x1
            x1 = 0
        if x2 > background.shape[1]:
            sprite_x2 = w - (x2 - background.shape[1])
            x2 = background.shape[1]
        
        sprite = sprite[sprite_y1:sprite_y2, sprite_x1:sprite_x2]
        if sprite.shape[0] == 0 or sprite.shape[1] == 0:
            return
        h, w = sprite.shape[:2]
        y2, x2 = y1 + h, x1 + w
    
    alpha = sprite[:, :, 3] / 255.0
    for c in range(3):
        background[y1:y2, x1:x2, c] = (
            alpha * sprite[:, :, c] + 
            (1 - alpha) * background[y1:y2, x1:x2, c]
        )

def create_building_icon(building_type, width=60, height=50):
    icon = np.zeros((height, width, 4), dtype=np.uint8)
    
    colors = {
        "gas": ((0, 100, 200, 255), (255, 255, 255, 255)),
        "school": ((200, 200, 50, 255), (50, 50, 50, 255)),
        "home": ((150, 100, 50, 255), (100, 50, 0, 255)),
        "park": ((100, 200, 100, 255), (0, 100, 0, 255)),
        "restaurant": ((50, 150, 50, 255), (255, 200, 0, 255)),
        "mall": ((200, 100, 200, 255), (100, 50, 100, 255)),
        "hospital": ((255, 255, 255, 255), (0, 0, 255, 255)),
        "bank": ((200, 150, 50, 255), (255, 255, 0, 255)),
        "police": ((100, 50, 150, 255), (255, 255, 255, 255)),
        "fire": ((50, 50, 200, 255), (255, 255, 255, 255)),
        "library": ((150, 50, 150, 255), (200, 200, 255, 255)),
        "airport": ((150, 150, 150, 255), (100, 100, 100, 255)),
        "stadium": ((50, 50, 150, 255), (200, 200, 200, 255)),
    }
    
    base_color, detail_color = colors.get(building_type, ((150, 150, 150, 255), (100, 100, 100, 255)))
    
    cv2.rectangle(icon, (5, 10), (width-5, height-5), base_color, -1)
    cv2.rectangle(icon, (5, 10), (width-5, height-5), (30, 30, 30, 255), 2)
    cv2.rectangle(icon, (3, 5), (width-3, 12), (40, 40, 40, 255), -1)
    
    if building_type == "gas":
        cv2.rectangle(icon, (width//2-8, 18), (width//2+8, 38), detail_color, -1)
        cv2.line(icon, (width//2, 18), (width//2, 12), detail_color, 3)
    elif building_type == "hospital":
        cx, cy = width//2, height//2 + 3
        cv2.rectangle(icon, (cx-3, cy-8), (cx+3, cy+8), detail_color, -1)
        cv2.rectangle(icon, (cx-8, cy-3), (cx+8, cy+3), detail_color, -1)
    elif building_type == "school":
        cv2.line(icon, (width//2, 15), (width//2, 35), detail_color, 2)
        cv2.rectangle(icon, (width//2, 15), (width//2+10, 22), detail_color, -1)
    elif building_type == "home":
        pts = np.array([[5, 10], [width//2, 2], [width-5, 10]], np.int32)
        cv2.fillPoly(icon, [pts], detail_color)
    elif building_type == "restaurant":
        cv2.line(icon, (width//2-5, 20), (width//2-5, 35), detail_color, 2)
        cv2.line(icon, (width//2+5, 20), (width//2+5, 35), detail_color, 2)
    elif building_type == "park":
        cv2.circle(icon, (width//2, 25), 8, detail_color, -1)
        cv2.rectangle(icon, (width//2-2, 33), (width//2+2, 40), (100, 50, 0, 255), -1)
    
    return icon

def parse_destination(text, car_x, car_y, user_id):
    """
    FIX 5: Save command now returns a proper 3-tuple so the caller never crashes.
    Returns (display_message, road_pos_or_None, original_pos_or_None)
    """
    text = text.lower().strip()
    
    save_match = re.match(r"save (?:this|location|place) as (.+)", text)
    if save_match:
        return "Save command processed", None, None
    
    favorite_commands = ["home", "work", "office", "gym", "school"]
    for cmd in favorite_commands:
        if text in [cmd, f"my {cmd}", f"go to {cmd}", f"take me to {cmd}", 
                   f"drive to {cmd}", f"navigate to {cmd}"]:
            fav = get_favorite(user_id, cmd)
            if fav:
                return fav["landmark_name"], (fav["x"], fav["y"]), (fav["x"], fav["y"])
            else:
                return f"No {cmd} saved yet", None, None
    
    text = re.sub(r"^(take me to|drive to|go to|navigate to|i want to go to|let's go to|nearest|closest)\s*", "", text)
    text = re.sub(r"^(the|a|an)\s+", "", text)
    text = text.strip(" .!?")
    
    type_keywords = {
        "gas": "gas", "station": "gas", "fuel": "gas", "petrol": "gas",
        "school": "school", "college": "school", "university": "school",
        "restaurant": "restaurant", "food": "restaurant", "eat": "restaurant", 
        "hungry": "restaurant", "burger": "restaurant", "pizza": "restaurant",
        "home": "home", "house": "home",
        "mall": "mall", "shopping": "mall", "shop": "mall",
        "hospital": "hospital", "doctor": "hospital", "medical": "hospital",
        "park": "park",
        "bank": "bank", "money": "bank", "atm": "bank",
        "police": "police", "cop": "police",
        "fire": "fire",
        "library": "library", "book": "library",
        "airport": "airport", "fly": "airport", "plane": "airport",
        "stadium": "stadium", "football": "stadium", "game": "stadium",
    }
    
    # Exact or substring name match
    for landmark in LANDMARKS:
        if landmark["name"].lower() in text or text in landmark["name"].lower():
            lx, ly = landmark["pos"]
            road_pos = get_drop_off_point(lx, ly)
            return landmark["name"], road_pos, (lx, ly)
    
    # Keyword match  find closest of that type
    for keyword, ltype in type_keywords.items():
        if keyword in text:
            closest, dist = find_closest_landmark(car_x, car_y, ltype)
            if closest:
                lx, ly = closest["pos"]
                road_pos = get_drop_off_point(lx, ly)
                return closest["name"], road_pos, (lx, ly)
    
    return None, None, None

def find_closest_landmark(car_x, car_y, landmark_type):
    closest = None
    min_dist = float('inf')
    for landmark in LANDMARKS:
        if landmark["type"] == landmark_type or landmark_type in landmark["name"].lower():
            dist = math.sqrt((landmark["pos"][0] - car_x)**2 + (landmark["pos"][1] - car_y)**2)
            if dist < min_dist:
                min_dist = dist
                closest = landmark
    return closest, min_dist

def registration_screen():
    username = ""
    password = ""
    confirm_password = ""
    active_field = "username"
    message = ""
    message_color = (0, 0, 255)
    
    while True:
        frame = np.zeros((500, 600, 3), dtype=np.uint8)
        frame[:] = (20, 20, 25)
        
        cv2.putText(frame, "CREATE ACCOUNT", (140, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        cv2.putText(frame, "Join AI Driver today", (200, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
        
        y_offset = 140
        
        cv2.putText(frame, "Username", (150, y_offset-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40), (40, 40, 45), -1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40),
                      (0, 255, 255) if active_field=="username" else (100, 100, 100), 2)
        cv2.putText(frame, username + ("_" if active_field=="username" else ""),
                    (160, y_offset+28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += 70
        
        cv2.putText(frame, "Password", (150, y_offset-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40), (40, 40, 45), -1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40),
                      (0, 255, 255) if active_field=="password" else (100, 100, 100), 2)
        hidden = "*" * len(password)
        cv2.putText(frame, hidden + ("_" if active_field=="password" else ""),
                    (160, y_offset+28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += 70
        
        cv2.putText(frame, "Confirm Password", (150, y_offset-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40), (40, 40, 45), -1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40),
                      (0, 255, 255) if active_field=="confirm" else (100, 100, 100), 2)
        hidden_conf = "*" * len(confirm_password)
        cv2.putText(frame, hidden_conf + ("_" if active_field=="confirm" else ""),
                    (160, y_offset+28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        if message:
            y_msg = 380
            words = message.split()
            lines = []
            current_line = ""
            for word in words:
                if len(current_line + word) < 40:
                    current_line += word + " "
                else:
                    lines.append(current_line.strip())
                    current_line = word + " "
            if current_line:
                lines.append(current_line.strip())
            
            for i, line in enumerate(lines):
                cv2.putText(frame, line, (150, y_msg + i*20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, message_color, 1)
        
        cv2.putText(frame, "TAB: Next Field | ENTER: Register | ESC: Back to Login",
                    (100, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)
        
        cv2.imshow("AI Driver - Registration", frame)
        key = cv2.waitKey(30) & 0xFF
        
        if key == 27:
            cv2.destroyWindow("AI Driver - Registration")
            return None
        elif key == 13:
            if not username or not password or not confirm_password:
                message = "All fields are required"
                message_color = (0, 0, 255)
            elif password != confirm_password:
                message = "Passwords do not match"
                message_color = (0, 0, 255)
                confirm_password = ""
            else:
                success, msg, user_id = register_user(username, password)
                if success:
                    message = "Registration successful! Redirecting..."
                    message_color = (0, 255, 0)
                    cv2.imshow("AI Driver - Registration", frame)
                    cv2.waitKey(1000)
                    cv2.destroyWindow("AI Driver - Registration")
                    return user_id
                else:
                    message = msg
                    message_color = (0, 0, 255)
        elif key == 9:
            if active_field == "username":
                active_field = "password"
            elif active_field == "password":
                active_field = "confirm"
            else:
                active_field = "username"
        elif key == 8:
            if active_field == "username":
                username = username[:-1]
            elif active_field == "password":
                password = password[:-1]
            else:
                confirm_password = confirm_password[:-1]
        elif 32 <= key < 127:
            char = chr(key)
            if active_field == "username" and len(username) < 20:
                if char.isalnum() or char == '_':
                    username += char
            elif active_field == "password" and len(password) < 20:
                password += char
            elif active_field == "confirm" and len(confirm_password) < 20:
                confirm_password += char

def login_screen():
    username = ""
    password = ""
    active_field = "username"
    message = ""
    message_color = (0, 0, 255)
    
    while True:
        frame = np.zeros((500, 600, 3), dtype=np.uint8)
        frame[:] = (20, 20, 25)
        
        cv2.putText(frame, "AI DRIVER LOGIN", (160, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        
        cv2.putText(frame, "Username", (150, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.rectangle(frame, (150, 140), (450, 180), (40, 40, 45), -1)
        cv2.rectangle(frame, (150, 140), (450, 180),
                      (0, 255, 255) if active_field=="username" else (100, 100, 100), 2)
        cv2.putText(frame, username + ("_" if active_field=="username" else ""),
                    (160, 168), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        cv2.putText(frame, "Password", (150, 220),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.rectangle(frame, (150, 230), (450, 270), (40, 40, 45), -1)
        cv2.rectangle(frame, (150, 230), (450, 270),
                      (0, 255, 255) if active_field=="password" else (100, 100, 100), 2)
        hidden = "*" * len(password)
        cv2.putText(frame, hidden + ("_" if active_field=="password" else ""),
                    (160, 258), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        if message:
            cv2.putText(frame, message, (150, 310),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, message_color, 1)
        
        cv2.rectangle(frame, (100, 340), (500, 420), (35, 35, 40), -1)
        cv2.rectangle(frame, (100, 340), (500, 420), (80, 80, 80), 1)
        
        cv2.putText(frame, "CONTROLS:", (120, 365),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)
        cv2.putText(frame, "ENTER - Login", (120, 390),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        cv2.putText(frame, "TAB - Switch Field", (280, 390),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        cv2.putText(frame, "R - Register New Account", (120, 410),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        cv2.putText(frame, "ESC - Quit", (280, 410),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        
        cv2.imshow("AI Driver - Login", frame)
        key = cv2.waitKey(30) & 0xFF
        
        if key == 27:
            cv2.destroyAllWindows()
            sys.exit(0)
        elif key == ord('r') or key == ord('R'):
            cv2.destroyWindow("AI Driver - Login")
            user_id = registration_screen()
            if user_id:
                return user_id
            cv2.namedWindow("AI Driver - Login")
        elif key == 13:
            if not username or not password:
                message = "Please enter username and password"
                message_color = (0, 0, 255)
            else:
                user_id = authenticate_user(username, password)
                if user_id:
                    cv2.destroyWindow("AI Driver - Login")
                    return user_id
                else:
                    message = "Invalid username or password"
                    message_color = (0, 0, 255)
                    password = ""
        elif key == 9:
            active_field = "password" if active_field=="username" else "username"
        elif key == 8:
            if active_field == "username":
                username = username[:-1]
            else:
                password = password[:-1]
        elif 32 <= key < 127:
            char = chr(key)
            if active_field == "username" and len(username) < 20:
                if char.isalnum() or char == '_':
                    username += char
            elif active_field == "password" and len(password) < 20:
                password += char

# ==================== MAIN CONFIGURATION ====================

SCREEN_WIDTH = 1200
SIM_HEIGHT = 700
PANEL_HEIGHT = 250
TOTAL_HEIGHT = SIM_HEIGHT + PANEL_HEIGHT

MAP_WIDTH = 3000
MAP_HEIGHT = 2500

ROAD_X = [200, 600, 1100, 1600, 2100, 2600]
ROAD_Y = [200, 700, 1300, 1900, 2400]
ROAD_HALF_WIDTH = 60

LANDMARKS = [
    {"name": "Your Home", "pos": (400, 400), "color": (150, 100, 50), "size": (90, 80), "type": "home"},
    {"name": "Shell Gas", "pos": (150, 150), "color": (0, 100, 200), "size": (80, 70), "type": "gas"},
    {"name": "Lincoln High", "pos": (850, 350), "color": (200, 200, 50), "size": (100, 90), "type": "school"},
    {"name": "Burger King", "pos": (1300, 150), "color": (50, 150, 50), "size": (70, 70), "type": "restaurant"},
    {"name": "Westfield Mall", "pos": (1800, 450), "color": (200, 100, 200), "size": (120, 110), "type": "mall"},
    {"name": "Airport", "pos": (2400, 300), "color": (150, 150, 150), "size": (150, 130), "type": "airport"},
    {"name": "General Hospital", "pos": (350, 1000), "color": (255, 255, 255), "size": (110, 100), "type": "hospital"},
    {"name": "Police Station", "pos": (150, 1100), "color": (100, 50, 150), "size": (90, 85), "type": "police"},
    {"name": "City Library", "pos": (900, 1000), "color": (150, 50, 150), "size": (85, 80), "type": "library"},
    {"name": "Central Park", "pos": (1300, 1100), "color": (100, 200, 100), "size": (120, 100), "type": "park"},
    {"name": "Chase Bank", "pos": (1800, 1000), "color": (200, 150, 50), "size": (80, 75), "type": "bank"},
    {"name": "Pizza Hut", "pos": (2400, 1100), "color": (60, 160, 60), "size": (75, 75), "type": "restaurant"},
    {"name": "Stadium", "pos": (400, 1600), "color": (50, 50, 150), "size": (130, 120), "type": "stadium"},
    {"name": "Fire Station", "pos": (150, 1750), "color": (50, 50, 200), "size": (90, 85), "type": "fire"},
    {"name": "Community College", "pos": (850, 1600), "color": (180, 180, 40), "size": (120, 110), "type": "school"},
    {"name": "McDonald's", "pos": (1300, 1750), "color": (70, 170, 70), "size": (80, 75), "type": "restaurant"},
    {"name": "Galleria Mall", "pos": (1850, 1600), "color": (210, 110, 210), "size": (130, 120), "type": "mall"},
    {"name": "St. Mary's Hospital", "pos": (2400, 1750), "color": (240, 240, 240), "size": (100, 90), "type": "hospital"},
    {"name": "Riverside Park", "pos": (400, 2200), "color": (110, 210, 110), "size": (130, 110), "type": "park"},
    {"name": "Chevron", "pos": (150, 2300), "color": (0, 110, 210), "size": (85, 75), "type": "gas"},
    {"name": "Wells Fargo", "pos": (900, 2200), "color": (210, 160, 60), "size": (85, 80), "type": "bank"},
    {"name": "Taco Bell", "pos": (1350, 2300), "color": (55, 155, 55), "size": (75, 75), "type": "restaurant"},
    {"name": "Mom's House", "pos": (1850, 2200), "color": (140, 90, 40), "size": (90, 85), "type": "home"},
    {"name": "Friend's House", "pos": (2400, 2300), "color": (160, 110, 60), "size": (90, 85), "type": "home"},
]

def create_map():
    img = np.ones((MAP_HEIGHT, MAP_WIDTH, 3), dtype=np.uint8)
    img[:] = (70, 130, 70)
    
    road_color = (40, 40, 40)
    line_color = (0, 160, 255)
    rw = ROAD_HALF_WIDTH
    
    for x in ROAD_X:
        cv2.rectangle(img, (x-rw, 0), (x+rw, MAP_HEIGHT), road_color, -1)
        for y in range(0, MAP_HEIGHT, 80):
            cv2.line(img, (x, y), (x, min(y+40, MAP_HEIGHT)), line_color, 3)
    
    for y in ROAD_Y:
        cv2.rectangle(img, (0, y-rw), (MAP_WIDTH, y+rw), road_color, -1)
        for x in range(0, MAP_WIDTH, 80):
            cv2.line(img, (x, y), (min(x+40, MAP_WIDTH), y), line_color, 3)
    
    building_icons = {}
    for ltype in set(l["type"] for l in LANDMARKS):
        building_icons[ltype] = create_building_icon(ltype, 60, 50)
    
    for landmark in LANDMARKS:
        x, y = landmark["pos"]
        icon = building_icons.get(landmark["type"], building_icons["home"])
        ih, iw = icon.shape[:2]
        x1, y1 = x - iw//2, y - ih//2
        
        if x1 >= 0 and y1 >= 0 and x1 + iw < MAP_WIDTH and y1 + ih < MAP_HEIGHT:
            alpha = icon[:, :, 3] / 255.0
            for c in range(3):
                img[y1:y1+ih, x1:x1+iw, c] = (
                    alpha * icon[:, :, c] + 
                    (1 - alpha) * img[y1:y1+ih, x1:x1+iw, c]
                )
        
        cv2.putText(img, landmark["name"][:12], (x-45, y+ih//2+15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)
    
    return img

# ==================== MAIN EXECUTION ====================

init_database()
current_user_id = login_screen()

world_map = create_map()

# Create traffic lights
traffic_lights = []
light_id = 0
for i, rx in enumerate(ROAD_X[1:-1]):
    for j, ry in enumerate(ROAD_Y[1:-1]):
        if (i + j) % 2 == 0:
            is_vertical = (i % 2 == 0)
            traffic_lights.append(TrafficLight(rx, ry, 'vertical' if is_vertical else 'horizontal', light_id))
            light_id += 1

# Create vehicles
vehicles = []
next_vehicle_id = 1

# Player vehicle — start on a road intersection
player_vehicle = VehicleAgent(600, 700, AgentType.HUMAN, 0, (50, 50, 220))
vehicles.append(player_vehicle)

def spawn_ai_vehicle(agent_type=None):
    global next_vehicle_id

    if agent_type is None:
        agent_type = random.choices(
            [AgentType.AI_RANDOM, AgentType.AI_EFFICIENT, AgentType.AI_AGGRESSIVE],
            weights=[0.55, 0.30, 0.15]
        )[0]

    # Try up to 20 times to find a spawn point not too close to existing cars
    spawn_x, spawn_y = None, None
    for _ in range(20):
        rx = random.choice(ROAD_X)
        ry = random.choice(ROAD_Y)
        # Spawn either on a horizontal or vertical road segment, not just at intersections
        if random.random() > 0.5:
            sx = rx
            sy = ry + random.randint(-200, 200)
            sy = max(60, min(MAP_HEIGHT - 60, sy))
        else:
            sx = rx + random.randint(-200, 200)
            sx = max(60, min(MAP_WIDTH - 60, sx))
            sy = ry
        # Make sure it's actually on a road
        if not is_on_road(sx, sy):
            continue
        # Not too close to any existing car
        if any(math.sqrt((v.x-sx)**2 + (v.y-sy)**2) < 100 for v in vehicles):
            continue
        spawn_x, spawn_y = sx, sy
        break

    if spawn_x is None:
        spawn_x = random.choice(ROAD_X)
        spawn_y = random.choice(ROAD_Y)

    vehicle = VehicleAgent(spawn_x, spawn_y, agent_type, next_vehicle_id)

    # Pick a destination
    if LANDMARKS:
        if agent_type == AgentType.AI_EFFICIENT:
            target = min(LANDMARKS, key=lambda l:
                math.sqrt((l["pos"][0]-spawn_x)**2 + (l["pos"][1]-spawn_y)**2))
        elif agent_type == AgentType.AI_AGGRESSIVE:
            dists  = [math.sqrt((l["pos"][0]-spawn_x)**2+(l["pos"][1]-spawn_y)**2)
                      for l in LANDMARKS]
            total  = sum(dists) or 1
            target = random.choices(LANDMARKS, weights=[d/total for d in dists], k=1)[0]
        else:
            target = random.choice(LANDMARKS)

        dest_pos = get_drop_off_point(target["pos"][0], target["pos"][1])
        # set_destination sets the angle toward destination and snaps to lane
        vehicle.set_destination(target["name"], dest_pos, target["pos"])
    else:
        # No landmarks
        nearest_x = min(ROAD_X, key=lambda rx: abs(rx - spawn_x))
        nearest_y = min(ROAD_Y, key=lambda ry: abs(ry - spawn_y))
        if abs(spawn_x - nearest_x) < abs(spawn_y - nearest_y):
            vehicle.angle = random.choice([90, 270])
        else:
            vehicle.angle = random.choice([0, 180])
        vehicle._update_lane_direction(0, 0)
        vehicle._snap_to_lane()

    # Seed the idle delay so the car leaves immediately
    vehicle._idle_delay = 0

    vehicles.append(vehicle)
    next_vehicle_id += 1
    return vehicle

# Module-level reference so _unstick() can read the vehicles list
_all_vehicles_ref = vehicles

# Initial traffic — spawn_ai_vehicle already assigns a destination
for _ in range(12):
    spawn_ai_vehicle()

chat_history = []
running = True
current_input = ""
input_active = False
show_stats = True

def add_chat(sender, message):
    chat_history.append((sender, message))
    if len(chat_history) > 6:
        chat_history.pop(0)

def draw_traffic_light(img, light, car_x, car_y):
    scr_x = SCREEN_WIDTH//2 + int(light.x - car_x)
    scr_y = SIM_HEIGHT//2 + int(light.y - car_y)
    
    if not (0 < scr_x < SCREEN_WIDTH and 0 < scr_y < SIM_HEIGHT):
        return
        
    cv2.line(img, (scr_x, scr_y), (scr_x, scr_y - 30), (80, 80, 80), 3)
    cv2.rectangle(img, (scr_x-8, scr_y-45), (scr_x+8, scr_y-25), (40, 40, 40), -1)
    
    if light.state == TrafficLightState.RED:
        color = (0, 0, 255)
    elif light.state == TrafficLightState.YELLOW:
        color = (0, 255, 255)
    else:
        color = (0, 255, 0)
    
    cv2.circle(img, (scr_x, scr_y-35), 5, color, -1)
    
    if light.queue_length > 0:
        cv2.putText(img, str(light.queue_length), (scr_x+10, scr_y-35),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)

add_chat("System", "AI Driver ready! Type a destination below.")
add_chat("System", "Try: 'airport', 'mall', 'hospital', 'gas station'")

frame_count = 0
while running:
    frame = np.zeros((TOTAL_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
    sim = frame[0:SIM_HEIGHT, 0:SCREEN_WIDTH]
    
    if frame_count % 90 == 0 and len(vehicles) < 25:
        spawn_ai_vehicle()
    
    for light in traffic_lights:
        light.update(vehicles, traffic_lights)
    
    for vehicle in vehicles[:]:
        vehicle.update(world_map, traffic_lights, vehicles)
        
        if vehicle.agent_type != AgentType.HUMAN and vehicle.state == "arrived":
            # Despawn immediately on arrival and spawn a fresh car elsewhere
            vehicles.remove(vehicle)
            if len(vehicles) < 22:
                spawn_ai_vehicle()
            continue


        if vehicle.stuck_counter > 200 and vehicle.agent_type == AgentType.HUMAN:
            vehicle.x, vehicle.y = snap_to_road(vehicle.x, vehicle.y)
            vehicle.stuck_counter = 0
    
    cx, cy = int(player_vehicle.x), int(player_vehicle.y)
    mx1 = max(0, cx - SCREEN_WIDTH//2)
    my1 = max(0, cy - SIM_HEIGHT//2)
    
    visible = world_map[my1:min(MAP_HEIGHT, my1+SIM_HEIGHT), mx1:min(MAP_WIDTH, mx1+SCREEN_WIDTH)]
    vx = SCREEN_WIDTH//2 - (cx - mx1)
    vy = SIM_HEIGHT//2 - (cy - my1)
    
    h, w = visible.shape[:2]
    y1, y2 = max(0, vy), min(SIM_HEIGHT, vy+h)
    x1, x2 = max(0, vx), min(SCREEN_WIDTH, vx+w)
    
    if y2 > y1 and x2 > x1 and h > 0 and w > 0:
        sim[y1:y2, x1:x2] = visible[max(0,-vy):max(0,-vy)+(y2-y1), max(0,-vx):max(0,-vx)+(x2-x1)]
    
    for light in traffic_lights:
        draw_traffic_light(sim, light, player_vehicle.x, player_vehicle.y)
    
    sorted_vehicles = sorted(vehicles, key=lambda v: v.y)
    for vehicle in sorted_vehicles:
        is_player = (vehicle.id == 0)
        draw_vehicle(sim, vehicle, player_vehicle.x, player_vehicle.y, is_player)
    
    # Draw route path for player
    if player_vehicle.state == "driving" and player_vehicle.path:
        for i in range(len(player_vehicle.path)-1):
            px1 = SCREEN_WIDTH//2 + int(player_vehicle.path[i][0] - player_vehicle.x)
            py1 = SIM_HEIGHT//2 + int(player_vehicle.path[i][1] - player_vehicle.y)
            px2 = SCREEN_WIDTH//2 + int(player_vehicle.path[i+1][0] - player_vehicle.x)
            py2 = SIM_HEIGHT//2 + int(player_vehicle.path[i+1][1] - player_vehicle.y)
            cv2.line(sim, (px1, py1), (px2, py2), (0, 255, 255), 2)
        # Draw next waypoint marker
        if player_vehicle.waypoint_idx < len(player_vehicle.path):
            nwx, nwy = player_vehicle.path[player_vehicle.waypoint_idx]
            nsx = SCREEN_WIDTH//2 + int(nwx - player_vehicle.x)
            nsy = SIM_HEIGHT//2 + int(nwy - player_vehicle.y)
            cv2.circle(sim, (nsx, nsy), 6, (255, 128, 0), -1)
    
    cv2.rectangle(frame, (0, SIM_HEIGHT), (SCREEN_WIDTH, TOTAL_HEIGHT), (30,30,30), -1)
    cv2.line(frame, (0, SIM_HEIGHT), (SCREEN_WIDTH, SIM_HEIGHT), (100,100,100), 3)

    
    status = f"Player: {player_vehicle.state.upper()}"
    if player_vehicle.in_queue:
        status += " [FOLLOWING]"
    if player_vehicle.destination_name:
        status += f" | To: {player_vehicle.destination_name[:15]}"
    cv2.putText(sim, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
    cv2.putText(sim, f"Speed: {player_vehicle.speed:.1f}  WP: {player_vehicle.waypoint_idx}/{max(0,len(player_vehicle.path)-1)}", 
                (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)
    
    y = SIM_HEIGHT + 30
    for sender, msg in chat_history:
        if sender == "User":
            color = (0, 200, 255)
            prefix = "You: "
        elif sender == "Driver":
            color = (50, 255, 50)
            prefix = "Driver: "
        else:
            color = (200, 200, 200)
            prefix = ""
        cv2.putText(frame, prefix + msg[:70], (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y += 25
    
    input_y = TOTAL_HEIGHT - 40
    cv2.rectangle(frame, (20, input_y-10), (SCREEN_WIDTH-120, input_y+20), (60,60,60), -1)
    cv2.putText(frame, "> " + current_input + ("_" if input_active else ""), (30, input_y+10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
    
    if show_stats:
        total_wait = sum(v.total_wait_time for v in vehicles)
        avg_speed = sum(v.speed for v in vehicles) / len(vehicles) if vehicles else 0
        in_queue = len([v for v in vehicles if v.in_queue])
        
        cv2.rectangle(frame, (20, SIM_HEIGHT+130), (320, SIM_HEIGHT+220), (30, 30, 30), -1)
        cv2.putText(frame, "TRAFFIC STATS", (30, SIM_HEIGHT+150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(frame, f"Vehicles: {len(vehicles)}  Queued: {in_queue}", (30, SIM_HEIGHT+170),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        cv2.putText(frame, f"Avg Speed: {avg_speed:.1f}  Wait: {total_wait:.0f}s", (30, SIM_HEIGHT+190),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        cv2.putText(frame, "1=Random  2=Efficient  3=Aggressive  A=Toggle lights  T=Stats",
                    (30, SIM_HEIGHT+210), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (150, 150, 150), 1)
    
    cv2.putText(frame, "Blue=You  Red=Random  Green=Efficient  Yellow=Aggressive | dot=Following", 
                (20, TOTAL_HEIGHT-10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150,150,150), 1)
    
    cv2.imshow("AI Driver - Realistic Traffic", frame)
    
    key = cv2.waitKey(30) & 0xFF
    
    if key == 27 or key == ord('q'):
        running = False
    elif key == ord('1'):
        spawn_ai_vehicle(AgentType.AI_RANDOM)
        add_chat("System", "Spawned: Random AI")
    elif key == ord('2'):
        spawn_ai_vehicle(AgentType.AI_EFFICIENT)
        add_chat("System", "Spawned: Efficient AI")
    elif key == ord('3'):
        spawn_ai_vehicle(AgentType.AI_AGGRESSIVE)
        add_chat("System", "Spawned: Aggressive AI")
    elif key == ord('t'):
        show_stats = not show_stats
    elif key == ord('a'):
        for light in traffic_lights:
            light.adaptive_mode = not light.adaptive_mode
        mode = "AI-Adaptive" if traffic_lights[0].adaptive_mode else "Fixed-Timing"
        add_chat("System", f"Traffic lights: {mode}")
    elif key == 13 and current_input.strip():
        user_text = current_input.strip()
        add_chat("User", user_text)
        
        dest_name, road_pos, orig_pos = parse_destination(
            user_text, player_vehicle.x, player_vehicle.y, current_user_id
        )
        
        if dest_name and road_pos:
            player_vehicle.set_destination(dest_name, road_pos, orig_pos)
            add_chat("Driver", f"Navigating to {dest_name}...")
        elif dest_name:
            # Message but no navigation target (e.g. "No home saved yet")
            add_chat("Driver", dest_name)
        else:
            add_chat("Driver", "Unknown destination. Try: 'airport', 'mall', 'hospital'")
        
        current_input = ""
        input_active = False
    elif key == 8:
        current_input = current_input[:-1]
    elif 32 <= key < 127 and len(current_input) < 60:
        current_input += chr(key)
        input_active = True
    
    frame_count += 1

cv2.destroyAllWindows()
sys.exit(0)
