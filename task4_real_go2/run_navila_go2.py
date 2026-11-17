"""NaVILA driving the real Go2: camera -> NaVILA server -> navila_bridge ->
Task 1's Go2Interface.

    # dry run (default): reads the camera, asks NaVILA, prints what it WOULD do
    python3 run_navila_go2.py eth0 "Walk forward and stop at the door."
    # actually move
    python3 run_navila_go2.py eth0 "Walk forward and stop at the door." --execute
    # no robot at all (fake camera + fake robot), to test the loop
    python3 run_navila_go2.py fake "Walk forward" --fake

Like navila_eval.py, a camera frame is stored every --frame_interval
seconds (also while the robot moves), and each decision sends NaVILA 7
frames spread over the whole history plus the current one.

The VLM server binds to localhost on the lab machine, so from the Orin use
an SSH tunnel first:  ssh -N -L 54321:localhost:54321 lab_user@<lab machine>

Safety: moves are open loop (time x speed, no obstacle check), amounts are
clamped to 75 cm / 45 degrees, unknown answers stop the robot, Ctrl+C stops
the robot, and the run ends after --max_decisions. Keep the remote at hand.

Every run is saved to --save_dir/<time>/: decisions.jsonl and the current
camera frame of each decision.
"""
import argparse
import json
import os
import sys
import threading
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from navila_bridge import ask_navila, encode_jpeg, execute_on_go2, parse_action, sample_frames  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("network_interface", help="e.g. eth0 (ignored with --fake)")
p.add_argument("instruction")
p.add_argument("--execute", action="store_true", help="actually move the robot (default: dry run)")
p.add_argument("--vlm_host", default="localhost")
p.add_argument("--vlm_port", type=int, default=54321)
p.add_argument("--speed", type=float, default=0.3, help="m/s (sim used 0.5)")
p.add_argument("--yaw_rate", type=float, default=0.5, help="rad/s (sim used 0.52)")
p.add_argument("--max_decisions", type=int, default=60)
p.add_argument("--frame_interval", type=float, default=0.5)
p.add_argument("--save_dir", default=os.path.join(HERE, "runs"))
p.add_argument("--fake", action="store_true", help="fake camera and robot, for testing without a Go2")
args = p.parse_args()


class FakeGo2:
    """Stands in for Go2Interface: random camera frames, prints motions."""
    def wait_for_state(self, timeout=5.0):
        return True

    def get_camera_frame(self):
        return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    def move_distance(self, d, speed=0.3):
        print(f"   [fake go2] move_distance({d:.2f} m, {speed} m/s)")
        time.sleep(min(abs(d) / speed, 0.3))

    def turn_degrees(self, deg, yaw_rate=0.5):
        print(f"   [fake go2] turn_degrees({deg:.0f} deg, {yaw_rate} rad/s)")
        time.sleep(0.2)

    def stop(self):
        print("   [fake go2] stop()")


def main():
    if args.fake:
        go2 = FakeGo2()
    else:
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "task1_orin_go2"))
        from go2_interface import Go2Interface
        go2 = Go2Interface(args.network_interface)
    if not go2.wait_for_state(timeout=5.0):
        sys.exit("Timed out waiting for robot state. Check the network interface and robot connection.")

    run_dir = os.path.join(args.save_dir, time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)
    mode = "EXECUTE (robot will move)" if args.execute else "DRY RUN (robot will not move)"
    print(f"Instruction: {args.instruction}\nMode: {mode}\nSaving to: {run_dir}")
    if args.execute:
        print("WARNING: open-loop motion, no obstacle avoidance. Clear the area, keep the remote ready.")
        input("Press Enter to start, Ctrl+C to abort...")

    # Camera thread: one RGB frame every frame_interval seconds.
    history, lock, running = [], threading.Lock(), threading.Event()
    running.set()

    def grab():
        while running.is_set():
            bgr = go2.get_camera_frame()          # OpenCV BGR, or None on failure
            if bgr is not None:
                with lock:
                    history.append(np.ascontiguousarray(bgr[:, :, ::-1]))
            time.sleep(args.frame_interval)

    cam = threading.Thread(target=grab, daemon=True)
    cam.start()
    log = open(os.path.join(run_dir, "decisions.jsonl"), "w")
    try:
        deadline = time.time() + 10
        while not history:
            if time.time() > deadline:
                sys.exit("No camera frames after 10 s.")
            time.sleep(0.1)
        for n in range(args.max_decisions):
            with lock:
                frames = sample_frames(history)
                size = history[-1].shape[:2]
                current = history[-1]
            images = [encode_jpeg(f, size) for f in frames]
            t0 = time.time()
            text = ask_navila(images, args.instruction, args.vlm_host, args.vlm_port)
            if not isinstance(text, str):          # a non-default server mode answered
                text = json.dumps(text)
            action = parse_action(text)
            Image.fromarray(current).save(os.path.join(run_dir, f"{n:03d}.jpg"))
            print(f"[{n:02d}] NaVILA ({time.time() - t0:.1f} s): {text}\n     -> {action}")
            log.write(json.dumps({"decision": n, "time": time.time(), "navila": text,
                                  "action": str(action), "executed": args.execute}) + "\n")
            log.flush()
            if action.kind in ("stop", "unknown"):
                go2.stop()
                print("Stopping:", "NaVILA says it is done." if action.kind == "stop" else "answer not understood.")
                break
            if args.execute:
                execute_on_go2(go2, action, speed=args.speed, yaw_rate=args.yaw_rate)
            else:
                time.sleep(args.frame_interval)   # dry run: let a new frame arrive
        else:
            print(f"Reached --max_decisions ({args.max_decisions}); stopping.")
    except KeyboardInterrupt:
        print("\nCtrl+C: stopping the robot.")
    finally:
        go2.stop()
        running.clear()
        log.close()


if __name__ == "__main__":
    main()
