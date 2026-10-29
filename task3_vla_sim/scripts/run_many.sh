#!/bin/bash
# Run many NaVILA-Bench episodes back to back, resumably.
#
# Usage:  ./run_many.sh START END        (dataset episode indexes, inclusive)
# Overnight (survives closing the terminal; tmux isn't installed on the lab machine):
#   nohup ./run_many.sh 10 209 > ~/go2-sim/run_many.log 2>&1 &
#
# Why not NaVILA-Bench's own scripts/run_benchmark.py:
#   - it calls bare `python`, which on this account resolves to /usr/bin/python
#     (not the conda env), and
#   - it always runs from --start-idx to the end of all 1077 episodes (~2 days).
#
# Expects the 8-bit VLM server to already be running (see README, Step 6).
# Lives in ~/go2-sim/NaVILA-Bench/ on the lab machine.

PY=~/miniconda3/envs/vlnce-isaac/bin/python
export PYTHONNOUSERSITE=1
unset PYTHONPATH
cd ~/go2-sim/NaVILA-Bench
R=eval_results/go2_matterport_vision_loco_2024-09-25_23-22-02
mkdir -p $R/logs
START=${1:-10}; END=${2:-209}
for i in $(seq $START $END); do
  grep -qx "$i" $R/logs/done.txt 2>/dev/null && continue        # already done -> skip (resume)
  # Check the server *process*, not the port: an empty connection crashes vlm_server.py.
  if ! pgrep -f vlm_server_8bit.py > /dev/null; then
    echo "$(date +%H:%M:%S) VLM server is not running - stopping before episode $i"; exit 1
  fi
  echo "$(date +%H:%M:%S) episode_idx $i ..."
  # -u = unbuffered: without it, "VLM output" lines are lost when Isaac's
  # fastShutdown exits the process before Python flushes stdout.
  # timeout 900 = 15 min cap in case Isaac Sim hangs.
  timeout 900 $PY -u scripts/navila_eval.py --task=go2_matterport_vision --num_envs=1 --history_length=9 \
    --load_run=2024-09-25_23-22-02 --headless --enable_cameras --episode_idx=$i \
    > $R/logs/episode_idx_$i.log 2>&1
  if grep -q "Traceback" $R/logs/episode_idx_$i.log; then
    echo "   FAILED (see logs/episode_idx_$i.log)"; echo "$i" >> $R/logs/failed.txt
  else
    echo "$i" >> $R/logs/done.txt
  fi
done
echo "$(date +%H:%M:%S) ALL DONE"
