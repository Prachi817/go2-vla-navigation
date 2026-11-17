"""Build an episode file with our own instructions on benchmark routes.

Reads custom_instructions.json. For each route it writes:
- the route's original benchmark episodes (re-run under the same
  conditions, as the fair comparison), and
- one episode per custom instruction: a copy of the 'base' episode (same
  house, start, path, goal and scoring) with only the instruction replaced.
Each is repeated --repeats times, since runs vary a little.

Also checks that every original of a route really has the same start and
goal as its base episode.

    cd ~/go2-sim/NaVILA-Bench
    python3 make_custom_episodes.py custom_instructions.json --repeats 2
    -> eval_results/custom/custom_episodes.json.gz   (for --episodes_file)
       eval_results/custom/custom_list.txt           (for run_controller.sh)
       eval_results/custom/custom_map.json           (for compare_custom.py)

Pure standard library; any python3 works.
"""
import argparse
import copy
import gzip
import json
import math
import os

p = argparse.ArgumentParser()
p.add_argument("instructions")
p.add_argument("--repeats", type=int, default=2)
p.add_argument("--data", default="isaaclab_exts/omni.isaac.vlnce/assets/vln_ce_isaac_v1.json.gz")
p.add_argument("--out", default="eval_results/custom")
args = p.parse_args()

dataset = json.load(gzip.open(args.data, "rt"))
episodes = dataset["episodes"]
routes = json.load(open(args.instructions))["routes"]


def same_place(a, b, tol=0.5):
    return math.dist(a[:2], b[:2]) < tol


out_eps, mapping = [], []
for route in routes:
    base = episodes[route["base"]]
    for idx in route["originals"]:
        ep = episodes[idx]
        if not (same_place(ep["start_position"], base["start_position"])
                and same_place(ep["reference_path"][-1], base["reference_path"][-1])):
            print(f"WARNING route {route['name']}: episode {idx} does not share start/goal with base {route['base']}")
    items = [("original", idx, episodes[idx]["instruction"]["instruction_text"], episodes[idx])
             for idx in route["originals"]]
    items += [("custom", route["base"], text, base) for text in route["custom"]]
    for kind, src, text, src_ep in items:
        for r in range(args.repeats):
            ep = copy.deepcopy(src_ep)
            ep["episode_id"] = str(900001 + len(out_eps))     # file name = episode_id - 1
            ep["instruction"] = {"instruction_text": text}
            mapping.append({"i": len(out_eps), "file": int(ep["episode_id"]) - 1, "route": route["name"],
                            "kind": kind, "source_idx": src, "repeat": r, "instruction": text})
            out_eps.append(ep)

os.makedirs(args.out, exist_ok=True)
custom = {k: v for k, v in dataset.items() if k != "episodes"}
custom["episodes"] = out_eps
with gzip.open(os.path.join(args.out, "custom_episodes.json.gz"), "wt") as f:
    json.dump(custom, f)
open(os.path.join(args.out, "custom_list.txt"), "w").write("\n".join(str(m["i"]) for m in mapping) + "\n")
json.dump(mapping, open(os.path.join(args.out, "custom_map.json"), "w"), indent=1)
n_orig = sum(m["kind"] == "original" for m in mapping)
print(f"wrote {len(out_eps)} episodes to {args.out}/ ({n_orig} original, {len(out_eps) - n_orig} custom, "
      f"{args.repeats} repeats each), ~{len(out_eps) * 2.5:.0f} min to run")
