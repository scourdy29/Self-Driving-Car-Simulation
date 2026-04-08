#SQLite setup, authentication, favorites and history

import sqlite3
import hashlib
import re

DB_PATH = "ai_driver.db"


def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            password   TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER,
            name           TEXT NOT NULL,
            landmark_name  TEXT,
            pos_x          REAL,
            pos_y          REAL,
            category       TEXT,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, name)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER,
            landmark_name  TEXT,
            pos_x          REAL,
            pos_y          REAL,
            visited_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            frequency      INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            user_id    INTEGER,
            pref_key   TEXT,
            pref_value TEXT,
            PRIMARY KEY (user_id, pref_key),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def check_user_exists(username: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def register_user(username: str, password: str):
    """Returns (success: bool, message: str, user_id: int | None)."""
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
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, _hash(password))
        )
        user_id = cursor.lastrowid
        conn.commit()
        return True, "Registration successful", user_id
    except Exception as e:
        return False, f"Database error: {e}", None
    finally:
        conn.close()


def authenticate_user(username: str, password: str):
    """Returns user_id on success, None on failure."""
    if not username or not password:
        return None
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, password FROM users WHERE username = ?", (username,)
    )
    result = cursor.fetchone()
    conn.close()
    if result and result[1] == _hash(password):
        return result[0]
    return None


def add_favorite(user_id, name, landmark_name, pos_x, pos_y, category="general"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT OR REPLACE INTO favorites
               (user_id, name, landmark_name, pos_x, pos_y, category)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, name.lower(), landmark_name, pos_x, pos_y, category)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding favorite: {e}")
        return False
    finally:
        conn.close()


def get_favorite(user_id, name):
    """Returns dict with keys landmark_name, x, y — or None."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT landmark_name, pos_x, pos_y FROM favorites WHERE user_id=? AND name=?",
        (user_id, name.lower())
    )
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"landmark_name": result[0], "x": result[1], "y": result[2]}
    return None


def add_to_history(user_id, landmark_name, pos_x, pos_y):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, frequency FROM history WHERE user_id=? AND landmark_name=?",
        (user_id, landmark_name)
    )
    result = cursor.fetchone()
    if result:
        cursor.execute(
            "UPDATE history SET frequency=?, visited_at=CURRENT_TIMESTAMP WHERE id=?",
            (result[1] + 1, result[0])
        )
    else:
        cursor.execute(
            "INSERT INTO history (user_id, landmark_name, pos_x, pos_y) VALUES (?,?,?,?)",
            (user_id, landmark_name, pos_x, pos_y)
        )
    conn.commit()
    conn.close()