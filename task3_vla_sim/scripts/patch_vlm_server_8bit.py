"""Create vlm_server_8bit.py: a copy of NaVILA-Bench's vlm_server.py that can
load NaVILA in 8-bit (bitsandbytes) via `--precision W8A16`.

The stock server only supports fp16 (W16A16), which needs ~17 GB idle /
~19.5 GB peak VRAM -- too much to share a 20 GB RTX A4500 with Isaac Sim.
8-bit brings that down to ~10.4 GB idle / ~12.9 GB peak.

The original vlm_server.py is left untouched. `--precision W16A16` on the new
file still behaves exactly like the original.

Run from NaVILA-Bench/scripts with the `navila` env's python:
    cd ~/go2-sim/NaVILA-Bench/scripts
    $PY /path/to/patch_vlm_server_8bit.py

Requires the companion Transformers fix (fix_transformers_8bit.sh), otherwise
8-bit loading crashes with:
    TypeError: set_module_quantized_tensor_to_device() got an unexpected
    keyword argument 'fp16_statistics'
"""

src = open('vlm_server.py').read()
edits = [
    # 1. Accept W8A16 as a valid precision (loads through the same method).
    ('''        if self.args.precision == "W16A16":
            self._load_checkpoint_w16a16()''',
     '''        if self.args.precision in ("W16A16", "W8A16"):
            self._load_checkpoint_w16a16()'''),
    # 2. Ask NaVILA's loader for 8-bit. torch_dtype must be passed explicitly:
    #    NaVILA's prepare_config_for_eval() does kwargs.pop("torch_dtype"),
    #    which only exists in kwargs on the fp16 path -> KeyError otherwise.
    ('''load_pretrained_model(args.model_path, model_name, None)''',
     '''load_pretrained_model(args.model_path, model_name, None, load_8bit=(self.args.precision == "W8A16"), torch_dtype=torch.float16)'''),
    # 3. An 8-bit model is already placed on the GPU by device_map="auto";
    #    calling .to() on it is unsupported, so only do it for fp16.
    ('''        self.model = self.model.to(self.args.device)''',
     '''        if self.args.precision == "W16A16":
            self.model = self.model.to(self.args.device)'''),
]
for old, new in edits:
    assert src.count(old) == 1, "not found: " + old
    src = src.replace(old, new)
open('vlm_server_8bit.py', 'w').write(src)
print('wrote vlm_server_8bit.py')
