#Road geometry helpers and grid pathfinder

import math
from config import ROAD_X, ROAD_Y, ROAD_HALF_WIDTH, MAP_WIDTH, MAP_HEIGHT


def is_on_road(x: float, y: float) -> bool:
    for rx in ROAD_X:
        if abs(x - rx) <= ROAD_HALF_WIDTH:
            return True
    for ry in ROAD_Y:
        if abs(y - ry) <= ROAD_HALF_WIDTH:
            return True
    return False


def snap_to_road(x: float, y: float):
    nearest_x = min(ROAD_X, key=lambda rx: abs(rx - x))
    nearest_y = min(ROAD_Y, key=lambda ry: abs(ry - y))
    if abs(nearest_x - x) <= abs(nearest_y - y):
        return (nearest_x, y)
    return (x, nearest_y)


def get_drop_off_point(landmark_x: float, landmark_y: float):
    best_v = min(ROAD_X, key=lambda rx: abs(rx - landmark_x))
    best_h = min(ROAD_Y, key=lambda ry: abs(ry - landmark_y))

    if abs(best_v - landmark_x) <= abs(best_h - landmark_y):
        #Nearest road is vertical
        offset = 20 if landmark_x > best_v else -20
        road_y = max(50, min(MAP_HEIGHT - 50, landmark_y))
        return (best_v + offset, road_y)
    else:
        #Nearest road is horizontal
        offset = 20 if landmark_y > best_h else -20
        road_x = max(50, min(MAP_WIDTH - 50, landmark_x))
        return (road_x, best_h + offset)


def find_grid_path(start, goal):
    LANE_W = 18
    sx, sy = start
    gx, gy = goal

    start_rx = min(ROAD_X, key=lambda rx: abs(rx - sx))
    start_ry = min(ROAD_Y, key=lambda ry: abs(ry - sy))
    goal_rx  = min(ROAD_X, key=lambda rx: abs(rx - gx))
    goal_ry  = min(ROAD_Y, key=lambda ry: abs(ry - gy))

    raw = [(sx, sy, 0, 0)]
    cur_x, cur_y = start_rx, start_ry

    h_dist = abs(goal_rx - start_rx)
    v_dist = abs(goal_ry - start_ry)

    if h_dist >= v_dist:
        dx_sign = 1 if goal_rx >= cur_x else -1
        xs = sorted(x for x in ROAD_X if min(cur_x, goal_rx) <= x <= max(cur_x, goal_rx))
        if dx_sign < 0: xs = xs[::-1]
        for x in xs:
            raw.append((x, cur_y, dx_sign, 0))
        cur_x = goal_rx

        dy_sign = 1 if goal_ry >= cur_y else -1
        ys = sorted(y for y in ROAD_Y if min(cur_y, goal_ry) <= y <= max(cur_y, goal_ry))
        if dy_sign < 0: ys = ys[::-1]
        for y in ys:
            raw.append((cur_x, y, 0, dy_sign))
    else:
        dy_sign = 1 if goal_ry >= cur_y else -1
        ys = sorted(y for y in ROAD_Y if min(cur_y, goal_ry) <= y <= max(cur_y, goal_ry))
        if dy_sign < 0: ys = ys[::-1]
        for y in ys:
            raw.append((cur_x, y, 0, dy_sign))
        cur_y = goal_ry

        dx_sign = 1 if goal_rx >= cur_x else -1
        xs = sorted(x for x in ROAD_X if min(cur_x, goal_rx) <= x <= max(cur_x, goal_rx))
        if dx_sign < 0: xs = xs[::-1]
        for x in xs:
            raw.append((x, cur_y, dx_sign, 0))

    raw.append((gx, gy, 0, 0))

    #Convert the center line points to lane offset points
    path = []
    for x, y, dxs, dys in raw:
        if dxs != 0:
            path.append((x, y + LANE_W * dxs))
        elif dys != 0:
            path.append((x + LANE_W * dys, y))
        else:
            path.append((x, y))

    #Deduplicate nearby points
    filtered = []
    for p in path:
        if not filtered or abs(p[0] - filtered[-1][0]) > 2 or abs(p[1] - filtered[-1][1]) > 2:
            filtered.append(p)

    return filtered