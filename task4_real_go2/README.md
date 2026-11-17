# Task 4 - NaVILA on the real Go2

Goal: the same loop as Task 3, on the physical robot. The Go2's camera
frames and an instruction go to NaVILA (the 8-bit server on the lab
machine), and NaVILA's answers are turned into Task 1 high-level commands.

## Status

**Bridge written and tested without hardware (2026-11-16). Not yet run on
the robot.** Task 1's movement commands (`move_distance`, `turn_degrees`)
are also still unconfirmed on hardware, so the first robot runs should be
dry runs.

## Files

| File | Purpose |
|---|---|
| [`navila_bridge.py`](navila_bridge.py) | NaVILA's answer -> `Action` -> sim velocity command or Go2 command; frame sampling and the server client. No robot imports |
| [`run_navila_go2.py`](run_navila_go2.py) | The real-robot loop: camera thread, NaVILA requests, execution, logging. Dry run by default; `--execute` moves the robot; `--fake` runs without a robot |
| [`test_bridge.py`](test_bridge.py) | Tests the bridge on all 35,597 NaVILA answers from the Task 3 full run |

## How NaVILA's answers become Go2 commands

| NaVILA says | Go2 (Task 1 `Go2Interface`) | Simulator (NaVILA-Bench) |
|---|---|---|
| "move forward 25 / 50 / 75 cm" | `move_distance(0.25 / 0.5 / 0.75)` at 0.3 m/s | 0.5 m/s for 0.5 / 1 / 1.5 s |
| "turn left / right 15 / 30 / 45 degree" | `turn_degrees(+/-15 / 30 / 45)` at 0.5 rad/s (left = positive) | 0.52 rad/s for 0.5 / 1 / 1.5 s |
| "I think I should stop ..." | `stop()`, run ends | episode ends |
| anything else | `stop()`, run ends | **moves forward 25 cm** |

The bridge gives the same command as the simulator for 35,594 of the
35,597 Task 3 answers. The 3 differences are on purpose: two answers
describing "motion blur" (episode 234) stop the robot instead of moving it
forward, and one "turn left 25 degree" turns 25 degrees instead of 15.
Moves are clamped to 75 cm / 45 degrees as a safety limit.

The real robot defaults to Task 1's slower speeds (0.3 m/s, 0.5 rad/s);
the distance and angle are the same, only slower. `--speed 0.5` matches
the simulator.

## Running it

1. Tests (any machine): `python3 task4_real_go2/test_bridge.py` -> `ALL TESTS PASSED`
2. Loop without a robot: start any VLM server (or a fake one), then
   `python3 run_navila_go2.py x "Walk to the door" --fake`
3. On the Orin, connected to the Go2 (`eth0`). The VLM server only listens
   on the lab machine's localhost, so tunnel to it first:
   ```bash
   ssh -N -L 54321:localhost:54321 lab_user@<lab machine> &
   ```
   - Dry run: the robot doesn't move, the camera and NaVILA are live:
     `python3 run_navila_go2.py eth0 "Walk forward and stop at the door."`
   - Then, in a clear space with the remote at hand:
     `python3 run_navila_go2.py eth0 "Walk forward and stop at the door." --execute`

Each run is saved to `runs/<time>/` (one camera frame per decision plus
`decisions.jsonl`).

## Known limits

- **Open loop.** `move_distance` and `turn_degrees` hold a velocity for a
  computed time; no odometry correction, no obstacle check.
- **Latency.** NaVILA takes ~1-2 s per decision in 8-bit; the robot stands
  still while it thinks, as in the simulator.
- **Network.** Not yet checked whether the Orin can reach the lab machine
  (SSH from the user's Mac to it was blocked).
- The stop-aware controller from Task 3 isn't in this loop yet.
