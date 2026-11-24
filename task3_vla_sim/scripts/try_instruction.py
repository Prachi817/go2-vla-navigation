"""Type an instruction, run it once in simulation on a benchmark route.

The route (house, start, goal, scoring) comes from a benchmark episode; only
the instruction is replaced by what you type. Prints NaVILA's decisions as
they happen, then the result and where the video is.

    cd ~/go2-sim/NaVILA-Bench
    python3 try_instruction.py --route D "Go to the pantry and stop between the two shelves on the right."
    python3 try_instruction.py --base 7 "Cross the hall and stop in the archway."
    python3 try_instruction.py --list                     # show the routes

--route uses the routes in custom_instructions.json (A-E); --base takes any
benchmark episode index (0-1076). Each try takes ~2-3 min. Plain NaVILA by
default; pass --stop_rule prob --fine_steps to try the stop-aware controller.

Needs the VLM server running (vlm_server_stopcheck.py, or vlm_server_8bit.py)
and scripts/navila_eval_stopaware.py (patch_eval_stopaware.py).
Runs with any python3; the simulator itself uses the vlnce-isaac env.
"""
import argparse
import copy
import glob
import gzip
import json
import os
import subprocess
import sys

PY = os.environ.get("NAVILA_PY", os.path.expanduser("~/miniconda3/envs/vlnce-isaac/bin/python"))
DATA = "isaaclab_exts/omni.isaac.vlnce/assets/vln_ce_isaac_v1.json.gz"
TRY_DIR = "eval_results/try"
RESULTS = "eval_results/go2_matterport_vision_loco_2024-09-25_23-22-02_try"

p = argparse.ArgumentParser()
p.add_argument("instruction", nargs="?")
p.add_argument("--route", help="A-E from custom_instructions.json")
p.add_argument("--base", type=int, help="benchmark episode index to take the route from")
p.add_argument("--routes_file", default="custom_instructions.json")
p.add_argument("--stop_rule", choices=["none", "prob"], default="none")
p.add_argument("--fine_steps", action="store_true")
p.add_argument("--list", action="store_true")
args = p.parse_args()

episodes = json.load(gzip.open(DATA, "rt"))["episodes"]
routes = {r["name"]: r for r in json.load(open(args.routes_file))["routes"]} \
    if os.path.exists(args.routes_file) else {}

if args.list:
    for name, r in routes.items():
        print(f"Route {name} (episode {r['base']}): {episodes[r['base']]['instruction']['instruction_text']}")
    sys.exit(0)
if not args.instruction or (args.route is None) == (args.base is None):
    sys.exit("give an instruction and exactly one of --route or --base (see --list)")
base = routes[args.route.upper()]["base"] if args.route else args.base

# One-episode file: the base episode's route, your words.
os.makedirs(TRY_DIR, exist_ok=True)
n = len(glob.glob(os.path.join(TRY_DIR, "try_*.json.gz"))) + 1
ep = copy.deepcopy(episodes[base])
ep["episode_id"] = str(990000 + n)            # results file = episode_id - 1
ep["instruction"] = {"instruction_text": args.instruction}
ep_file = os.path.join(TRY_DIR, f"try_{n:03d}.json.gz")
with gzip.open(ep_file, "wt") as f:
    json.dump({"episodes": [ep]}, f)
json.dump({"try": n, "base": base, "route": args.route, "instruction": args.instruction,
           "original_instruction": episodes[base]["instruction"]["instruction_text"],
           "stop_rule": args.stop_rule, "fine_steps": args.fine_steps},
          open(os.path.join(TRY_DIR, f"try_{n:03d}.json"), "w"), indent=1)

print(f"Try {n}: route of episode {base}")
print(f"  original: {episodes[base]['instruction']['instruction_text']}")
print(f"  yours:    {args.instruction}\nRunning (~2-3 min)...")

cmd = ["timeout", "-k", "30", "900", PY, "-u", "scripts/navila_eval_stopaware.py",
       "--task=go2_matterport_vision", "--num_envs=1", "--history_length=9",
       "--load_run=2024-09-25_23-22-02", "--headless", "--enable_cameras", "--episode_idx=0",
       f"--episodes_file={ep_file}", "--results_suffix=_try", f"--stop_rule={args.stop_rule}"]
if args.fine_steps:
    cmd.append("--fine_steps")
env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
env["PYTHONNOUSERSITE"] = "1"
log_path = os.path.join(TRY_DIR, f"try_{n:03d}.log")
with open(log_path, "w") as log:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    for line in proc.stdout:
        log.write(line)
        if line.startswith("VLM output:") or line.startswith("Controller:"):
            print("  " + line.strip())
    proc.wait()

m_path = os.path.join(RESULTS, "measurements", f"{990000 + n - 1}.json")
if not os.path.exists(m_path):
    sys.exit(f"No result - see {log_path}")
m = json.load(open(m_path))
said_stop = any("stop" in l and "next action" not in l
                for l in open(log_path) if l.startswith("VLM output:"))
if m["success"] == 1.0:
    verdict = "SUCCESS"
elif m["oracle_success"] == 1.0:
    verdict = "reached the goal area, but " + ("stopped outside it" if said_stop else "never stopped")
else:
    verdict = "never reached the goal area, " + ("stopped in the wrong place" if said_stop else "never stopped")
print(f"\nResult: {verdict}")
print(f"  ended {m['distance_to_goal']:.2f} m from the goal (success needs < 3 m and a stop), "
      f"closest {m['oracle_navigation_error']:.2f} m, walked {m['path_length']:.1f} m")
print(f"  video: {RESULTS}/videos/output_{990000 + n - 1}.mp4")
