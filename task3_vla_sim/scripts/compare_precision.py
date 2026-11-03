"""8-bit vs fp16: send the requests saved by record_8bit.sh to a running VLM
server and compare its answers with the recorded 8-bit answers.

Each request is exactly what NaVILA saw during the 8-bit run (8 images +
instruction), so any difference comes from the model's precision alone.
Decoding is greedy (vlm_server.py: do_sample=False, num_beams=1), so the same
model and input should always give the same answer.

    cd ~/go2-sim/NaVILA-Bench
    python3 compare_precision.py --label 8bit   # sanity check: expect ~100%
    python3 compare_precision.py --label fp16   # the real test

Answers are saved to <requests dir>/replay_<label>.json; re-running with the
same label only prints the summary again (pass --force to re-query).

Pure standard library; any python3 works.
"""
import argparse
import glob
import json
import os
import re
import socket
from collections import Counter

p = argparse.ArgumentParser()
p.add_argument("--label", required=True, help="name for this replay, e.g. fp16")
p.add_argument("--requests", default="eval_results/quant_test_requests")
p.add_argument("--host", default="localhost")
p.add_argument("--port", type=int, default=54321)
p.add_argument("--force", action="store_true", help="re-query even if saved answers exist")
args = p.parse_args()


def ask(images, query):
    """Same wire protocol as navila_eval.py: 8-byte big-endian length + JSON."""
    req = json.dumps({"images": images, "query": query}).encode()
    with socket.create_connection((args.host, args.port), timeout=300) as s:
        s.sendall(len(req).to_bytes(8, "big"))
        s.sendall(req)
        size = int.from_bytes(s.recv(8), "big")
        data = b""
        while len(data) < size:
            packet = s.recv(4096)
            if not packet:
                break
            data += packet
    return json.loads(data.decode())


def action(text):
    """(kind, amount), checked in the same order as get_vel_command in
    eval_utils.py, so the kind is what the robot would actually do."""
    t = text.lower()
    if "turn left" in t:
        kind = "left"
    elif "turn right" in t:
        kind = "right"
    elif "move forward" in t or "move" in t:
        kind = "forward"
    elif "stop" in t:
        kind = "stop"
    else:
        kind = "other"
    m = re.search(r"(\d+)\s*(cm|centimeter|degree)", t)
    return kind, int(m.group(1)) if m else None


files = sorted(glob.glob(os.path.join(args.requests, "episode_idx_*", "*.json")))
if not files:
    raise SystemExit(f"no recorded requests under {args.requests}")

out_path = os.path.join(args.requests, f"replay_{args.label}.json")
replay = {}
if os.path.exists(out_path) and not args.force:
    replay = json.load(open(out_path))
todo = [f for f in files if f not in replay]
for k, f in enumerate(todo, 1):
    rec = json.load(open(f))
    replay[f] = ask(rec["images"], rec["query"])
    print(f"\r{k}/{len(todo)} requests", end="", flush=True)
    if k % 50 == 0 or k == len(todo):  # save as we go, so an interrupted run can resume
        json.dump(replay, open(out_path, "w"), indent=1)
if todo:
    print()

# Compare per decision and per episode.
episodes = {}
for f in files:
    ep = int(os.path.basename(os.path.dirname(f)).split("_")[-1])
    rec = json.load(open(f))["response"]
    episodes.setdefault(ep, []).append((rec, replay[f]))

n = exact = same_action = same_kind = 0
pairs = Counter()
print(f"\nReplay '{args.label}' vs recorded 8-bit answers ({out_path})\n")
print(" idx  decisions  same_action  first_diff")
for ep in sorted(episodes):
    rows = episodes[ep]
    first_diff = None
    ep_same = 0
    for step, (rec, new) in enumerate(rows):
        a, b = action(rec), action(new)
        n += 1
        exact += rec.strip() == new.strip()
        same_action += a == b
        same_kind += a[0] == b[0]
        ep_same += a == b
        if a != b:
            pairs[(f"{a[0]} {a[1]}", f"{b[0]} {b[1]}")] += 1
            if first_diff is None:
                first_diff = step
    print(f"{ep:>4}  {len(rows):>9}  {100 * ep_same / len(rows):10.1f}%  {first_diff if first_diff is not None else '-':>10}")

print(f"\nDecisions compared: {n}")
print(f"  identical text:        {100 * exact / n:.1f}%")
print(f"  same action + amount:  {100 * same_action / n:.1f}%")
print(f"  same action type:      {100 * same_kind / n:.1f}%")
if pairs:
    print("\nMost common differences (8-bit -> " + args.label + "):")
    for (a, b), c in pairs.most_common(10):
        print(f"  {a:>14} -> {b:<14} {c:4d}")
