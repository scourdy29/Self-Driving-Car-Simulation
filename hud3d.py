from direct.gui.DirectGui import (
    DirectFrame, DirectLabel, DirectEntry
)
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode, Vec4


# Colour helpers
_BLACK  = (0, 0, 0, 1)
_WHITE  = (1, 1, 1, 1)
_CYAN   = (0, 0.8, 1, 1)
_GREEN  = (0.2, 1, 0.3, 1)
_AMBER  = (1, 0.8, 0, 1)
_GREY   = (0.7, 0.7, 0.7, 1)
_PANEL  = (0.1, 0.1, 0.12, 0.88)
_TRANSP = (0, 0, 0, 0)

class HUD3D:
    def __init__(self):
        # Status bar
        self.status_text = OnscreenText(
            text="Player: IDLE",
            pos=(-1.33, 0.92),
            scale=0.055,
            fg=_WHITE,
            shadow=(0, 0, 0, 0.8),
            align=TextNode.ALeft,
        )
        self.speed_text = OnscreenText(
            text="Speed: 0.0",
            pos=(-1.33, 0.86),
            scale=0.045,
            fg=_GREY,
            shadow=(0, 0, 0, 0.8),
            align=TextNode.ALeft,
        )

        # Chat Panel
        self.chat_frame = DirectFrame(
            frameColor=_PANEL,
            frameSize=(-1.33, 0.0, -0.62, -0.30),
            pos=(0, 0, 0),
        )
        self.chat_lines = []
        for i in range(6):
            t = OnscreenText(
                text="",
                pos=(-1.28, -0.33 - i * 0.055),
                scale=0.042,
                fg=_GREY,
                shadow=(0, 0, 0, 0.7),
                align=TextNode.ALeft,
                mayChange=True,
            )
            self.chat_lines.append(t)

        # Input bar
        self.input_frame = DirectFrame(
            frameColor=(0.15, 0.15, 0.18, 0.9),
            frameSize=(-1.33, 0.80, -0.72, -0.64),
            pos=(0, 0, 0),
        )
        self.input_label = OnscreenText(
            text=">",
            pos=(-1.28, -0.69),
            scale=0.05,
            fg=_CYAN,
            align=TextNode.ALeft,
            mayChange=True,
        )

        # Stats 
        self.stats_frame = DirectFrame(
            frameColor=_PANEL,
            frameSize=(0.70, 1.33, -0.72, -0.42),
            pos=(0, 0, 0),
        )
        self.stats_title = OnscreenText(
            text="TRAFFIC STATS",
            pos=(0.75, -0.46),
            scale=0.048,
            fg=_CYAN,
            align=TextNode.ALeft,
        )
        self.stats_body = OnscreenText(
            text="",
            pos=(0.75, -0.52),
            scale=0.040,
            fg=_GREY,
            align=TextNode.ALeft,
            mayChange=True,
        )
        self.controls_text = OnscreenText(
            text="1=Random  2=Efficient  3=Aggressive\nA=Lights  T=Stats  W=Weather  Q=Quit",
            pos=(0.75, -0.60),
            scale=0.035,
            fg=(0.5, 0.5, 0.5, 1),
            align=TextNode.ALeft,
        )

        # Legend
        self.legend = OnscreenText(
            text="Blue=You  Red=Random  Green=Efficient  Yellow=Aggressive",
            pos=(0, -0.90),
            scale=0.038,
            fg=(0.55, 0.55, 0.55, 1),
            shadow=(0, 0, 0, 0.7),
            align=TextNode.ACenter,
        )

        # Arrived banner
        self.arrived_banner = OnscreenText(
            text="",
            pos=(0, 0.3),
            scale=0.08,
            fg=_GREEN,
            shadow=(0, 0, 0, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )

        self._stats_visible = True
        self._arrived_timer = 0

        # Weather 
        self.weather_text = OnscreenText(
            text="Weather: Clear",
            pos=(1.33, 0.92),
            scale=0.048,
            fg=(1.0, 0.87, 0.3, 1),
            shadow=(0, 0, 0, 0.8),
            align=TextNode.ARight,
            mayChange=True,
        )
        self.weather_sub = OnscreenText(
            text="",
            pos=(1.33, 0.86),
            scale=0.038,
            fg=(0.7, 0.7, 0.7, 1),
            shadow=(0, 0, 0, 0.7),
            align=TextNode.ARight,
            mayChange=True,
        )

    def update_status(self, player):
        state = player.state.upper()
        if player.in_queue:
            state += " [FOLLOWING]"
        self.status_text.setText(f"Player: {state}")

        dest = f"  →  {player.destination_name[:20]}" if player.destination_name else ""
        self.speed_text.setText(
            f"Speed: {player.speed:.1f}  WP: {player.waypoint_idx}/"
            f"{max(0, len(player.path)-1)}{dest}"
        )

        # Arrived flash
        if player.state == "arrived" and self._arrived_timer == 0:
            self.arrived_banner.setText(f"Arrived at {player.destination_name}!")
            self._arrived_timer = 120
        if self._arrived_timer > 0:
            self._arrived_timer -= 1
            if self._arrived_timer == 0:
                self.arrived_banner.setText("")

    def update_chat(self, chat_history: list):
        for i, line_node in enumerate(self.chat_lines):
            if i < len(chat_history):
                sender, msg = chat_history[i]
                if sender == "User":
                    color = _CYAN
                    text  = f"You: {msg[:55]}"
                elif sender == "Driver":
                    color = _GREEN
                    text  = f"Driver: {msg[:50]}"
                else:
                    color = _GREY
                    text  = msg[:60]
                line_node.setFg(color)
                line_node.setText(text)
            else:
                line_node.setText("")

    def update_input(self, text: str, active: bool):
        cursor = "_" if active else ""
        self.input_label.setText(f"> {text}{cursor}")

    def update_stats(self, vehicles: list):
        if not self._stats_visible:
            self.stats_frame.hide()
            self.stats_body.hide()
            return
        self.stats_frame.show()
        self.stats_body.show()

        total_wait = sum(v.total_wait_time for v in vehicles)
        avg_speed  = sum(v.speed for v in vehicles) / max(1, len(vehicles))
        in_queue   = sum(1 for v in vehicles if v.in_queue)
        self.stats_body.setText(
            f"Vehicles: {len(vehicles)}   Queued: {in_queue}\n"
            f"Avg speed: {avg_speed:.1f}   Wait: {total_wait:.0f}s"
        )

    def update_weather(self, weather_state_value: str, speed_mult: float):
        icons = {
            "Clear":      "☀ Clear",
            "Rain":       "🌧 Rain",
            "Heavy Rain": "⛈ Heavy Rain",
            "Night":      "🌙 Night",
        }
        label = icons.get(weather_state_value, weather_state_value)
        self.weather_text.setText(label)
        if speed_mult < 1.0:
            self.weather_sub.setText(f"Speed ×{speed_mult:.0%}")
        else:
            self.weather_sub.setText("")

    def toggle_stats(self):
        self._stats_visible = not self._stats_visible

    def destroy(self):
        for item in (
            self.status_text, self.speed_text, self.chat_frame,
            self.input_frame, self.input_label, self.stats_frame,
            self.stats_title, self.stats_body, self.controls_text,
            self.legend, self.arrived_banner, self.weather_text, self.weather_sub,
            *self.chat_lines,
        ):
            try:
                item.destroy()
            except Exception:
                pass
