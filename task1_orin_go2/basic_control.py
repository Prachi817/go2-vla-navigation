import sys
import time

from go2_interface import Go2Interface

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
    if len(sys.argv) < 3 or sys.argv[2] not in COMMANDS:
        print(f"Usage: python3 {sys.argv[0]} <network_interface> <{'|'.join(COMMANDS)}>")
        sys.exit(1)

    go2 = Go2Interface(sys.argv[1])
    if not go2.wait_for_state(timeout=5.0):
        print("Timed out waiting for robot state. Check the network interface and robot connection.")
        sys.exit(1)

    print("WARNING: ensure there is clear space around the robot.")
    input("Press Enter to run the command...")

    COMMANDS[sys.argv[2]](go2)
    time.sleep(1)
    print(f"Done. position={go2.position}")
