# ROS 2 dependencies

Nothing installs via `pip` here — `rclpy`, `unitree_go`, and `unitree_api`
all come from the ROS 2 workspace build, not PyPI. See the "ROS 2 setup"
section in the parent [README.md](../README.md) for the actual install
steps (ROS 2 itself, `unitree_ros2`, and `colcon build`).

Every script in this folder must be run in a terminal where
`~/unitree_ros2/setup.sh` has been sourced — that's what puts `rclpy` and
the Unitree message packages on `PYTHONPATH`.
