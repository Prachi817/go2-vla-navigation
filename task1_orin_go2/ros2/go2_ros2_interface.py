import json
import math
import struct
import threading
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String
from unitree_api.msg import Request, Response
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

UTLIDAR_CLOUD_TOPIC = "/utlidar/cloud"
UTLIDAR_SWITCH_TOPIC = "/utlidar/switch"
POINTFIELD_FLOAT32 = 7  # sensor_msgs/PointField datatype constant

# UNCONFIRMED: every other unitree_ros2 service (sport, motion_switcher,
# voice, arm) follows the "/api/<service_name>/request" + "/response"
# pattern, and the SDK's video service is internally named "videohub"
# (unitree_sdk2py's VIDEO_SERVICE_NAME), so these are inferred by that
# pattern, not copied from a working example -- unitree_ros2 has zero
# camera/video example code anywhere. Verify these topic names actually
# exist (`ros2 topic list`) before trusting get_camera_frame().
VIDEO_REQUEST_TOPIC = "/api/videohub/request"
VIDEO_RESPONSE_TOPIC = "/api/videohub/response"
VIDEO_API_ID_GETIMAGESAMPLE = 1001


def _decode_point_cloud_xyz(cloud: PointCloud2) -> List[Tuple[float, float, float]]:
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


class Go2RosInterface(Node):
    def __init__(self, node_name: str = "go2_ros2_interface"):
        if not rclpy.ok():
            rclpy.init()
        super().__init__(node_name)

        self._sport_state: Optional[SportModeState] = None
        self._low_state: Optional[LowState] = None
        self._point_cloud: Optional[PointCloud2] = None
        self._video_response: Optional[Response] = None
        self._pending_video_request_id: Optional[int] = None

        self.create_subscription(SportModeState, SPORTMODESTATE_TOPIC, self._on_sport_state, 10)
        self.create_subscription(LowState, LOWSTATE_TOPIC, self._on_low_state, 10)
        self._request_pub = self.create_publisher(Request, SPORT_REQUEST_TOPIC, 10)

        self.create_subscription(PointCloud2, UTLIDAR_CLOUD_TOPIC, self._on_point_cloud, 10)
        self._lidar_switch_pub = self.create_publisher(String, UTLIDAR_SWITCH_TOPIC, 10)

        self.create_subscription(Response, VIDEO_RESPONSE_TOPIC, self._on_video_response, 10)
        self._video_request_pub = self.create_publisher(Request, VIDEO_REQUEST_TOPIC, 10)

        self._spin_thread = threading.Thread(target=rclpy.spin, args=(self,), daemon=True)
        self._spin_thread.start()

    def _on_sport_state(self, msg: SportModeState):
        self._sport_state = msg

    def _on_low_state(self, msg: LowState):
        self._low_state = msg

    def _on_point_cloud(self, msg: PointCloud2):
        self._point_cloud = msg

    def _on_video_response(self, msg: Response):
        if msg.header.identity.id == self._pending_video_request_id:
            self._video_response = msg

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

    def set_lidar(self, on: bool):
        msg = String()
        msg.data = "ON" if on else "OFF"
        self._lidar_switch_pub.publish(msg)

    @property
    def point_cloud(self) -> Optional[PointCloud2]:
        """Latest raw sensor_msgs/PointCloud2 message, or None if nothing has
        arrived yet -- e.g. the LiDAR is off (see set_lidar) or no data has
        been received yet.
        """
        return self._point_cloud

    def point_cloud_xyz(self) -> Optional[List[Tuple[float, float, float]]]:
        """Latest point cloud decoded into a plain list of (x, y, z) tuples."""
        if self._point_cloud is None:
            return None
        return _decode_point_cloud_xyz(self._point_cloud)

    def get_camera_frame(self, timeout: float = 3.0):
        """One-shot RGB frame as a BGR numpy array (OpenCV convention), or
        None on failure/timeout. UNCONFIRMED: see the VIDEO_REQUEST_TOPIC
        comment above -- this topic name is inferred from every other
        service's naming pattern, not verified against a working example.
        If this never returns a frame, check `ros2 topic list` for the
        actual videohub topic names before assuming the decoding is wrong.
        """
        request_id = time.time_ns()
        self._pending_video_request_id = request_id
        self._video_response = None

        req = Request()
        req.header.identity.id = request_id
        req.header.identity.api_id = VIDEO_API_ID_GETIMAGESAMPLE
        self._video_request_pub.publish(req)

        deadline = time.time() + timeout
        while self._video_response is None and time.time() < deadline:
            time.sleep(0.02)

        if self._video_response is None or self._video_response.header.status.code != 0:
            return None

        image_bytes = np.frombuffer(bytes(self._video_response.binary), dtype=np.uint8)
        return cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)

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
