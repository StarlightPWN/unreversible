from enum import Enum
from dataclasses import dataclass

class IO(Enum):
    Input = 0
    Output = 1

@dataclass
class NodePort:
    direction: IO
    connection_count: int

@dataclass
class Node:
    x: float
    y: float
    folded: bool
    ports: dict[str, NodePort]

@dataclass
class NodeGraph:
    nodes: list[Node]