import math
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, SportModeState_

# Go2 publishes odometry-style state (position, velocity, gait mode) on this
# topic. Confirmed against unitree_sdk2_python's other quadruped/humanoid
# examples (rt/lowstate is identical across all of them); sportmodestate is
# not exercised by a go2-specific example in the SDK repo, so double check
# this string against `ros2 topic list` / a DDS spy on the real robot before
# relying on it.
SPORTMODESTATE_TOPIC = "rt/sportmodestate"
LOWSTATE_TOPIC = "rt/lowstate"


class Go2Interface:
    def __init__(self, network_interface: str):
        ChannelFactoryInitialize(0, network_interface)

        self._sport_state: SportModeState_ | None = None
        self._low_state: LowState_ | None = None

        self._sport_state_sub = ChannelSubscriber(SPORTMODESTATE_TOPIC, SportModeState_)
        self._sport_state_sub.Init(self._on_sport_state, 10)

        self._low_state_sub = ChannelSubscriber(LOWSTATE_TOPIC, LowState_)
        self._low_state_sub.Init(self._on_low_state, 10)

        self.sport = SportClient()
        self.sport.SetTimeout(5.0)
        self.sport.Init()

    def _on_sport_state(self, msg: SportModeState_):
        self._sport_state = msg

    def _on_low_state(self, msg: LowState_):
        self._low_state = msg

    def wait_for_state(self, timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._sport_state is not None and self._low_state is not None:
                return True
            time.sleep(0.05)
        return False

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

    def stand_up(self):
        return self.sport.StandUp()

    def stand_down(self):
        return self.sport.StandDown()

    def stop(self):
        return self.sport.StopMove()

    def move(self, vx: float = 0.0, vy: float = 0.0, vyaw: float = 0.0):
        return self.sport.Move(vx, vy, vyaw)

    def forward(self, speed: float = 0.3):
        return self.move(vx=speed)

    def backward(self, speed: float = 0.3):
        return self.move(vx=-speed)

    def turn(self, yaw_rate: float = 0.5):
        return self.move(vyaw=yaw_rate)

    def move_distance(self, distance_m: float, speed: float = 0.3):
        """Open-loop forward/backward move: holds a velocity command for the
        time needed to cover distance_m, then stops. Go2 has no built-in
        "move N meters" API, so this is what a VLA action like "move forward
        75 cm" gets translated into for now. It drifts with terrain/battery
        sag; swap in closed-loop odometry (self.position) once that's needed.
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
