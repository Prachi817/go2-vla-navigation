import sys
import time

from go2_ros2_interface import Go2RosInterface

COMMANDS = {
    "standup": lambda go2: go2.stand_up(),
    "standdown": lambda go2: go2.stand_down(),
    "stop": lambda go2: go2.stop(),
    "forward": lambda go2: go2.move_distance(0.75),
    "backward": lambda go2: go2.move_distance(-0.5),
    "turn_left_90": lambda go2: go2.turn_degrees(90),
    "turn_right_90": lambda go2: go2.turn_degrees(-90),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python3 {sys.argv[0]} <{'|'.join(COMMANDS)}>")
        sys.exit(1)

    go2 = Go2RosInterface()
    if not go2.wait_for_state(timeout=5.0):
        print("Timed out waiting for robot state. Did you `source ~/unitree_ros2/setup.sh` first?")
        go2.shutdown()
        sys.exit(1)

    print("WARNING: ensure there is clear space around the robot.")
    input("Press Enter to run the command...")

    COMMANDS[sys.argv[1]](go2)
    time.sleep(1)
    print(f"Done. position={go2.position}")
    go2.shutdown()
