from .yarn_spinner_pb2 import (
    Program,
    Node as SerializedNode,
)
from .vm import Instruction
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
    def __init__(self, data):
        self._raw_program = Program()
        self._raw_program.ParseFromString(bytes.fromhex(data["compiledYarnProgram"]))
        self.name = self._raw_program.name
        self.nodes = {}

        # TODO: document that this relies on Unity asset logic, or refactor such that it doesn't (so we can keep Protobuf here)
        self.base_localization = Localization(
            data["baseLocalization"].data["_LocaleCode"],
            dict(
                zip(
                    data["baseLocalization"].data["_stringTable"]["keys"],
                    data["baseLocalization"].data["_stringTable"]["values"],
                )
            ),
            dict(
                zip(
                    data["baseLocalization"].data["_assetTable"]["keys"],
                    data["baseLocalization"].data["_assetTable"]["values"],
                )
            ),
        )

        for node_name in self._raw_program.nodes:
            self.nodes[node_name] = YarnNode.from_serialized(
                self._raw_program.nodes[node_name], self
            )
