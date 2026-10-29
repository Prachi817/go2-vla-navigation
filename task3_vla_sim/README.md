# Task 3 - VLA-Based Control in Simulation

Goal: run a pretrained Vision-Language-Action model in simulation so the Go2
takes **camera input + a natural-language instruction** and produces
navigation actions, closing the loop end to end.

## Status

**Working end to end** (2026-10-28). NaVILA (8-bit) drives the simulated
Go2 in Isaac Sim through NaVILA-Bench's Matterport3D scenes, on a single
RTX A4500 (20 GB) shared with Isaac Sim.

- First 10 episodes: **70% success, 90% oracle success, SPL 0.647**
  (see [Results](#results)).
- Overnight run of episodes 10-209 in progress - results to be added below.

**Closes Task 2's open item**: the Task 2 README couldn't confirm that
simulated *sensors* were exercised (the planner demo only proved control).
`navila_eval.py` uses the robot's simulated RGB camera (`camera_obs`,
512x512) for every NaVILA decision, and the environment also exposes
`depth_obs` (1x512x512). Sensing + control in sim are both confirmed.

No physical robot is needed for this task - everything runs on the lab
machine.

## How it works

```
 Isaac Sim (vlnce-isaac env)                         VLM server (navila env)
 +-----------------------------------+   TCP :54321  +-------------------------+
 | navila_eval.py                    |  8 JPEG frames| vlm_server_8bit.py      |
 |  - Go2 in a Matterport3D scene    |  + instruction|  NaVILA llama3-8b-8f    |
 |  - robot camera frame every 0.5 s |-------------->|  (8-bit, ~1.3-1.7 s per |
 |  - low-level walking policy       |               |   decision)             |
 |    (pretrained, 2024-09-25_...)   |<--------------|                         |
 |  - get_vel_command(): text -> vel | "The next     +-------------------------+
 +-----------------------------------+  action is move forward 75 cm."
```

Per decision, `navila_eval.py`:
1. Samples **8 frames** from the camera history (7 evenly spaced + the latest;
   pads with black frames at the start of an episode - hence the harmless
   `Not enough images received, padding.` messages).
2. Sends them + the instruction to the server over a socket.
3. Turns NaVILA's text answer into a velocity command and a duration with
   simple keyword matching (`get_vel_command()` in NaVILA-Bench's
   [`eval_utils.py`](navila_bench/utils/eval_utils.py)):

   | NaVILA says | Velocity (vx, vy, wz) | Duration |
   |---|---|---|
   | move forward 25 / 50 / 75 cm | (0.5 m/s, 0, 0) | 0.5 / 1.0 / 1.5 s |
   | turn left 15 / 30 / 45 degree | (0, 0, +pi/6 rad/s) | 0.5 / 1.0 / 1.5 s |
   | turn right 15 / 30 / 45 degree | (0, 0, -pi/6 rad/s) | 0.5 / 1.0 / 1.5 s |
   | stop | (0, 0, 0) | ends episode |
   | anything else | (0.5 m/s, 0, 0) | 0.5 s |

4. Runs the walking policy on that command for that many sim steps, then
   asks again.

An episode ends when NaVILA says **stop**, the robot is stuck for 1000
steps, or it hits the step limit (50 s of sim time = 100 x the 0.5 s
camera interval). Results are
written to `eval_results/<task>_loco_<run>/`:
`measurements/<episode_id-1>.json` and `videos/output_<episode_id-1>.mp4`
(robot camera + third-person view, with the instruction and NaVILA's current
decision drawn on the frames).

**Metrics** (NaVILA-Bench's [`measures.py`](navila_bench/utils/measures.py)):
- **Success** - NaVILA said stop **and** the robot is within the goal radius
  (~3 m). Being close without stopping does *not* count.
- **Oracle success** - got within the radius at any point.
- **SPL** - success weighted by path efficiency (shortest path / path taken).
- **Distance to goal**, **oracle navigation error** (closest approach),
  **path length** - metres.

These are the standard vision-and-language navigation metrics, and the
NaVILA paper reports the same ones on this benchmark (Table IV, Go2 with the
vision walking policy): **50.2% success, 58.7% oracle success, SPL 45.5**
over all 1,077 episodes at full precision. The metric definitions are
NaVILA-Bench's; the numbers in [Results](#results) are from our own runs.

## Which code is whose

Task 3 runs mostly on NaVILA-Bench's code, unchanged. Our repo adds the
scripts we wrote, plus reference copies of the NaVILA-Bench files we use.

### Files we use from NaVILA-Bench

Source: [yang-zj1026/NaVILA-Bench](https://github.com/yang-zj1026/NaVILA-Bench)
(MIT license). Reference copies, pinned to commit `e9d2db1`, are in
[`navila_bench/`](navila_bench/) - see its [README](navila_bench/README.md).

| File (path in NaVILA-Bench) | What it does for us | Copy in this repo |
|---|---|---|
| `scripts/navila_eval.py` | Runs one episode: loads the scene, captures camera frames, asks NaVILA, moves the robot, saves results | [`navila_bench/scripts/navila_eval.py`](navila_bench/scripts/navila_eval.py) |
| `isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/utils/eval_utils.py` | `get_vel_command()`: turns NaVILA's words into a velocity and a duration | [`navila_bench/utils/eval_utils.py`](navila_bench/utils/eval_utils.py) |
| `isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/utils/measures.py` | Computes success, oracle success, SPL and distances | [`navila_bench/utils/measures.py`](navila_bench/utils/measures.py) |
| `scripts/vlm_server.py` | The original NaVILA server (16-bit only); our patch script builds `vlm_server_8bit.py` from it | [`navila_bench/scripts/vlm_server.py`](navila_bench/scripts/vlm_server.py) |
| `scripts/run_benchmark.py` | Their batch runner, which we replaced with our `run_many.sh` | [`navila_bench/scripts/run_benchmark.py`](navila_bench/scripts/run_benchmark.py) |
| `scripts/demo_planner.py` | The Task 2 demo | not copied (see Task 2) |
| `logs/rsl_rl/go2_vision/2024-09-25_23-22-02/` | The pretrained walking policy (below) | not copied (model weights) |

On the lab machine these are under `~/go2-sim/NaVILA-Bench/`, for example
`~/go2-sim/NaVILA-Bench/scripts/navila_eval.py`. `vlm_server_8bit.py` is
not in NaVILA-Bench or in this repo: it only exists on the lab machine,
generated by our `patch_vlm_server_8bit.py`.

The copies are for reading and reference. The runs use the files in
`~/go2-sim/NaVILA-Bench/` on the lab machine.

### The walking policy (the "legs")

The low-level walking policy also comes from NaVILA-Bench. It is the
`--load_run=2024-09-25_23-22-02` passed to `navila_eval.py`, and its files
are in their repo:

```
logs/rsl_rl/go2_vision/2024-09-25_23-22-02/
    model_26499.pt          <- the trained policy (checkpoint)
    exported/policy.jit     <- exported version
```

- The NaVILA authors trained it with reinforcement learning in Isaac Lab.
  Their paper says they trained it on an RTX 4090. We didn't train it; we
  load it.
- It's a much smaller neural network than NaVILA, and it runs fast and
  continuously. It takes the velocity command plus the robot's own body
  sensing and outputs the 12 leg-motor commands that make the Go2 walk at
  that speed while staying balanced.
- It's the paper's "vision" policy: it also uses LiDAR / height-scan data of
  the ground around the robot, which lets it step around obstacles. In the
  paper it beat a "blind" policy without that data by 14 points of success.

The full chain for one decision:

```
NaVILA: "move forward 75 cm"
  -> get_vel_command(): [0.5, 0, 0] for 1.5 s            (NaVILA-Bench code)
  -> walking policy: 12 leg-motor commands, many per second (NaVILA-Bench's pretrained model)
  -> Go2 walks ~75 cm in Isaac Sim
```

### What we wrote

Only these files are ours, in [`scripts/`](scripts/):

| Our file | Purpose |
|---|---|
| [`patch_vlm_server_8bit.py`](scripts/patch_vlm_server_8bit.py) | Creates `vlm_server_8bit.py` from NaVILA-Bench's server |
| [`fix_transformers_8bit.sh`](scripts/fix_transformers_8bit.sh) | The one-line Transformers fix |
| [`test_vlm_server.py`](scripts/test_vlm_server.py) | Sends a test request to the server |
| [`run_many.sh`](scripts/run_many.sh) | Our resumable batch runner |
| [`summarize_results.py`](scripts/summarize_results.py) | Reads the saved result files, averages the metrics and sorts failures into types (the metrics themselves are computed by `measures.py`) |

## Machine

| | |
|---|---|
| OS | Ubuntu 22.04.5, kernel 6.8 |
| CPU / RAM | Intel Xeon w5-3425 (12C/24T), 62 GB RAM |
| GPU | NVIDIA RTX A4500, **20,470 MiB** (driver 535.288, CUDA 12.2) |
| Disk | ~1 TB, shared `lab_user` account, ~95-98% full |

GPU was the only real constraint - RAM (58 GB free) and disk (after cleanup)
were fine.

## Setup (what actually worked)

Two conda envs, talking only over a local socket:

| Env | Runs | Key versions |
|---|---|---|
| `vlnce-isaac` (from Task 2) | Isaac Sim 4.1.0, Isaac Lab 1.1.0, `navila_eval.py` | torch 2.2.2, **pillow 10.2.0** |
| `navila` (new) | NaVILA model server | torch 2.3.0+cu121, flash-attn 2.5.8, transformers 4.37.2 (patched) |

**Why a separate env:** NaVILA needs torch 2.3.0, a flash-attn wheel built
for exactly that torch, and an old Transformers with NaVILA's own files
copied over it. Installing that into `vlnce-isaac` would upgrade its torch
and risk breaking Isaac Sim - the hardest part of Task 2. Separate envs cost
~3-5 GB of disk and nothing else. The NVIDIA driver/CUDA is system-wide and
shared automatically.

Paths on the lab machine:
```
~/go2-sim/
|-- NaVILA-Bench/                   # from Task 2
|   |-- scripts/vlm_server.py       # original (fp16 only)
|   |-- scripts/vlm_server_8bit.py  # created in Step 4
|   |-- run_many.sh                 # Step 7
|   `-- eval_results/...
|-- NaVILA/                         # cloned in Step 1
|-- checkpoints/navila-llama3-8b-8f/   # Step 2 (16 GB)
|-- vlm_server.log                  # background server output
`-- run_many.log                    # batch progress
```
Helper scripts are in [`scripts/`](scripts/).

### Always use `$PY`, never bare `python`/`pip`

On this account, `conda activate` does **not** put the env first on `PATH`
(something in the shell startup puts `/usr/bin` ahead of it):
```
(navila) $ which python pip
/usr/bin/python
/usr/bin/pip
```
Bare `pip install` therefore hits the **system** pip 22.0, which fails with
`Permission denied: '/usr/local/lib/python3.10/dist-packages/...'`, pulls
unpinned packages (it tried to install torch 2.14 / CUDA 13), and can't do
editable installs (`build backend is missing the 'build_editable' hook`).
Same root cause as Task 2's `ModuleNotFoundError: No module named 'omni'`.

Every new terminal:
```bash
conda activate navila            # or vlnce-isaac
export PYTHONNOUSERSITE=1        # never look in ~/.local
export PIP_NO_CACHE_DIR=1        # disk is nearly full
unset PYTHONPATH
PY=~/miniconda3/envs/navila/bin/python     # or .../envs/vlnce-isaac/bin/python
```
Then use `$PY` and `$PY -m pip` for everything.

### Step 0 - Check resources

```bash
free -h                 # RAM: 62 GB total, 58 GB available
nvidia-smi              # VRAM: 20470 MiB total, ~0.5 GB used by desktop + Firefox
df -h ~                 # disk: was 33 GB free
```
Freed 16 GB by clearing the pip cache (`rm -rf ~/.cache/pip`). Close Firefox
before big runs (~250 MiB VRAM).

### Step 1 - `navila` env + NaVILA

```bash
conda create -n navila python=3.10 -y
conda activate navila
export PYTHONNOUSERSITE=1; export PIP_NO_CACHE_DIR=1; unset PYTHONPATH
PY=~/miniconda3/envs/navila/bin/python

cd ~/go2-sim
git clone https://github.com/AnjieCheng/NaVILA.git
cd NaVILA

# torch first, so the flash-attn wheel doesn't drag in the newest torch
$PY -m pip install torch==2.3.0 torchvision==0.18.0
# prebuilt wheel matching CUDA 12.2 + torch 2.3 (no compiling)
$PY -m pip install https://github.com/Dao-AILab/flash-attention/releases/download/v2.5.8/flash_attn-2.5.8+cu122torch2.3cxx11abiFALSE-cp310-cp310-linux_x86_64.whl
$PY -m pip install -e .
$PY -m pip install -e ".[train]"
$PY -m pip install -e ".[eval]"

# pinned Transformers + NaVILA's patched files
$PY -m pip install git+https://github.com/huggingface/transformers@v4.37.2
site_pkg_path=$($PY -c 'import site; print(site.getsitepackages()[0])')
echo $site_pkg_path     # MUST be .../miniconda3/envs/navila/lib/python3.10/site-packages
cp -rv ./llava/train/transformers_replace/* $site_pkg_path/transformers/
cp -rv ./llava/train/deepspeed_replace/* $site_pkg_path/deepspeed/
```
This follows NaVILA's own `environment_setup.sh`, minus its optional
`conda install -c nvidia cuda-toolkit` (several GB, not needed with the
prebuilt wheel).

Verify:
```bash
$PY -c "import torch, transformers, flash_attn, llava; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('transformers', transformers.__version__)"
# torch 2.3.0+cu121 cuda True
# transformers 4.37.2
```
(A one-time "Migrating your old cache" message from Transformers is harmless.)

### Step 2 - Download the checkpoint (16 GB)

```bash
mkdir -p ~/go2-sim/checkpoints
$PY -c "
from huggingface_hub import snapshot_download
p = snapshot_download('a8cheng/navila-llama3-8b-8f', local_dir='/home/lab_user/go2-sim/checkpoints/navila-llama3-8b-8f')
print('DONE ->', p)
"
```
Re-running resumes an interrupted download. Result: `config.json`,
`trainer_state.json`, `llm/`, `vision_tower/`, `mm_projector/` - 16 GB.
No Hugging Face login was needed.

### Step 3 - Test the server alone (fp16)

Terminal 1:
```bash
cd ~/go2-sim/NaVILA-Bench/scripts
$PY vlm_server.py --model_path ~/go2-sim/checkpoints/navila-llama3-8b-8f --port 54321
# ... VLM Server listening on localhost:54321
```
Terminal 2 (navila env): [`scripts/test_vlm_server.py`](scripts/test_vlm_server.py)
sends 8 grey images + an instruction:
```
NaVILA says: The next action is move forward 75 cm.
```

| fp16 | VRAM used (whole GPU) |
|---|---|
| idle (model loaded) | 17,013 MiB (NaVILA process: 16,538) |
| during inference | 19,514 MiB (NaVILA process: 19,032) |

Works, but leaves <1 GB at peak - no room for Isaac Sim. Generation took
~1.7 s per decision.

The `attention_mask` / `pad_token_id` warnings in the server log are
standard Hugging Face warnings and harmless. Ctrl+C often doesn't stop the
server (it blocks waiting for a connection) - use `pkill -f vlm_server`.

### Step 4 - Switch to 8-bit

NaVILA's loader (`llava/model/builder.py: load_pretrained_model`) already
supports `load_8bit` via bitsandbytes, but `vlm_server.py` hard-codes fp16
and two things break when you turn 8-bit on.

**4a. Server patch** - [`scripts/patch_vlm_server_8bit.py`](scripts/patch_vlm_server_8bit.py)
writes `vlm_server_8bit.py` next to the original (original untouched):
1. accepts `--precision W8A16`;
2. calls `load_pretrained_model(..., load_8bit=True, torch_dtype=torch.float16)`
   - `torch_dtype` must be passed explicitly because NaVILA's
   `prepare_config_for_eval()` does `kwargs.pop("torch_dtype")`, which
   only exists on the fp16 path;
3. skips `model.to(device)` for 8-bit (the model is already placed by
   `device_map="auto"`).

```bash
cd ~/go2-sim/NaVILA-Bench/scripts
$PY patch_vlm_server_8bit.py     # -> wrote vlm_server_8bit.py
```

**4b. Transformers fix** - first 8-bit start crashed with:
```
File ".../transformers/modeling_utils.py", line 780, in _load_state_dict_into_meta_model
    set_module_quantized_tensor_to_device(
TypeError: set_module_quantized_tensor_to_device() got an unexpected keyword argument 'fp16_statistics'
```
Cause: the `modeling_utils.py` that NaVILA copies over Transformers 4.37.2
(Step 1) comes from an older Transformers, where the argument was
`fp16_statistics`; 4.37.2 renamed it to `quantized_stats` (a dict,
`{"SCB": ...}`). fp16 never hits this code path, which is why nobody using
NaVILA normally sees it. [`scripts/fix_transformers_8bit.sh`](scripts/fix_transformers_8bit.sh)
renames the argument in the installed file (backup kept as `.bak`):
```bash
F=~/miniconda3/envs/navila/lib/python3.10/site-packages/transformers/modeling_utils.py
cp $F $F.bak
sed -i 's/value=param, fp16_statistics=fp16_statistics/value=param, quantized_stats=({"SCB": fp16_statistics} if fp16_statistics is not None else None)/' $F
grep -n 'quantized_stats=({"SCB"' $F      # exactly one line, ~781
```

**4c. Run 8-bit:**
```bash
$PY vlm_server_8bit.py --model_path ~/go2-sim/checkpoints/navila-llama3-8b-8f --port 54321 --precision W8A16
```

| | fp16 | **8-bit** |
|---|---|---|
| VRAM idle (whole GPU) | 17,013 MiB | **10,410 MiB** |
| VRAM peak during inference | 19,514 MiB | **12,884 MiB** |
| Test answer | "move forward 75 cm" | "move forward 75 cm" (same) |
| Generation time | ~1.7 s | ~1.3 s |

~7.5 GB left for Isaac Sim - enough.

### Step 5 - Full loop, one episode

Terminal 1: 8-bit server running. Terminal 2:
```bash
conda activate vlnce-isaac
export PYTHONNOUSERSITE=1; unset PYTHONPATH
PY=~/miniconda3/envs/vlnce-isaac/bin/python
cd ~/go2-sim/NaVILA-Bench
$PY scripts/navila_eval.py --task=go2_matterport_vision --num_envs=1 --history_length=9 \
  --load_run=2024-09-25_23-22-02 --headless --enable_cameras --episode_idx=0
```

**Pillow fix.** The first attempt started Isaac Sim, then crashed:
```
File ".../omni/isaac/vlnce/vlnce/mdp/actions/navigation_actions.py", line 13, in <module>
    import torchvision
  ...
  File ".../isaacsim/extscache/omni.kit.pip_archive/pip_prebundle/PIL/ImageFont.py", line 40, in <module>
    from ._util import is_directory, is_path
ImportError: cannot import name 'is_directory' from 'PIL._util' (.../envs/vlnce-isaac/lib/python3.10/site-packages/PIL/_util.py)
```
Isaac Sim ships its own **Pillow 10.2.0** (`pip_prebundle/`) but the env had
**Pillow 11.3.0**, which removed `is_directory`; the two copies get mixed
when torchvision imports PIL. The same mismatch also caused an earlier
`Failed to import python module omni.kit.window.material_graph.tests` error
during startup. Task 2's `demo_planner.py` never imports torchvision, so it
didn't show up there.
```bash
ls ~/miniconda3/envs/vlnce-isaac/lib/python3.10/site-packages/isaacsim/extscache/omni.kit.pip_archive/pip_prebundle/ | grep -i pillow
# pillow-10.2.0.dist-info
$PY -m pip install "pillow==10.2.0"
```
Fixes both errors; no Traceback afterwards.

Then the episode ran end to end: Isaac Sim started (~5 s once the shader
cache is warm; the very first start took ~60 s), 100 warmup steps, then 24
NaVILA decisions ending in its own
`I think I should stop because I have finished the instruction.`
Total ~2 min. Harmless log noise you can ignore: `omni.hydra ... corrupted
data in primvar` (Go2 mesh UVs), `Possible version incompatibility ...
IPath`, `IOMMU is enabled`, `ActorCritic.__init__ got unexpected arguments
['history_length']`.

### Step 6 - Run the server in the background

For long runs, the server must survive closing the terminal. tmux isn't
installed (and needs sudo), so use `nohup`:
```bash
pkill -f vlm_server_8bit.py; sleep 3
cd ~/go2-sim/NaVILA-Bench/scripts
nohup env PYTHONNOUSERSITE=1 ~/miniconda3/envs/navila/bin/python -u vlm_server_8bit.py \
  --model_path ~/go2-sim/checkpoints/navila-llama3-8b-8f --port 54321 --precision W8A16 \
  > ~/go2-sim/vlm_server.log 2>&1 &
sleep 90; tail -3 ~/go2-sim/vlm_server.log    # -> VLM Server listening on localhost:54321
```
`-u` matters: without it, the "listening" line sits in Python's output
buffer and never reaches the log.

**Don't check the server by opening an empty connection** (`nc`,
`/dev/tcp`, etc.): `vlm_server.py` does `json.loads('')` on it, the
exception isn't caught, and the server exits. Check the process instead
(`pgrep -f vlm_server_8bit.py`), or send a real request with
`test_vlm_server.py`.

### Step 7 - Many episodes

NaVILA-Bench's `scripts/run_benchmark.py` isn't usable as-is here: it calls
bare `python` (-> `/usr/bin/python`) and always runs to the end of the
dataset (1,077 episodes, ~2 days). [`scripts/run_many.sh`](scripts/run_many.sh)
replaces it:
- runs a chosen index range with `$PY -u`, one log per episode;
- **resumable** - `logs/done.txt` records finished episodes, re-running skips them;
- 15-min `timeout` per episode in case Isaac hangs;
- stops if the server process has died, instead of burning through failures;
- episodes with a Traceback go to `logs/failed.txt`.

```bash
cp run_many.sh ~/go2-sim/NaVILA-Bench/ && chmod +x ~/go2-sim/NaVILA-Bench/run_many.sh
cd ~/go2-sim/NaVILA-Bench
nohup ./run_many.sh 10 209 > ~/go2-sim/run_many.log 2>&1 &

# progress (any terminal)
tail ~/go2-sim/run_many.log
wc -l eval_results/go2_matterport_vision_loco_2024-09-25_23-22-02/logs/done.txt
# stop on purpose
pkill -f run_many.sh; pkill -f navila_eval.py
```
Closing terminals / locking the screen is fine; rebooting or logging out of
the desktop is not. Keep other GPU jobs off the machine while it runs.

Why `-u` again: with plain `| grep`, the `VLM output` lines never appeared,
because Python buffers piped output and Isaac's `fastShutdown` exits the
process before the buffer is flushed. Measurements and videos were still
saved (they're written to files), only the console text was lost.

### Step 8 - Summarize

[`scripts/summarize_results.py`](scripts/summarize_results.py) prints the
averages, an outcome breakdown and a per-episode table. It maps dataset
indexes to result files and uses the per-episode logs to classify each
failure (see [Failure analysis](#failure-analysis)).
```bash
cd ~/go2-sim/NaVILA-Bench
$PY summarize_results.py
```

## Results

All runs: `go2_matterport_vision`, low-level policy `2024-09-25_23-22-02`,
NaVILA `navila-llama3-8b-8f` in **8-bit**, dataset `vln_ce_isaac_v1`
(1,077 episodes).

**File names are not dataset indexes.** Results are saved as
`measurements/<episode_id - 1>.json` and the dataset's IDs skip numbers, so
indexes 0-9 became files 0, 1, 2, 6, 7, 8, 9, 10, 11, 12.

### Run 1 - dataset indexes 0-9

| idx | file | success | oracle | dist. to goal (m) | path (m) |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 1 | 4.14 | 8.31 |
| 1 | 1 | 1 | 1 | 1.19 | 9.11 |
| 2 | 2 | 1 | 1 | 0.56 | 8.52 |
| 3 | 6 | 0 | 0 | 3.31 | 7.27 |
| 4 | 7 | 1 | 1 | 1.30 | 9.27 |
| 5 | 8 | 1 | 1 | 0.44 | 10.66 |
| 6 | 9 | 1 | 1 | 1.59 | 8.63 |
| 7 | 10 | 1 | 1 | 0.46 | 6.69 |
| 8 | 11 | 1 | 1 | 1.04 | 8.05 |
| 9 | 12 | 0 | 1 | 2.72 | 16.47 |

| Metric | Run 1 average |
|---|---|
| **Success rate** | **0.700** |
| Oracle success | 0.900 |
| **SPL** | **0.647** |
| Distance to goal | 1.678 m |
| Path length | 9.298 m |

The 7 successes stopped 0.44-1.59 m from the goal. Each episode took
~1.5-3 min of wall time. Run 1 results are backed up at
`eval_results/go2_matterport_vision_loco_2024-09-25_23-22-02_first10_backup/`.

### Run 2 - re-run of the 3 failures, with logs

Indexes 0, 3, 9 were re-run with `$PY -u ... | tee logs/episode_idx_<i>.log`
to capture NaVILA's decisions as text:

| idx | file | Run 1 | Run 2 | Same? |
|---|---|---|---|---|
| 0 | 0 | fail - 4.14 m, oracle 1 | **success** - 1.13 m, closest approach 0.14 m, SPL 0.887 | **No** |
| 3 | 6 | fail - 3.31 m, oracle 0 | fail - 3.31 m, oracle 0 | Yes |
| 9 | 12 | fail - 2.72 m, oracle 1, 16.5 m path | fail - 2.74 m, oracle 1, 16.4 m path | Yes |

Combining Run 1 with Run 2's re-runs gives 0.800 success / 0.900 oracle /
SPL 0.736 - but that mixes two runs, so report it as **70-80% on the same
10 episodes** rather than one number.

**Run-to-run variation.** NaVILA is deterministic (greedy decoding,
`do_sample=False`), so the variation comes from the physics simulation:
tiny differences in how the robot walks produce slightly different camera
frames, which can change a decision, and the difference compounds. Index 0
is a borderline episode that can go either way; indexes 3 and 9 fail
consistently. With only 10 episodes this alone moved the success rate by 10
points - small evaluations need repeated runs or many more episodes.

### Run 3 - dataset indexes 10-209 (overnight)

Started 2026-10-28 19:43 with `run_many.sh 10 209` (~2.5 min/episode,
~8 h). Fill in from `summarize_results.py`:

| Metric | Indexes 10-209 | All 210 (0-209) |
|---|---|---|
| Episodes completed | _TBD_ | _TBD_ |
| Success rate | _TBD_ | _TBD_ |
| Oracle success | _TBD_ | _TBD_ |
| SPL | _TBD_ | _TBD_ |
| Distance to goal | _TBD_ | _TBD_ |
| Path length | _TBD_ | _TBD_ |
| Failed to run (`failed.txt`) | _TBD_ | - |

Outcome breakdown: _TBD_

## Failure analysis

Benchmark success needs **both** "NaVILA said stop" **and** "within the goal
radius". Combining that with oracle success gives four kinds of failure:

| | NaVILA said stop | NaVILA never said stop |
|---|---|---|
| **Reached the goal area** (oracle = 1) | stopped too late / outside radius | wandered near the goal until the step limit |
| **Never reached it** (oracle = 0) | stopped confidently in the wrong place | lost |

All three types seen so far, with NaVILA's decisions from the Run 2 logs:

**Index 9 (file 12) - reached the goal area, never stopped.** 43 decisions,
no "stop" at all. Starts with ~135 degrees of left turns (45, 45, 30, 15), then
forward x6, `right 15` x2, forward x11, and from there keeps correcting
right (`right 15` x3; `right 15, 45, 15, 15`; `right 15, 30`) between short
forward runs without ever committing to stop, until the step limit. Ended 2.7 m from the goal - inside the radius - but without a
stop it doesn't count. Path 16.4 m, about twice the average. Consistent
across both runs.

**Index 3 (file 6) - stopped in the wrong place.** 18 decisions:
`right 15, right 15`, forward x2, `right 15, right 15`, forward x8,
`forward 25`, `right 15`, `forward 75`, **stop**. Confident and efficient-
looking, but it never came within 3 m of the goal (closest 3.30 m) - it
believed it had finished somewhere else. An instruction-grounding error
(wrong room / wrong turn), not a stopping problem. Consistent across both
runs.

**Index 0 (file 0) - borderline; stopped outside the radius in Run 1.**
Run 1: got within 2.65 m of the goal (oracle success), kept going and
stopped 4.14 m away. Run 2: 26 decisions (`left 30, left 15`, `forward 25`,
forward 75 x3, `left 30/15/30/15`, forward x8, `right 15` x4, forward x3, **stop**),
passed within 0.14 m of the goal and stopped 1.13 m away - success. Same
episode, opposite outcome: the stopping point is sensitive to small path
differences. Contributing factor: NaVILA moves in coarse 75 cm steps and
only re-decides after each one, so once it's near the goal one extra
"forward 75 cm" can carry it out of the radius. (Run 1's text log wasn't
captured; its outcome comes from the metrics and video.)

**Takeaways (so far):**
- NaVILA nearly always finds the goal region (90% oracle success); most
  failures are about **when to stop**, not where to go.
- The coarse action set (fixed 0.5 m/s, pi/6 rad/s, 25/50/75 cm, 15/30/45 degrees)
  limits how precisely it can stop.
- Runs aren't exactly repeatable in simulation; borderline episodes flip.

## Known caveats

- **8-bit, not fp16.** The NaVILA paper's numbers use full precision; 8-bit
  may cost some accuracy. A small fp16-vs-8-bit comparison would need
  Isaac Sim and fp16 NaVILA on separate GPUs, or a 24 GB+ card.
- **Patched installed library.** The 8-bit fix edits the installed
  Transformers file in the `navila` env. Reinstalling Transformers or
  re-running NaVILA's `cp -rv transformers_replace` step undoes it - re-run
  `fix_transformers_8bit.sh`.
- **`pillow==10.2.0` pinned in `vlnce-isaac`.** Pip may warn that some
  package wants `pillow>=11`; it hasn't caused problems. Upgrading Pillow in
  that env will bring the torchvision crash back.
- **Disk.** ~26 GB free after the checkpoint. `~/.local` (93 GB) and
  `~/.local.bak` (40 GB) look like leftovers of Task 2's `~/.local` pip
  problem, but this is a shared account - check before deleting anything.

## Next steps

- [ ] Add Run 3 (indexes 10-209) results and outcome breakdown above.
- [ ] Supervisor review: is ~200 episodes enough, or a larger/full split?
      Repeated runs per episode to measure variance? Is 8-bit acceptable?
- [ ] Custom instructions (outside the R2R dataset) - needs a small custom
      script instead of `navila_eval.py`.
- [ ] Bridge toward Task 4: a loop of Go2 camera -> `vlm_server_8bit.py` ->
      `get_vel_command()` -> Task 1 high-level commands, so the same server
      and command mapping carry over to the real robot.
