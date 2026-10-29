# NaVILA-Bench reference copies

These files are **not ours**. They are unmodified copies from
[yang-zj1026/NaVILA-Bench](https://github.com/yang-zj1026/NaVILA-Bench),
commit [`e9d2db1`](https://github.com/yang-zj1026/NaVILA-Bench/tree/e9d2db12ce5788c0f987d734c0094100b6bc0d3a),
kept here so the Task 3 documentation can point at the exact code we ran.
They are distributed under NaVILA-Bench's MIT license, included as
[`LICENSE`](LICENSE).

| Copy here | Original path in NaVILA-Bench |
|---|---|
| `scripts/navila_eval.py` | `scripts/navila_eval.py` |
| `scripts/vlm_server.py` | `scripts/vlm_server.py` |
| `scripts/run_benchmark.py` | `scripts/run_benchmark.py` |
| `utils/eval_utils.py` | `isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/utils/eval_utils.py` |
| `utils/measures.py` | `isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/utils/measures.py` |

They won't run from this folder: they import Isaac Lab and NaVILA-Bench's own
packages. To run them, use the NaVILA-Bench checkout on the lab machine
(`~/go2-sim/NaVILA-Bench/`), as described in the
[Task 3 README](../README.md).

Citation: Cheng et al., "NaVILA: Legged Robot Vision-Language-Action Model
for Navigation", RSS 2025, [arXiv:2412.04453](https://arxiv.org/abs/2412.04453).
