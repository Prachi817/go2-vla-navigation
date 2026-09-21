import sys
import time

from go2_interface import Go2Interface

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <network_interface>")
        print("Example: python3 read_state.py eth0")
        sys.exit(1)

    go2 = Go2Interface(sys.argv[1])

    if not go2.wait_for_state(timeout=5.0):
        print("Timed out waiting for robot state. Check the network interface and robot connection.")
        sys.exit(1)

    while True:
        print(
            f"pos={go2.position} vel={go2.velocity} yaw_speed={go2.yaw_speed:.2f} "
            f"gait_mode={go2.gait_mode} battery={go2.battery_percent}%"
        )
        time.sleep(0.5)
