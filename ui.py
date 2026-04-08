#Login and registration OpenCV screens

import sys
import cv2
import numpy as np

from database import register_user, authenticate_user


def registration_screen():
    """Show the registration form. Returns user_id on success, None if cancelled."""
    username, password, confirm = "", "", ""
    active = "username"
    message, msg_color = "", (0, 0, 255)

    while True:
        frame = np.zeros((500, 600, 3), dtype=np.uint8)
        frame[:] = (20, 20, 25)
        cv2.putText(frame, "CREATE ACCOUNT", (140, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        cv2.putText(frame, "Join AI Driver today", (200, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        fields = [
            ("Username",         username,  "username"),
            ("Password",         "*" * len(password),  "password"),
            ("Confirm Password", "*" * len(confirm),   "confirm"),
        ]
        y = 140
        for label, value, key in fields:
            cv2.putText(frame, label, (150, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            cv2.rectangle(frame, (150, y), (450, y + 40), (40, 40, 45), -1)
            cv2.rectangle(frame, (150, y), (450, y + 40),
                          (0, 255, 255) if active == key else (100, 100, 100), 2)
            cv2.putText(frame, value + ("_" if active == key else ""),
                        (160, y + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            y += 70

        if message:
            for i, line in enumerate(_wrap(message, 40)):
                cv2.putText(frame, line, (150, 385 + i * 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, msg_color, 1)

        cv2.putText(frame, "TAB: Next Field | ENTER: Register | ESC: Back",
                    (110, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)
        cv2.imshow("AI Driver - Registration", frame)
        key = cv2.waitKey(30) & 0xFF

        if key == 27:
            cv2.destroyWindow("AI Driver - Registration")
            return None
        elif key == 13:
            if not username or not password or not confirm:
                message, msg_color = "All fields are required", (0, 0, 255)
            elif password != confirm:
                message, msg_color = "Passwords do not match", (0, 0, 255)
                confirm = ""
            else:
                ok, msg, uid = register_user(username, password)
                if ok:
                    message, msg_color = "Registration successful!", (0, 255, 0)
                    cv2.imshow("AI Driver - Registration", frame)
                    cv2.waitKey(1000)
                    cv2.destroyWindow("AI Driver - Registration")
                    return uid
                message, msg_color = msg, (0, 0, 255)
        elif key == 9:
            active = {"username": "password", "password": "confirm", "confirm": "username"}[active]
        elif key == 8:
            if   active == "username": username = username[:-1]
            elif active == "password": password = password[:-1]
            else:                      confirm  = confirm[:-1]
        elif 32 <= key < 127:
            ch = chr(key)
            if   active == "username" and len(username) < 20 and (ch.isalnum() or ch == '_'):
                username += ch
            elif active == "password" and len(password) < 20:
                password += ch
            elif active == "confirm"  and len(confirm)  < 20:
                confirm  += ch


def login_screen():
    """Show the login form. Returns user_id on successful login; exits on ESC."""
    username, password = "", ""
    active = "username"
    message, msg_color = "", (0, 0, 255)

    while True:
        frame = np.zeros((500, 600, 3), dtype=np.uint8)
        frame[:] = (20, 20, 25)
        cv2.putText(frame, "AI DRIVER LOGIN", (160, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

        for label, y_top, value, field in [
            ("Username", 140, username,         "username"),
            ("Password", 230, "*" * len(password), "password"),
        ]:
            cv2.putText(frame, label, (150, y_top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            cv2.rectangle(frame, (150, y_top), (450, y_top + 40), (40, 40, 45), -1)
            cv2.rectangle(frame, (150, y_top), (450, y_top + 40),
                          (0, 255, 255) if active == field else (100, 100, 100), 2)
            cv2.putText(frame, value + ("_" if active == field else ""),
                        (160, y_top + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        if message:
            cv2.putText(frame, message, (150, 310),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, msg_color, 1)

        cv2.rectangle(frame, (100, 340), (500, 420), (35, 35, 40), -1)
        cv2.rectangle(frame, (100, 340), (500, 420), (80, 80, 80), 1)
        cv2.putText(frame, "CONTROLS:",              (120, 365), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)
        cv2.putText(frame, "ENTER - Login",          (120, 390), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        cv2.putText(frame, "TAB - Switch Field",     (280, 390), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        cv2.putText(frame, "R - Register Account",   (120, 410), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        cv2.putText(frame, "ESC - Quit",             (280, 410), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        cv2.imshow("AI Driver - Login", frame)
        key = cv2.waitKey(30) & 0xFF

        if key == 27:
            cv2.destroyAllWindows()
            sys.exit(0)
        elif key in (ord('r'), ord('R')):
            cv2.destroyWindow("AI Driver - Login")
            uid = registration_screen()
            if uid:
                return uid
            cv2.namedWindow("AI Driver - Login")
        elif key == 13:
            if not username or not password:
                message, msg_color = "Please enter username and password", (0, 0, 255)
            else:
                uid = authenticate_user(username, password)
                if uid:
                    cv2.destroyWindow("AI Driver - Login")
                    return uid
                message, msg_color = "Invalid username or password", (0, 0, 255)
                password = ""
        elif key == 9:
            active = "password" if active == "username" else "username"
        elif key == 8:
            if active == "username": username = username[:-1]
            else:                    password = password[:-1]
        elif 32 <= key < 127:
            ch = chr(key)
            if   active == "username" and len(username) < 20 and (ch.isalnum() or ch == '_'):
                username += ch
            elif active == "password" and len(password) < 20:
                password += ch


#Utility
def _wrap(text: str, width: int):
    words, lines, line = text.split(), [], ""
    for w in words:
        if len(line + w) < width:
            line += w + " "
        else:
            lines.append(line.strip())
            line = w + " "
    if line:
        lines.append(line.strip())
    return lines