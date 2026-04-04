import os
import os.path
from unreversible.yarn import YarnProject, Decompiler
from unreversible.unity import init_assetstore
from unreversible.unity.loader import load_path, load_guid, ShallowLoader

os.chdir(os.path.dirname(__file__))

base = "/Volumes/exFAT Drive/Sikarugir/Steam.app/Contents/drive_c/Program Files (x86)/Steam/steamapps/common/UNBEATABLE/ExportedProject/ExportedProject"
assets_path = os.path.join(base, 'Assets')

init_assetstore(assets_path)

chapter_index = load_path(os.path.join(assets_path, 'Resources', 'ChapterIndex.asset'), ShallowLoader)

graphs = set()
yarn_project_guids_hashset = {}

for chapter in chapter_index.data['chapters']:
    for graph in map(lambda ptr: load_guid(ptr, ShallowLoader), chapter['graphs']):
        yarn_project_guids_hashset[load_guid(graph.data['_properties'], ShallowLoader).data['yarnProject']['guid']] = None

for project_guid in yarn_project_guids_hashset.keys():
    project_behaviour = load_guid(project_guid)
    project = YarnProject(project_behaviour.data)
    decompiler = Decompiler(project)

    with open(os.path.join('./decompiled/yarn/', (project.name or project_behaviour.name) + '.hldisasm.txt'), "w") as f:
        f.write(decompiler.disassemble_all())
        print('Disassembled', project_behaviour.name)
