import math
import struct
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.go2.video.video_client import VideoClient
from unitree_sdk2py.idl.sensor_msgs.msg.dds_ import PointCloud2_
from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, SportModeState_

# Go2 publishes odometry-style state (position, velocity, gait mode) on this
# topic. Confirmed against unitree_sdk2_python's other quadruped/humanoid
# examples (rt/lowstate is identical across all of them); sportmodestate is
# not exercised by a go2-specific example in the SDK repo, so double check
# this string against `ros2 topic list` / a DDS spy on the real robot before
# relying on it.
SPORTMODESTATE_TOPIC = "rt/sportmodestate"
LOWSTATE_TOPIC = "rt/lowstate"
UTLIDAR_CLOUD_TOPIC = "rt/utlidar/cloud"
UTLIDAR_SWITCH_TOPIC = "rt/utlidar/switch"

# sensor_msgs/PointField datatype constant for float32 (see PointField_Constants
# in the SDK's idl). Go2's LiDAR cloud uses float32 x/y/z, same as any standard
# ROS PointCloud2 producer.
POINTFIELD_FLOAT32 = 7


def _decode_point_cloud_xyz(cloud: PointCloud2_) -> List[Tuple[float, float, float]]:
    offsets = {
        f.name: f.offset
        for f in cloud.fields
        if f.name in ("x", "y", "z") and f.datatype == POINTFIELD_FLOAT32
    }
    if not all(axis in offsets for axis in ("x", "y", "z")):
        raise ValueError("point cloud has no float32 x/y/z fields")

    data = bytes(cloud.data)
    num_points = cloud.width * cloud.height
    points = []
    for i in range(num_points):
        base = i * cloud.point_step
        x = struct.unpack_from("<f", data, base + offsets["x"])[0]
        y = struct.unpack_from("<f", data, base + offsets["y"])[0]
        z = struct.unpack_from("<f", data, base + offsets["z"])[0]
        points.append((x, y, z))
    return points


class Go2Interface:
    def __init__(self, network_interface: str):
        ChannelFactoryInitialize(0, network_interface)

        self._sport_state: Optional[SportModeState_] = None
        self._low_state: Optional[LowState_] = None
        self._point_cloud: Optional[PointCloud2_] = None

        self._sport_state_sub = ChannelSubscriber(SPORTMODESTATE_TOPIC, SportModeState_)
        self._sport_state_sub.Init(self._on_sport_state, 10)

        self._low_state_sub = ChannelSubscriber(LOWSTATE_TOPIC, LowState_)
        self._low_state_sub.Init(self._on_low_state, 10)

        self._point_cloud_sub = ChannelSubscriber(UTLIDAR_CLOUD_TOPIC, PointCloud2_)
        self._point_cloud_sub.Init(self._on_point_cloud, 10)

        self._lidar_switch_pub = ChannelPublisher(UTLIDAR_SWITCH_TOPIC, String_)
        self._lidar_switch_pub.Init()

        self.sport = SportClient()
        self.sport.SetTimeout(5.0)
        self.sport.Init()

        self.video = VideoClient()
        self.video.SetTimeout(3.0)
        self.video.Init()

    def _on_sport_state(self, msg: SportModeState_):
        self._sport_state = msg

    def _on_low_state(self, msg: LowState_):
        self._low_state = msg

    def _on_point_cloud(self, msg: PointCloud2_):
        self._point_cloud = msg

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

    def get_camera_frame(self):
        """One-shot RGB frame as a BGR numpy array (OpenCV convention), or
        None on failure. This is a request/response call (VIDEO_API_ID_GETIMAGESAMPLE),
        not a subscription -- there is no continuous camera topic on the Go2,
        so call this again each time you need a fresh frame.
        """
        code, data = self.video.GetImageSample()
        if code != 0:
            return None
        image_bytes = np.frombuffer(bytes(data), dtype=np.uint8)
        return cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)

    def set_lidar(self, on: bool):
        self._lidar_switch_pub.Write(String_(data="ON" if on else "OFF"))

    @property
    def point_cloud(self) -> Optional[PointCloud2_]:
        """Latest raw sensor_msgs/PointCloud2 message, or None if nothing has
        arrived yet -- e.g. the LiDAR is off (see set_lidar) or no data has
        been received within the subscriber's window yet.
        """
        return self._point_cloud

    def point_cloud_xyz(self) -> Optional[List[Tuple[float, float, float]]]:
        """Latest point cloud decoded into a plain list of (x, y, z) tuples."""
        if self._point_cloud is None:
            return None
        return _decode_point_cloud_xyz(self._point_cloud)

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
