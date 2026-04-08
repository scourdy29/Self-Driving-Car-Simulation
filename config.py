#Global constants for screen, map, roads and landmarks

SCREEN_WIDTH  = 1200
SIM_HEIGHT    = 700
PANEL_HEIGHT  = 250
TOTAL_HEIGHT  = SIM_HEIGHT + PANEL_HEIGHT

MAP_WIDTH  = 3000
MAP_HEIGHT = 2500

ROAD_X          = [200, 600, 1100, 1600, 2100, 2600]
ROAD_Y          = [200, 700, 1300, 1900, 2400]
ROAD_HALF_WIDTH = 60

LANDMARKS = [
    {"name": "Your Home",         "pos": (400,  400),  "color": (150, 100,  50), "size": ( 90,  80), "type": "home"},
    {"name": "Shell Gas",         "pos": (150,  150),  "color": (  0, 100, 200), "size": ( 80,  70), "type": "gas"},
    {"name": "Lincoln High",      "pos": (850,  350),  "color": (200, 200,  50), "size": (100,  90), "type": "school"},
    {"name": "Burger King",       "pos": (1300, 150),  "color": ( 50, 150,  50), "size": ( 70,  70), "type": "restaurant"},
    {"name": "Westfield Mall",    "pos": (1800, 450),  "color": (200, 100, 200), "size": (120, 110), "type": "mall"},
    {"name": "Airport",           "pos": (2400, 300),  "color": (150, 150, 150), "size": (150, 130), "type": "airport"},
    {"name": "General Hospital",  "pos": (350,  1000), "color": (255, 255, 255), "size": (110, 100), "type": "hospital"},
    {"name": "Police Station",    "pos": (150,  1100), "color": (100,  50, 150), "size": ( 90,  85), "type": "police"},
    {"name": "City Library",      "pos": (900,  1000), "color": (150,  50, 150), "size": ( 85,  80), "type": "library"},
    {"name": "Central Park",      "pos": (1300, 1100), "color": (100, 200, 100), "size": (120, 100), "type": "park"},
    {"name": "Chase Bank",        "pos": (1800, 1000), "color": (200, 150,  50), "size": ( 80,  75), "type": "bank"},
    {"name": "Pizza Hut",         "pos": (2400, 1100), "color": ( 60, 160,  60), "size": ( 75,  75), "type": "restaurant"},
    {"name": "Stadium",           "pos": (400,  1600), "color": ( 50,  50, 150), "size": (130, 120), "type": "stadium"},
    {"name": "Fire Station",      "pos": (150,  1750), "color": ( 50,  50, 200), "size": ( 90,  85), "type": "fire"},
    {"name": "Community College", "pos": (850,  1600), "color": (180, 180,  40), "size": (120, 110), "type": "school"},
    {"name": "McDonald's",        "pos": (1300, 1750), "color": ( 70, 170,  70), "size": ( 80,  75), "type": "restaurant"},
    {"name": "Galleria Mall",     "pos": (1850, 1600), "color": (210, 110, 210), "size": (130, 120), "type": "mall"},
    {"name": "St. Mary's Hosp",   "pos": (2400, 1750), "color": (240, 240, 240), "size": (100,  90), "type": "hospital"},
    {"name": "Riverside Park",    "pos": (400,  2200), "color": (110, 210, 110), "size": (130, 110), "type": "park"},
    {"name": "Chevron",           "pos": (150,  2300), "color": (  0, 110, 210), "size": ( 85,  75), "type": "gas"},
    {"name": "Wells Fargo",       "pos": (900,  2200), "color": (210, 160,  60), "size": ( 85,  80), "type": "bank"},
    {"name": "Taco Bell",         "pos": (1350, 2300), "color": ( 55, 155,  55), "size": ( 75,  75), "type": "restaurant"},
    {"name": "Mom's House",       "pos": (1850, 2200), "color": (140,  90,  40), "size": ( 90,  85), "type": "home"},
    {"name": "Friend's House",    "pos": (2400, 2300), "color": (160, 110,  60), "size": ( 90,  85), "type": "home"},
]