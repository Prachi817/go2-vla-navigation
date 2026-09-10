# 🐾 WalkTheTalk

**Vision-Language-Action navigation on a Unitree Go2**

A capstone project: teaching a quadruped robot to follow natural-language
instructions using a Vision-Language-Action (VLA) model. A person gives an
instruction like *"go to the kitchen and stop at the red bowl"*, the robot's
camera and a VLA model decide what to do, and the Go2 walks there — no
pre-built map required.

---

## Overview

The system follows a two-level design, inspired by the NaVILA framework:

- **The "brain" (high level):** a Vision-Language model reads the camera feed
  and the instruction, then outputs a simple mid-level action in words
  (e.g. *"move forward 75 cm"*).
- **The "legs" (low level):** the Go2's controller turns that command into
  real walking, handling balance and obstacles.

The VLA model runs off-board on a GPU (SLU's Libra HPC cluster) and
communicates with the robot's onboard NVIDIA Jetson Orin.

```
Instruction ──▶ Camera + VLA (GPU) ──▶ "move forward 75 cm" ──▶ Go2 walks
```

---

## Project Tasks

### Core tasks
1. **Orin–Go2 integration & high-level control** — Set up communication
   between the Jetson Orin and the Unitree Go2: read sensors/state, and send
   high-level commands (forward, backward, turn, velocity, stop).
2. **Go2 simulation environment** — Bring up the Go2 in NVIDIA Isaac Sim with
   the same sensing and high-level control interface used on the real robot.
3. **VLA-based control in simulation** — Run a pretrained VLA in simulation so
   the Go2 takes camera input + a language instruction and produces navigation
   actions.
4. **VLA deployment on the real Go2** — Deploy the pipeline on the physical
   robot via the Orin, and evaluate language-conditioned navigation in the
   real world.

### Stretch goals
- **VLM + classical planning** — Use a VLM to pick a target, then a classical
  planner (Nav2) to drive to it.
- **Semantic mapping** — Build a map labeled with objects (chair, door, stairs…).
- **Object-goal navigation** — "Find the backpack" → locate and navigate to it.

---

## Hardware & Compute

- **Robot:** Unitree Go2 EDU
- **Onboard computer:** NVIDIA Jetson Orin
- **Off-board GPU:** SLU Libra HPC cluster (for running the VLA and simulation)
- **Sensors:** RGB camera, LiDAR, IMU

---

## Repository Structure

> _Work in progress — updated as the project develops._

```
go2-vla-navigation/
├── README.md
├── task1_orin_go2/      # Orin–Go2 communication & high-level control
├── task2_simulation/    # Isaac Sim setup for the Go2
├── task3_vla_sim/       # Running the VLA in simulation
├── task4_deployment/    # Real-robot deployment
└── docs/                # Notes, setup guides, results
```

---

## Setup

> _Detailed setup instructions will be added as each task is completed._

### Prerequisites
- Ubuntu (matching your Jetson's JetPack version)
- ROS 2 (version paired with your Ubuntu, e.g. Humble)
- Python 3.10
- NVIDIA Isaac Sim 4.1.0 / Isaac Lab 1.1.0 (for simulation)

### Task 1 — quick start (placeholder)
```bash
# Clone the Unitree Python SDK
git clone https://github.com/unitreerobotics/unitree_sdk2_python
# ...connection & install steps to be documented here
```

---

## Built On

### Key paper
- **NaVILA: Legged Robot Vision-Language-Action Model for Navigation**
  (Cheng et al., RSS 2025) — the main framework this project builds on.
  [Paper](https://arxiv.org/abs/2412.04453) ·
  [Project page](https://navila-bot.github.io/)

### Related papers reviewed
- MobileVLA-R1 — reinforcement learning for mobile-robot VLAs
- TrackVLA — embodied visual tracking in the wild
- MoRE — scaling RL for quadruped VLA models
- History-Conditioned Spatio-Temporal Token Pruning — efficient VLN

### Key repositories
| Repo | Use |
|------|-----|
| [unitreerobotics/unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python) | Go2 Python SDK (Task 1) |
| [unitreerobotics/unitree_ros2](https://github.com/unitreerobotics/unitree_ros2) | ROS 2 bridge for the Go2 |
| [AnjieCheng/NaVILA](https://github.com/AnjieCheng/NaVILA) | VLA model & checkpoint (Task 3) |
| [yang-zj1026/NaVILA-Bench](https://github.com/yang-zj1026/NaVILA-Bench) | Isaac Sim navigation benchmark |
| [yang-zj1026/legged-loco](https://github.com/yang-zj1026/legged-loco) | Low-level locomotion policy training |
| [InternRobotics/StreamVLN](https://github.com/InternRobotics/StreamVLN) | Alternative VLA with Go2 deployment guide |

---

## Status

🚧 **In progress** — Task 1 (Orin–Go2 integration) underway.

---

## Author

Prachi · Capstone Project · Saint Louis University

## Acknowledgements

Thanks to the open-source Unitree, ROS 2, and Isaac Lab ecosystems.
