"""Tests for navila_bridge.py, using every NaVILA answer from the full Task 3
run (task3_vla_sim/results/navila_decisions.tsv). No robot or simulator.

    python3 task4_real_go2/test_bridge.py
"""
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from navila_bridge import (Action, execute_on_go2, parse_action, sample_frames,  # noqa: E402
                           sim_command)

REPO = os.path.dirname(HERE)
ANSWERS = os.path.join(REPO, "task3_vla_sim", "results", "navila_decisions.tsv")
EVAL_UTILS = os.path.join(REPO, "task3_vla_sim", "navila_bench", "utils", "eval_utils.py")
failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


# NaVILA-Bench's own mapping, taken from its source (its module imports cv2,
# which isn't needed here).
import numpy as np  # noqa: E402
src = open(EVAL_UTILS).read()
ns = {"np": np}
exec(src[src.index("def get_vel_command"):], ns)
get_vel_command = ns["get_vel_command"]

# 1. Every real answer parses, and matches the simulator's command.
answers = [line.rstrip("\n").split("\t", 1)[1] for line in open(ANSWERS)]
kinds = Counter()
differs = Counter()
for text in answers:
    a = parse_action(text)
    kinds[str(a)] += 1
    vel, secs = sim_command(a)
    ref_vel, ref_secs = get_vel_command(text)
    if not (np.allclose(vel, ref_vel) and math.isclose(secs, ref_secs, abs_tol=1e-6)):
        differs[(text, str(a), f"sim: {ref_vel} for {ref_secs}s")] += 1

print(f"{len(answers)} NaVILA answers parsed:")
for k, c in kinds.most_common():
    print(f"  {k:22s} {c:6d}")
print("\nDifferent from NaVILA-Bench's get_vel_command (on purpose):")
for (text, a, ref), c in differs.items():
    print(f"  {c:3d} x {text!r}\n        bridge: {a}   {ref}")
check(set(a for (_, a, _) in differs) <= {"unknown", "turn left 25 deg"},
      "unexpected difference from get_vel_command")
check(kinds["unknown"] == 2, "expected exactly the 2 'motion blur' answers to be unknown")

# 2. Parser edge cases.
cases = {
    "The next action is move forward 75 cm.": ("forward", 0.75),
    "The next action is turn right 30 degree.": ("right", 30.0),
    "The next action is turn left 45 degrees.": ("left", 45.0),
    "I think I should stop because I have finished the instruction.": ("stop", None),
    "The next action is turn left.": ("unknown", None),
    "The next action is move forward.": ("unknown", None),
    "": ("unknown", None),
}
for text, (kind, amount) in cases.items():
    a = parse_action(text)
    check(a.kind == kind and (amount is None or math.isclose(a.amount, amount)),
          f"parse {text!r} -> {a.kind} {a.amount}, expected {kind} {amount}")


# 3. Go2 commands, with a fake robot that records calls.
class FakeGo2:
    def __init__(self):
        self.calls = []

    def move_distance(self, d, speed):
        self.calls.append(("move_distance", round(d, 3), speed))

    def turn_degrees(self, deg, yaw_rate):
        self.calls.append(("turn_degrees", deg, yaw_rate))

    def stop(self):
        self.calls.append(("stop",))


expect = [
    (Action("forward", 0.75), ("move_distance", 0.75, 0.3)),
    (Action("forward", 2.0), ("move_distance", 0.75, 0.3)),      # clamped
    (Action("left", 30.0), ("turn_degrees", 30.0, 0.5)),         # left = positive
    (Action("right", 15.0), ("turn_degrees", -15.0, 0.5)),
    (Action("right", 90.0), ("turn_degrees", -45.0, 0.5)),       # clamped
    (Action("stop"), ("stop",)),
    (Action("unknown"), ("stop",)),
]
for action, call in expect:
    go2 = FakeGo2()
    execute_on_go2(go2, action)
    check(go2.calls == [call], f"{action} -> {go2.calls}, expected {call}")

# 4. Frame sampling matches navila_eval.py's sample_images_and_send_to_vlm.
for n in range(1, 40):
    hist = list(range(n))
    got = sample_frames(hist)
    if n < 8:
        ref = [None] * (8 - n) + hist
    else:
        ref = [hist[int(i * (n - 1) / 7)] for i in range(7)] + [hist[-1]]
    check(got == ref, f"sample_frames with {n} frames")

print("\nALL TESTS PASSED" if not failures else "\nFAILED:\n  " + "\n  ".join(failures))
sys.exit(1 if failures else 0)
