# Task 1 — Orin–Go2 Integration & High-Level Control

Goal: get the Jetson Orin talking to the Go2 over the Unitree SDK — read
robot state (pose, velocity, battery) and send high-level motion commands
(forward, backward, turn, stop). This is the "legs" interface the VLA brain
(Task 3/4) will eventually call with commands like *"move forward 75 cm"*.

## How the Go2 SDK actually works

Unitree's `unitree_sdk2py` talks to the robot over **CycloneDDS**, a
pub/sub protocol on the local network — there's no socket/IP call you make
directly. Once `ChannelFactoryInitialize` is pointed at the right network
interface, everything is either:

- a **topic subscription** (`ChannelSubscriber`) — for state that streams
  continuously (IMU, joint angles, battery, pose), or
- a **service client** (`SportClient`, `VideoClient`, ...) — for
  request/response calls (move, stand up, get a camera frame).

Two levels of control exist:

| Level | Use for | Topic/Client |
|---|---|---|
| **High-level** | Whole-body motion: walk, turn, stand, stop, canned tricks | `SportClient` (commands) + `rt/sportmodestate` (pose/velocity/gait mode) |
| **Low-level** | Direct per-joint torque/position control | `rt/lowcmd` (publish) + `rt/lowstate` (subscribe: joint angles, IMU, battery, foot force) |

Task 1 only needs the high-level path — `go2_interface.py` in this folder
wraps it. Low-level joint control is what you'd reach for if you were
writing your own gait controller, which is out of scope here since the
Go2's onboard controller already handles balance/walking.

**Caveat to verify on hardware:** `rt/lowstate` is confirmed identical
across every robot in the SDK's examples. `rt/sportmodestate` is used by
other Unitree quadrupeds/humanoids in this SDK but there's no Go2-specific
example exercising it — confirm the exact topic string with a DDS spy or
`ros2 topic list` (if running the ROS 2 bridge) the first time you connect.

## Why raw SDK instead of unitree_ros2 (for now)

Two ways to talk to the Go2: this SDK directly, or through `unitree_ros2`
(a ROS 2 bridge over the same underlying DDS topics — it wraps, not
replaces, what's used here). Going with the raw SDK for Task 1:

- No ROS 2 install needed on the Orin just to read state and send a move
  command — less setup, faster to get something working.
- `unitree_ros2` pays off once Task 2 (Isaac Sim, which is ROS 2-native)
  and the Nav2 stretch goal are in play — that's the point to add or switch
  to the ROS 2 layer, not before.
- Since `unitree_ros2` sits on top of the same SDK/DDS topics documented
  above, moving to it later is an added interface layer, not a rewrite of
  `go2_interface.py`'s logic.

## Setup

1. **Network**: connect the Jetson Orin to the Go2 (Ethernet is most
   reliable; the Go2 also exposes Wi-Fi). Follow Unitree's
   [Quick Start guide](https://support.unitree.com/home/en/developer/Quick_start)
   to get an IP on the robot's subnet, then find your interface name:
   ```bash
   ip addr    # look for the interface connected to the robot, e.g. eth0
   ```

2. **Install the SDK** on the Orin:
   ```bash
   git clone https://github.com/unitreerobotics/unitree_sdk2_python
   cd unitree_sdk2_python
   pip3 install -e .
   ```
   If `pip3 install -e .` fails to find `cyclonedds`, build it from source —
   see the [SDK README](https://github.com/unitreerobotics/unitree_sdk2_python#faq)
   FAQ for the exact steps.

3. **Install this task's dependencies** (same versions the SDK expects):
   ```bash
   pip3 install -r requirements.txt
   ```

## Usage

Read live robot state:
```bash
python3 read_state.py <network_interface>
# e.g. python3 read_state.py eth0
```

Send a basic high-level command:
```bash
python3 basic_control.py <network_interface> <command>
# commands: standup, standdown, stop, forward, backward, turn_left_90, turn_right_90
```

**Safety**: always clear space around the robot before running
`basic_control.py`, and keep the wireless controller within reach to
override — the script won't stop the robot for you if something looks wrong.

## Next steps for this task

- [ ] Confirm `rt/sportmodestate` topic name and field units on real hardware
- [ ] Replace the open-loop `move_distance`/`turn_degrees` timing with
      closed-loop control using `go2.position` feedback
- [ ] Wrap `go2_interface.py` in a small command-server (e.g. a socket or
      ROS 2 node) so the off-board VLA (running on the GPU cluster) can send
      it text-like actions ("move forward 75 cm") over the network
- [ ] Add camera streaming (`VideoClient`, see SDK's
      `example/go2/front_camera/`) once Task 3 needs live frames
