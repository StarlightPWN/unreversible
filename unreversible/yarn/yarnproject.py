from .yarn_spinner_pb2 import (
    Program,
    Node as SerializedNode,
)
from .vm import Instruction, Opcode
from typing import Any
from dataclasses import dataclass
import yaml


@dataclass
class YarnNode:
    name: str
    instructions: list[Instruction]
    labels: dict[str, int]
    tags: list[str]
    project: "YarnProject"

    def from_serialized(serialized_node: SerializedNode, project: "YarnProject"):
        return YarnNode(
            serialized_node.name,
            list(map(Instruction.from_serialized, serialized_node.instructions)),
            serialized_node.labels,
            serialized_node.tags,
            project,
        )

    def disassemble(self, use_base_locale = False):
        lines = []

        for i, instruction in enumerate(self.instructions):
            lines.append(instruction.disassemble(self.project.base_localization if use_base_locale else None))

        if len(lines) and lines[-1] == "<<stop>>":
            lines.pop()

        return (
            yaml.safe_dump({"title": self.name}).strip()
            + "\n---\n"
            + "\n".join(lines)
        )


@dataclass
class Localization:
    locale_code: str
    string_table: dict[str, str]
    asset_table: dict[str, Any]


class YarnProject:
    def __init__(self, data_or_nodes, localization = None):
        self.nodes = {}
        self.base_localization = None

        if isinstance(data_or_nodes, dict):
            if "compiledYarnProgram" in data_or_nodes:
                self._raw_program = Program()
                self._raw_program.ParseFromString(bytes.fromhex(data_or_nodes["compiledYarnProgram"]))
                self.name = self._raw_program.name

                for node_name in self._raw_program.nodes:
                    self.nodes[node_name] = YarnNode.from_serialized(
                        self._raw_program.nodes[node_name], self
                    )
                if "baseLocalization" in data_or_nodes and localization is None:
                    self.base_localization = Localization(
                        data_or_nodes["baseLocalization"].data["_LocaleCode"],
                        dict(
                            zip(
                                data_or_nodes["baseLocalization"].data["_stringTable"]["keys"],
                                data_or_nodes["baseLocalization"].data["_stringTable"]["values"],
                            )
                        ),
                        dict(
                            zip(
                                data_or_nodes["baseLocalization"].data["_assetTable"]["keys"],
                                data_or_nodes["baseLocalization"].data["_assetTable"]["values"],
                            )
                        ),
                    )
            else:
                if "nodes" in data_or_nodes:
                    data_or_nodes = data_or_nodes["nodes"]

                for _, node in data_or_nodes.items():
                    instructions = []
                    for instruction in node["instructions"]:
                        if 'opcode' not in instruction:
                            instruction['opcode'] = 'JUMP_TO'
                        instructions.append(Instruction(Opcode.__members__[instruction['opcode']], list(
                            map(
                                lambda operand: operand['stringValue']
                                if "stringValue" in operand
                                else operand['boolValue']
                                if "boolValue" in operand
                                else float(operand['floatValue']),
                                instruction['operands'] if 'operands' in instruction else (),
                            )
                        )))

                    self.nodes[node['name']] = YarnNode(
                        node['name'],
                        instructions,
                        node['labels'],
                        [],
                        self,
                    )
            self.base_localization = localization if localization else (self.base_localization or Localization("und", {}, {}))
