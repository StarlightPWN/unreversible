import os
import yaml
import functools
from .assets import MonoBehaviour, Script

cache = {}
# surely this won't cause any weird bugs
# (temporary variables that persist only for a root invocation of `yaml.load`)
hole = []
shallow = False

def rehydrate(mapping: dict) -> dict:
    if set(mapping.keys()) == {'fileID', 'guid', 'type'}:
        try:
            return load_guid(mapping['guid'])
        except BaseException as _:
            cache[mapping['guid']] = mapping
            return cache[mapping['guid']]

    for key in mapping:
        match mapping[key]:
            case {"fileID": str(), "guid": guid, "type": int()}:
                try:
                    mapping[key] = load_guid(guid)
                except BaseException as e:
                    print('Error loading from GUID:', e)
            case list():
                for i, obj in enumerate(mapping[key]):
                    if isinstance(obj, dict):
                        mapping[key][i] = rehydrate(obj)
            case dict():
                mapping[key] = rehydrate(mapping[key])
    return mapping

type LoadableAsset = MonoBehaviour | Script

def unity_constructor(deep: bool, loader: yaml.BaseLoader, node: yaml.MappingNode) -> LoadableAsset:
    values = loader.construct_mapping(node, deep=True)
    if deep:
        if {"MonoBehaviour"} == set(values.keys()):
            cache[hole[-1]] = MonoBehaviour(None, None, None, None, {})
            rehydrate(values)
        else:
            cache[hole[-1]] = values
            rehydrate(values)

    match values:
        case {"MonoBehaviour": {"m_Script": script, "m_GameObject": gameobject, "m_Name": name, **data}}:
            match script:
                case { "guid": script_guid }:
                    script = None
                case Script() as script:
                    script_guid = None

            match gameobject:
                case { "guid": gameobject_guid }:
                    pass
                case { "fileID": 0 }:
                    gameobject_guid = None

            result = cache[hole.pop()] if deep else MonoBehaviour(None, None, None, None, None)
            result.name = name
            result.script_guid = script_guid
            result.script = script
            result.gameobject_guid = gameobject_guid
            result.data = data
            return result

def meta_constructor(loader: yaml.BaseLoader, node: yaml.MappingNode) -> dict:
    return loader.construct_mapping(node, deep=True)

yaml.add_constructor("tag:unity3d.com,2011:114", functools.partial(unity_constructor, True))
yaml.add_constructor("tag:unity3d.com,2011:21", meta_constructor)

def unknown(loader: yaml.BaseLoader, _suffix: str, node: yaml.Node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)

class ShallowLoader(yaml.SafeLoader):
    pass

ShallowLoader.add_multi_constructor("!", unknown)
ShallowLoader.add_multi_constructor("tag:", unknown)
ShallowLoader.add_constructor("tag:unity3d.com,2011:114", functools.partial(unity_constructor, False))

index_files = {}

def read_file(path: str, binary=False) -> str | bytes:
    with open(path, 'r' + ('b' if binary else '')) as f:
        return f.read()

def load_guid(guid: dict | str, loader: yaml.BaseLoader = yaml.FullLoader) -> LoadableAsset:
    global hole
    if isinstance(guid, dict):
        guid = guid['guid']
    if guid in cache:
        return cache[guid]

    match index_files[guid]:
        case {"type": "Script", "name": name}:
            assembly, *cls_parts = name.split('.')
            result = Script(assembly, '.'.join(cls_parts))
            cache[guid] = result
            return result
        case str(path):
            hole.append(guid)
            result = yaml.load(read_file(path), loader)
            return result

def load_path(path: str, loader: yaml.BaseLoader = yaml.FullLoader, meta_loader: yaml.BaseLoader = yaml.FullLoader) -> LoadableAsset:
    meta = yaml.load(read_file(path + ".meta"), meta_loader)
    return load_guid(meta['guid'], loader)

def init_assetstore(assets_path: str, index_path = './index.generated.py'):
    global index_files
    if os.path.isfile(index_path):
        with open(index_path, 'r') as f:
            import ast
            index_files = ast.literal_eval(f.read())

    if not index_files:
        print('Generating index...')

        for root, _dirs, files in os.walk(assets_path, topdown=True):
            for file in files:
                if file.startswith('._'): # macOS external filesystem AppleDouble metadata file
                    continue

                path = os.path.join(root, file)
                if file.endswith('.meta'):
                    try:
                        meta = yaml.load(read_file(path), yaml.FullLoader)
                        guid = meta['guid']
                        asset_path = os.path.join(root, file[:-5])

                        if os.path.isfile(asset_path) and asset_path.endswith('.asset'):
                            index_files[guid] = asset_path
                        elif asset_path.endswith('.cs'):
                            index_files[guid] = {'type': 'Script', 'name': os.path.relpath(path[:-3-5], start=os.path.join(assets_path, 'Scripts')).replace('/', '.')}
                    except BaseException as e:
                        print(f'Failure loading {path}:', e)

        with open(index_path, 'w') as f:
            f.write(repr(index_files))