#!/bin/bash
# Run a list of episodes with the stop-aware controller (navila_eval_stopaware.py).
#
# Usage:  ./run_controller.sh NAME EPISODE_LIST [controller options...]
#   NAME          results go to eval_results/<...>_ctrl_NAME/
#   EPISODE_LIST  file with one dataset index per line (subset_100.txt, subset_200.txt)
# Examples:
#   nohup ./run_controller.sh prob subset_100.txt --stop_rule=prob --t_stop=0.3 --fine_steps > ~/go2-sim/ctrl_prob.log 2>&1 &
#   nohup ./run_controller.sh none subset_100.txt --stop_rule=none > ~/go2-sim/ctrl_none.log 2>&1 &   # re-run baseline, with logging
#
# Resumable (logs/done.txt). Expects vlm_server_stopcheck.py to be running
# and scripts/navila_eval_stopaware.py to exist (patch_eval_stopaware.py).
# Lives in ~/go2-sim/NaVILA-Bench/.

PY=~/miniconda3/envs/vlnce-isaac/bin/python
export PYTHONNOUSERSITE=1
unset PYTHONPATH
NAME=$1; LIST=$2; shift 2
[ -n "$NAME" ] && [ -f "$LIST" ] || { echo "usage: $0 NAME EPISODE_LIST [options]"; exit 1; }
cd ~/go2-sim/NaVILA-Bench
R=eval_results/go2_matterport_vision_loco_2024-09-25_23-22-02_ctrl_$NAME
mkdir -p $R/logs
echo "options: $*" >> $R/logs/options.txt
for i in $(cat $LIST); do
  grep -qx "$i" $R/logs/done.txt 2>/dev/null && continue        # already done -> skip (resume)
  if ! pgrep -f vlm_server_stopcheck.py > /dev/null; then
    echo "$(date +%H:%M:%S) vlm_server_stopcheck.py is not running - stopping before episode $i"; exit 1
  fi
  echo "$(date +%H:%M:%S) episode_idx $i ..."
  # -k 30: Isaac Sim can ignore SIGTERM, so force-kill 30 s after the timeout.
  timeout -k 30 900 $PY -u scripts/navila_eval_stopaware.py --task=go2_matterport_vision --num_envs=1 --history_length=9 \
    --load_run=2024-09-25_23-22-02 --headless --enable_cameras --episode_idx=$i \
    --results_suffix=_ctrl_$NAME "$@" \
    > $R/logs/episode_idx_$i.log 2>&1
  if grep -q "Traceback" $R/logs/episode_idx_$i.log; then
    echo "   FAILED (see $R/logs/episode_idx_$i.log)"; echo "$i" >> $R/logs/failed.txt
  elif ! grep -q "Shutting Down" $R/logs/episode_idx_$i.log; then
    echo "   HUNG/KILLED (no result)"; echo "$i" >> $R/logs/hung.txt
  else
    echo "$i" >> $R/logs/done.txt
  fi
done
echo "$(date +%H:%M:%S) ALL DONE"
