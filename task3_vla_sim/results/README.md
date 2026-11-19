# Task 3 results (raw data)

Raw output of the full NaVILA-Bench run (all 1,077 episodes of
`vln_ce_isaac_v1`, NaVILA 8-bit, Go2 vision policy `2024-09-25_23-22-02`)
the 8-bit vs fp16 test, the offline stop-check test and the custom-instruction run. The numbers and what they mean are in the
[Task 3 README](../README.md#results); this folder is the data behind them.

| File | What it is |
|---|---|
| `summary_full.txt` | Output of [`summarize_results.py`](../scripts/summarize_results.py): averages, outcome breakdown, one row per episode |
| `measurements/<file>.json` | Metrics per episode, as written by `navila_eval.py`. File name = `episode_id - 1`, **not** the dataset index; `summary_full.txt` maps them (`idx` and `file` columns) |
| `navila_decisions.tsv` | Every NaVILA decision: `dataset index <tab> NaVILA's answer`, in order (35,597 lines). Indexes 1, 2, 4-8 are missing: their first run had no text log |
| `run_many.log` | Timestamps of the batch runs, including the re-run of the 4 hung episodes (374, 416, 666, 1055) |
| `quant_test/replay_8bit.json` | 8-bit server's answers to the 725 recorded requests (episodes 10-29); identical to the answers recorded during the episodes |
| `quant_test/replay_fp16.json` | fp16 server's answers to the same 725 requests |
| `quant_test/compare_fp16.log` | Output of [`compare_precision.py`](../scripts/compare_precision.py) `--label fp16` |
| `quant_test/rerun_10_29/measurements/` | Episodes 10-29 as re-run while recording for the 8-bit test (a second run of the same episodes; file names as in `measurements/`) |
| `stop_check/stop_check.tsv` | Offline stop-check test, one row per decision: stop probability, yes/no answer, labels, NaVILA's recorded answer |
| `stop_check/stop_check.json` | The same answers as returned by the server (incl. top-5 first tokens); `stop_check.log` is the printed report |
| `custom/custom_map.json` | Custom-instruction run: which episode file is which route, wording and repeat |
| `custom/measurements/`, `custom/decisions/` | Metrics per episode, and every decision with stop probability, position and true distance to goal |
| `custom/compare_custom.txt` | Output of [`compare_custom.py`](../scripts/compare_custom.py) |
| `controller_prob/`, `controller_fine/` | Stop-aware controller runs on `subset_100.txt`: measurements, per-decision logs, `compare_runs.txt` (output of [`compare_runs.py`](../scripts/compare_runs.py)), run log and options |

Not included (kept on the lab machine, `~/go2-sim/`): the per-episode
Isaac Sim logs, the videos (`results_backup/navila_full_20261103_1336.tar.gz`,
3.6 GB) and the recorded requests with images
(`NaVILA-Bench/eval_results/quant_test_requests/`, 144 MB).

Check the fp16 agreement from the two replay files alone:
```bash
python3 -c "
import json
a = json.load(open('quant_test/replay_8bit.json')); b = json.load(open('quant_test/replay_fp16.json'))
print(sum(a[k].strip() == b[k].strip() for k in a), 'of', len(a), 'identical')"
# -> 702 of 725 identical
```
