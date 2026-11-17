"""Compare a stop-aware controller run with the baseline on the same episodes.

    cd ~/go2-sim/NaVILA-Bench
    python3 compare_runs.py eval_results/go2_matterport_vision_loco_2024-09-25_23-22-02_ctrl_prob

Only episodes finished in the controller run are compared, against the
baseline's results for the same episodes (default: the full 1,077 run).

Prints: metrics side by side, outcome breakdowns, which episodes flipped,
what the controller did, and - from the per-decision logs - how NaVILA's stop
probability relates to the true distance to the goal (logged for analysis
only; the controller never sees it).

Pure standard library; any python3 works.
"""
import argparse
import glob
import gzip
import json
import os
import re
from collections import Counter

p = argparse.ArgumentParser()
p.add_argument("run")
p.add_argument("--baseline", default="eval_results/go2_matterport_vision_loco_2024-09-25_23-22-02")
p.add_argument("--data", default="isaaclab_exts/omni.isaac.vlnce/assets/vln_ce_isaac_v1.json.gz")
args = p.parse_args()

episodes = json.load(gzip.open(args.data, "rt"))["episodes"]
file_of = {i: int(ep["episode_id"]) - 1 for i, ep in enumerate(episodes)}
METRICS = ["success", "oracle_success", "spl", "distance_to_goal", "path_length"]


def load(run, idx):
    f = os.path.join(run, "measurements", f"{file_of[idx]}.json")
    return json.load(open(f)) if os.path.exists(f) else None


def outcome(run, idx, m):
    if m["success"] == 1.0:
        return "success"
    log = os.path.join(run, "logs", f"episode_idx_{idx}.log")
    if not os.path.exists(log):
        return "fail (no log)"
    outs = re.findall(r"VLM output: (.*)", open(log, errors="replace").read())
    stopped = bool(outs) and "stop" in outs[-1].lower() and "next action" not in outs[-1].lower()
    if m["oracle_success"] == 1.0:
        return "reached, stopped outside" if stopped else "reached, never stopped"
    return "never reached, stopped wrong" if stopped else "never reached, never stopped"


done_file = os.path.join(args.run, "logs", "done.txt")
idxs = [int(x) for x in open(done_file).read().split()] if os.path.exists(done_file) else []
pairs = [(i, load(args.baseline, i), load(args.run, i)) for i in idxs]
pairs = [(i, b, r) for i, b, r in pairs if b and r]
n = len(pairs)
if not n:
    raise SystemExit("no episodes to compare yet")
opts = open(os.path.join(args.run, "logs", "options.txt")).read().strip().splitlines()[-1] \
    if os.path.exists(os.path.join(args.run, "logs", "options.txt")) else "?"
print(f"Run: {args.run}\n  {opts}\nEpisodes compared: {n}\n")
print(f"  {'metric':18s} {'baseline':>9s} {'controller':>11s}")
for k in METRICS:
    b = sum(x[1][k] for x in pairs) / n
    r = sum(x[2][k] for x in pairs) / n
    print(f"  {k:18s} {b:9.3f} {r:11.3f}   ({r - b:+.3f})")

ob = {i: outcome(args.baseline, i, b) for i, b, _ in pairs}
orun = {i: outcome(args.run, i, r) for i, _, r in pairs}
print("\nOutcomes:                        baseline  controller")
for label in ["success", "reached, never stopped", "reached, stopped outside",
              "never reached, stopped wrong", "never reached, never stopped", "fail (no log)"]:
    cb, cr = Counter(ob.values())[label], Counter(orun.values())[label]
    if cb or cr:
        print(f"  {label:30s} {cb:8d}  {cr:10d}")

gained = [i for i, b, r in pairs if b["success"] == 0 and r["success"] == 1]
lost = [i for i, b, r in pairs if b["success"] == 1 and r["success"] == 0]
print(f"\nFailure -> success: {len(gained)}  {gained}")
print(f"Success -> failure: {len(lost)}  {lost}")
for i in lost[:10]:
    print(f"   {i}: now '{orun[i]}'")

# What the controller did, and stop probability vs true distance.
ctrl_stops = fine = decisions = 0
bins = {"< 1 m": [], "1-3 m": [], "3-5 m": [], "> 5 m": []}
for i, _, r in pairs:
    f = os.path.join(args.run, "decisions", f"{file_of[i]}.jsonl")
    if not os.path.exists(f):
        continue
    for line in open(f):
        d = json.loads(line)
        decisions += 1
        ctrl_stops += d["control"].startswith("stop")
        fine += d["control"].startswith("25 cm")
        dist, sp = d.get("dist_to_goal_logged_only"), d.get("stop_prob")
        if dist is not None and sp is not None:
            key = "< 1 m" if dist < 1 else "1-3 m" if dist < 3 else "3-5 m" if dist < 5 else "> 5 m"
            bins[key].append(sp)
if decisions:
    print(f"\nController: {decisions} decisions, {ctrl_stops} controller stops, {fine} forward moves cut to 25 cm")
    print("\nStop probability vs true distance to goal (analysis only):")
    print("  distance   decisions   mean stop_prob   >=0.1    >=0.3")
    for key, v in bins.items():
        if v:
            print(f"  {key:8s} {len(v):10d}   {sum(v) / len(v):14.3f}   {100 * sum(x >= 0.1 for x in v) / len(v):5.1f}%  "
                  f"{100 * sum(x >= 0.3 for x in v) / len(v):5.1f}%")
