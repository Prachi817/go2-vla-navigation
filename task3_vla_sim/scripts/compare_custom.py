"""Results of the custom-instruction run, per route: original benchmark
wording vs our wording, on the same start and goal.

    cd ~/go2-sim/NaVILA-Bench
    python3 compare_custom.py eval_results/go2_matterport_vision_loco_2024-09-25_23-22-02_ctrl_custom

Pure standard library; any python3 works.
"""
import argparse
import json
import os
import re

p = argparse.ArgumentParser()
p.add_argument("run")
p.add_argument("--map", default="eval_results/custom/custom_map.json")
args = p.parse_args()

mapping = json.load(open(args.map))


def result(m):
    f = os.path.join(args.run, "measurements", f"{m['file']}.json")
    if not os.path.exists(f):
        return None
    r = json.load(open(f))
    log = os.path.join(args.run, "logs", f"episode_idx_{m['i']}.log")
    outs = re.findall(r"VLM output: (.*)", open(log, errors="replace").read()) if os.path.exists(log) else []
    stopped = bool(outs) and "stop" in outs[-1].lower() and "next action" not in outs[-1].lower()
    if r["success"] == 1.0:
        tag = "success"
    elif r["oracle_success"] == 1.0:
        tag = "reached, " + ("stopped outside" if stopped else "never stopped")
    else:
        tag = "not reached, " + ("stopped wrong" if stopped else "never stopped")
    return r["success"], r["distance_to_goal"], tag


totals = {"original": [0, 0], "custom": [0, 0]}
for route in sorted(set(m["route"] for m in mapping)):
    print(f"\n=== Route {route}")
    seen = []
    for m in mapping:
        if m["route"] != route or (m["kind"], m["instruction"]) in seen:
            continue
        seen.append((m["kind"], m["instruction"]))
        reps = [result(x) for x in mapping if x["route"] == route and x["instruction"] == m["instruction"]
                and x["kind"] == m["kind"]]
        done = [r for r in reps if r]
        totals[m["kind"]][0] += sum(r[0] for r in done)
        totals[m["kind"]][1] += len(done)
        label = f"{m['kind']} (ep {m['source_idx']})" if m["kind"] == "original" else "custom"
        text = m["instruction"] if len(m["instruction"]) <= 90 else m["instruction"][:87] + "..."
        print(f"  {label:16s} \"{text}\"")
        for r in reps:
            print("      " + (f"{r[2]:30s} {r[1]:5.2f} m from goal" if r else "(not run yet)"))

print("\nSuccess over all runs:")
for kind, (s, n) in totals.items():
    if n:
        print(f"  {kind:9s} {int(s)}/{n}  ({100 * s / n:.0f}%)")
