import time

from go2_ros2_interface import Go2RosInterface

if __name__ == "__main__":
    go2 = Go2RosInterface()
    go2.set_lidar(True)

    print("Waiting for point cloud data...")
    deadline = time.time() + 10.0
    while go2.point_cloud is None and time.time() < deadline:
        time.sleep(0.2)

    if go2.point_cloud is None:
        print("Timed out waiting for point cloud. Is the LiDAR switched on / warmed up yet?")
        go2.shutdown()
        raise SystemExit(1)

    points = go2.point_cloud_xyz()
    print(f"Received point cloud with {len(points)} points.")
    print(f"Sample point: {points[0] if points else None}")
    go2.shutdown()
