import os
import os.path

from unreversible.yarn import YarnProject, Decompiler
from unreversible.yarn.yarnproject import Localization
import json

import yaml
import binascii

from util import get_mod_export_folder, get_working_directory

def decompile_for_editing(decompiler: Decompiler) -> str:
    decompiled_nodes = []

    for node in decompiler.project.nodes.values():
        try:
            source = decompiler.decompile_node(node, False) or "<<stop>>"
            decompiled_nodes.append(yaml.safe_dump({"title": node.name, "originalCrc32": binascii.crc32(source.encode()).to_bytes(4).hex()}).strip() + "\n---\n" + source)
        except BaseException as e:
            source = f"<<FAILED TO DECOMPILE NODE: {e!r}>>"
            decompiled_nodes.append(yaml.safe_dump({"title": node.name, "originalCrc32": binascii.crc32(source.encode()).to_bytes(4).hex(), "opaque": True}).strip() + "\n---\n" + source)

    return "\n===\n".join(decompiled_nodes) + "\n==="

base = get_mod_export_folder()

with open(os.path.join(base, "lines.json"), "r", encoding="utf-8") as f:
    lines = json.load(f)
localization = Localization("und", lines, {})

os.chdir(get_working_directory())
os.makedirs('./decompiled/yarn', exist_ok=True)

print("Decompiling to", os.path.join(os.path.abspath(os.curdir), 'decompiled/yarn'))

for path in os.listdir(base):
    if path.endswith(".yarnproject.json") and not path.startswith('.'):
        with open(os.path.join(base, path), "r", encoding="utf-8") as f:
            project = YarnProject(json.load(f), localization)
            project.name = os.path.basename(path)[:-len(".yarnproject.json")]
        decompiler = Decompiler(project)

        with open(os.path.join('./decompiled/yarn/', project.name + '.yarn'), "w", encoding="utf-8") as f:
            f.write(decompile_for_editing(decompiler))
            print('Decompiled', project.name, '(for editing)')
