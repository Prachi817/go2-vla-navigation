import time

from go2_ros2_interface import Go2RosInterface

if __name__ == "__main__":
    go2 = Go2RosInterface()

    if not go2.wait_for_state(timeout=5.0):
        print("Timed out waiting for robot state. Did you `source ~/unitree_ros2/setup.sh` first?")
        go2.shutdown()
        raise SystemExit(1)

    try:
        while True:
            print(
                f"pos={go2.position} vel={go2.velocity} yaw_speed={go2.yaw_speed:.2f} "
                f"gait_mode={go2.gait_mode} battery={go2.battery_percent}%"
            )
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        go2.shutdown()
