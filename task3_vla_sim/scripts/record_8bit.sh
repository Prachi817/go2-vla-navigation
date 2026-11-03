#!/bin/bash
# Re-run a few episodes with the 8-bit server and save every NaVILA request,
# for the 8-bit vs fp16 comparison (compare_precision.py).
#
# Usage:  ./record_8bit.sh START END     (dataset episode indexes, inclusive)
#   nohup ./record_8bit.sh 10 29 > ~/go2-sim/record_8bit.log 2>&1 &
#
# Requests go to eval_results/quant_test_requests/episode_idx_<i>/.
# Measurements/videos go to a separate folder (..._quant_test), so the
# benchmark results are not overwritten.
#
# Expects the 8-bit VLM server to be running, and navila_eval_record.py to
# exist (made by patch_eval_record.py). Lives in ~/go2-sim/NaVILA-Bench/.

PY=~/miniconda3/envs/vlnce-isaac/bin/python
export PYTHONNOUSERSITE=1
unset PYTHONPATH
cd ~/go2-sim/NaVILA-Bench
REC=eval_results/quant_test_requests
mkdir -p $REC/logs
START=${1:-10}; END=${2:-29}
for i in $(seq $START $END); do
  grep -qx "$i" $REC/logs/done.txt 2>/dev/null && continue        # already done -> skip (resume)
  if ! pgrep -f vlm_server_8bit.py > /dev/null; then
    echo "$(date +%H:%M:%S) VLM server is not running - stopping before episode $i"; exit 1
  fi
  echo "$(date +%H:%M:%S) episode_idx $i ..."
  rm -rf $REC/episode_idx_$i          # a re-run must not mix with old files
  # -k 30: Isaac Sim can ignore SIGTERM, so force-kill 30 s after the timeout.
  timeout -k 30 900 $PY -u scripts/navila_eval_record.py --task=go2_matterport_vision --num_envs=1 --history_length=9 \
    --load_run=2024-09-25_23-22-02 --headless --enable_cameras --episode_idx=$i \
    --record_dir=$REC --results_suffix=_quant_test \
    > $REC/logs/episode_idx_$i.log 2>&1
  if grep -q "Traceback" $REC/logs/episode_idx_$i.log; then
    echo "   FAILED (see $REC/logs/episode_idx_$i.log)"; echo "$i" >> $REC/logs/failed.txt
  else
    echo "$i" >> $REC/logs/done.txt
  fi
done
echo "$(date +%H:%M:%S) ALL DONE"
