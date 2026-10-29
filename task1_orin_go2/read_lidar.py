import sys
import time

from go2_interface import Go2Interface

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <network_interface>")
        sys.exit(1)

    go2 = Go2Interface(sys.argv[1])
    go2.set_lidar(True)

    print("Waiting for point cloud data...")
    deadline = time.time() + 10.0
    while go2.point_cloud is None and time.time() < deadline:
        time.sleep(0.2)

    if go2.point_cloud is None:
        print("Timed out waiting for point cloud. Is the LiDAR switched on / warmed up yet?")
        sys.exit(1)

    points = go2.point_cloud_xyz()
    print(f"Received point cloud with {len(points)} points.")
    print(f"Sample point: {points[0] if points else None}")
