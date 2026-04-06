from .vm import Instruction, Opcode

import yaml
import json
import functools

from enum import Enum
from typing import Literal
from dataclasses import dataclass

OPERATOR_FORMAT = {
    "String.EqualTo": "{} == {}",
    "String.NotEqualTo": "{} != {}",
    "String.Add": "{} + {}",
    "Bool.EqualTo": "{} == {}",
    "Bool.NotEqualTo": "{} == {}",
    "Bool.And": "{} && {}",
    "Bool.Or": "{} || {}",
    "Bool.Xor": "{} ^ {}",
    "Bool.Not": "!{}",
    "Number.EqualTo": "{} == {}",
    "Number.NotEqualTo": "{} != {}",
    "Number.Add": "{} + {}",
    "Number.Minus": "{} - {}",
    "Number.Divide": "{} / {}",
    "Number.Multiply": "{} * {}",
    "Number.Modulo": "{} % {}",
    "Number.UnaryMinus": "-{}",
    "Number.GreaterThan": "{} > {}",
    "Number.GreaterThanOrEqualTo": "{} >= {}",
    "Number.LessThan": "{} < {}",
    "Number.LessThanOrEqualTo": "{} <= {}",
}

HIGHERLEVEL_INCOMPLETE = 1 << 8
LOWERLEVEL_COMPLETE = {Opcode.STOP}
# lower-level opcodes that conditionally or unconditionally jump to another location in the same node
LOWERLEVEL_EXITABLE = {
    Opcode.JUMP_TO,
    Opcode.JUMP,
    Opcode.JUMP_IF_FALSE,
}


class HigherLevelOpcode(Enum):
    # "complete" opcodes, standalone
    CALL_ACTION_ADV = 0
    RUN_NODE_ADV = 1
    STORE_VARIABLE_ADV = 2
    ADD_OPTION_ADV = 3
    # RUN_COMMAND, RUN_LINE and STOP can be preserved
    LOWER_LEVEL_COMPLETE_REPR = 4
    # placeholder for spacing (so two choice blocks don't get merged by accident)
    SPACER = 6
    IF = 7
    RUN_LINE_ADV = 8
    RUN_COMMAND_ADV = 9

    # "incomplete"/expression opcodes, can't stand alone
    # each one pushes one value without popping
    CALL_FUNC_ADV = 1 | HIGHERLEVEL_INCOMPLETE
    PUSH_REPR = 2 | HIGHERLEVEL_INCOMPLETE
    # INVARIANT: pushes one element onto the stack, should be followed by a POP (assume all choices jump to a POP)
    JUMP_OPTIONS = 3 | HIGHERLEVEL_INCOMPLETE
    IF_CLAUSE = 4 | HIGHERLEVEL_INCOMPLETE
    # PUSH_* opcodes are not possible
    LOWER_LEVEL_OPCODE = 0xFF | HIGHERLEVEL_INCOMPLETE


@dataclass
class HigherLevelInstruction:
    opcode: HigherLevelOpcode


@dataclass
class HigherLevelInstructionCallDelegateAdvanced(HigherLevelInstruction):
    opcode: (
        Literal[HigherLevelOpcode.CALL_FUNC_ADV]
        | Literal[HigherLevelOpcode.CALL_ACTION_ADV]
    )
    function: str
    arguments: list[str]


@dataclass
class HigherLevelInstructionRunNodeAdvanced(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.RUN_NODE_ADV]
    node: str


@dataclass
class HigherLevelInstructionRunLineAdvanced(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.RUN_LINE_ADV]
    line: str
    expressions: list[str]


@dataclass
class HigherLevelInstructionRunCommandAdvanced(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.RUN_COMMAND_ADV]
    command: str
    expressions: list[str]

@dataclass
class HigherLevelInstructionStoreVariableAdvanced(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.STORE_VARIABLE_ADV]
    variable: str
    # the string representation of the value
    value: str


@dataclass
class HigherLevelInstructionAddOptionAdvanced(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.ADD_OPTION_ADV]
    line: str
    destination: str  # basic block name
    # there's another field here but it's not useful as far as I can tell
    _unknown: int
    condition: str | None


@dataclass
class HigherLevelInstructionLowerLevelCompleteRepr(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.LOWER_LEVEL_COMPLETE_REPR]
    representation: str


@dataclass
class HigherLevelInstructionSpacer(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.SPACER]


@dataclass
class HigherLevelInstructionIf(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.IF]
    # else clause if existing will be on the last IfClause
    clauses: list["HigherLevelInstructionIfClause"]


# this one kinda just stores any expression as a string, we want these as the final output for lower level opcodes to consume
@dataclass
class HigherLevelInstructionPushRepr(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.PUSH_REPR]
    representation: str
    # variables and strings can't be distinguished, we don't need that anyways
    value: float | bool | None | str


# simple pair of SHOW_OPTIONS and JUMP, neither take operands so this is easy to scan for
# we don't even support orphaned SHOW_OPTIONS opcodes
# this doesn't really do much beyond being a jump
@dataclass
class HigherLevelInstructionJumpOptions(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.JUMP_OPTIONS]


@dataclass
class HigherLevelInstructionIfClause(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.IF_CLAUSE]
    condition: str
    destination: str
    end: str
    else_: str


@dataclass
class HigherLevelInstructionLowerLevelOpcode(HigherLevelInstruction):
    opcode: Literal[HigherLevelOpcode.LOWER_LEVEL_OPCODE]
    inst_ll: "Instruction"


class NotYetLiftedError(ValueError):
    def __init__(self, message, node, errors=[]):
        self.node = node
        self.errors = errors

        super(NotYetLiftedError, self).__init__(message)

class CannotLiftInstructionError(ValueError):
    def __init__(self, message, node: "LiftedNode", instruction_index: int):
        self.node = node
        self.instruction = self.node.instructions[instruction_index]

        super(CannotLiftInstructionError, self).__init__(message)


@dataclass
class LiftedNode:
    # INCLUSIVE ranges: (0, 0) is the first instruction and (0, 1) is the first two
    basic_blocks: dict[str, tuple[int, int]]
    instructions: list[HigherLevelInstruction]

    def remove(self, start: int, end: int):
        return self.mutate(start, end, ())

    # folds a range of instructions into a replacement instruction
    def fold(self, start: int, end: int, new_inst: HigherLevelInstruction):
        return self.mutate(start, end, (new_inst,))
        """
        self.instructions[start : end + 1] = (new_inst,)

        if start != end:
            length = end - start

            for basic_block_name in self.basic_blocks:
                self.basic_blocks[basic_block_name] = tuple(
                    bound - length
                    if bound > start
                    else start
                    if bound >= start and bound <= end
                    else bound
                    for bound in self.basic_blocks[basic_block_name]
                )
        """

    # replaces a range of instructions with a MONOLITHIC list of instructions (can be empty)
    def mutate(self, start: int, end: int, new_insts: list[HigherLevelInstruction] | tuple[HigherLevelInstruction]):
        # this correctly creates an empty basic block of the form (i, i - 1) if an entire block is removed
        new_start = start
        new_end = start + len(new_insts) - 1
        difference = new_end - end

        self.instructions[start : end + 1] = new_insts

        for basic_block_name in self.basic_blocks:
            bound_start, bound_end = self.basic_blocks[basic_block_name]
            is_empty_block = bound_end == bound_start - 1

            if start <= bound_start <= end:
                bound_start = new_start
            elif bound_start > end:
                bound_start += difference

            if start <= bound_end <= end:
                bound_end = new_end
            elif bound_end > end:
                bound_end += difference

            if is_empty_block:
                bound_end = bound_start - 1

            if bound_end - bound_start < -1:
                raise ValueError(f"Trying to assign invalid bounds {(bound_start, bound_end)} (original bounds {self.basic_blocks[basic_block_name]}), mutating section {(start, end)} to length {len(new_insts)}")

            self.basic_blocks[basic_block_name] = (bound_start, bound_end)

    def block(self, block_name: str):
        return self.instructions[self.basic_blocks[block_name][0]:self.basic_blocks[block_name][1] + 1]

    def block_needs_lifting(self, block_name: str = 'start'):
        return self.need_lifting(self.instructions[self.basic_blocks[block_name][0]:self.basic_blocks[block_name][1] + 1])

    # needs to be updated if ever an instruction type has a dependency on other blocks
    def need_lifting(self, instructions: list[HigherLevelInstruction]):
        for instruction in instructions:
            match instruction:
                case HigherLevelInstructionAddOptionAdvanced(_, _, destination):
                    if self.block_needs_lifting(destination):
                        return True
                case HigherLevelInstructionIf(_, clauses):
                    for clause in clauses:
                        if self.need_lifting(self.block(clause.destination)):
                            return True

            if instruction.opcode.value & HIGHERLEVEL_INCOMPLETE:
                return True

        return False

def indent(text: str, level: int):
    return '\n'.join(map(lambda line: ' ' * (4 * level) + line, text.split('\n')))

class Decompiler:
    def __init__(self, project):
        self.project = project
        self.lifted_nodes = {}

    # for debugging purposes only
    def disassemble_all(self):
        return (
            "\n===\n".join(self.disassemble_node(node, True, True) for node in (item[1] for item in sorted(self.project.nodes.items())))
            + "\n==="
        )

    def decompile_all(self):
        return (
            "\n===\n".join(map(self.decompile_node, (item[1] for item in sorted(self.project.nodes.items()))))
            + "\n==="
        )

    def decompile_node(self, node, include_front_matter=True):
        node_repr = self.repr_block(self.lift_node(node), "start")
        if node_repr.endswith("\n<<stop>>"):
            node_repr = node_repr[:-9]
        node_repr = node_repr.strip()
        if include_front_matter:
            return (
                yaml.safe_dump({"title": node.name, **node.headers}).strip()
                + "\n---\n"
                + node_repr
            )

        return node_repr

    # for debugging purposes only
    def disassemble_node(self, node, include_front_matter=True, full_node=False):
        errors = []
        try:
            lifted_node = self.lift_node(node)
        except NotYetLiftedError as e:
            print('failed to lift node:', node.name)
            lifted_node = e.node
            errors = e.errors

        node_disasm = self.disassemble_lifted_node(lifted_node) if full_node else self.disassemble_block(lifted_node, "start")
        if not lifted_node.block_needs_lifting("start"):
            node_disasm = self.repr_block(lifted_node, "start")
        if node_disasm.endswith("\n<<stop>>"):
            node_disasm = node_disasm[:-9]
        node_disasm = node_disasm.strip()
        if include_front_matter:
            return (
                yaml.safe_dump({"title": node.name} | ({ "errors": list(map(str, errors)) } if errors else {})).strip()
                + "\n---\n"
                + node_disasm
            )

        return node_disasm

    def disassemble_inst(self, node: LiftedNode, instruction: HigherLevelInstruction):
        try_repr = self.higherlevel_repr(node, instruction)
        if try_repr is not None:
            return f"<<$-INCOMPLETE EXPRESSION {try_repr}>>" if instruction.opcode.value & HIGHERLEVEL_INCOMPLETE else try_repr
        else:
            fields = {
                x: instruction.__dict__[x]
                for x in instruction.__dict__
                if x != "opcode"
            }
            operands = ', '.join(map(lambda pair: (pair[0] + "=" if len(fields) > 1 else "") + repr(pair[1]), fields.items()))
            return f"<<$-{instruction.opcode.name}({operands})>>"

    # for debugging purposes only
    def disassemble_lifted_node(self, node: LiftedNode):
        lines = []
        leaders = list(map(lambda block: block[0], node.basic_blocks.values()))
        trailers = list(map(lambda block: block[1], node.basic_blocks.values()))
        block_names = list(node.basic_blocks.keys())

        for i, instruction in enumerate(node.instructions):
            if i in leaders:
                for j, leader in enumerate(leaders):
                    if leader == i:
                        complement = ''
                        if node.block_needs_lifting(block_names[j]):
                            if node.need_lifting(node.block(block_names[j])[:-1]):
                                complement = '(UNLIFTED)'
                            else:
                                complement = '(UNLIFTED-1)'
                        lines.append(f"<<$-START BLOCK {block_names[j]}{' ' + complement if complement else ''}>>")

            lines.append(self.disassemble_inst(node, instruction))

            if i in trailers and i != 0:
                for j, trailer in enumerate(trailers):
                    if trailer == i:
                        lines.append(f"<<$-END BLOCK {block_names[j]}>>")

        return "\n".join(lines)

    def repr_block(self, node, block_name: str, indent_level=0):
        # basic blocks can reference each other so this should be fine
        # why would you need to call this early anyways
        if node.block_needs_lifting(block_name):
            raise NotYetLiftedError(
                "Refusing to represent basic block containing orphaned expressions!",
                node,
            )

        lines = []

        for inst in node.instructions[
            node.basic_blocks[block_name][0] : node.basic_blocks[block_name][1] + 1
        ]:
            lines.append(indent(self.higherlevel_repr(node, inst), indent_level))

        return "\n".join(lines)

    # for debugging purposes only
    def disassemble_block(self, node, block_name: str, indent_level=0):
        lines = []

        for inst in node.instructions[
            node.basic_blocks[block_name][0] : node.basic_blocks[block_name][1] + 1
        ]:
            lines.append(indent(self.disassemble_inst(node, inst), indent_level))

        return "\n".join(lines)

    def lift_node(self, node):
        if (
            not node.instructions
            or len(node.instructions) == 1
            and node.instructions[0].opcode == Opcode.STOP
        ):
            return LiftedNode({"start": (0, -1)}, [])

        last_inst_idx = len(node.instructions) - 1

        leaders = [0]
        block_names = ["start"]

        for label in node.labels:
            leaders.append(node.labels[label])
            block_names.append(label)
        for i, inst in enumerate(node.instructions[:-1]):
            if inst.opcode in LOWERLEVEL_EXITABLE and i + 1 not in leaders:
                leaders.append(i + 1)
                block_names.append(f"after_jump_{i}")

        block_starts = sorted(zip(leaders, block_names))
        block_starts += [(last_inst_idx + 1, "end")]

        basic_blocks = {}

        for i, start in enumerate(block_starts[:-1]):
            basic_blocks[start[1]] = (start[0], block_starts[i + 1][0] - 1)

        # INVARIANT: instruction indices are initially synced between node and lifted_node
        lifted_node = LiftedNode(
            basic_blocks,
            list(
                map(
                    lambda inst_ll: HigherLevelInstructionLowerLevelOpcode(
                        HigherLevelOpcode.LOWER_LEVEL_OPCODE, inst_ll
                    ),
                    node.instructions,
                )
            ),
        )

        # we technically should be skipping complete nodes, but that's a mess so we expect things to be pushed in sequence
        def peek_incomplete_representable(index, length):
            result = lifted_node.instructions[index - length : index]
            for node in result:
                if (
                    node.opcode.value & HIGHERLEVEL_INCOMPLETE == 0
                    or node.opcode == HigherLevelOpcode.LOWER_LEVEL_OPCODE
                    or node.opcode == HigherLevelOpcode.JUMP_OPTIONS
                ):
                    return None
            return result if len(result) == length else None

        def peek(index, length):
            result = lifted_node.instructions[index - length : index]
            return result if len(result) == length else None

        def peek_one_incomplete_representable(index):
            result = peek_incomplete_representable(index, 1)
            return result[0] if result else None

        def peek_one(index):
            result = peek(index, 1)
            return result[0] if result else None

        def is_basic_block_start(index: int):
            return any(map(lambda block: block[0] == index, lifted_node.basic_blocks))

        # look up the code listing until we hit a complete operation or the start of a basic block
        def consume_options(index) -> list[HigherLevelInstructionAddOptionAdvanced] | None:
            options = []

            while True:
                if index == 0:
                    break
                inst = peek_one(index) # this can't be None because 0 is always in leaders

                if inst.opcode == HigherLevelOpcode.ADD_OPTION_ADV:
                    options.append(inst)
                elif inst.opcode.value & HIGHERLEVEL_INCOMPLETE == 0:
                    break
                else:
                    return None
                if is_basic_block_start(index):
                    break
                index -= 1

            return options

        errors = []
        block_dependencies = ['start']

        while True:
            # nothing *bad* happens if you mutate the list while enumerate is still... enumerating
            # we just waste iterations, because enumerate has an internal index so it'll skip things
            # for this reason and to detect when we're not doing anything, we break whenever we mutate the list
            for i, inst in enumerate(lifted_node.instructions):
                match inst:
                    case HigherLevelInstructionLowerLevelOpcode(_, inst_ll):
                        if inst_ll.opcode in LOWERLEVEL_COMPLETE:
                            lifted_node.fold(
                                i,
                                i,
                                HigherLevelInstructionLowerLevelCompleteRepr(
                                    HigherLevelOpcode.LOWER_LEVEL_COMPLETE_REPR,
                                    self.higherlevel_repr(lifted_node, inst),
                                ),
                            )
                            break
                        else:
                            match inst_ll:
                                case (
                                    Instruction(Opcode.PUSH_STRING, [push_value])
                                    | Instruction(Opcode.PUSH_VARIABLE, [push_value])
                                    | Instruction(Opcode.PUSH_BOOL, [push_value])
                                    | Instruction(Opcode.PUSH_FLOAT, [push_value])
                                    | Instruction(Opcode.PUSH_NULL, push_value)
                                ):
                                    if push_value == []:
                                        push_value = None

                                    lifted_node.fold(
                                        i,
                                        i,
                                        HigherLevelInstructionPushRepr(
                                            HigherLevelOpcode.PUSH_REPR,
                                            self.higherlevel_repr(lifted_node, inst),
                                            push_value,
                                        ),
                                    )
                                    break
                                case Instruction(Opcode.CALL_FUNC, [function]):
                                    if arity_inst := peek_one(i):
                                        match arity_inst:
                                            case HigherLevelInstructionPushRepr(
                                                _, _, value
                                            ):
                                                if (
                                                    isinstance(value, float)
                                                    and value.is_integer()
                                                ):
                                                    arity = int(value)
                                                    arguments = (
                                                        peek_incomplete_representable(
                                                            i - 1, arity
                                                        )
                                                    )
                                                    if arguments:
                                                        lifted_node.fold(
                                                            i - 1 - arity,
                                                            i,
                                                            # there are no functions that don't return as far as I know
                                                            HigherLevelInstructionCallDelegateAdvanced(
                                                                HigherLevelOpcode.CALL_FUNC_ADV,
                                                                function,
                                                                list(
                                                                    map(
                                                                        functools.partial(
                                                                            self.higherlevel_repr,
                                                                            lifted_node,
                                                                        ),
                                                                        arguments,
                                                                    )
                                                                ),
                                                            ),
                                                        )
                                                        break
                                case Instruction(Opcode.JUMP, _):
                                    if show_options_inst := peek_one(i):
                                        match show_options_inst:
                                            case HigherLevelInstructionLowerLevelOpcode(
                                                _, Instruction(Opcode.SHOW_OPTIONS, _)
                                            ):
                                                lifted_node.fold(
                                                    i - 1,
                                                    i,
                                                    HigherLevelInstructionJumpOptions(
                                                        HigherLevelOpcode.JUMP_OPTIONS
                                                    ),
                                                )
                                                break
                                case Instruction(Opcode.RUN_NODE, _):
                                    if node_inst := peek_one_incomplete_representable(
                                        i
                                    ):
                                        match node_inst:
                                            case HigherLevelInstructionPushRepr(
                                                _, _, value
                                            ):
                                                lifted_node.fold(
                                                    i - 1,
                                                    i,
                                                    HigherLevelInstructionRunNodeAdvanced(
                                                        HigherLevelOpcode.RUN_NODE_ADV,
                                                        value,
                                                    ),
                                                )
                                                break
                                case Instruction(Opcode.POP, _):
                                    if previous_inst := peek_one(i):
                                        match previous_inst:
                                            case HigherLevelInstructionLowerLevelOpcode(
                                                _,
                                                Instruction(
                                                    Opcode.STORE_VARIABLE, [variable]
                                                ),
                                            ):
                                                if (
                                                    value
                                                    := peek_one_incomplete_representable(
                                                        i - 1
                                                    )
                                                ):
                                                    lifted_node.fold(
                                                        i - 2,
                                                        i,
                                                        HigherLevelInstructionStoreVariableAdvanced(
                                                            HigherLevelOpcode.STORE_VARIABLE_ADV,
                                                            variable,
                                                            self.higherlevel_repr(
                                                                lifted_node, value
                                                            ),
                                                        ),
                                                    )
                                                    break
                                case Instruction(
                                    Opcode.ADD_OPTION,
                                    [line, destination, _unknown, conditional],
                                ):
                                    if conditional:
                                        if (
                                            condition_inst
                                            := peek_one_incomplete_representable(i)
                                        ):
                                            lifted_node.fold(
                                                i - 1,
                                                i,
                                                HigherLevelInstructionAddOptionAdvanced(
                                                    HigherLevelOpcode.ADD_OPTION_ADV,
                                                    line,
                                                    destination,
                                                    _unknown,
                                                    self.higherlevel_repr(lifted_node, condition_inst),
                                                ),
                                            )
                                            block_dependencies.append(destination)
                                            break
                                    else:
                                        lifted_node.fold(
                                            i,
                                            i,
                                            HigherLevelInstructionAddOptionAdvanced(
                                                HigherLevelOpcode.ADD_OPTION_ADV,
                                                line,
                                                destination,
                                                _unknown,
                                                None,
                                            ),
                                        )
                                        block_dependencies.append(destination)
                                        break
                                # if statements
                                case Instruction(Opcode.JUMP_IF_FALSE, [else_]):
                                    if condition := peek_one_incomplete_representable(i):
                                        # one of the after jump blocks we add during block analysis
                                        # we can always specify invariants on these
                                        if len(blocks_after := list(filter(lambda block: block[1][0] == i + 1, lifted_node.basic_blocks.items()))) != 1:
                                            errors.append(CannotLiftInstructionError("JUMP_IF_FALSE should end a basic block", lifted_node, i))
                                        else:
                                            [destination, _], = blocks_after
                                            body = lifted_node.block(destination)

                                            if not lifted_node.need_lifting(body[:-1]):
                                                match final_inst := body[-1]:
                                                    case HigherLevelInstructionLowerLevelOpcode(_, Instruction(Opcode.JUMP_TO, [end])):
                                                        lifted_node.fold(i - 1, i, HigherLevelInstructionIfClause(HigherLevelOpcode.IF_CLAUSE, self.higherlevel_repr(lifted_node, condition), destination, end, else_))
                                                        break
                                                    case HigherLevelInstructionIfClause(_, _, _, nested_dest):
                                                        if not lifted_node.need_lifting(lifted_node.block(nested_dest)[:-1]):
                                                            nested_body = lifted_node.block(nested_dest)
                                                            match nested_body[-1]:
                                                                case HigherLevelInstructionLowerLevelOpcode(_, Instruction(Opcode.JUMP_TO, [end])):
                                                                    lifted_node.fold(i - 1, i, HigherLevelInstructionIfClause(HigherLevelOpcode.IF_CLAUSE, self.higherlevel_repr(lifted_node, condition), destination, end, else_))
                                                                    break
                                                                case _:
                                                                    errors.append(CannotLiftInstructionError(f"Expected JUMP_TO instruction at end of nested if body '{destination}' -> '{nested_dest}', found {final_inst}", lifted_node, i))
                                                    case _:
                                                        errors.append(CannotLiftInstructionError(f"Expected JUMP_TO instruction at end of if body '{destination}', found {final_inst}", lifted_node, i))
                                case Instruction(Opcode.RUN_LINE, [line, *operands]):
                                    arity = int(operands[0]) if operands else 0
                                    if (substitution_nodes := peek_incomplete_representable(i, arity)) is not None:
                                        lifted_node.fold(i - arity, i, HigherLevelInstructionRunLineAdvanced(HigherLevelOpcode.RUN_LINE_ADV, line, [self.higherlevel_repr(lifted_node, substitution_node) for substitution_node in substitution_nodes]))
                                        break
                                case Instruction(Opcode.RUN_COMMAND, [command, *operands]):
                                    arity = int(operands[0]) if operands else 0
                                    if (substitution_nodes := peek_incomplete_representable(i, arity)) is not None:
                                        lifted_node.fold(i - arity, i, HigherLevelInstructionRunCommandAdvanced(HigherLevelOpcode.RUN_COMMAND_ADV, command, [self.higherlevel_repr(lifted_node, substitution_node) for substitution_node in substitution_nodes]))
                                        break
                    case HigherLevelInstructionJumpOptions(_):
                        if options := consume_options(i):
                            give_up = False

                            if any(lifted_node.need_lifting(lifted_node.block(option.destination)[:-1]) for option in options):
                                give_up = True

                            choice_final_insts = [([None] + lifted_node.block(option.destination))[-1] for option in options]
                            destinations = set()

                            for j, choice_final_inst in enumerate(choice_final_insts):
                                match choice_final_inst:
                                    case HigherLevelInstructionLowerLevelOpcode(_, Instruction(Opcode.JUMP_TO, [destination])):
                                        destinations.add(destination)
                                    # contains (unlifted) nested options
                                    case HigherLevelInstructionJumpOptions(_) | HigherLevelInstructionLowerLevelOpcode(_, Instruction(Opcode.JUMP, [])):
                                        give_up = True
                                    # contains unlifted if statement
                                    case HigherLevelInstructionIfClause(_) | HigherLevelInstructionLowerLevelOpcode(_, Instruction(Opcode.JUMP_IF_FALSE, _)):
                                        give_up = True
                                    case _:
                                        errors.append(CannotLiftInstructionError(f"Expected JUMP_TO instruction at end of choice body '{options[j].destination}', found {choice_final_inst}", lifted_node, i))
                                        give_up = True

                            if len(destinations) != 1 and not give_up:
                                errors.append(CannotLiftInstructionError(f"Expected matching jump targets at end of choice body, found {destinations}", lifted_node, j))
                                give_up = True

                            if not give_up:
                                destination, = destinations
                                after_jump = lifted_node.block(destination)

                                if not after_jump or not (after_jump[0].opcode == HigherLevelOpcode.LOWER_LEVEL_OPCODE and after_jump[0].inst_ll.opcode == Opcode.POP):
                                    errors.append(CannotLiftInstructionError("After-choice block must begin with a POP instruction", lifted_node, lifted_node.basic_blocks[destination][0]))
                                    give_up = True

                                # we don't really need to get rid of the original block
                                # we also don't have a dependency on the original block, because the block gets integrated into 'start', which we're already checking for completeness
                                # skip the POP instruction
                                lifted_node.mutate(i, i, [HigherLevelInstructionSpacer(HigherLevelOpcode.SPACER)] + after_jump[1:])

                                for option in options:
                                    jump_index = lifted_node.basic_blocks[option.destination][-1]
                                    lifted_node.remove(jump_index, jump_index)

                                first_option_index = lifted_node.instructions.index(options[-1])
                                lifted_node.mutate(first_option_index, first_option_index, [HigherLevelInstructionSpacer(HigherLevelOpcode.SPACER), options[-1]])
                                break
                    case HigherLevelInstructionIfClause(_, _, _, end):
                        # we need to make sure this is actually the first IF_CLAUSE for this value of `end` (i.e. this if statement group)
                        branch_count = 0
                        for inst_ll in node.instructions:
                            if inst_ll.opcode == Opcode.JUMP_TO and inst_ll.operands[0] == end:
                                branch_count += 1

                        clauses = [inst]
                        give_up = False
                        current_clause = inst

                        end_body = lifted_node.block(end)

                        if lifted_node.block_needs_lifting(end) and not (not lifted_node.need_lifting(end_body[:-1]) and end_body[-1].opcode == HigherLevelOpcode.LOWER_LEVEL_OPCODE and end_body[-1].inst_ll.opcode == Opcode.JUMP_TO):
                            give_up = True

                        while current_clause:
                            else_body = lifted_node.block(current_clause.else_)
                            if lifted_node.need_lifting(else_body[1:-1]):
                                give_up = True
                                break
                            if current_clause.condition != '<dummy>':
                                match else_body[0]:
                                    case HigherLevelInstructionLowerLevelOpcode(_, Instruction(Opcode.POP, _)):
                                        pass
                                    case _:
                                        errors.append(CannotLiftInstructionError(f"Expected POP instruction at start of else body '{current_clause.else_}', found {else_body[0]}", lifted_node, i))
                                        give_up = True
                                if len(else_body) == 1:
                                    # if we have an else branch without a `JUMP_TO`, that's an extra branch we missed
                                    branch_count += 1
                                    if lifted_node.basic_blocks[current_clause.else_][0] + 1 != lifted_node.basic_blocks[current_clause.end][0]:
                                        errors.append(CannotLiftInstructionError(f"Invalid empty else body '{current_clause.else_}'", lifted_node, i))
                                        give_up = True
                                        break
                            match else_body[-1]:
                                case HigherLevelInstructionIfClause(_, _, _, next_clause_end):
                                    if next_clause_end == end:
                                        clauses.append(else_body[-1])
                                        current_clause = else_body[-1]
                                    else:
                                        # hacky way to avoid recursion
                                        current_clause = HigherLevelInstructionIfClause(HigherLevelOpcode.IF_CLAUSE, '<dummy>', '<dummy>', '<dummy>', else_body[-1].end)
                                # case HigherLevelInstructionLowerLevelOpcode(_, Instruction(Opcode.JUMP_TO, _)):
                                case _:
                                    current_clause = None
                        if not give_up:
                            # ensure all clauses are covered (+ an extra else)
                            if len(clauses) + 1 == branch_count:
                                lifted_node.mutate(i, i, [HigherLevelInstructionIf(HigherLevelOpcode.IF, clauses),] + lifted_node.block(end))
                                for clause in clauses:
                                    jump_to_instr = lifted_node.basic_blocks[clause.destination][1]
                                    lifted_node.remove(jump_to_instr, jump_to_instr)
                                    try:
                                        clause_line = lifted_node.instructions.index(clause)
                                        lifted_node.remove(clause_line, clause_line)
                                    except ValueError:
                                        pass
                                else_body = lifted_node.block(clauses[-1].else_)
                                if else_body[-1].opcode.value & HIGHERLEVEL_INCOMPLETE:
                                    else_trailer = lifted_node.basic_blocks[clauses[-1].else_][1]
                                    lifted_node.remove(else_trailer, else_trailer)
                                if else_body[0].opcode.value & HIGHERLEVEL_INCOMPLETE:
                                    else_header = lifted_node.basic_blocks[clauses[-1].else_][0]
                                    lifted_node.remove(else_header, else_header)
                                break # we mutated the length of the node
                pass
            else:
                if lifted_node.block_needs_lifting():
                    raise NotYetLiftedError(
                        "Failed to lift unsupported node", lifted_node, errors
                    )
                else:
                    break

        return lifted_node

    # can be overridden
    def localize(self, line):
        return self.project.base_localization.string_table.get(line, line)

    # includes both incomplete and complete nodes, not responsible for determining if something is complete or not
    def higherlevel_repr(self, node: LiftedNode, inst: HigherLevelInstruction):
        match inst:
            case HigherLevelInstructionSpacer(_):
                return ""
            case HigherLevelInstructionPushRepr(_, representation):
                return representation
            case HigherLevelInstructionLowerLevelCompleteRepr(_, representation):
                return representation
            case HigherLevelInstructionCallDelegateAdvanced(_, function, operands):
                if (
                    function in OPERATOR_FORMAT
                    and inst.opcode == HigherLevelOpcode.CALL_FUNC_ADV
                ):
                    return OPERATOR_FORMAT[function].format(*operands)
                else:
                    return f"{function}({', '.join(operands)})"
            case HigherLevelInstructionRunNodeAdvanced(_, node):
                return f"<<jump {node}>>"
            case HigherLevelInstructionStoreVariableAdvanced(_, variable, value):
                return f"<<set {variable} = {value}>>"
            case HigherLevelInstructionAddOptionAdvanced(_, line, destination, _, condition):
                # return (f"-> {self.localize(line)}{' <<' + condition + '>>' if condition else ''}\n" + self.repr_block(node, destination, 1)).rstrip()
                # TODO: DEBUGGING PURPOSES ONLY (use of `disassemble_block`)
                return (f"-> {self.localize(line)}{' <<if ' + condition + '>>' if condition else ''}\n" + self.disassemble_block(node, destination, 1)).rstrip()
            case HigherLevelInstructionIf(_, clauses):
                clauses_repr = []
                for i, clause in enumerate(clauses):
                    command = 'if' if i == 0 else 'elseif'
                    # TODO: DEBUGGING PURPOSES ONLY (use of `disassemble_block`)
                    clauses_repr.append((f'<<{command} {clause.condition}>>\n' + self.disassemble_block(node, clause.destination, 1)).rstrip())
                if len(node.block(clauses[-1].else_)) > 0:
                    try:
                        self.repr_block(node, clauses[-1].else_, 1)
                    except BaseException:
                        print(self.disassemble_block(node, clauses[-1].else_, 1))
                    finally:
                        clauses_repr.append(('<<else>>\n' + self.disassemble_block(node, clauses[-1].else_, 1)).rstrip())
                clauses_repr.append('<<endif>>')
                return '\n'.join(clauses_repr)
            case HigherLevelInstructionRunLineAdvanced(_, line, substitutions):
                translated_line = self.localize(line)
                for i, substitution in enumerate(substitutions):
                    translated_line = translated_line.replace(f"{{{i}}}", f"{{{substitution}}}")
                return translated_line
            case HigherLevelInstructionRunCommandAdvanced(_, command, substitutions):
                for i, substitution in enumerate(substitutions):
                    command = command.replace(f"{{{i}}}", f"{{{substitution}}}")
                return f"<<{command}>>"
            case HigherLevelInstructionLowerLevelOpcode(_, inst_ll):
                match inst_ll:
                    case Instruction(Opcode.STOP):
                        return "<<stop>>"

                    case Instruction(Opcode.PUSH_STRING, [value]):
                        return json.dumps(value)
                    case Instruction(Opcode.PUSH_BOOL, [value]):
                        return repr(value).lower()
                    case Instruction(Opcode.PUSH_FLOAT, [value]):
                        return repr(int(value)) if value.is_integer() else repr(value)
                    case Instruction(Opcode.PUSH_VARIABLE, [value]):
                        return value
                    # not sure if this is used
                    # > Starting with Yarn Spinner 2.0, variables are never `null`. All variables are required to have a value.
                    # https://docs.yarnspinner.dev/2.0/getting-started/writing-in-yarn/logic-and-variables
                    case Instruction(Opcode.PUSH_NULL, []):
                        return "null"
