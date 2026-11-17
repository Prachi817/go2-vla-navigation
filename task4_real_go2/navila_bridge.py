"""Bridge from NaVILA's text answers to robot commands, shared by simulation
and the real Go2.

NaVILA answers with one sentence from a small fixed set:
    "The next action is move forward 25 / 50 / 75 cm."
    "The next action is turn left / right 15 / 30 / 45 degree."
    "I think I should stop because I have finished the instruction."

parse_action() turns that into an Action. Then:
    sim_command(action)        -> (velocity [vx, vy, vyaw], seconds), the same
                                  mapping NaVILA-Bench's get_vel_command uses
    execute_on_go2(go2, action) -> Task 1's Go2Interface.move_distance /
                                  turn_degrees / stop

Differences from NaVILA-Bench's get_vel_command, on purpose:
- an answer that can't be parsed is "unknown" and the robot stops; the sim
  version moves forward 25 cm.
- amounts are used exactly ("turn left 25 degree" turns 25 degrees; the sim
  version turns 15).

No robot or simulator imports, so this file can be tested anywhere.
"""
import base64
import io
import json
import math
import re
import socket
from dataclasses import dataclass
from typing import List, Optional

# NaVILA-Bench's simulated speeds (eval_utils.get_vel_command).
SIM_FORWARD_SPEED = 0.5          # m/s
SIM_YAW_RATE = math.pi / 6.0     # rad/s, 30 degrees per second


@dataclass
class Action:
    kind: str                     # "forward", "left", "right", "stop" or "unknown"
    amount: Optional[float] = None  # meters for forward, degrees for turns
    text: str = ""

    def __str__(self):
        if self.kind == "forward":
            return f"forward {self.amount * 100:.0f} cm"
        if self.kind in ("left", "right"):
            return f"turn {self.kind} {self.amount:.0f} deg"
        return self.kind


def parse_action(text: str) -> Action:
    t = text.lower()
    if "turn left" in t or "turn right" in t:
        m = re.search(r"(\d+(?:\.\d+)?)\s*degree", t)
        if not m:
            return Action("unknown", None, text)
        return Action("left" if "turn left" in t else "right", float(m.group(1)), text)
    if "move forward" in t:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(cm|centimeter|m\b|meter)", t)
        if not m:
            return Action("unknown", None, text)
        value = float(m.group(1))
        return Action("forward", value / 100.0 if m.group(2).startswith("c") else value, text)
    if "stop" in t:
        return Action("stop", None, text)
    return Action("unknown", None, text)


def sim_command(action: Action):
    """(velocity [vx, vy, vyaw], seconds) at NaVILA-Bench's simulated speeds."""
    if action.kind == "forward":
        return [SIM_FORWARD_SPEED, 0.0, 0.0], action.amount / SIM_FORWARD_SPEED
    if action.kind in ("left", "right"):
        sign = 1.0 if action.kind == "left" else -1.0
        return [0.0, 0.0, sign * SIM_YAW_RATE], math.radians(action.amount) / SIM_YAW_RATE
    return [0.0, 0.0, 0.0], 0.0


def execute_on_go2(go2, action: Action, speed: float = 0.3, yaw_rate: float = 0.5,
                   max_forward_m: float = 0.75, max_turn_deg: float = 45.0):
    """Run one action on Task 1's Go2Interface (blocking, open loop).
    Amounts are clamped to NaVILA's largest normal action as a safety limit.
    Positive turn = left (counter-clockwise), as in basic_control.py."""
    if action.kind == "forward":
        go2.move_distance(min(action.amount, max_forward_m), speed=speed)
    elif action.kind in ("left", "right"):
        deg = min(action.amount, max_turn_deg)
        go2.turn_degrees(deg if action.kind == "left" else -deg, yaw_rate=yaw_rate)
    else:  # stop or unknown
        go2.stop()


def sample_frames(history: List, n: int = 8) -> List:
    """The 8 frames NaVILA sees, picked like navila_eval.py: 7 spread evenly
    over the whole history plus the current frame; padded with black frames
    at the front when there are fewer than 8."""
    if len(history) < n:
        return [None] * (n - len(history)) + list(history)
    idx = [int(i * (len(history) - 1) / (n - 1)) for i in range(n - 1)]
    return [history[i] for i in idx] + [history[-1]]


def encode_jpeg(rgb_array, size=None) -> str:
    """RGB uint8 array (H, W, 3) -> base64 JPEG, the format the server expects.
    None -> a black frame of `size` (H, W)."""
    from PIL import Image
    import numpy as np
    if rgb_array is None:
        rgb_array = np.zeros((size[0], size[1], 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgb_array).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def ask_navila(images_b64: List[str], instruction: str, host="localhost", port=54321,
               timeout=120.0, extra=None):
    """One request to vlm_server*.py (8-byte big-endian length + JSON)."""
    payload = {"images": images_b64, "query": instruction}
    if extra:
        payload.update(extra)
    req = json.dumps(payload).encode()
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(len(req).to_bytes(8, "big"))
        s.sendall(req)
        size = int.from_bytes(s.recv(8), "big")
        data = b""
        while len(data) < size:
            packet = s.recv(4096)
            if not packet:
                break
            data += packet
    return json.loads(data.decode())
