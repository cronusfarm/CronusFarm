#!/usr/bin/env python3
import sys
from pathlib import Path

p = Path(sys.argv[1]).expanduser()
import onnx

m = onnx.load(str(p))
for i in m.graph.input:
    sh = [d.dim_value or d.dim_param for d in i.type.tensor_type.shape.dim]
    print("in", i.name, sh)
for o in m.graph.output:
    sh = [d.dim_value or d.dim_param for d in o.type.tensor_type.shape.dim]
    print("out", o.name, sh)
meta = {p.key: p.value for p in m.metadata_props}
if meta:
    print("meta", meta)
