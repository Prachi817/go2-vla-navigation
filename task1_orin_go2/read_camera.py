import sys

import cv2

from go2_interface import Go2Interface

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <network_interface>")
        sys.exit(1)

    go2 = Go2Interface(sys.argv[1])
    frame = go2.get_camera_frame()

    if frame is None:
        print("Failed to get a camera frame.")
        sys.exit(1)

    out_path = "camera_frame.jpg"
    cv2.imwrite(out_path, frame)
    print(f"Saved {out_path}, shape={frame.shape}")
