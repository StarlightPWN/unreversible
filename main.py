import os
import os.path

from unreversible.yarn import YarnProject, Decompiler
from unreversible.yarn.yarnproject import Localization
import json

import sys
import yaml
import binascii

def decompile_for_editing(decompiler: Decompiler) -> str:
    decompiled_nodes = []

    for node in (item[1] for item in sorted(decompiler.project.nodes.items())):
        try:
            source = decompiler.decompile_node(node, False) or "<<stop>>"
            decompiled_nodes.append(yaml.safe_dump({"title": node.name, "originalCrc32": binascii.crc32(source.encode()).to_bytes(4).hex()}).strip() + "\n---\n" + source)
        except BaseException as e:
            source = f"<<FAILED TO DECOMPILE NODE: {e!r}>>"
            decompiled_nodes.append(yaml.safe_dump({"title": node.name, "originalCrc32": binascii.crc32(source.encode()).to_bytes(4).hex(), "opaque": True}).strip() + "\n---\n" + source)

    return "\n===\n".join(decompiled_nodes) + "\n==="

os.chdir(os.path.dirname(__file__))

base = sys.argv[1] if len(sys.argv) >= 2 else r"C:\Program Files (x86)\Steam\steamapps\common\UNBEATABLE\dumped"

with open(os.path.join(base, "lines.json"), "r") as f:
    lines = json.load(f)
localization = Localization("und", lines, {})

for path in os.listdir(base):
    if path.endswith(".yarnproject.json") and not path.startswith('.'):
        with open(os.path.join(base, path), "r") as f:
            project = YarnProject(json.load(f), localization)
            project.name = os.path.basename(path)[:-len(".yarnproject.json")]
        decompiler = Decompiler(project)

        with open(os.path.join('./decompiled/yarn/', project.name + '.yarn'), "w") as f:
            f.write(decompile_for_editing(decompiler))
            print('Decompiled', project.name, '(for editing)')
