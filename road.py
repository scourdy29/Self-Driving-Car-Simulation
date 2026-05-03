# road.py

import math
from config import ROAD_X, ROAD_Y, ROAD_HALF_WIDTH, MAP_WIDTH, MAP_HEIGHT, PARKING_LOTS


def is_on_road(x: float, y: float) -> bool:
    for rx in ROAD_X:
        if abs(x - rx) <= ROAD_HALF_WIDTH:
            return True
    for ry in ROAD_Y:
        if abs(y - ry) <= ROAD_HALF_WIDTH:
            return True
    return False


def snap_to_road(x: float, y: float, lane_offset: int = 0):
    nearest_x = min(ROAD_X, key=lambda rx: abs(rx - x))
    nearest_y = min(ROAD_Y, key=lambda ry: abs(ry - y))
    if abs(nearest_x - x) <= abs(nearest_y - y):
        return (nearest_x + lane_offset, y)
    return (x, nearest_y + lane_offset)


def get_drop_off_point(landmark_x: float, landmark_y: float, name: str = ""):
    if name and name in PARKING_LOTS:
        return PARKING_LOTS[name]["spot"]

    # Fallback for landmarks
    best_v = min(ROAD_X, key=lambda rx: abs(rx - landmark_x))
    best_h = min(ROAD_Y, key=lambda ry: abs(ry - landmark_y))
    if abs(best_v - landmark_x) <= abs(best_h - landmark_y):
        offset = 20 if landmark_x > best_v else -20
        road_y = max(50, min(MAP_HEIGHT - 50, landmark_y))
        return (best_v + offset, road_y)
    else:
        offset = 20 if landmark_y > best_h else -20
        road_x = max(50, min(MAP_WIDTH - 50, landmark_x))
        return (road_x, best_h + offset)


def get_driveway_point(name: str):
    if name in PARKING_LOTS:
        return PARKING_LOTS[name]["driveway"]
    return None


def lane_pos(road_centre: float, direction_sign: int, lane_w: int = 18) -> float:
    return road_centre + lane_w * direction_sign


def find_grid_path(start, goal, start_angle_deg: float = None):
    import math as _math
    LANE_W = 18
    sx, sy = start
    gx, gy = goal

    start_rx = min(ROAD_X, key=lambda rx: abs(rx - sx))
    start_ry = min(ROAD_Y, key=lambda ry: abs(ry - sy))
    goal_rx  = min(ROAD_X, key=lambda rx: abs(rx - gx))
    goal_ry  = min(ROAD_Y, key=lambda ry: abs(ry - gy))

    h_dist = abs(goal_rx - start_rx)
    v_dist = abs(goal_ry - start_ry)
    dxs = 1 if goal_rx >= start_rx else -1
    dys = 1 if goal_ry >= start_ry else -1

    # Determine preferred axis order by distance
    h_first = (h_dist >= v_dist)

    # Anti-U-turn
    if start_angle_deg is not None and h_dist > 0 and v_dist > 0:
        rad = _math.radians(start_angle_deg)
        cos_h = _math.cos(rad)
        sin_h = _math.sin(rad)
        moving_h = abs(cos_h) >= abs(sin_h)

        if h_first and moving_h:
            # Going horizontal first
            current_dx = 1 if cos_h >= 0 else -1
            if current_dx != dxs:
                h_first = False  # swap: go vertical first to avoid U-turn
        elif not h_first and not moving_h:
            # Going vertical first
            current_dy = 1 if sin_h >= 0 else -1
            if current_dy != dys:
                h_first = True  # swap: go horizontal first to avoid U-turn

    def h_leg(cur_x, cur_y):
        if goal_rx == cur_x:
            return []
        xs = sorted(x for x in ROAD_X
                    if min(cur_x, goal_rx) <= x <= max(cur_x, goal_rx))
        if dxs < 0: xs = xs[::-1]
        return [(x, cur_y, 'h', dxs) for x in xs]

    def v_leg(cur_x, cur_y):
        if goal_ry == cur_y:
            return []
        ys = sorted(y for y in ROAD_Y
                    if min(cur_y, goal_ry) <= y <= max(cur_y, goal_ry))
        if dys < 0: ys = ys[::-1]
        return [(cur_x, y, 'v', dys) for y in ys]

    cur_x, cur_y = start_rx, start_ry
    if h_first:
        steps = h_leg(cur_x, cur_y)
        cur_x = goal_rx
        steps += v_leg(cur_x, cur_y)
    else:
        steps = v_leg(cur_x, cur_y)
        cur_y = goal_ry
        steps += h_leg(cur_x, cur_y)

    # This keeps the car in its correct lane
    path = []
    prev_axis  = None
    last_lane_x = None   # x position of last vertical leg
    last_lane_y = None   # y position of last horizontal leg

    for rx, ry, axis, dsign in steps:
        if axis == 'h':
            lane_y = lane_pos(ry, dsign, LANE_W)
            if prev_axis == 'v':
                # Transitioning from vertical to horizontal.
                path.append((last_lane_x, lane_y))
            path.append((rx, lane_y))
            last_lane_y = lane_y
        else:  # 'v'
            lane_x = lane_pos(rx, dsign, LANE_W)
            if prev_axis == 'h':
                # Transitioning from horizontal to vertical.
                path.append((lane_x, last_lane_y))
            path.append((lane_x, ry))
            last_lane_x = lane_x
        prev_axis = axis

    if not path:
        path.append((gx, gy))
    else:
        path.append((gx, gy))

    # Deduplicate
    filtered = []
    for p in path:
        if not filtered or abs(p[0]-filtered[-1][0]) > 2 or abs(p[1]-filtered[-1][1]) > 2:
            filtered.append(p)
    return filtered
