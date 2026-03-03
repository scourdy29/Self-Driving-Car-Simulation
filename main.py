import cv2
import numpy as np
from datetime import datetime
import re
import sys
import random
import sqlite3
import os
import hashlib

# Database setup
DB_PATH = "ai_driver.db"

def init_database():
    """Initialize SQLite database with tables for users, favorites, and history"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Favorites table
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
    
    # History table
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
    
    # Preferences table
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
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_user_exists(username):
    """Check if username already exists in database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def register_user(username, password):
    """Register a new user. Returns (success, message, user_id)"""
    # Validation
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
    
    # Create user
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        hashed_pw = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed_pw)
        )
        user_id = cursor.lastrowid
        conn.commit()
        return True, "Registration successful", user_id
    except Exception as e:
        return False, f"Database error: {str(e)}", None
    finally:
        conn.close()

def authenticate_user(username, password):
    """Authenticate existing user. Returns user_id or None"""
    if not username or not password:
        return None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        stored_hash = result[1]
        if stored_hash == hash_password(password):
            return result[0]
    return None

def get_or_create_user(username):
    """Legacy function - now requires registration first"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def add_favorite(user_id, name, landmark_name, pos_x, pos_y, category="general"):
    """Add a favorite location for user"""
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
    """Get favorite location by name"""
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

def get_all_favorites(user_id):
    """Get all favorites for user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT name, landmark_name, pos_x, pos_y, category FROM favorites 
        WHERE user_id = ?
    ''', (user_id,))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{"name": r[0], "landmark": r[1], "x": r[2], "y": r[3], "category": r[4]} for r in results]

def add_to_history(user_id, landmark_name, pos_x, pos_y):
    """Add destination to history"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if this destination exists in history
    cursor.execute('''
        SELECT id, frequency FROM history 
        WHERE user_id = ? AND landmark_name = ?
    ''', (user_id, landmark_name))
    
    result = cursor.fetchone()
    
    if result:
        # Update frequency
        cursor.execute('''
            UPDATE history SET frequency = ?, visited_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (result[1] + 1, result[0]))
    else:
        # Insert new
        cursor.execute('''
            INSERT INTO history (user_id, landmark_name, pos_x, pos_y)
            VALUES (?, ?, ?, ?)
        ''', (user_id, landmark_name, pos_x, pos_y))
    
    conn.commit()
    conn.close()

def get_recent_destinations(user_id, limit=5):
    """Get recent destinations for user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT landmark_name, pos_x, pos_y, visited_at, frequency
        FROM history 
        WHERE user_id = ?
        ORDER BY visited_at DESC
        LIMIT ?
    ''', (user_id, limit))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{"name": r[0], "x": r[1], "y": r[2], "last_visit": r[3], "frequency": r[4]} for r in results]

def get_frequent_destinations(user_id, limit=3):
    """Get most frequent destinations"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT landmark_name, pos_x, pos_y, frequency
        FROM history 
        WHERE user_id = ?
        ORDER BY frequency DESC
        LIMIT ?
    ''', (user_id, limit))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{"name": r[0], "x": r[1], "y": r[2], "frequency": r[3]} for r in results]

def set_preference(user_id, key, value):
    """Set user preference"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO preferences (user_id, pref_key, pref_value)
        VALUES (?, ?, ?)
    ''', (user_id, key, value))
    
    conn.commit()
    conn.close()

def get_preference(user_id, key, default=None):
    """Get user preference"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT pref_value FROM preferences 
        WHERE user_id = ? AND pref_key = ?
    ''', (user_id, key))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else default

def draw_rounded_rect(img, pt1, pt2, color, thickness=-1, radius=10):
    """Draw a rectangle with rounded corners"""
    x1, y1 = pt1
    x2, y2 = pt2
    
    # Ensure radius isn't too large
    radius = min(radius, (x2-x1)//2, (y2-y1)//2)
    
    if thickness == -1:
        # Filled rectangle
        cv2.rectangle(img, (x1+radius, y1), (x2-radius, y2), color, -1)
        cv2.rectangle(img, (x1, y1+radius), (x2, y2-radius), color, -1)
        cv2.circle(img, (x1+radius, y1+radius), radius, color, -1)
        cv2.circle(img, (x2-radius, y1+radius), radius, color, -1)
        cv2.circle(img, (x1+radius, y2-radius), radius, color, -1)
        cv2.circle(img, (x2-radius, y2-radius), radius, color, -1)
    else:
        cv2.rectangle(img, pt1, pt2, color, thickness)

def registration_screen():
    """Registration screen with validation"""
    username = ""
    password = ""
    confirm_password = ""
    active_field = "username"
    message = ""
    message_color = (0, 0, 255)  # Red for errors
    success = False
    
    while True:
        frame = np.zeros((500, 600, 3), dtype=np.uint8)
        frame[:] = (20, 20, 25)  # Dark blue gray background
        
        # Title
        cv2.putText(frame, "CREATE ACCOUNT", (140, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        
        # Subtitle
        cv2.putText(frame, "Join AI Driver today", (200, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
        
        y_offset = 140
        
        # Username field
        cv2.putText(frame, "Username", (150, y_offset-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40), (40, 40, 45), -1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40),
                      (0, 255, 255) if active_field=="username" else (100, 100, 100), 2)
        cv2.putText(frame, username + ("_" if active_field=="username" else ""),
                    (160, y_offset+28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += 70
        
        # Password field
        cv2.putText(frame, "Password", (150, y_offset-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40), (40, 40, 45), -1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40),
                      (0, 255, 255) if active_field=="password" else (100, 100, 100), 2)
        hidden = "*" * len(password)
        cv2.putText(frame, hidden + ("_" if active_field=="password" else ""),
                    (160, y_offset+28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += 70
        
        # Confirm Password field
        cv2.putText(frame, "Confirm Password", (150, y_offset-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40), (40, 40, 45), -1)
        cv2.rectangle(frame, (150, y_offset), (450, y_offset+40),
                      (0, 255, 255) if active_field=="confirm" else (100, 100, 100), 2)
        hidden_conf = "*" * len(confirm_password)
        cv2.putText(frame, hidden_conf + ("_" if active_field=="confirm" else ""),
                    (160, y_offset+28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Message/Error display
        if message:
            y_msg = 380
            # Split long messages
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
        
        # Instructions
        cv2.putText(frame, "TAB: Next Field | ENTER: Register | ESC: Back to Login",
                    (100, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)
        
        cv2.imshow("AI Driver - Registration", frame)
        key = cv2.waitKey(30) & 0xFF
        
        if key == 27:  # ESC - go back to login
            cv2.destroyWindow("AI Driver - Registration")
            return None
        elif key == 13:  # ENTER - attempt registration
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
        elif key == 9:  # TAB - cycle fields
            if active_field == "username":
                active_field = "password"
            elif active_field == "password":
                active_field = "confirm"
            else:
                active_field = "username"
        elif key == 8:  # Backspace
            if active_field == "username":
                username = username[:-1]
            elif active_field == "password":
                password = password[:-1]
            else:
                confirm_password = confirm_password[:-1]
        elif 32 <= key < 127:  # Printable characters
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
        frame[:] = (20, 20, 25)  # Dark blue gray background
        
        # Title
        cv2.putText(frame, "AI DRIVER LOGIN", (160, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        
        # Username field
        cv2.putText(frame, "Username", (150, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.rectangle(frame, (150, 140), (450, 180), (40, 40, 45), -1)
        cv2.rectangle(frame, (150, 140), (450, 180),
                      (0, 255, 255) if active_field=="username" else (100, 100, 100), 2)
        cv2.putText(frame, username + ("_" if active_field=="username" else ""),
                    (160, 168), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Password field
        cv2.putText(frame, "Password", (150, 220),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.rectangle(frame, (150, 230), (450, 270), (40, 40, 45), -1)
        cv2.rectangle(frame, (150, 230), (450, 270),
                      (0, 255, 255) if active_field=="password" else (100, 100, 100), 2)
        hidden = "*" * len(password)
        cv2.putText(frame, hidden + ("_" if active_field=="password" else ""),
                    (160, 258), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Message display
        if message:
            cv2.putText(frame, message, (150, 310),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, message_color, 1)
        
        # Instructions box
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
        
        if key == 27:  # ESC - quit
            cv2.destroyAllWindows()
            sys.exit(0)
        elif key == ord('r') or key == ord('R'):  # R - go to registration
            cv2.destroyWindow("AI Driver - Login")
            user_id = registration_screen()
            if user_id:
                return user_id
            # If registration was cancelled, reopen login
            cv2.namedWindow("AI Driver - Login")
        elif key == 13:  # ENTER - login
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
        elif key == 9:  # TAB - switch field
            active_field = "password" if active_field=="username" else "username"
        elif key == 8:  # Backspace
            if active_field == "username":
                username = username[:-1]
            else:
                password = password[:-1]
        elif 32 <= key < 127:  # Printable characters
            char = chr(key)
            if active_field == "username" and len(username) < 20:
                if char.isalnum() or char == '_':
                    username += char
            elif active_field == "password" and len(password) < 20:
                password += char

# Initialize database
init_database()

# Run login/registration flow
current_user_id = login_screen()

# MAIN CODE

SCREEN_WIDTH = 1200
SIM_HEIGHT = 700
PANEL_HEIGHT = 250
TOTAL_HEIGHT = SIM_HEIGHT + PANEL_HEIGHT

MAP_WIDTH = 3000
MAP_HEIGHT = 2500

# Car state
car_x = 600.0
car_y = 300.0
car_angle = 0
car_speed = 0
max_speed = 5.0
car_state = "idle"
stuck_counter = 0
last_pos = (car_x, car_y)

# Tire tracks
tire_tracks = []
MAX_TRACKS = 100

# Navigation
current_destination = None
destination_name = None
original_goal = None
path = []
waypoint_idx = 0

# Road grid
ROAD_X = [200, 600, 1100, 1600, 2100, 2600]
ROAD_Y = [200, 700, 1300, 1900, 2400]
ROAD_HALF_WIDTH = 60

# Traffic lights
traffic_lights = []
LIGHT_CYCLE = 300
LIGHT_RED_DURATION = 150

def init_traffic_lights():
    lights = []
    for i, rx in enumerate(ROAD_X[1:-1]):
        for j, ry in enumerate(ROAD_Y[1:-1]):
            if (i + j) % 2 == 0:
                is_vertical_priority = (i % 2 == 0)
                lights.append({
                    'x': rx,
                    'y': ry,
                    'state': 'green',
                    'timer': random.randint(0, LIGHT_CYCLE),
                    'orientation': 'vertical' if is_vertical_priority else 'horizontal'
                })
    return lights

def snap_to_road(x, y):
    """Snap position to nearest road center"""
    nearest_x = min(ROAD_X, key=lambda rx: abs(rx - x))
    nearest_y = min(ROAD_Y, key=lambda ry: abs(ry - y))
    
    if abs(nearest_x - x) <= abs(nearest_y - y):
        return (nearest_x, y)
    else:
        return (x, nearest_y)

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

traffic_lights = init_traffic_lights()
chat_history = []
running = True

def add_chat(sender, message):
    chat_history.append((sender, message))
    if len(chat_history) > 8:
        chat_history.pop(0)

def find_closest_landmark(car_x, car_y, landmark_type):
    closest = None
    min_dist = float('inf')
    for landmark in LANDMARKS:
        if landmark["type"] == landmark_type or landmark_type in landmark["name"].lower():
            dist = np.sqrt((landmark["pos"][0] - car_x)**2 + (landmark["pos"][1] - car_y)**2)
            if dist < min_dist:
                min_dist = dist
                closest = landmark
    return closest, min_dist

def get_drop_off_point(landmark_x, landmark_y):
    """Get drop-off point on road nearest to building"""
    nearest_x = min(ROAD_X, key=lambda rx: abs(rx - landmark_x))
    nearest_y = min(ROAD_Y, key=lambda ry: abs(ry - landmark_y))
    
    dist_to_v = abs(nearest_x - landmark_x)
    dist_to_h = abs(nearest_y - landmark_y)
    
    if dist_to_v < dist_to_h:
        offset = 35 if landmark_x > nearest_x else -35
        return (nearest_x + offset, landmark_y)
    else:
        offset = 35 if landmark_y > nearest_y else -35
        return (landmark_x, nearest_y + offset)

def parse_destination(text, car_x, car_y, user_id):
    text = text.lower().strip()
    
    # Check for save command
    save_match = re.match(r"save (?:this|location|place) as (.+)", text)
    if save_match:
        favorite_name = save_match.group(1).strip()
        if current_destination:
            add_favorite(user_id, favorite_name, destination_name, 
                        current_destination[0], current_destination[1])
            return f"Saved as '{favorite_name}'", None, None
        else:
            return "No destination to save", None, None
    
    # Check for favorite commands
    favorite_commands = ["home", "work", "office", "gym", "school"]
    for cmd in favorite_commands:
        if text in [cmd, f"my {cmd}", f"go to {cmd}", f"take me to {cmd}", 
                   f"drive to {cmd}", f"navigate to {cmd}"]:
            fav = get_favorite(user_id, cmd)
            if fav:
                return fav["landmark_name"], (fav["x"], fav["y"]), (fav["x"], fav["y"])
            else:
                return f"No {cmd} saved", None, None
    
    # Regular parsing
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
    
    for landmark in LANDMARKS:
        if landmark["name"].lower() in text or text in landmark["name"].lower():
            lx, ly = landmark["pos"]
            road_pos = get_drop_off_point(lx, ly)
            return landmark["name"], road_pos, (lx, ly)
    
    for keyword, ltype in type_keywords.items():
        if keyword in text:
            closest, dist = find_closest_landmark(car_x, car_y, ltype)
            if closest:
                lx, ly = closest["pos"]
                road_pos = get_drop_off_point(lx, ly)
                return closest["name"], road_pos, (lx, ly)
    
    return None, None, None

def find_grid_path(start, goal):
    sx, sy = start
    gx, gy = goal
    
    path = []
    path.append((sx, sy))
    
    start_ix = min(ROAD_X, key=lambda rx: abs(rx - sx))
    start_iy = min(ROAD_Y, key=lambda ry: abs(ry - sy))
    goal_ix = min(ROAD_X, key=lambda rx: abs(rx - gx))
    goal_iy = min(ROAD_Y, key=lambda ry: abs(ry - gy))
    
    if abs(sx - start_ix) > 5 or abs(sy - start_iy) > 5:
        path.append((start_ix, start_iy))
    
    current_x, current_y = start_ix, start_iy
    
    dist_h_first = abs(goal_ix - current_x) + abs(goal_iy - start_iy)
    dist_v_first = abs(goal_iy - current_y) + abs(goal_ix - start_ix)
    
    if dist_h_first <= dist_v_first:
        if goal_ix > current_x:
            for x in ROAD_X:
                if x > current_x and x <= goal_ix:
                    path.append((x, current_y))
        elif goal_ix < current_x:
            for x in reversed(ROAD_X):
                if x < current_x and x >= goal_ix:
                    path.append((x, current_y))
        current_x = goal_ix
        
        if goal_iy > current_y:
            for y in ROAD_Y:
                if y > current_y and y <= goal_iy:
                    path.append((current_x, y))
        elif goal_iy < current_y:
            for y in reversed(ROAD_Y):
                if y < current_y and y >= goal_iy:
                    path.append((current_x, y))
        current_y = goal_iy
    else:
        if goal_iy > current_y:
            for y in ROAD_Y:
                if y > current_y and y <= goal_iy:
                    path.append((current_x, y))
        elif goal_iy < current_y:
            for y in reversed(ROAD_Y):
                if y < current_y and y >= goal_iy:
                    path.append((current_x, y))
        current_y = goal_iy
        
        if goal_ix > current_x:
            for x in ROAD_X:
                if x > current_x and x <= goal_ix:
                    path.append((x, current_y))
        elif goal_ix < current_x:
            for x in reversed(ROAD_X):
                if x < current_x and x >= goal_ix:
                    path.append((x, current_y))
        current_x = goal_ix
    
    if abs(current_x - gx) > 5 or abs(current_y - gy) > 5:
        path.append((gx, gy))
    
    filtered = []
    for p in path:
        if not filtered or abs(p[0] - filtered[-1][0]) > 2 or abs(p[1] - filtered[-1][1]) > 2:
            filtered.append(p)
    
    return filtered

def create_car_sprite(width=40, height=24):
    car_img = np.zeros((height, width, 4), dtype=np.uint8)
    body_color = (50, 50, 220, 255)
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

def draw_tire_tracks(img, tracks, car_x, car_y):
    for tx, ty, angle, opacity in tracks:
        scr_x = SCREEN_WIDTH//2 + int(tx - car_x)
        scr_y = SIM_HEIGHT//2 + int(ty - car_y)
        
        if 0 < scr_x < SCREEN_WIDTH and 0 < scr_y < SIM_HEIGHT:
            rad = np.radians(angle)
            x1 = int(scr_x - 6 * np.cos(rad))
            y1 = int(scr_y - 6 * np.sin(rad))
            x2 = int(scr_x + 6 * np.cos(rad))
            y2 = int(scr_y + 6 * np.sin(rad))
            
            color = (30, 30, 30)
            cv2.line(img, (x1, y1), (x2, y2), color, 2)

def update_traffic_lights():
    for light in traffic_lights:
        light['timer'] += 1
        if light['timer'] >= LIGHT_CYCLE:
            light['timer'] = 0
        
        if light['timer'] < LIGHT_RED_DURATION:
            light['state'] = 'red'
        else:
            light['state'] = 'green'

def draw_traffic_lights(img, car_x, car_y):
    for light in traffic_lights:
        scr_x = SCREEN_WIDTH//2 + int(light['x'] - car_x)
        scr_y = SIM_HEIGHT//2 + int(light['y'] - car_y)
        
        if 0 < scr_x < SCREEN_WIDTH and 0 < scr_y < SIM_HEIGHT:
            cv2.line(img, (scr_x, scr_y), (scr_x, scr_y - 30), (80, 80, 80), 3)
            cv2.rectangle(img, (scr_x-8, scr_y-45), (scr_x+8, scr_y-25), (40, 40, 40), -1)
            
            if light['state'] == 'red':
                color = (0, 0, 255)
            else:
                color = (0, 255, 0)
            
            cv2.circle(img, (scr_x, scr_y-35), 5, color, -1)
    
    return img

def check_traffic_light_stop(car_x, car_y, car_angle):
    for light in traffic_lights:
        if light['state'] != 'red':
            continue
        
        dx = light['x'] - car_x
        dy = light['y'] - car_y
        dist = np.sqrt(dx**2 + dy**2)
        
        if dist > 200 or dist < 30:
            continue
        
        angle_to_light = np.degrees(np.arctan2(dy, dx))
        angle_diff = abs(angle_to_light - car_angle)
        while angle_diff > 180:
            angle_diff = 360 - angle_diff
        
        if angle_diff < 45:
            car_orientation = 'vertical' if abs(np.cos(np.radians(car_angle))) < 0.5 else 'horizontal'
            if car_orientation != light['orientation']:
                return True, dist
    
    return False, float('inf')

def is_on_road(x, y):
    for rx in ROAD_X:
        if abs(x - rx) <= ROAD_HALF_WIDTH:
            return True
    for ry in ROAD_Y:
        if abs(y - ry) <= ROAD_HALF_WIDTH:
            return True
    return False

car_sprite = create_car_sprite(40, 24)
building_icons = {}
for ltype in set(l["type"] for l in LANDMARKS):
    building_icons[ltype] = create_building_icon(ltype, 60, 50)

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

# Load recent destinations for display
def get_suggestions_text(user_id):
    """Get text for suggested destinations"""
    recent = get_recent_destinations(user_id, 3)
    if recent:
        suggestions = ", ".join([r["name"] for r in recent])
        return f"Recent: {suggestions}"
    
    favorites = get_all_favorites(user_id)
    if favorites:
        fav_names = ", ".join([f["name"] for f in favorites[:3]])
        return f"Favorites: {fav_names}"
    
    return "Examples: 'airport', 'stadium', 'save this as home'"

add_chat("System", "AI Driver with Memory Ready!")
add_chat("System", "Try: 'home', 'work', 'save this as gym'")
world_map = create_map()

current_input = ""
input_active = False
waiting_at_light = False

while running:
    frame = np.zeros((TOTAL_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
    sim = frame[0:SIM_HEIGHT, 0:SCREEN_WIDTH]
    
    update_traffic_lights()
    
    cx, cy = int(car_x), int(car_y)
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
    
    sim = draw_traffic_lights(sim, car_x, car_y)
    draw_tire_tracks(sim, tire_tracks, car_x, car_y)
    
    if car_speed > 0.5 and car_state == "driving":
        tire_tracks.append((car_x, car_y, car_angle, 1.0))
        if len(tire_tracks) > MAX_TRACKS:
            tire_tracks.pop(0)
    
    tire_tracks = [(x, y, a, o*0.97) for x, y, a, o in tire_tracks if o > 0.05]
    
    for landmark in LANDMARKS:
        lx, ly = landmark["pos"]
        scr_x = SCREEN_WIDTH//2 + int(lx - car_x)
        scr_y = SIM_HEIGHT//2 + int(ly - car_y)
        
        if 0 < scr_x < SCREEN_WIDTH and 0 < scr_y < SIM_HEIGHT:
            is_dest = (original_goal and 
                      abs(lx - original_goal[0]) < 10 and 
                      abs(ly - original_goal[1]) < 10)
            
            if is_dest:
                cv2.circle(sim, (scr_x, scr_y), 35, (0, 255, 255), 3)
            
            dist = int(np.sqrt((lx-car_x)**2 + (ly-car_y)**2))
            if dist < 800:
                cv2.putText(sim, f"{dist}m", (scr_x-20, scr_y-25), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)
    
    if car_state == "driving" and current_destination:
        dx, dy = current_destination
        scr_dx = SCREEN_WIDTH//2 + int(dx - car_x)
        scr_dy = SIM_HEIGHT//2 + int(dy - car_y)
        if 0 < scr_dx < SCREEN_WIDTH and 0 < scr_dy < SIM_HEIGHT:
            cv2.circle(sim, (scr_dx, scr_dy), 8, (0, 255, 255), -1)
    
    # Stuck detection
    current_pos = (car_x, car_y)
    moved = np.sqrt((current_pos[0]-last_pos[0])**2 + (current_pos[1]-last_pos[1])**2)
    
    if moved < 0.2 and car_state == "driving" and not waiting_at_light and car_speed > 0.1:
        stuck_counter += 1
        if stuck_counter > 90:
            add_chat("Driver", "Stuck! Resetting...")
            car_x, car_y = snap_to_road(car_x, car_y)
            if path and waypoint_idx < len(path):
                wx, wy = path[waypoint_idx]
                car_angle = np.degrees(np.arctan2(wy - car_y, wx - car_x))
            car_speed = 1.0
            stuck_counter = 0
    else:
        stuck_counter = 0
    last_pos = current_pos
    
    arrived_this_frame = False
    if car_state == "driving" and current_destination:
        dist_to_dest = np.sqrt((car_x-current_destination[0])**2 + (car_y-current_destination[1])**2)
        
        if dist_to_dest < 50:
            car_state = "arrived"
            car_speed = 0
            car_x = current_destination[0]
            car_y = current_destination[1]
            
            # Save to history
            if destination_name:
                add_to_history(current_user_id, destination_name, 
                             current_destination[0], current_destination[1])
            
            path = []
            waypoint_idx = 0
            waiting_at_light = False
            arrived_this_frame = True
            add_chat("Driver", f"Arrived at {destination_name}!")
        
        elif not path or waypoint_idx >= len(path):
            path = find_grid_path((car_x, car_y), current_destination)
            waypoint_idx = 1 if len(path) > 1 else 0
        
        elif waypoint_idx < len(path):
            wx, wy = path[waypoint_idx]
            wp_dist = np.sqrt((wx-car_x)**2 + (wy-car_y)**2)
            if wp_dist < 40:
                waypoint_idx += 1
    
    if car_state == "driving" and not arrived_this_frame and path and waypoint_idx < len(path):
        should_stop, light_dist = check_traffic_light_stop(car_x, car_y, car_angle)
        
        if should_stop and light_dist < 120:
            if not waiting_at_light:
                waiting_at_light = True
                add_chat("Driver", "Stopping at red light...")
            
            car_speed *= 0.8
            if car_speed < 0.2:
                car_speed = 0
            
            should_stop, _ = check_traffic_light_stop(car_x, car_y, car_angle)
            if not should_stop:
                waiting_at_light = False
                add_chat("Driver", "Green light! Proceeding...")
        else:
            waiting_at_light = False
            
            wx, wy = path[waypoint_idx]
            
            target_angle = np.degrees(np.arctan2(wy - car_y, wx - car_x))
            angle_diff = target_angle - car_angle
            
            while angle_diff > 180: angle_diff -= 360
            while angle_diff < -180: angle_diff += 360
            
            if abs(angle_diff) > 2:
                steering = max(-15, min(15, angle_diff * 0.4))
            else:
                steering = 0
            
            next_wp_dist = np.sqrt((wx-car_x)**2 + (wy-car_y)**2)
            turn_sharpness = abs(angle_diff)
            
            if turn_sharpness > 70:
                target_speed = 1.5
            elif turn_sharpness > 40:
                target_speed = 2.5
            else:
                target_speed = max_speed
            
            if next_wp_dist < 100 and turn_sharpness > 30:
                approach_factor = next_wp_dist / 100
                target_speed = min(target_speed, 1.5 + approach_factor * 2)
            
            if should_stop:
                target_speed = min(target_speed, light_dist / 40)
            
            car_angle += steering * 0.25
            
            if target_speed < car_speed:
                car_speed += (target_speed - car_speed) * 0.15
            else:
                car_speed += (target_speed - car_speed) * 0.1
            
            car_speed = max(0, min(car_speed, max_speed))
            
            if car_speed > 0.1:
                rad = np.radians(car_angle)
                new_x = car_x + car_speed * np.cos(rad)
                new_y = car_y + car_speed * np.sin(rad)
                
                if is_on_road(new_x, new_y):
                    car_x, car_y = new_x, new_y
                else:
                    car_speed *= 0.3
                    car_x, car_y = snap_to_road(car_x, car_y)
    
    # Draw path
    if car_state == "driving" and path and len(path) > 1:
        for i in range(len(path)-1):
            x1 = SCREEN_WIDTH//2 + int(path[i][0] - car_x)
            y1 = SIM_HEIGHT//2 + int(path[i][1] - car_y)
            x2 = SCREEN_WIDTH//2 + int(path[i+1][0] - car_x)
            y2 = SIM_HEIGHT//2 + int(path[i+1][1] - car_y)
            cv2.line(sim, (x1,y1), (x2,y2), (0,255,255), 3)
        
        for i in range(waypoint_idx, min(waypoint_idx+5, len(path))):
            wx, wy = path[i]
            wpx = SCREEN_WIDTH//2 + int(wx - car_x)
            wpy = SIM_HEIGHT//2 + int(wy - car_y)
            if 0 < wpx < SCREEN_WIDTH and 0 < wpy < SIM_HEIGHT:
                cv2.circle(sim, (wpx, wpy), 6, (0,255,0), -1)
    
    cs_x, cs_y = SCREEN_WIDTH//2, SIM_HEIGHT//2
    rotated_car, _ = rotate_sprite(car_sprite, car_angle)
    draw_sprite_on_image(sim, rotated_car, cs_x, cs_y, shadow=True)
    
    status = f"{car_state.upper()}"
    if waiting_at_light:
        status = "STOPPING (RED LIGHT)"
    if destination_name and car_state != "idle":
        status += f" | To: {destination_name[:12]}"
        if car_state == "driving":
            dist = int(np.sqrt((car_x-current_destination[0])**2 + (car_y-current_destination[1])**2))
            status += f" ({dist}m)"
    
    cv2.putText(sim, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
    cv2.putText(sim, f"Speed: {car_speed:.1f}", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1)
    
    cv2.rectangle(frame, (0, SIM_HEIGHT), (SCREEN_WIDTH, TOTAL_HEIGHT), (30,30,30), -1)
    cv2.line(frame, (0, SIM_HEIGHT), (SCREEN_WIDTH, SIM_HEIGHT), (100,100,100), 3)
    
    cv2.putText(frame, "TEXT ASSISTANT - Press ESC or Q to quit", (15, SIM_HEIGHT+25), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
    
    y = SIM_HEIGHT + 55
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
        
        text = prefix + msg
        if len(text) > 70:
            text = text[:67] + "..."
        
        cv2.putText(frame, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y += 28
    
    input_y = TOTAL_HEIGHT - 50
    cv2.rectangle(frame, (20, input_y-10), (SCREEN_WIDTH-120, input_y+30), (60,60,60), -1)
    cv2.rectangle(frame, (20, input_y-10), (SCREEN_WIDTH-120, input_y+30), (150,150,150), 2)
    
    prompt = "> " + current_input + ("_" if input_active else "")
    cv2.putText(frame, prompt, (30, input_y+15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
    
    cv2.putText(frame, "ENTER to send", (SCREEN_WIDTH-110, input_y+15), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150,150,150), 1)
    
    # Show suggestions
    suggestions = get_suggestions_text(current_user_id)
    cv2.putText(frame, suggestions, (20, TOTAL_HEIGHT-15), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150,150,150), 1)
    
    cv2.imshow("AI Driver - Working Grid", frame)
    
    key = cv2.waitKey(30) & 0xFF
    
    if key == 27 or key == ord('q') or key == ord('Q'):
        running = False
        break
    elif key == 13 and current_input.strip():
        add_chat("User", current_input)
        
        # Check for user switch command
        user_match = re.match(r"user (\w+)", current_input.lower())
        if user_match:
            username = user_match.group(1)
            current_user_id = get_or_create_user(username)
            if current_user_id:
                add_chat("System", f"Switched to user: {username}")
            else:
                add_chat("System", f"User '{username}' not found. Please login first.")
        else:
            # Parse destination with user context
            result = parse_destination(current_input, car_x, car_y, current_user_id)
            
            if result[0] and result[1]:  # Valid destination
                dest_name, road_pos, orig_pos = result
                destination_name = dest_name
                current_destination = road_pos
                original_goal = orig_pos
                
                # Snap to road before starting
                car_x, car_y = snap_to_road(car_x, car_y)
                
                path = find_grid_path((car_x, car_y), current_destination)
                waypoint_idx = 1 if len(path) > 1 else 0
                car_state = "driving"
                car_speed = 2.0
                stuck_counter = 0
                waiting_at_light = False
                tire_tracks = []
                
                dist = int(np.sqrt((road_pos[0]-car_x)**2 + (road_pos[1]-car_y)**2))
                add_chat("Driver", f"Going to {dest_name} ({dist}m)...")
            elif result[0]: 
                add_chat("Driver", result[0])
            else:
                add_chat("Driver", "I don't know that place. Try: 'home', 'mall', 'save this as work'...")
        
        current_input = ""
        input_active = False
    elif key == 8:
        current_input = current_input[:-1]
    elif key == 9:
        input_active = not input_active
    elif 32 <= key < 127 and len(current_input) < 60:
        current_input += chr(key)
        input_active = True
    elif key == ord('g'):
        current_input = "gas station"
    elif key == ord('s'):
        current_input = "school"
    elif key == ord('r'):
        current_input = "restaurant"
    elif key == ord('p'):
        current_input = "park"

print("Cleaning up...")
cv2.destroyAllWindows()
for i in range(5):
    cv2.waitKey(1)
sys.exit(0)
