# entry point: game loop, spawning, HUD rendering

import sys
import math
import random

import cv2
import numpy as np

from config     import (SCREEN_WIDTH, SIM_HEIGHT, PANEL_HEIGHT, TOTAL_HEIGHT,
                        MAP_WIDTH, MAP_HEIGHT, ROAD_X, ROAD_Y, LANDMARKS)
from database   import init_database
from road       import is_on_road, snap_to_road, get_drop_off_point
from traffic    import AgentType, TrafficLight, VehicleAgent, _all_vehicles_ref
import traffic  as _traffic_module
from rendering  import (create_map, draw_vehicle, draw_traffic_light)
from navigation import parse_destination
from ui         import login_screen


# Initialisation
init_database()
current_user_id = login_screen()
world_map       = create_map()

# Traffic lights at every other intersection
traffic_lights = []
for i, rx in enumerate(ROAD_X[1:-1]):
    for j, ry in enumerate(ROAD_Y[1:-1]):
        if (i + j) % 2 == 0:
            orientation = 'vertical' if i % 2 == 0 else 'horizontal'
            traffic_lights.append(TrafficLight(rx, ry, orientation, len(traffic_lights)))

# Vehicle list
vehicles       = []
next_vehicle_id = 1
_traffic_module._all_vehicles_ref = vehicles   # give traffic.py a live reference

# Vehicle
player_vehicle = VehicleAgent(600, 700, AgentType.HUMAN, 0, (50, 50, 220))
vehicles.append(player_vehicle)


# Spawn helper
def spawn_ai_vehicle(agent_type=None):
    global next_vehicle_id

    if agent_type is None:
        agent_type = random.choices(
            [AgentType.AI_RANDOM, AgentType.AI_EFFICIENT, AgentType.AI_AGGRESSIVE],
            weights=[0.55, 0.30, 0.15]
        )[0]

    spawn_x = spawn_y = None
    for _ in range(20):
        rx = random.choice(ROAD_X)
        ry = random.choice(ROAD_Y)
        if random.random() > 0.5:
            sx = rx
            sy = max(60, min(MAP_HEIGHT - 60, ry + random.randint(-200, 200)))
        else:
            sx = max(60, min(MAP_WIDTH  - 60, rx + random.randint(-200, 200)))
            sy = ry
        if not is_on_road(sx, sy):
            continue
        if any(math.sqrt((v.x - sx)**2 + (v.y - sy)**2) < 100 for v in vehicles):
            continue
        spawn_x, spawn_y = sx, sy
        break

    if spawn_x is None:
        spawn_x, spawn_y = float(random.choice(ROAD_X)), float(random.choice(ROAD_Y))

    v = VehicleAgent(spawn_x, spawn_y, agent_type, next_vehicle_id)

    if LANDMARKS:
        if agent_type == AgentType.AI_EFFICIENT:
            target = min(LANDMARKS, key=lambda l:
                math.sqrt((l["pos"][0] - spawn_x)**2 + (l["pos"][1] - spawn_y)**2))
        elif agent_type == AgentType.AI_AGGRESSIVE:
            dists  = [math.sqrt((l["pos"][0]-spawn_x)**2 + (l["pos"][1]-spawn_y)**2)
                      for l in LANDMARKS]
            total  = sum(dists) or 1
            target = random.choices(LANDMARKS, weights=[d/total for d in dists], k=1)[0]
        else:
            target = random.choice(LANDMARKS)

        v.set_destination(target["name"],
                          get_drop_off_point(*target["pos"]),
                          target["pos"])
    v._idle_delay = 0
    vehicles.append(v)
    next_vehicle_id += 1
    return v


# Initial traffic
for _ in range(12):
    spawn_ai_vehicle()


# Chat and UI state
chat_history  = []
running       = True
current_input = ""
input_active  = False
show_stats    = True


def add_chat(sender, message):
    chat_history.append((sender, message))
    if len(chat_history) > 6:
        chat_history.pop(0)


add_chat("System", "AI Driver ready! Type a destination below.")
add_chat("System", "Try: 'airport', 'mall', 'hospital', 'gas station'")


# Main loop
frame_count = 0

while running:
    frame = np.zeros((TOTAL_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
    sim   = frame[:SIM_HEIGHT, :SCREEN_WIDTH]

    # Periodic AI spawn
    if frame_count % 90 == 0 and len(vehicles) < 25:
        spawn_ai_vehicle()

    # Update traffic lights
    for light in traffic_lights:
        light.update(vehicles, traffic_lights)

    # Update vehicles
    for vehicle in vehicles[:]:
        vehicle.update(world_map, traffic_lights, vehicles)

        if vehicle.agent_type != AgentType.HUMAN and vehicle.state == "arrived":
            vehicles.remove(vehicle)
            if len(vehicles) < 22:
                spawn_ai_vehicle()
            continue

        if vehicle.stuck_counter > 200 and vehicle.agent_type == AgentType.HUMAN:
            vehicle.x, vehicle.y = snap_to_road(vehicle.x, vehicle.y)
            vehicle.stuck_counter = 0


    # Rendering
    cx  = int(player_vehicle.x)
    cy  = int(player_vehicle.y)
    mx1 = max(0, cx - SCREEN_WIDTH // 2)
    my1 = max(0, cy - SIM_HEIGHT  // 2)

    visible = world_map[my1:min(MAP_HEIGHT, my1 + SIM_HEIGHT),
                        mx1:min(MAP_WIDTH,  mx1 + SCREEN_WIDTH)]
    vx = SCREEN_WIDTH // 2 - (cx - mx1)
    vy = SIM_HEIGHT   // 2 - (cy - my1)
    h, w = visible.shape[:2]
    y1, y2 = max(0, vy),        min(SIM_HEIGHT, vy + h)
    x1, x2 = max(0, vx),        min(SCREEN_WIDTH, vx + w)
    if y2 > y1 and x2 > x1:
        sim[y1:y2, x1:x2] = visible[
            max(0, -vy): max(0, -vy) + (y2 - y1),
            max(0, -vx): max(0, -vx) + (x2 - x1)
        ]

    for light in traffic_lights:
        draw_traffic_light(sim, light, player_vehicle.x, player_vehicle.y)

    for v in sorted(vehicles, key=lambda v: v.y):
        draw_vehicle(sim, v, player_vehicle.x, player_vehicle.y, v.id == 0)

    # Player route path
    if player_vehicle.state == "driving" and player_vehicle.path:
        for i in range(len(player_vehicle.path) - 1):
            p1x = SCREEN_WIDTH // 2 + int(player_vehicle.path[i][0]     - player_vehicle.x)
            p1y = SIM_HEIGHT   // 2 + int(player_vehicle.path[i][1]     - player_vehicle.y)
            p2x = SCREEN_WIDTH // 2 + int(player_vehicle.path[i + 1][0] - player_vehicle.x)
            p2y = SIM_HEIGHT   // 2 + int(player_vehicle.path[i + 1][1] - player_vehicle.y)
            cv2.line(sim, (p1x, p1y), (p2x, p2y), (0, 255, 255), 2)
        if player_vehicle.waypoint_idx < len(player_vehicle.path):
            nwx, nwy = player_vehicle.path[player_vehicle.waypoint_idx]
            cv2.circle(sim,
                       (SCREEN_WIDTH // 2 + int(nwx - player_vehicle.x),
                        SIM_HEIGHT   // 2 + int(nwy - player_vehicle.y)),
                       6, (255, 128, 0), -1)

    # HUD
    status = f"Player: {player_vehicle.state.upper()}"
    if player_vehicle.in_queue:
        status += " [FOLLOWING]"
    if player_vehicle.destination_name:
        status += f" | To: {player_vehicle.destination_name[:15]}"
    cv2.putText(sim, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(sim, f"Speed: {player_vehicle.speed:.1f}  WP: {player_vehicle.waypoint_idx}/{max(0, len(player_vehicle.path)-1)}",
                (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Panel background
    cv2.rectangle(frame, (0, SIM_HEIGHT), (SCREEN_WIDTH, TOTAL_HEIGHT), (30, 30, 30), -1)
    cv2.line(frame, (0, SIM_HEIGHT), (SCREEN_WIDTH, SIM_HEIGHT), (100, 100, 100), 3)

    # Chat log
    y = SIM_HEIGHT + 30
    for sender, msg in chat_history:
        if sender == "User":
            color, prefix = (0, 200, 255), "You: "
        elif sender == "Driver":
            color, prefix = (50, 255, 50), "Driver: "
        else:
            color, prefix = (200, 200, 200), ""
        cv2.putText(frame, prefix + msg[:70], (20, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y += 25

    # Input bar
    iy = TOTAL_HEIGHT - 40
    cv2.rectangle(frame, (20, iy - 10), (SCREEN_WIDTH - 120, iy + 20), (60, 60, 60), -1)
    cv2.putText(frame, "> " + current_input + ("_" if input_active else ""),
                (30, iy + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # Traffic stats panel
    if show_stats:
        total_wait = sum(v.total_wait_time for v in vehicles)
        avg_speed  = sum(v.speed for v in vehicles) / len(vehicles) if vehicles else 0
        in_queue   = sum(1 for v in vehicles if v.in_queue)
        cv2.rectangle(frame, (20, SIM_HEIGHT + 130), (320, SIM_HEIGHT + 220), (30, 30, 30), -1)
        cv2.putText(frame, "TRAFFIC STATS",
                    (30, SIM_HEIGHT + 150), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(frame, f"Vehicles: {len(vehicles)}  Queued: {in_queue}",
                    (30, SIM_HEIGHT + 170), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        cv2.putText(frame, f"Avg Speed: {avg_speed:.1f}  Wait: {total_wait:.0f}s",
                    (30, SIM_HEIGHT + 190), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        cv2.putText(frame, "1=Random  2=Efficient  3=Aggressive  A=Lights  T=Stats",
                    (30, SIM_HEIGHT + 210), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (150, 150, 150), 1)

    cv2.putText(frame, "Blue=You  Red=Random  Green=Efficient  Yellow=Aggressive",
                (20, TOTAL_HEIGHT - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)

    cv2.imshow("AI Driver - Realistic Traffic", frame)


    # Input handling
    key = cv2.waitKey(30) & 0xFF

    if key == 27 or key == ord('q'):
        running = False
    elif key == ord('1'):
        spawn_ai_vehicle(AgentType.AI_RANDOM);     add_chat("System", "Spawned: Random AI")
    elif key == ord('2'):
        spawn_ai_vehicle(AgentType.AI_EFFICIENT);  add_chat("System", "Spawned: Efficient AI")
    elif key == ord('3'):
        spawn_ai_vehicle(AgentType.AI_AGGRESSIVE); add_chat("System", "Spawned: Aggressive AI")
    elif key == ord('t'):
        show_stats = not show_stats
    elif key == ord('a'):
        for light in traffic_lights:
            light.adaptive_mode = not light.adaptive_mode
        add_chat("System", "Lights: " + ("Adaptive" if traffic_lights[0].adaptive_mode else "Fixed"))
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
            add_chat("Driver", dest_name)
        else:
            add_chat("Driver", "Unknown destination. Try: 'airport', 'mall', 'hospital'")
        current_input = ""
        input_active  = False
    elif key == 8:
        current_input = current_input[:-1]
    elif 32 <= key < 127 and len(current_input) < 60:
        current_input += chr(key)
        input_active   = True

    frame_count += 1

cv2.destroyAllWindows()
sys.exit(0)