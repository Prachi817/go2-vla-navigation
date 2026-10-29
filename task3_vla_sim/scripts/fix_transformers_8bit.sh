#!/bin/bash
# Fix 8-bit loading in the `navila` env's patched Transformers 4.37.2.
#
# NaVILA's setup copies its own modeling_utils.py over Transformers 4.37.2
# (llava/train/transformers_replace/). That copy was written against an older
# Transformers and calls:
#     set_module_quantized_tensor_to_device(..., fp16_statistics=...)
# but in 4.37.2 the argument is called `quantized_stats` (a dict, {"SCB": ...}).
# fp16 never reaches this code path, so only 8-bit loading crashes:
#     TypeError: set_module_quantized_tensor_to_device() got an unexpected
#     keyword argument 'fp16_statistics'
#
# Safe for fp16. Keeps a backup at modeling_utils.py.bak.

set -e
F=~/miniconda3/envs/navila/lib/python3.10/site-packages/transformers/modeling_utils.py
cp "$F" "$F.bak"
sed -i 's/value=param, fp16_statistics=fp16_statistics/value=param, quantized_stats=({"SCB": fp16_statistics} if fp16_statistics is not None else None)/' "$F"

# Expect exactly one matching line (~line 781).
grep -n 'quantized_stats=({"SCB"' "$F"
