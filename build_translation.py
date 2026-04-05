import os
import sys
import csv
import json
import yaml
import tempfile
import binascii
import subprocess

from unreversible.yarn.vm import Instruction, Opcode
from unreversible.yarn.yarn_spinner_pb2 import Program

base = sys.argv[1] if len(sys.argv) >= 2 else r"C:\Program Files (x86)\Steam\steamapps\common\UNBEATABLE\dumped"

def read_varint(fp):
    value = 0
    while True:
        byte = fp.read(1)[0]
        value <<= 7
        value |= byte & 0x7F
        if byte & 0x80 == 0:
            break

def encode_variant_json(value):
    match value:
        case float():
            return {'floatValue': value}
        case str():
            return {'stringValue': value}
        case bool():
            return {'boolValue': value}

def find_modified(path):
    with open(path, "r") as f:
        project = f.read()

    for node in project.split('\n===\n'):
        if not node.strip():
            continue
        front_matter, source = node.split('\n---\n')
        if source.endswith('\n==='):
            source = source[:-4]

        # NOTE: THIS IS NOT YAML!!!!! I REALLY NEED TO STOP TREATING THIS AS YAML OR THINGS WILL FALL APART
        metadata = yaml.safe_load(front_matter)
        if 'opaque' in metadata and metadata.pop('opaque'):
            continue

        original_checksum = metadata.pop('originalCrc32')

        if binascii.crc32(source.encode()).to_bytes(4).hex() != original_checksum:
            yield yaml.safe_dump(metadata).strip() + '\n---\n' + source

os.chdir(os.path.dirname(__file__))
with open(os.path.join(base, 'lines.json'), 'r') as f:
    original_lines = json.load(f)
    original_lines_backwards = dict(map(reversed, original_lines.items()))

added_lines = {}

os.makedirs('./Translation', exist_ok=True)
with tempfile.TemporaryDirectory() as tmpdir:
    for yarn_filename in os.listdir("./decompiled/yarn"):
        if not yarn_filename.endswith('.yarn'):
            continue

        source_to_compile = ''

        for node_source in find_modified(os.path.join("./decompiled/yarn", yarn_filename)):
            source_to_compile += node_source.strip() + '\n===\n'
        if not source_to_compile:
            continue

        project_json_name = yarn_filename[:-len('.yarn')] + '.yarnproject.json'

        with open(os.path.join(base, project_json_name), 'r') as f:
            project_json = json.load(f)

        tmp_source_file = os.path.join(tmpdir, 'source.yarn')
        lines_file = os.path.join(tmpdir, 'lines.csv')

        with open(tmp_source_file, "w") as f:
            f.write(source_to_compile)
        subprocess.run(['ysc', 'tag', tmp_source_file])
        subprocess.run(('ysc', 'tag', tmp_source_file))
        with open(tmp_source_file, "r") as f:
            tagged_source = f.read()
        tagged_source_lines = tagged_source.split('\n')
        subprocess.run(('ysc', 'compile', '-t', 'lines.csv', '-o', tmpdir, tmp_source_file))

        with open(lines_file, 'r') as f:
            reader = csv.reader(f)
            next(reader) # skip header line
            for line_id, text, _, _, line_number in reader:
                line_index = int(line_number) - 1
                replacement_line = tagged_source_lines[line_index].rstrip()
                original_tag = ' #' + line_id
                assert replacement_line.endswith(original_tag)
                replacement_line = replacement_line[:-len(original_tag)]

                if replacement_line in original_lines_backwards:
                    replacement_line += ' #' + original_lines_backwards[replacement_line]
                else:
                    new_line_id = 'line:unreversible-' + yarn_filename.replace(' ', '-') + '-L' + line_number
                    added_lines[new_line_id] = text
                    replacement_line += ' #' + new_line_id

                tagged_source_lines[line_index] = replacement_line

        with open(tmp_source_file, "w") as f:
            f.write('\n'.join(tagged_source_lines))

        subprocess.run(('ysc', 'compile', '-n', 'compiledStream.yarnc', '-o', tmpdir, tmp_source_file))

        with open(os.path.join(tmpdir, 'compiledStream.yarnc'), "rb") as f:
            program = Program()
            program.MergeFromString(f.read())

            for variable in program.initial_values:
                if variable not in project_json['initialValues']:
                    variant = program.initial_values[variable]
                    project_json['initialValues'][variable] = { 'boolValue': variant.bool_value } if variant.HasField("bool_value") else { 'floatValue': variant.float_value } if variant.HasField("float_value") else { 'stringValue': variant.string_value }
            for node_title in program.nodes:
                if node_title in project_json['nodes']:
                    raw_node = program.nodes[node_title]
                    node_json = project_json['nodes'][node_title]
                    node_json['instructions'] = []
                    for serialized_instruction in raw_node.instructions:
                        match (inst := Instruction.from_serialized(serialized_instruction)).opcode:
                            case Opcode.JUMP_TO:
                                node_json['instructions'].append({ 'operands': [ { 'stringValue': inst.operands[0] } ] })
                            case _:
                                node_json['instructions'].append({'opcode': inst.opcode.name} | ({'operands': list(map(encode_variant_json, inst.operands))} if inst.operands else {}))
                    node_json['labels'] = dict(raw_node.labels)
                    project_json['nodes'][node_title] = node_json

        with open(os.path.join('./Translation/', project_json_name), "w") as f:
            json.dump(project_json, f)

lines = original_lines | added_lines

with open('./Translation/lines.json', "w") as f:
    json.dump(lines, f)
