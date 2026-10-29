import cv2

from go2_ros2_interface import Go2RosInterface

if __name__ == "__main__":
    go2 = Go2RosInterface()
    frame = go2.get_camera_frame()

    if frame is None:
        print("Failed to get a camera frame. If this always fails, the inferred")
        print("VIDEO_REQUEST_TOPIC/VIDEO_RESPONSE_TOPIC names may be wrong --")
        print("check `ros2 topic list` for the actual videohub topic names.")
        go2.shutdown()
        raise SystemExit(1)

    out_path = "camera_frame_ros2.jpg"
    cv2.imwrite(out_path, frame)
    print(f"Saved {out_path}, shape={frame.shape}")
    go2.shutdown()
