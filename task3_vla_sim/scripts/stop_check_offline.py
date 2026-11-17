"""Offline test of two stop signals for the stop-aware controller, on the
requests saved by record_8bit.sh (episodes 10-29, 725 decisions). No Isaac Sim.

For every saved decision (same 8 images + instruction NaVILA saw), ask a
vlm_server_stopcheck.py server:
    stop_prob  how likely NaVILA's normal answer is to start like a stop
    ask        a direct yes/no question: QUESTION below

Robot positions weren't recorded, so there is no exact "at the goal" label
per decision. The test uses labels we do know:
    start      first 3 decisions of each episode: just started, not done
    said_stop  the decision where NaVILA itself said stop
    before_ok  the 5 decisions just before a successful stop: near the goal
A useful signal is low on "start" and high on "said_stop" / "before_ok".

    cd ~/go2-sim/NaVILA-Bench
    python3 stop_check_offline.py

Answers are cached in <requests dir>/stop_check.json (re-running only prints
the report; --force re-queries). Per-decision table: stop_check.tsv.
Pure standard library; any python3 works.
"""
import argparse
import glob
import gzip
import json
import os
import socket

QUESTION = ('Have you completed the assigned task and reached the place where '
            'the instruction says to stop? Answer with only "yes" or "no".')

p = argparse.ArgumentParser()
p.add_argument("--requests", default="eval_results/quant_test_requests")
p.add_argument("--measurements",
               default="eval_results/go2_matterport_vision_loco_2024-09-25_23-22-02_quant_test/measurements")
p.add_argument("--data", default="isaaclab_exts/omni.isaac.vlnce/assets/vln_ce_isaac_v1.json.gz")
p.add_argument("--host", default="localhost")
p.add_argument("--port", type=int, default=54321)
p.add_argument("--force", action="store_true")
args = p.parse_args()


def ask_server(payload):
    req = json.dumps(payload).encode()
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


def yes_no(text):
    t = text.strip().lower()
    if t.startswith("yes"):
        return "yes"
    if t.startswith("no"):
        return "no"
    return "other"


files = sorted(glob.glob(os.path.join(args.requests, "episode_idx_*", "*.json")))
if not files:
    raise SystemExit(f"no recorded requests under {args.requests}")

cache_path = os.path.join(args.requests, "stop_check.json")
cache = {}
if os.path.exists(cache_path) and not args.force:
    cache = json.load(open(cache_path))
todo = [f for f in files if f not in cache]
for k, f in enumerate(todo, 1):
    rec = json.load(open(f))
    sp = ask_server({"images": rec["images"], "query": rec["query"], "mode": "stop_prob"})
    if k == 1:
        print("first stop_prob reply (check the top tokens look like 'The' / 'I'):", sp)
    ans = ask_server({"images": rec["images"], "query": rec["query"], "mode": "ask", "question": QUESTION})
    cache[f] = {"stop_prob": sp["stop_prob"], "top5": sp["top5"], "ask": ans}
    print(f"\r{k}/{len(todo)} requests", end="", flush=True)
    if k % 25 == 0 or k == len(todo):
        json.dump(cache, open(cache_path, "w"), indent=1)
if todo:
    print()

# Episode outcomes from the recording run's own measurements.
episodes = json.load(gzip.open(args.data, "rt"))["episodes"]
outcome = {}
for i in range(len(episodes)):
    m_path = os.path.join(args.measurements, f"{int(episodes[i]['episode_id']) - 1}.json")
    if os.path.exists(m_path):
        m = json.load(open(m_path))
        outcome[i] = "success" if m["success"] == 1.0 else \
            ("reached, no stop" if m["oracle_success"] == 1.0 else "never reached")

rows = []  # (idx, step, recorded answer, stop_prob, ask answer, labels)
by_ep = {}
for f in files:
    idx = int(os.path.basename(os.path.dirname(f)).split("_")[-1])
    by_ep.setdefault(idx, []).append(f)
for idx in sorted(by_ep):
    fs = by_ep[idx]
    recs = [json.load(open(f))["response"] for f in fs]
    stop_at = next((s for s, r in enumerate(recs) if "stop" in r.lower() and "next action" not in r.lower()), None)
    for s, f in enumerate(fs):
        labels = []
        if s < 3:
            labels.append("start")
        if s == stop_at:
            labels.append("said_stop")
        if outcome.get(idx) == "success" and stop_at is not None and stop_at - 5 <= s < stop_at:
            labels.append("before_ok")
        rows.append((idx, s, recs[s], cache[f]["stop_prob"], yes_no(cache[f]["ask"]), labels))

n = len(rows)
fmt = {a: sum(r[4] == a for r in rows) for a in ("yes", "no", "other")}
print(f"\nDecisions: {n}   yes/no answers: yes {fmt['yes']}, no {fmt['no']}, other {fmt['other']}")
if fmt["other"]:
    print("  examples of 'other':", [cache[f]["ask"] for f in files if yes_no(cache[f]["ask"]) == "other"][:3])

print("\n label        n   says yes   mean stop_prob   stop_prob>=0.1   >=0.3")
groups = [("start", lambda r: "start" in r[5]),
          ("said_stop", lambda r: "said_stop" in r[5]),
          ("before_ok", lambda r: "before_ok" in r[5]),
          ("all", lambda r: True)]
for name, sel in groups:
    g = [r for r in rows if sel(r)]
    if not g:
        print(f" {name:10s}   0")
        continue
    k = len(g)
    print(f" {name:10s} {k:3d}   {100 * sum(r[4] == 'yes' for r in g) / k:7.1f}%   "
          f"{sum(r[3] for r in g) / k:14.3f}   {100 * sum(r[3] >= 0.1 for r in g) / k:13.1f}%   "
          f"{100 * sum(r[3] >= 0.3 for r in g) / k:5.1f}%")

print("\n idx  outcome            decisions  stop_prob>=0.1 at steps       first 'yes'")
for idx in sorted(by_ep):
    g = [r for r in rows if r[0] == idx]
    hi = [r[1] for r in g if r[3] >= 0.1]
    first_yes = next((r[1] for r in g if r[4] == "yes"), "-")
    print(f"{idx:>4}  {outcome.get(idx, '?'):17s}  {len(g):9d}  {str(hi)[:28]:28s}  {first_yes}")

tsv = os.path.join(args.requests, "stop_check.tsv")
with open(tsv, "w") as out:
    out.write("idx\tstep\tstop_prob\task\tlabels\trecorded_answer\n")
    for idx, s, rec, sp, a, labels in rows:
        out.write(f"{idx}\t{s}\t{sp:.4f}\t{a}\t{','.join(labels)}\t{rec}\n")
print(f"\nPer-decision table: {tsv}")
