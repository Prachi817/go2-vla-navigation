import json
import math
import threading
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from unitree_api.msg import Request
from unitree_go.msg import LowState, SportModeState

# Same numeric IDs as unitree_sdk2py's sport_api.py (SPORT_API_ID_*) and
# unitree_ros2's ros2_sport_client.h (ROBOT_SPORT_API_ID_*) -- both talk to
# the same onboard "sport" service, just over a different transport. Only
# the subset go2_interface.py (the raw-SDK version) exposes is ported here.
SPORT_API_ID_DAMP = 1001
SPORT_API_ID_STOPMOVE = 1003
SPORT_API_ID_STANDUP = 1004
SPORT_API_ID_STANDDOWN = 1005
SPORT_API_ID_MOVE = 1008

SPORTMODESTATE_TOPIC = "/sportmodestate"
LOWSTATE_TOPIC = "/lowstate"
SPORT_REQUEST_TOPIC = "/api/sport/request"


class Go2RosInterface(Node):
    def __init__(self, node_name: str = "go2_ros2_interface"):
        if not rclpy.ok():
            rclpy.init()
        super().__init__(node_name)

        self._sport_state: Optional[SportModeState] = None
        self._low_state: Optional[LowState] = None

        self.create_subscription(SportModeState, SPORTMODESTATE_TOPIC, self._on_sport_state, 10)
        self.create_subscription(LowState, LOWSTATE_TOPIC, self._on_low_state, 10)
        self._request_pub = self.create_publisher(Request, SPORT_REQUEST_TOPIC, 10)

        self._spin_thread = threading.Thread(target=rclpy.spin, args=(self,), daemon=True)
        self._spin_thread.start()

    def _on_sport_state(self, msg: SportModeState):
        self._sport_state = msg

    def _on_low_state(self, msg: LowState):
        self._low_state = msg

    def wait_for_state(self, timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._sport_state is not None and self._low_state is not None:
                return True
            time.sleep(0.05)
        return False

    def shutdown(self):
        self.destroy_node()
        rclpy.shutdown()

    @property
    def position(self):
        return tuple(self._sport_state.position) if self._sport_state else None

    @property
    def velocity(self):
        return tuple(self._sport_state.velocity) if self._sport_state else None

    @property
    def yaw_speed(self):
        return self._sport_state.yaw_speed if self._sport_state else None

    @property
    def gait_mode(self):
        return self._sport_state.mode if self._sport_state else None

    @property
    def battery_percent(self):
        return self._low_state.bms_state.soc if self._low_state else None

    def _send_request(self, api_id: int, parameter: Optional[dict] = None):
        req = Request()
        req.header.identity.api_id = api_id
        if parameter is not None:
            req.parameter = json.dumps(parameter)
        self._request_pub.publish(req)

    def stand_up(self):
        self._send_request(SPORT_API_ID_STANDUP)

    def stand_down(self):
        self._send_request(SPORT_API_ID_STANDDOWN)

    def stop(self):
        self._send_request(SPORT_API_ID_STOPMOVE)

    def move(self, vx: float = 0.0, vy: float = 0.0, vyaw: float = 0.0):
        self._send_request(SPORT_API_ID_MOVE, {"x": vx, "y": vy, "z": vyaw})

    def forward(self, speed: float = 0.3):
        self.move(vx=speed)

    def backward(self, speed: float = 0.3):
        self.move(vx=-speed)

    def turn(self, yaw_rate: float = 0.5):
        self.move(vyaw=yaw_rate)

    def move_distance(self, distance_m: float, speed: float = 0.3):
        """Same open-loop timing approach as go2_interface.py's version --
        ROS2 sport commands are fire-and-forget publishes too, there's no
        built-in "move N meters" here either.
        """
        if speed <= 0:
            raise ValueError("speed must be positive")
        direction = 1.0 if distance_m >= 0 else -1.0
        duration = abs(distance_m) / speed
        self.move(vx=direction * speed)
        time.sleep(duration)
        self.stop()

    def turn_degrees(self, degrees: float, yaw_rate: float = 0.5):
        if yaw_rate <= 0:
            raise ValueError("yaw_rate must be positive")
        direction = 1.0 if degrees >= 0 else -1.0
        duration = abs(math.radians(degrees)) / yaw_rate
        self.move(vyaw=direction * yaw_rate)
        time.sleep(duration)
        self.stop()
