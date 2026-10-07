# Task 2 — Go2 Simulation Environment

Goal: set up the Go2 in a robotic simulator, with simulated sensors and
high-level control similar to the real robot's interface (Task 1). This
is what lets the VLA (Task 3) be developed and tested safely before
touching the physical robot.

## Status

✅ **Confirmed working** — ran `demo_planner.py` (`go2_matterport_vision`
task) on the lab computer's Isaac Sim. Watched the Go2 walk around inside
a rendered Matterport3D house scene via a PD path planner + pretrained
low-level walking policy, for a full ~12 minute run that shut down cleanly.

⏳ **Not yet separately confirmed**: whether this specific demo exercises
actual simulated *sensor* access (camera/depth), or only position/goal
state to drive the PD planner. The task's own wording asks for sensor
access *and* control — the control half is confirmed; the sensor half is
more likely exercised by Task 3's VLA evaluation scripts
(`navila_eval.py`), not this planner demo. Worth checking explicitly
before calling sensing fully done.

## What this actually is

Not a generic Isaac Sim setup — this uses the specific toolchain your
project's root README already names:

- **[NaVILA-Bench](https://github.com/yang-zj1026/NaVILA-Bench)** — sets
  up the Go2 in a Matterport3D-scanned house, with sensing + high-level
  control, driven by a path planner for now (VLA comes in Task 3).
- **[legged-loco](https://github.com/yang-zj1026/legged-loco)** — trains
  the low-level walking policy. Not used directly yet — NaVILA-Bench ships
  a pretrained policy (`load_run=2024-09-25_23-22-02`), so training a new
  one is optional/later, not required for this milestone.
- Both depend on a **forked Isaac Lab 1.1.0**
  ([yang-zj1026/IsaacLab](https://github.com/yang-zj1026/IsaacLab)), not
  the official NVIDIA Isaac Lab repo.

This isn't an arbitrary choice: NaVILA-Bench is the actual benchmark for
the NaVILA VLA model this whole capstone is built on, so it sets up
Task 3's integration path for free.

## The real gotcha: Isaac Sim version mismatch

The lab computer came with **Isaac Sim 5.1.0** already installed. NaVILA-Bench's
forked Isaac Lab is pinned to **Isaac Sim 4.1.0** and explicitly warns it
"may not be compatible with newer versions."

This isn't a theoretical warning — it broke concretely. Somewhere between
4.x and 5.x, NVIDIA renamed Isaac Sim's entire extension namespace from
`omni.isaac.*` to `isaacsim.*`. Isaac Lab 1.1.0 is written entirely
against the old names, so running it against a 5.1.0 install fails
immediately:
```
ModuleNotFoundError: No module named 'omni.isaac.kit'
```

We tried avoiding a second Isaac Sim install by using 5.1.0's bundled
`extsDeprecated/omni.isaac.kit` compatibility shim via `PYTHONPATH` — this
is a real thing Isaac Sim ships for exactly this transition, and it's
worth knowing about, but we didn't get a clean result from it before
switching approaches.

**What actually fixed it:** install Isaac Sim **4.1.0** as pip packages
into a dedicated conda env, instead of pointing at the system's 5.1.0
install. The two installs don't conflict — 5.1.0 stays available for
anything else on that machine.

## The second gotcha: pip silently installing to the wrong place

After installing the 4.1.0 pip packages, `from omni.isaac.kit import
SimulationApp` still failed with `ModuleNotFoundError: No module named
'omni'`. Cause: pip had printed `Defaulting to user installation because
normal site-packages is not writeable` and silently installed everything
into `~/.local/lib/python3.10/site-packages` instead of the conda env's
own site-packages — so the conda env's Python couldn't see any of it.

**Fix:**
```bash
export PYTHONNOUSERSITE=1          # stop Python from ever looking at ~/.local
unset PYTHONPATH                    # clear out any leftover path overrides
PY=~/miniconda3/envs/vlnce-isaac/bin/python   # call the conda env's python directly,
                                               # bypassing PATH resolution entirely
$PY -m pip install ...
```
Also worth doing once: purge any conflicting packages already sitting in
the *system* Python's user site-packages (`/usr/bin/python3 -m pip freeze
--user | grep -iE "isaacsim|torch|nvidia|cuda" | ...uninstall`), since
stale installs from unrelated earlier work on a shared lab machine can
leak in and cause exactly this kind of confusion.

After this fix:
```bash
$PY -c "import isaacsim; from omni.isaac.kit import SimulationApp; print('Isaac Sim OK')"
# -> Isaac Sim OK
```

## Known dependency conflicts (noted, not acted on)

Pip flags these during install. None have caused an actual runtime
failure so far — same "watch for it, don't preemptively fix it" approach
used in Task 1:
- `omni-isaac-lab-tasks` wants `protobuf<5.0.0`, but something else
  (`onnx`) pulls in `protobuf 7.x`.
- `ml-dtypes` wants `numpy>=2.0.0`, but `isaacsim-core` forces
  `numpy<2.0.0`.
- `matplotlib`/`pyparsing` version mismatch (cosmetic).

If you ever see an error mentioning any of these package names directly,
this is where to start looking.

## Setup (condensed from what actually worked)

Lab machine: Ubuntu 22.04.5, NVIDIA RTX A4500 (~21.5 GB VRAM), 66 GB RAM.

```bash
# 1. Dedicated conda env
conda create -n vlnce-isaac python=3.10
conda activate vlnce-isaac
export PYTHONNOUSERSITE=1
PY=~/miniconda3/envs/vlnce-isaac/bin/python

# 2. Clone the two repos
mkdir -p ~/go2-sim && cd ~/go2-sim
git clone https://github.com/yang-zj1026/NaVILA-Bench.git
git clone https://github.com/yang-zj1026/IsaacLab.git

# 3. Isaac Sim 4.1.0 as pip packages (NOT the system's 5.1.0 install)
$PY -m pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cu121
$PY -m pip install isaacsim-rl==4.1.0 isaacsim-replicator==4.1.0 isaacsim-extscache-physics==4.1.0 isaacsim-extscache-kit-sdk==4.1.0 isaacsim-extscache-kit==4.1.0 isaacsim-app==4.1.0 --extra-index-url https://pypi.nvidia.com

# 4. Link NaVILA-Bench's extensions into IsaacLab
cd ~/go2-sim/IsaacLab/source/extensions
ln -s ~/go2-sim/NaVILA-Bench/isaaclab_exts/omni.isaac.vlnce .
ln -s ~/go2-sim/NaVILA-Bench/isaaclab_exts/omni.isaac.matterport .
cd ..

# 5. Install Isaac Lab + rsl_rl
./isaaclab.sh -i none
./isaaclab.sh -p -m pip install -e ~/go2-sim/NaVILA-Bench/scripts/rsl_rl

# 6. Download the Matterport3D scene data (~5 GB)
$PY -m pip install -U huggingface_hub
$PY -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='Zhaojing/VLN-CE-Isaac', repo_type='dataset', local_dir='/home/lab_user/go2-sim/NaVILA-Bench/isaaclab_exts/omni.isaac.vlnce/assets')
"
cd ~/go2-sim/NaVILA-Bench/isaaclab_exts/omni.isaac.vlnce/assets
unzip matterport_usd.zip && rm matterport_usd.zip
```

## Usage

```bash
cd ~/go2-sim/NaVILA-Bench
python scripts/demo_planner.py --task=go2_matterport_vision --history_length=9 --load_run=2024-09-25_23-22-02
```
Confirmed: opens an Isaac Sim window, Go2 walks around the house scene,
runs for several minutes, shuts down cleanly.

## Next steps

- [ ] Confirm whether this demo actually exercises simulated camera/depth
      sensor access, or just planner state — check `navila_eval.py` if not
- [ ] Try `legged-loco` only if a custom-trained walking policy is ever
      needed (not required for the current milestone)
- [ ] Task 3: integrate the actual NaVILA VLA model using this same
      environment (`navila_eval.py` / `run_benchmark.py` in NaVILA-Bench)
