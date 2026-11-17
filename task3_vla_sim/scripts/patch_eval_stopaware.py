"""Create navila_eval_stopaware.py: NaVILA-Bench's navila_eval.py plus our
training-free stop-aware controller between NaVILA's answer and the walking
policy. The original navila_eval.py is left untouched.

New options:
    --stop_rule none|prob|ask  when the controller may stop the robot itself:
        none  never (plain NaVILA; useful as a re-run baseline with logging)
        prob  NaVILA's stop probability >= --t_stop
        ask   NaVILA answers "yes" to the stop question (asked every
              --ask_every decisions)
    --t_stop 0.3          threshold for --stop_rule prob
    --ask_every 3
    --fine_steps          cap forward moves at 25 cm when NaVILA looks unsure:
                          stop probability >= --t_fine, or its last 4 decisions
                          are all turns in both directions (searching)
    --t_fine 0.1
    --min_decisions 5     never stop or slow down before this many decisions
    --results_suffix SFX  results go to eval_results/<task>_loco_<run><SFX>
    --episodes_file F     read episodes from F (.json.gz) instead of the
                          benchmark, e.g. custom instructions

The controller only uses NaVILA's own outputs. The simulator's distance to
the goal is never used for control; it is only logged, per decision, in
decisions/<file>.jsonl next to measurements/ for later analysis.

Stop probability needs vlm_server_stopcheck.py. With the plain 8-bit server
it is logged as null and only --stop_rule none works.

A stop made by the controller ends the episode exactly like NaVILA's own
stop, and is printed as "VLM output: [controller] stop (...)" so
summarize_results.py counts it as a stop.

Run from NaVILA-Bench/scripts (any python3):
    cd ~/go2-sim/NaVILA-Bench/scripts
    python3 /path/to/patch_eval_stopaware.py
"""

src = open('navila_eval.py').read()
edits = [
    # 1. Options.
    ('''parser.add_argument("--episode_idx", type=int, default=0)''',
     '''parser.add_argument("--episode_idx", type=int, default=0)
parser.add_argument("--results_suffix", type=str, default="")
parser.add_argument("--stop_rule", choices=["none", "prob", "ask"], default="none")
parser.add_argument("--t_stop", type=float, default=0.3)
parser.add_argument("--ask_every", type=int, default=3)
parser.add_argument("--fine_steps", action="store_true")
parser.add_argument("--t_fine", type=float, default=0.1)
parser.add_argument("--min_decisions", type=int, default=5)
parser.add_argument("--episodes_file", type=str, default=None)'''),
    # 2. Let a request carry extra fields ("mode", "question").
    ('''def sample_images_and_send_to_vlm(image_list, vlm_host, vlm_port, query):''',
     '''def sample_images_and_send_to_vlm(image_list, vlm_host, vlm_port, query, extra=None):'''),
    ('''        'query': query
    }''',
     '''        'query': query
    }
    if extra:
        request_data.update(extra)'''),
    # 3. The controller.
    ('''def main():''',
     '''STOP_QUESTION = ('Have you completed the assigned task and reached the place where '
                 'the instruction says to stop? Answer with only "yes" or "no".')


def action_kind(text):
    t = text.lower()
    if "turn left" in t:
        return "left"
    if "turn right" in t:
        return "right"
    if "move" in t:
        return "forward"
    if "stop" in t:
        return "stop"
    return "other"


def stop_aware_control(text, n_decision, stop_prob, ask_answer, recent_kinds):
    """NaVILA's answer -> (velocity command, seconds to run it, note).
    Uses only NaVILA's own outputs, never the simulator's goal distance."""
    vel, time_to_go = get_vel_command(text)
    if time_to_go == 0 or n_decision < args_cli.min_decisions:
        return vel, time_to_go, ""
    if args_cli.stop_rule == "prob" and stop_prob is not None and stop_prob >= args_cli.t_stop:
        return [0.0, 0.0, 0.0], 0.0, f"stop (stop_prob {stop_prob:.2f})"
    if args_cli.stop_rule == "ask" and ask_answer is not None and ask_answer.strip().lower().startswith("yes"):
        return [0.0, 0.0, 0.0], 0.0, f"stop (answered {ask_answer.strip()[:20]!r})"
    if args_cli.fine_steps and action_kind(text) == "forward" and time_to_go > 0.5:
        searching = len(recent_kinds) >= 4 and \\
            all(k in ("left", "right") for k in recent_kinds[-4:]) and \\
            {"left", "right"} <= set(recent_kinds[-4:])
        if (stop_prob is not None and stop_prob >= args_cli.t_fine) or searching:
            why = f"stop_prob {stop_prob:.2f}" if stop_prob is not None and stop_prob >= args_cli.t_fine else "searching"
            return vel, 0.5, f"25 cm instead ({why})"
    return vel, time_to_go, ""


def main():'''),
    # 4. Per-episode decision log.
    ('''    num_steps = 0
    target_steps = 0''',
     '''    num_steps = 0
    target_steps = 0
    decision_log = []
    recent_kinds = []'''),
    # 5. Ask NaVILA, then let the controller decide.
    ('''                stream_output = sample_images_and_send_to_vlm(image_observations, args_cli.vlm_host, args_cli.vlm_port, instruction.instruction_text)
                vlm_vel_commands, time_to_go = get_vel_command(stream_output)''',
     '''                stream_output = sample_images_and_send_to_vlm(image_observations, args_cli.vlm_host, args_cli.vlm_port, instruction.instruction_text)
                n_decision = len(decision_log)
                sp_reply = sample_images_and_send_to_vlm(image_observations, args_cli.vlm_host, args_cli.vlm_port,
                                                         instruction.instruction_text, extra={"mode": "stop_prob"})
                stop_prob = sp_reply.get("stop_prob") if isinstance(sp_reply, dict) else None
                ask_answer = None
                if args_cli.stop_rule == "ask" and n_decision >= args_cli.min_decisions \\
                        and n_decision % args_cli.ask_every == 0 and action_kind(stream_output) != "stop":
                    ask_answer = sample_images_and_send_to_vlm(image_observations, args_cli.vlm_host, args_cli.vlm_port,
                                                               instruction.instruction_text,
                                                               extra={"mode": "ask", "question": STOP_QUESTION})
                vlm_vel_commands, time_to_go, control_note = stop_aware_control(
                    stream_output, n_decision, stop_prob, ask_answer, recent_kinds)
                recent_kinds.append(action_kind(stream_output))
                try:
                    dist = float(infos["measurements"]["distance_to_goal"])
                except Exception:
                    dist = None
                decision_log.append({
                    "decision": n_decision, "sim_step": num_steps, "navila": stream_output,
                    "stop_prob": stop_prob, "ask": ask_answer, "control": control_note,
                    "vel": [float(v) for v in vlm_vel_commands], "time_to_go": time_to_go,
                    "pos": [float(v) for v in env.unwrapped.scene["robot"].data.root_pos_w[0].detach().cpu().numpy()],
                    "dist_to_goal_logged_only": dist,
                })
                if control_note.startswith("stop"):
                    print(f"VLM output: [controller] {control_note}")
                elif control_note:
                    print(f"Controller: {control_note}")'''),
    # 6. Optional custom episode file (make_custom_episodes.py).
    ('''    r2r_data_path = os.path.join(ASSETS_DIR, "vln_ce_isaac_v1.json.gz")''',
     '''    r2r_data_path = args_cli.episodes_file or os.path.join(ASSETS_DIR, "vln_ce_isaac_v1.json.gz")'''),
    # 7. Separate results folder + save the decision log.
    ('''    result_dir = f"eval_results/{args_cli.task}_loco_{args_cli.load_run}"''',
     '''    result_dir = f"eval_results/{args_cli.task}_loco_{args_cli.load_run}{args_cli.results_suffix}"'''),
    ('''        json.dump(measurements, f, indent=4)''',
     '''        json.dump(measurements, f, indent=4)
    decision_dir = os.path.join(result_dir, "decisions")
    os.makedirs(decision_dir, exist_ok=True)
    with open(f"{decision_dir}/{int(episode['episode_id'])-1}.jsonl", "w") as f:
        for d in decision_log:
            f.write(json.dumps(d) + "\\n")'''),
]
for old, new in edits:
    assert src.count(old) == 1, "not found: " + old
    src = src.replace(old, new)
open('navila_eval_stopaware.py', 'w').write(src)
print('wrote navila_eval_stopaware.py')
