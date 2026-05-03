# traffic.py

import math
import random
from enum import Enum

from config  import ROAD_X, ROAD_Y, ROAD_HALF_WIDTH, MAP_WIDTH, MAP_HEIGHT, LANDMARKS
from road    import is_on_road, snap_to_road, get_drop_off_point, get_driveway_point, find_grid_path


class AgentType(Enum):
    HUMAN      = "human"
    AI_RANDOM  = "ai_random"
    AI_EFFICIENT  = "ai_efficient"
    AI_AGGRESSIVE = "ai_aggressive"


class TrafficLightState(Enum):
    RED    = "red"
    GREEN  = "green"
    YELLOW = "yellow"

_all_vehicles_ref = []


class TrafficLight:
    def __init__(self, x, y, orientation, light_id, phase_offset=0):
        self.x = x
        self.y = y
        self.orientation  = orientation   # 'horizontal' or 'vertical'
        self.id           = light_id
        self.green_duration  = 150
        self.yellow_duration = 30
        self.red_duration    = 120
        # phase_offset shifts
        self.timer        = phase_offset
        self.state        = TrafficLightState.GREEN
        self.queue_length = 0
        self.waiting_vehicles = []

    def update(self, vehicles, _all_lights, dt=1):
        self.waiting_vehicles = [
            v.id for v in vehicles
            if v.state == "driving" and v.waiting_at_light and v.target_light is self
        ]
        self.queue_length = len(self.waiting_vehicles)

        self.timer += dt
        cycle = self.green_duration + self.yellow_duration + self.red_duration
        pos   = self.timer % cycle

        if pos < self.green_duration:
            self.state = TrafficLightState.GREEN
        elif pos < self.green_duration + self.yellow_duration:
            self.state = TrafficLightState.YELLOW
        else:
            self.state = TrafficLightState.RED


class VehicleAgent:
    def __init__(self, x, y, agent_type=AgentType.AI_RANDOM, vehicle_id=0, color=None):
        self.id         = vehicle_id
        self.x          = float(x)
        self.y          = float(y)
        self.angle      = random.choice([0, 90, 180, 270])
        self.speed      = 0.0
        self.agent_type = agent_type

        # Visual colour
        if color is not None:
            self.color = color
        elif agent_type == AgentType.HUMAN:
            self.color = (50, 50, 220)
        elif agent_type == AgentType.AI_RANDOM:
            self.color = (220, 50, 50)
        elif agent_type == AgentType.AI_EFFICIENT:
            self.color = (50, 220, 50)
        else:
            self.color = (220, 220, 50)

        # Navigation state
        self.current_destination = None
        self.destination_name    = None
        self.path         = []
        self.waypoint_idx = 0
        self.state        = "idle"
        self.stuck_counter = 0
        self.last_pos     = (x, y)

        # Per-type driving personality
        if agent_type == AgentType.AI_AGGRESSIVE:
            self.max_speed          = 6.5
            self.following_distance = 45
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
        else:   # HUMAN
            self.max_speed          = 5.0
            self.following_distance = 70
            self.comfortable_decel  = 0.15
            self.max_decel          = 0.4
            self.acceleration       = 0.1

        self.desired_speed = self.max_speed
        self.lane_offset   = 18

        # Traffic state
        self.waiting_at_light = False
        self.target_light     = None
        self.wait_time        = 0
        self.total_wait_time  = 0
        self.in_queue         = False
        self.vehicle_ahead    = None

        # Misc
        self.tire_tracks   = []
        self.behavior_timer = 0
        self.park_duration  = random.randint(60, 240)
        self.bounds = {
            'min_x': 50, 'max_x': MAP_WIDTH  - 50,
            'min_y': 50, 'max_y': MAP_HEIGHT - 50,
        }

    # Interface

    def set_destination(self, dest_name, dest_pos, original_pos=None):
        self.destination_name    = dest_name
        self.current_destination = dest_pos
        self.original_goal       = original_pos or dest_pos
        self.state        = "driving"
        self.path         = []
        self.waypoint_idx = 0
        self.speed        = 0
        self.waiting_at_light = False
        self.in_queue         = False

        # Build path to driveway
        driveway = get_driveway_point(dest_name)
        if driveway:
            self.path = find_grid_path((self.x, self.y), driveway, self.angle)
            # Parking spot
        else:
            self.path = find_grid_path((self.x, self.y), dest_pos, self.angle)
        self.waypoint_idx = 0
        
        start_angle_set = False
        for wp in self.path[1:]:
            ddx = wp[0] - self.x
            ddy = wp[1] - self.y
            if abs(ddx) > 5 or abs(ddy) > 5:
                raw = math.degrees(math.atan2(ddy, ddx))
                # Snap to nearest cardinal direction for clean lane entry
                if abs(ddx) >= abs(ddy):
                    self.angle = 0 if ddx >= 0 else 180
                else:
                    self.angle = 90 if ddy >= 0 else 270
                start_angle_set = True
                break
        if not start_angle_set:
            dx = dest_pos[0] - self.x
            dy = dest_pos[1] - self.y
            self.angle = 0 if abs(dx) >= abs(dy) and dx >= 0 else \
                         180 if abs(dx) >= abs(dy) else \
                         90 if dy >= 0 else 270

        # Snap the car precisely into the correct lane
        self._update_lane_direction(self.x, self.y)
        if self.path:
            travel_ddx, travel_ddy = 0, 0
            for wp in self.path:
                ddx = wp[0] - self.x
                ddy = wp[1] - self.y
                if abs(ddx) > 30 or abs(ddy) > 30:
                    travel_ddx, travel_ddy = ddx, ddy
                    break
            if abs(travel_ddx) >= abs(travel_ddy):
                # Primarily horizontal travel
                nearest_ry = min(ROAD_Y, key=lambda ry: abs(ry - self.y))
                self.lane_offset = 18 if travel_ddx >= 0 else -18
                self.y = float(nearest_ry + self.lane_offset)
            elif abs(travel_ddy) > 0:
                # Primarily vertical travel
                nearest_rx = min(ROAD_X, key=lambda rx: abs(rx - self.x))
                self.lane_offset = 18 if travel_ddy >= 0 else -18
                self.x = float(nearest_rx + self.lane_offset)
        if not is_on_road(self.x, self.y):
            self._snap_to_lane()

    def update(self, world_map, traffic_lights, all_vehicles, dt=1):
        self._enforce_boundaries()

        # Tire tracks
        if self.speed > 0.5:
            self.tire_tracks.append((self.x, self.y, self.angle, 1.0))
            if len(self.tire_tracks) > 40:
                self.tire_tracks.pop(0)
        self.tire_tracks = [
            (x, y, a, o * 0.95) for x, y, a, o in self.tire_tracks if o > 0.05
        ]

        if self.agent_type != AgentType.HUMAN and self.state == "idle":
            self._ai_select_destination()

        if self.state == "driving" and self.current_destination:
            self._navigate(all_vehicles, traffic_lights)

        self._check_stuck()

        if self.waiting_at_light:
            self.wait_time       += dt
            self.total_wait_time += dt

    # AI destination selection

    def _ai_select_destination(self):
        if not hasattr(self, '_idle_delay'):
            self._idle_delay = random.randint(0, 45)
        if self._idle_delay > 0:
            self._idle_delay -= 1
            return
        if not LANDMARKS:
            return

        if self.agent_type == AgentType.AI_EFFICIENT:
            target = min(LANDMARKS, key=lambda l:
                math.sqrt((l["pos"][0] - self.x)**2 + (l["pos"][1] - self.y)**2))

        elif self.agent_type == AgentType.AI_AGGRESSIVE:
            dists  = [math.sqrt((l["pos"][0]-self.x)**2 + (l["pos"][1]-self.y)**2)
                      for l in LANDMARKS]
            total  = sum(dists) or 1
            target = random.choices(LANDMARKS, weights=[d/total for d in dists], k=1)[0]

        else:
            target = random.choice(LANDMARKS)

        dest_pos = get_drop_off_point(target["pos"][0], target["pos"][1], target["name"])
        self.set_destination(target["name"], dest_pos, target["pos"])
        self._idle_delay = random.randint(30, 120)

    # Navigation and behavior

    def _navigate(self, all_vehicles, traffic_lights):
        # Arrival check
        dist_to_dest = math.sqrt(
            (self.x - self.current_destination[0])**2 +
            (self.y - self.current_destination[1])**2
        )
        if dist_to_dest < 25:
            self.state = "arrived"
            self.speed = 0
            self.waiting_at_light = False
            return

        # Build path only when empty
        if not self.path:
            self.path = find_grid_path((self.x, self.y), self.current_destination, self.angle)
            self.waypoint_idx = 0
        if not self.path:
            self.state = "idle"
            self.speed = 0
            return
        if self.waypoint_idx >= len(self.path):
            self.waypoint_idx = len(self.path) - 1

        wx, wy    = self.path[self.waypoint_idx]
        wp_dist   = math.sqrt((wx - self.x)**2 + (wy - self.y)**2)
        adv_r     = 20 if self.waypoint_idx == len(self.path) - 1 else 45
        if wp_dist < adv_r and self.waypoint_idx + 1 < len(self.path):
            self.waypoint_idx += 1
            wx, wy = self.path[self.waypoint_idx]

        # Speed decisions
        target_speed   = self.max_speed
        vehicle_ahead  = self._find_vehicle_ahead(all_vehicles)
        self.vehicle_ahead = vehicle_ahead
        light_ahead, dist_to_light = self._check_light_ahead(traffic_lights)

        # Vehicle following
        if vehicle_ahead:
            dist     = math.sqrt((vehicle_ahead.x - self.x)**2 + (vehicle_ahead.y - self.y)**2)
            safe_gap = 44   # larger gap = stops earlier
            if dist <= safe_gap:
                target_speed = 0
            elif dist < self.following_distance:
                ratio        = (dist - safe_gap) / (self.following_distance - safe_gap)
                target_speed = vehicle_ahead.speed * max(0.0, min(1.0, ratio))
            self.in_queue = (dist < self.following_distance)
        else:
            self.in_queue = False

        # --- Traffic light ---
        STOP_DIST  = 65    # Car front rests just behind the stop line
        BRAKE_DIST = 160   # Start easing off from here
        self.waiting_at_light = False
        if light_ahead and dist_to_light < BRAKE_DIST:
            if light_ahead.state == TrafficLightState.RED:
                if dist_to_light <= STOP_DIST:
                    target_speed = 0
                    self.waiting_at_light = True
                    self.target_light     = light_ahead
                else:
                    # Proportional braking
                    t = (dist_to_light - STOP_DIST) / (BRAKE_DIST - STOP_DIST)
                    target_speed = min(target_speed, self.max_speed * max(0.0, t))
            elif light_ahead.state == TrafficLightState.YELLOW:
                if dist_to_light <= STOP_DIST:
                    target_speed = 0
                    self.waiting_at_light = True
                    self.target_light     = light_ahead
                else:
                    t = (dist_to_light - STOP_DIST) / (BRAKE_DIST - STOP_DIST)
                    target_speed = min(target_speed, self.max_speed * max(0.0, t))

        # Cornering
        angle_to_wp = math.degrees(math.atan2(wy - self.y, wx - self.x))
        angle_diff  = abs(angle_to_wp - self.angle)
        while angle_diff > 180:
            angle_diff = 360 - angle_diff
        if angle_diff > 60:
            target_speed = min(target_speed, 2.0)
        elif angle_diff > 30:
            target_speed = min(target_speed, 3.5)

        # Acceleration / braking
        if target_speed < self.speed:
            if vehicle_ahead:
                vdist = math.sqrt((vehicle_ahead.x - self.x)**2 + (vehicle_ahead.y - self.y)**2)
                t     = max(0.0, 1.0 - (vdist - 35) / 50.0)
                decel = self.comfortable_decel + t * (self.max_decel - self.comfortable_decel)
            else:
                decel = self.max_decel
            self.speed = max(target_speed, self.speed - decel)
        else:
            self.speed = min(target_speed, self.speed + self.acceleration)
        self.speed = max(0.0, min(self.speed, self.max_speed))

        on_final_leg = (self.waypoint_idx >= len(self.path) - 1)

        if self.speed > 0.1:
            ddx = wx - self.x
            ddy = wy - self.y

            if on_final_leg:
                self._steer_toward(wx, wy)
                rad = math.radians(self.angle)
                self.x += self.speed * math.cos(rad)
                self.y += self.speed * math.sin(rad)

            elif abs(ddx) >= abs(ddy):
                # Horizontal segment
                nearest_ry = min(ROAD_Y, key=lambda ry: abs(ry - self.y))
                sign = 1 if ddx > 0 else -1
                self.lane_offset = 18 * sign
                lane_y = nearest_ry + self.lane_offset
                target_angle = 0.0 if sign > 0 else 180.0

                # Smoothly rotate angle toward target
                angle_err = target_angle - self.angle
                while angle_err >  180: angle_err -= 360
                while angle_err < -180: angle_err += 360
                self.angle += max(-8.0, min(8.0, angle_err))
                while self.angle >= 360: self.angle -= 360
                while self.angle <   0:  self.angle += 360

                # Move along X
                step = min(self.speed, abs(ddx))
                self.x += step * sign
                # Pull Y toward lane
                y_err = lane_y - self.y
                pull  = 0.25 if abs(y_err) < 5 else 0.6
                self.y += y_err * pull

            else:
                # Vertical segment
                nearest_rx = min(ROAD_X, key=lambda rx: abs(rx - self.x))
                sign = 1 if ddy > 0 else -1
                self.lane_offset = 18 * sign
                lane_x = nearest_rx + self.lane_offset
                target_angle = 90.0 if sign > 0 else 270.0

                # Smoothly rotate angle toward target
                angle_err = target_angle - self.angle
                while angle_err >  180: angle_err -= 360
                while angle_err < -180: angle_err += 360
                self.angle += max(-8.0, min(8.0, angle_err))
                while self.angle >= 360: self.angle -= 360
                while self.angle <   0:  self.angle += 360

                step = min(self.speed, abs(ddy))
                self.y += step * sign
                x_err = lane_x - self.x
                pull  = 0.25 if abs(x_err) < 5 else 0.6
                self.x += x_err * pull

        self._update_lane_direction(wx, wy)

    # Vehicle detection and traffic light checks

    def _find_vehicle_ahead(self, all_vehicles):
        closest, min_dist = None, float('inf')

        cardinal = round(self.angle / 90) * 90 % 360
        moving_h = (cardinal == 0 or cardinal == 180)

        for other in all_vehicles:
            if other.id == self.id:
                continue
            dx   = other.x - self.x
            dy   = other.y - self.y
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 120 or dist < 1:
                continue

            # Lane filter
            if moving_h:
                if abs(dy) > 28:
                    continue
            else:
                if abs(dx) > 28:
                    continue

            ahead_x = math.cos(math.radians(self.angle))
            ahead_y = math.sin(math.radians(self.angle))
            if dx * ahead_x + dy * ahead_y < 0:
                continue

            # Hard proximity stop
            if dist <= 44:
                if dist < min_dist:
                    min_dist = dist
                    closest  = other
                continue

            # Forward cone check
            bearing = math.degrees(math.atan2(dy, dx))
            b_diff  = bearing - self.angle
            while b_diff >  180: b_diff -= 360
            while b_diff < -180: b_diff += 360
            if abs(b_diff) > 35:
                continue

            if dist < min_dist:
                min_dist = dist
                closest  = other
        return closest

    def _check_light_ahead(self, traffic_lights):
        best_light, best_dist = None, float('inf')
        rad = math.radians(self.angle)
        moving_h = abs(math.cos(rad)) >= abs(math.sin(rad))
        my_axis  = 'horizontal' if moving_h else 'vertical'

        for light in traffic_lights:
            # Only check the light that matches our axis of travel
            if light.orientation != my_axis:
                continue
            dx   = light.x - self.x
            dy   = light.y - self.y
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 180 or dist < 20:
                continue
            diff = math.degrees(math.atan2(dy, dx)) - self.angle
            while diff >  180: diff -= 360
            while diff < -180: diff += 360
            if abs(diff) < 35 and dist < best_dist:
                best_dist  = dist
                best_light = light
        return best_light, best_dist

    # Steering and lane management

    def _steer_toward(self, wx, wy):
        dx = wx - self.x
        dy = wy - self.y
        if abs(dx) < 1 and abs(dy) < 1:
            return
        target_angle = math.degrees(math.atan2(dy, dx))
        steer = target_angle - self.angle
        while steer >  180: steer -= 360
        while steer < -180: steer += 360
        self.angle += max(-5.0, min(5.0, steer * 0.4))
        while self.angle >= 360: self.angle -= 360
        while self.angle < 0:    self.angle += 360

    def _get_lane_target(self, wx, wy):
        LANE_W = 18
        rad    = math.radians(self.angle)
        ch, sh = math.cos(rad), math.sin(rad)
        if abs(ch) >= abs(sh):
            road_y = min(ROAD_Y, key=lambda ry: abs(ry - self.y))
            return wx, road_y + (LANE_W if ch > 0 else -LANE_W)
        else:
            road_x = min(ROAD_X, key=lambda rx: abs(rx - self.x))
            return road_x + (LANE_W if sh > 0 else -LANE_W), wy

    def _update_lane_direction(self, wx, wy):
        LANE_W = 18
        rad    = math.radians(self.angle)
        ch, sh = math.cos(rad), math.sin(rad)
        self.lane_offset = LANE_W if (
            (abs(ch) >= abs(sh) and ch > 0) or
            (abs(sh) >  abs(ch) and sh > 0)
        ) else -LANE_W

    def _snap_to_lane(self):
        self._update_lane_direction(self.x, self.y)
        nx = min(ROAD_X, key=lambda rx: abs(rx - self.x))
        ny = min(ROAD_Y, key=lambda ry: abs(ry - self.y))
        if abs(self.x - nx) <= abs(self.y - ny):
            self.x = nx + self.lane_offset
        else:
            self.y = ny + self.lane_offset

    # Stuck detection and recovery

    def _check_stuck(self):
        moved = math.sqrt(
            (self.x - self.last_pos[0])**2 + (self.y - self.last_pos[1])**2
        )
        # Not stuck if: waiting at a light, following another car, or moving
        legitimately_stopped = (
            self.waiting_at_light or
            self.in_queue or
            self.vehicle_ahead is not None
        )
        if moved < 0.1 and self.state == "driving" and not legitimately_stopped:
            self.stuck_counter += 1
            if self.stuck_counter > 180:  # must exceed full red-light cycle (120 frames)
                if self.agent_type != AgentType.HUMAN:
                    self._unstick()
                else:
                    self.x, self.y = snap_to_road(self.x, self.y)
                self.stuck_counter = 0
        else:
            self.stuck_counter = 0
        self.last_pos = (self.x, self.y)

    def _unstick(self):
        lo = random.choice([-18, 18])   # Pick a lane
        for _ in range(20):
            rx = random.choice(ROAD_X)
            ry = random.choice(ROAD_Y)
            tx, ty = float(rx + lo), float(ry)
            if not any(
                v.id != self.id and math.sqrt((v.x-tx)**2 + (v.y-ty)**2) < 80
                for v in _all_vehicles_ref
            ):
                self.x, self.y = tx, ty
                self.lane_offset = lo
                break
        else:
            self.x = float(random.choice(ROAD_X)) + lo
            self.y = float(random.choice(ROAD_Y))
            self.lane_offset = lo
        self.speed        = 0
        self.path         = []
        self.waypoint_idx = 0
        self.state        = "idle"
        self._idle_delay  = random.randint(5, 20)

    # Boundary enforcement and road snapping

    def _enforce_boundaries(self):
        self.x = max(self.bounds['min_x'], min(self.bounds['max_x'], self.x))
        self.y = max(self.bounds['min_y'], min(self.bounds['max_y'], self.y))
        if not is_on_road(self.x, self.y):
            self.x, self.y = snap_to_road(self.x, self.y, self.lane_offset)
