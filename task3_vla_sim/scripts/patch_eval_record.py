"""Create navila_eval_record.py: a copy of NaVILA-Bench's navila_eval.py that
saves every request sent to the VLM server, for the 8-bit vs fp16 test.

Adds two options:
    --record_dir DIR       save each decision as DIR/episode_idx_<i>/<n>.json:
                           {"images": [8 base64 JPEGs], "query": instruction,
                            "response": what the server answered}
    --results_suffix SFX   write measurements/videos to
                           eval_results/<task>_loco_<run><SFX> instead, so a
                           test run doesn't overwrite the benchmark results

Without these options it behaves exactly like the original, which is left
untouched.

Run from NaVILA-Bench/scripts (any python3):
    cd ~/go2-sim/NaVILA-Bench/scripts
    python3 /path/to/patch_eval_record.py
"""

src = open('navila_eval.py').read()
edits = [
    # 1. New command-line options.
    ('''parser.add_argument("--episode_idx", type=int, default=0)''',
     '''parser.add_argument("--episode_idx", type=int, default=0)
parser.add_argument("--record_dir", type=str, default=None)
parser.add_argument("--results_suffix", type=str, default="")'''),
    # 2. Save the exact request and answer. A counter on the function numbers
    #    the decisions within the episode (one process = one episode).
    ('''        response = json.loads(response_data.decode())
        return response''',
     '''        response = json.loads(response_data.decode())
        if args_cli.record_dir:
            rec_dir = os.path.join(args_cli.record_dir, f"episode_idx_{args_cli.episode_idx}")
            os.makedirs(rec_dir, exist_ok=True)
            n = getattr(sample_images_and_send_to_vlm, "n", 0)
            sample_images_and_send_to_vlm.n = n + 1
            with open(os.path.join(rec_dir, f"{n:03d}.json"), "w") as rec:
                json.dump({"images": encoded_images, "query": query, "response": response}, rec)
        return response'''),
    # 3. Separate results folder.
    ('''    result_dir = f"eval_results/{args_cli.task}_loco_{args_cli.load_run}"''',
     '''    result_dir = f"eval_results/{args_cli.task}_loco_{args_cli.load_run}{args_cli.results_suffix}"'''),
]
for old, new in edits:
    assert src.count(old) == 1, "not found: " + old
    src = src.replace(old, new)
open('navila_eval_record.py', 'w').write(src)
print('wrote navila_eval_record.py')
