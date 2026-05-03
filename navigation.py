# navigation.py

import re
import math

from config   import LANDMARKS
from road     import get_drop_off_point, get_driveway_point
from database import get_favorite

TYPE_KEYWORDS = {
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

FAVORITE_NAMES = ["home", "work", "office", "gym", "school"]


def find_closest_landmark(car_x, car_y, landmark_type):
    closest, min_dist = None, float('inf')
    for lm in LANDMARKS:
        if lm["type"] == landmark_type or landmark_type in lm["name"].lower():
            d = math.sqrt((lm["pos"][0] - car_x)**2 + (lm["pos"][1] - car_y)**2)
            if d < min_dist:
                min_dist = d
                closest  = lm
    return closest, min_dist


def parse_destination(text: str, car_x: float, car_y: float, user_id: int):
    text = text.lower().strip()

    # Save command
    if re.match(r"save (?:this|location|place) as (.+)", text):
        return "Save command processed", None, None

    # Saved favorite shortcut
    for cmd in FAVORITE_NAMES:
        if text in [cmd, f"my {cmd}", f"go to {cmd}",
                    f"take me to {cmd}", f"drive to {cmd}", f"navigate to {cmd}"]:
            fav = get_favorite(user_id, cmd)
            if fav:
                return fav["landmark_name"], (fav["x"], fav["y"]), (fav["x"], fav["y"])
            return f"No {cmd} saved yet", None, None

    # Strip leading navigation verbs and articles
    text = re.sub(
        r"^(take me to|drive to|go to|navigate to|i want to go to|let's go to|nearest|closest)\s*",
        "", text
    )
    text = re.sub(r"^(the|a|an)\s+", "", text).strip(" .!?")

    # Exact / substring landmark name match
    for lm in LANDMARKS:
        if lm["name"].lower() in text or text in lm["name"].lower():
            lx, ly    = lm["pos"]
            road_pos  = get_drop_off_point(lx, ly, lm["name"])
            return lm["name"], road_pos, (lx, ly)

    # Keyword → type → nearest
    for keyword, ltype in TYPE_KEYWORDS.items():
        if keyword in text:
            closest, _ = find_closest_landmark(car_x, car_y, ltype)
            if closest:
                lx, ly   = closest["pos"]
                road_pos = get_drop_off_point(lx, ly, closest["name"])
                return closest["name"], road_pos, (lx, ly)

    return None, None, None
