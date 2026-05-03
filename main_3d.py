# 3d Version

import sys
import math
import random

from direct.showbase.ShowBase import ShowBase
from direct.task              import Task
from panda3d.core             import (
    WindowProperties, Vec3, Point3, ClockObject,
    loadPrcFileData,
)
from panda3d.core import ClockObject as _ClockObject
globalClock = _ClockObject.getGlobalClock()

# Configure window
loadPrcFileData("", "window-title AI Driver 3D")
loadPrcFileData("", "win-size 1280 720")
loadPrcFileData("", "sync-video 0")       # uncapped fps during dev
loadPrcFileData("", "show-frame-rate-meter 1")

from config     import (ROAD_X, ROAD_Y, ROAD_HALF_WIDTH,
                        MAP_WIDTH, MAP_HEIGHT, LANDMARKS)
from database   import init_database
from road       import is_on_road, snap_to_road, get_drop_off_point
from traffic    import AgentType, TrafficLight, VehicleAgent
import traffic  as _traffic_module
from navigation import parse_destination
from ui         import login_screen
from scene3d    import (
    SCALE, s2p,
    build_ground, build_roads, build_buildings, build_parking_lots,
    build_all_traffic_lights, update_traffic_light_visuals,
    create_vehicle_nodes, sync_vehicle_nodes,
    make_vehicle_node, setup_lighting,
)
from hud3d    import HUD3D
from weather  import WeatherSystem, SPEED_MULTIPLIERS

class AIDriver3D(ShowBase):

    def __init__(self, user_id: int):
        ShowBase.__init__(self)
        self.user_id = user_id

        # Disable default mouse
        self.disableMouse()

        # Window
        props = WindowProperties()
        props.setTitle("AI Driver 3D")
        self.win.requestProperties(props)

        # State of simulation
        self.vehicles        = []
        self.next_vehicle_id = 1
        self.traffic_lights  = []
        self.chat_history    = []
        self.current_input   = ""
        self.input_active    = False
        self._frame_count    = 0

        # Vehicles list
        _traffic_module._all_vehicles_ref = self.vehicles

        # Traffic lights
        half_cycle = 150 + 30
        for rx in ROAD_X[1:-1]:
            for ry in ROAD_Y[1:-1]:
                lid = len(self.traffic_lights)
                self.traffic_lights.append(TrafficLight(rx, ry, 'horizontal', lid,   phase_offset=0))
                self.traffic_lights.append(TrafficLight(rx, ry, 'vertical',   lid+1, phase_offset=half_cycle))

        # Vehicle
        self.player = VehicleAgent(600, 700, AgentType.HUMAN, 0, (50, 100, 220))
        self.vehicles.append(self.player)

        # 3D setup
        setup_lighting(self.render)
        build_ground(self.render, MAP_WIDTH, MAP_HEIGHT)
        build_roads(self.render, ROAD_X, ROAD_Y, ROAD_HALF_WIDTH, MAP_WIDTH, MAP_HEIGHT)
        build_buildings(self.render, LANDMARKS)
        build_parking_lots(self.render)
        self.light_fixtures = build_all_traffic_lights(self.render, self.traffic_lights)

        # 3D nodes
        self.vehicle_nodes: dict = {}
        self.vehicle_nodes[self.player.id] = make_vehicle_node(
            self.render, self.player.color, is_player=True
        )

        # Initial traffic
        for _ in range(12):
            self.spawn_ai_vehicle()

        # HUD
        self.hud = HUD3D()
        self._add_chat("System", "AI Driver 3D ready!")
        self._add_chat("System", "Type a destination in the input bar")
        self._add_chat("System", "W = cycle weather")
        # Weather
        self.weather = WeatherSystem()

        # Camera
        self.cam_distance = 4.0    # Units behind player
        self.cam_height   = 2.5    # Units above player
        self.cam_lag      = 0.08
        self._cam_target  = Point3(0, 0, 0)

        self._setup_keys()

        # Accumulator
        self._sim_dt       = 1.0 / 30.0
        self._time_accum   = 0.0

        self.taskMgr.add(self._update, "main_update")

    # Keayboard input

    def _setup_keys(self):
        # Printable characters
        for code in range(32, 127):
            ch = chr(code)
            self.accept(ch, self._on_char, [ch])

        self.accept("backspace",   self._on_backspace)
        self.accept("enter",       self._on_enter)
        self.accept("escape",      sys.exit)

        # Camera distance adjustment
        self.accept("wheel_up",   self._cam_zoom_in)
        self.accept("wheel_down", self._cam_zoom_out)

        # Special keys
        self.accept("1", self._hotkey, ["1"])
        self.accept("2", self._hotkey, ["2"])
        self.accept("3", self._hotkey, ["3"])
        self.accept("t", self._hotkey, ["t"])
        self.accept("a", self._hotkey, ["a"])
        self.accept("q", self._hotkey, ["q"])
        self.accept("w", self._hotkey, ["w"])

    def _on_char(self, ch: str):
        if len(self.current_input) < 60:
            self.current_input += ch
            self.input_active   = True

    def _on_backspace(self):
        self.current_input = self.current_input[:-1]

    def _hotkey(self, key: str):
        if self.input_active or self.current_input:
            self._on_char(key)
            return
        
        # No text typed yet — execute shortcut
        if   key == "1": self.spawn_ai_vehicle(AgentType.AI_RANDOM);     self._add_chat("System", "Spawned: Random AI")
        elif key == "2": self.spawn_ai_vehicle(AgentType.AI_EFFICIENT);  self._add_chat("System", "Spawned: Efficient AI")
        elif key == "3": self.spawn_ai_vehicle(AgentType.AI_AGGRESSIVE); self._add_chat("System", "Spawned: Aggressive AI")
        elif key == "t": self.hud.toggle_stats()
        elif key == "a": self._toggle_lights()
        elif key == "q": sys.exit()
        elif key == "w":
            new_wx = self.weather.cycle()
            self._apply_weather_to_scene()
            self._add_chat("System", f"Weather: {new_wx}")

    def _on_enter(self):
        text = self.current_input.strip()
        if not text:
            return
        self._add_chat("User", text)
        dest_name, road_pos, orig_pos = parse_destination(
            text, self.player.x, self.player.y, self.user_id
        )
        if dest_name and road_pos:
            self.player.set_destination(dest_name, road_pos, orig_pos)
            self._add_chat("Driver", f"Navigating to {dest_name}...")
        elif dest_name:
            self._add_chat("Driver", dest_name)
        else:
            self._add_chat("Driver", "Unknown destination. Try: airport, mall, hospital")
        self.current_input = ""
        self.input_active  = False

    def _toggle_lights(self):
        # Freeze/unfreeze lights
        if not hasattr(self, '_lights_frozen'):
            self._lights_frozen = False
        self._lights_frozen = not self._lights_frozen
        mode = "Frozen" if self._lights_frozen else "Running"
        self._add_chat("System", f"Lights: {mode}")

    def _cam_zoom_in(self):
        self.cam_distance = max(1.5, self.cam_distance - 0.3)

    def _cam_zoom_out(self):
        self.cam_distance = min(12.0, self.cam_distance + 0.3)

    # Chat management

    def _add_chat(self, sender: str, message: str):
        self.chat_history.append((sender, message))
        if len(self.chat_history) > 6:
            self.chat_history.pop(0)

    # Spawning

    def spawn_ai_vehicle(self, agent_type=None):
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
            if any(math.sqrt((v.x - sx)**2 + (v.y - sy)**2) < 100 for v in self.vehicles):
                continue
            spawn_x, spawn_y = sx, sy
            break

        if spawn_x is None:
            spawn_x, spawn_y = float(random.choice(ROAD_X)), float(random.choice(ROAD_Y))

        v = VehicleAgent(spawn_x, spawn_y, agent_type, self.next_vehicle_id)

        if LANDMARKS:
            if agent_type == AgentType.AI_EFFICIENT:
                target = min(LANDMARKS, key=lambda l:
                    math.sqrt((l["pos"][0]-spawn_x)**2 + (l["pos"][1]-spawn_y)**2))
            elif agent_type == AgentType.AI_AGGRESSIVE:
                dists  = [math.sqrt((l["pos"][0]-spawn_x)**2 + (l["pos"][1]-spawn_y)**2)
                          for l in LANDMARKS]
                total  = sum(dists) or 1
                target = random.choices(LANDMARKS, weights=[d/total for d in dists], k=1)[0]
            else:
                target = random.choice(LANDMARKS)
            v.set_destination(target["name"], get_drop_off_point(*target["pos"], target["name"]), target["pos"])

        v._idle_delay = 0
        self.vehicles.append(v)
        self.vehicle_nodes[v.id] = make_vehicle_node(self.render, v.color, is_player=False)
        self.next_vehicle_id += 1
        return v

    def _update(self, task):
        # Accumulate
        dt = globalClock.getDt()
        self._time_accum += dt

        sim_stepped = False
        while self._time_accum >= self._sim_dt:
            self._time_accum -= self._sim_dt
            self._sim_step()
            sim_stepped = True

        # Sync visuals and camera every render frame
        if sim_stepped:
            sync_vehicle_nodes(self.vehicle_nodes, self.vehicles)
            update_traffic_light_visuals(self.light_fixtures, self.traffic_lights)

        self._update_camera()

        # HUD updates
        self.hud.update_status(self.player)
        self.hud.update_chat(self.chat_history)
        self.hud.update_input(self.current_input, self.input_active)
        self.hud.update_stats(self.vehicles)
        self.hud.update_weather(
            self.weather.state.value,
            SPEED_MULTIPLIERS[self.weather.state]
        )

        return Task.cont

    def _sim_step(self):
        self._frame_count += 1

        # Weather tick
        self.weather.update()
        self.weather.apply_to_vehicles(self.vehicles)

        # Periodic AI spawn
        if self._frame_count % 90 == 0 and len(self.vehicles) < 25:
            self.spawn_ai_vehicle()

        # Traffic lights
        if not getattr(self, '_lights_frozen', False):
            for light in self.traffic_lights:
                light.update(self.vehicles, self.traffic_lights)

        # Vehicles
        for vehicle in self.vehicles[:]:
            vehicle.update(None, self.traffic_lights, self.vehicles)

            if vehicle.agent_type != AgentType.HUMAN and vehicle.state == "arrived":
                if vehicle.id in self.vehicle_nodes:
                    self.vehicle_nodes[vehicle.id].removeNode()
                    del self.vehicle_nodes[vehicle.id]
                self.vehicles.remove(vehicle)
                if len(self.vehicles) < 22:
                    self.spawn_ai_vehicle()
                continue

            if vehicle.stuck_counter > 200 and vehicle.agent_type == AgentType.HUMAN:
                vehicle.x, vehicle.y = snap_to_road(vehicle.x, vehicle.y)
                vehicle.stuck_counter = 0


    def _apply_weather_to_scene(self):
        from panda3d.core import AmbientLight, Fog, Vec4
        from weather import WeatherState
        self.render.clearFog()
        state = self.weather.state
        al = AmbientLight("weather_ambient")
        if state == WeatherState.CLEAR:
            al.setColor(Vec4(0.45, 0.45, 0.45, 1))
            self.render.setLight(self.render.attachNewNode(al))
        elif state == WeatherState.RAIN:
            al.setColor(Vec4(0.30, 0.32, 0.40, 1))
            self.render.setLight(self.render.attachNewNode(al))
            fog = Fog("rain_fog")
            fog.setColor(0.55, 0.58, 0.65)
            fog.setLinearRange(15, 60)
            self.render.setFog(fog)
        elif state == WeatherState.HEAVY_RAIN:
            al.setColor(Vec4(0.20, 0.22, 0.32, 1))
            self.render.setLight(self.render.attachNewNode(al))
            fog = Fog("heavy_rain_fog")
            fog.setColor(0.40, 0.43, 0.52)
            fog.setLinearRange(8, 35)
            self.render.setFog(fog)
        elif state == WeatherState.NIGHT:
            al.setColor(Vec4(0.08, 0.08, 0.15, 1))
            self.render.setLight(self.render.attachNewNode(al))
            fog = Fog("night_fog")
            fog.setColor(0.02, 0.02, 0.08)
            fog.setLinearRange(12, 45)
            self.render.setFog(fog)

    # Camera
    def _update_camera(self):
        px = self.player.x * SCALE
        py = -self.player.y * SCALE   # negate Y for Panda convention

        # Direction opposite to the car's heading
        angle_rad   = math.radians(self.player.angle)
        back_x      = -math.cos(angle_rad) * self.cam_distance
        back_y      =  math.sin(angle_rad) * self.cam_distance   # negated Y
        ideal_cam   = Point3(px + back_x, py + back_y, self.cam_height)

        # Lerp camera position
        cur = self.camera.getPos()
        new_pos = Point3(
            cur.x + (ideal_cam.x - cur.x) * self.cam_lag,
            cur.y + (ideal_cam.y - cur.y) * self.cam_lag,
            cur.z + (ideal_cam.z - cur.z) * self.cam_lag,
        )
        self.camera.setPos(new_pos)

        # Always look at player
        target = Point3(px, py, 0.15)
        self.camera.lookAt(target)


# Entry point

if __name__ == "__main__":
    init_database()
    user_id = login_screen()
    app     = AIDriver3D(user_id)
    app.run()
