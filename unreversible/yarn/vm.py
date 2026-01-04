from .yarn_spinner_pb2 import (
    Instruction as SerializedInstruction,
)

from enum import Enum
from dataclasses import dataclass


class Opcode(Enum):
    JUMP_TO = 0
    JUMP = 1
    RUN_LINE = 2
    RUN_COMMAND = 3
    ADD_OPTION = 4
    SHOW_OPTIONS = 5
    PUSH_STRING = 6
    PUSH_FLOAT = 7
    PUSH_BOOL = 8
    PUSH_NULL = 9
    JUMP_IF_FALSE = 10
    POP = 11
    CALL_FUNC = 12
    PUSH_VARIABLE = 13
    STORE_VARIABLE = 14
    STOP = 15
    RUN_NODE = 16


@dataclass
class Instruction:
    opcode: Opcode
    operands: list[str | bool | float]

    def from_serialized(serialized_instruction: SerializedInstruction):
        return Instruction(
            Opcode(serialized_instruction.opcode),
            list(
                map(
                    lambda operand: operand.string_value
                    if operand.HasField("string_value")
                    else operand.bool_value
                    if operand.HasField("bool_value")
                    else operand.float_value,
                    serialized_instruction.operands,
                )
            ),
        )

    def __repr__(self, localization=None):
        return f"{self.opcode.name}({', '.join(map(repr, self.operands))})"
