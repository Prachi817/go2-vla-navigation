# Task 1 — Orin–Go2 Integration & High-Level Control

Goal: get the Jetson Orin talking to the Go2 — read robot state (pose,
velocity, battery) and send high-level motion commands (forward, backward,
turn, stop). This is the "legs" interface the VLA brain (Task 3/4) will
eventually call with commands like *"move forward 75 cm"*.

Two parallel implementations live in this folder, both doing the same
thing over the same underlying robot API:

- **`go2_interface.py`, `read_state.py`, `basic_control.py`** — raw
  `unitree_sdk2py`, talking directly to the robot's DDS topics.
- **`ros2/`** — the same functionality over ROS 2 (`unitree_ros2`), using
  `rclpy` nodes instead of the SDK's `ChannelSubscriber`/`SportClient`.

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

**Topic names are confirmed**, not just assumed: `unitree_ros2`'s own docs
list `sportmodestate` (position/velocity/gait) and `lowstate`
(battery/IMU/joints) with the exact same field layout used here, which
cross-checks the raw SDK topic strings (`rt/sportmodestate`, `rt/lowstate`)
independently of the SDK's own examples.

## Why both the SDK and ROS 2 (not just one)

We originally planned raw SDK only, deferring ROS 2 to Task 2 (Isaac Sim
is ROS 2-native) and the Nav2 stretch goal, to avoid installing ROS 2 on
the Orin before it was needed. We reversed that: ROS 2 is being added now,
alongside the SDK, rather than waiting.

The two aren't really different robot APIs — they're two transports onto
the *same* one. `unitree_ros2` doesn't reimplement robot control; the
DDS topics `rt/sportmodestate`/`rt/lowstate` and the "sport" service's
numeric command IDs (`MOVE = 1008`, `STANDUP = 1004`, ...) are identical
on both sides. Concretely:

| | Raw SDK (`go2_interface.py`) | ROS 2 (`ros2/go2_ros2_interface.py`) |
|---|---|---|
| State | `ChannelSubscriber` on `rt/sportmodestate` / `rt/lowstate` | `rclpy` subscription on `/sportmodestate` / `/lowstate` |
| Commands | `SportClient.Move(...)` (SDK call, has a return code) | Publish a `unitree_api/msg/Request` with `api_id=1008` to `/api/sport/request` (fire-and-forget, no return code) |
| Needs installed | `unitree_sdk2py` only | ROS 2 (Foxy or Humble) + `unitree_ros2`'s `cyclonedds_ws` built |

`ros2/go2_ros2_interface.py` is a Python (`rclpy`) port of the request-ID
mapping that `unitree_ros2` only ships as a C++ example
(`ros2_sport_client.cpp`) — there's no bundled Python equivalent upstream,
so this repo's version is hand-written against that same numeric ID table,
not copied from an official Python example.

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

### ROS 2 setup (for `ros2/`)

First check which Ubuntu/ROS 2 you actually have — the two paths differ:
```bash
lsb_release -a   # Ubuntu 20.04 -> ROS 2 Foxy; Ubuntu 22.04 -> ROS 2 Humble (recommended)
```

1. **Install ROS 2** if it isn't already, following the [official
   instructions](https://docs.ros.org/en/humble/Installation.html) for
   your Ubuntu version.

2. **Clone `unitree_ros2`**:
   ```bash
   cd ~
   git clone https://github.com/unitreerobotics/unitree_ros2
   ```

3. **Get a matching CycloneDDS.** The robot uses cyclonedds 0.10.2, which
   the default ROS 2 RMW doesn't ship:
   - **Humble**: just install the prebuilt packages, no source build needed:
     ```bash
     sudo apt install ros-humble-rmw-cyclonedds-cpp ros-humble-rosidl-generator-dds-idl
     ```
   - **Foxy**: these prebuilt packages aren't ABI-compatible with 0.10.2,
     so it has to be built from source. Make sure ROS 2 is **not** sourced
     in the terminal you build in (comment out any
     `source /opt/ros/foxy/setup.bash` in `~/.bashrc` first), then:
     ```bash
     sudo apt install ros-foxy-rmw-cyclonedds-cpp ros-foxy-rosidl-generator-dds-idl libyaml-cpp-dev
     cd ~/unitree_ros2/cyclonedds_ws/src
     git clone https://github.com/ros2/rmw_cyclonedds -b foxy
     git clone https://github.com/eclipse-cyclonedds/cyclonedds -b releases/0.10.x
     cd ..
     colcon build --packages-select cyclonedds
     ```

4. **Build the Unitree message packages** (`unitree_go`, `unitree_api`,
   ...) — this is what makes `from unitree_go.msg import ...` importable
   from Python:
   ```bash
   source /opt/ros/<foxy-or-humble>/setup.bash
   cd ~/unitree_ros2
   colcon build
   ```

5. **Point it at the right network interface.** Edit
   `~/unitree_ros2/setup.sh` and replace `enp3s0` with your interface name
   (the same one from `ip addr` in the Network step above), then source it
   in every terminal you run these scripts from:
   ```bash
   source ~/unitree_ros2/setup.sh
   ```
   Sanity check before running anything in `ros2/`:
   ```bash
   ros2 topic list        # should include /sportmodestate, /lowstate
   ros2 topic echo /sportmodestate
   ```

## Usage

### Raw SDK
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

### ROS 2
After `source ~/unitree_ros2/setup.sh` (no network-interface argument needed —
that's baked into the sourced environment, not a script argument):
```bash
cd ros2
python3 read_state_ros2.py
python3 basic_control_ros2.py <command>
# same commands: standup, standdown, stop, forward, backward, turn_left_90, turn_right_90
```

**Safety**: always clear space around the robot before running either
`basic_control.py` or `basic_control_ros2.py`, and keep the wireless
controller within reach to override.
