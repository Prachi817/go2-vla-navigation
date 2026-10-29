"""Summarize NaVILA-Bench results: averages, per-episode table, failure types.

    cd ~/go2-sim/NaVILA-Bench
    $PY /path/to/summarize_results.py [RESULTS_DIR]

Pure standard library; any python3 works.

Note on file names: navila_eval.py names each result
measurements/<episode_id - 1>.json, where episode_id comes from the dataset,
and the IDs skip numbers. So dataset index != file name (index 3 -> file 6,
index 9 -> file 12). This script maps between them using the dataset itself.

Failure types need the per-episode logs (logs/episode_idx_<i>.log, written by
run_many.sh or `$PY -u ... | tee`) to know whether NaVILA said "stop".
Benchmark success = NaVILA said stop AND the robot is within the goal radius
(utils/measures.py: Success.update_metric).
"""
import glob
import gzip
import json
import os
import re
import sys
from collections import Counter

R = sys.argv[1] if len(sys.argv) > 1 else \
    "eval_results/go2_matterport_vision_loco_2024-09-25_23-22-02"
DATA = "isaaclab_exts/omni.isaac.vlnce/assets/vln_ce_isaac_v1.json.gz"

episodes = json.load(gzip.open(DATA, "rt"))["episodes"]
file_to_idx = {int(ep["episode_id"]) - 1: i for i, ep in enumerate(episodes)}


def vlm_outputs(idx):
    log = os.path.join(R, "logs", f"episode_idx_{idx}.log")
    if not os.path.exists(log):
        return None
    return re.findall(r"VLM output: (.*)", open(log, errors="replace").read())


def classify(m, outputs):
    if m["success"] == 1.0:
        return "success"
    if outputs is None:
        return "fail (no log)"
    stopped = bool(outputs) and "stop" in outputs[-1].lower()
    if m["oracle_success"] == 1.0:
        return "reached goal, stopped outside radius" if stopped else "reached goal, never stopped"
    return "never reached, stopped in wrong place" if stopped else "never reached, never stopped"


rows = []
for f in glob.glob(os.path.join(R, "measurements", "*.json")):
    fid = int(os.path.basename(f)[:-5])
    m = json.load(open(f))
    idx = file_to_idx.get(fid)
    outs = vlm_outputs(idx) if idx is not None else None
    rows.append((idx, fid, m, len(outs) if outs is not None else None, classify(m, outs)))
rows.sort(key=lambda r: (r[0] is None, r[0]))

n = len(rows)
print(f"Results dir: {R}\nEpisodes: {n}\n")
for k in ["success", "oracle_success", "spl", "distance_to_goal", "oracle_navigation_error", "path_length"]:
    print(f"  {k:24s} {sum(r[2][k] for r in rows) / n:.3f}")

print("\nOutcome breakdown:")
for label, c in Counter(r[4] for r in rows).most_common():
    print(f"  {label:40s} {c:4d}  ({100 * c / n:.1f}%)")

print("\n idx  file  succ  oracle  dist_goal  path_len  decisions  outcome")
for idx, fid, m, nd, label in rows:
    print(f"{str(idx):>4}  {fid:>4}  {m['success']:4.0f}  {m['oracle_success']:6.0f}  "
          f"{m['distance_to_goal']:9.2f}  {m['path_length']:8.2f}  {str(nd):>9}  {label}")
