from ..yarn import YarnProject
from xnode import NodeGraph
from enum import Enum
from dataclasses import dataclass

class GraphEventType(Enum):
    String = 0
    Bool = 1
    Float = 2

@dataclass
class SceneEventDefinition:
    event_name: str
    event_type: GraphEventType
    is_persistent: bool

@dataclass
class StateSwitch:
    name: str
    default_state: int
    states: list[str]

@dataclass
class NarrativeGraph(NodeGraph):
    chapters: list[str]
    yarn_project: YarnProject
    cast_list: list[str]
    yarn_variable_names: list[str]
    nodes: list[str]
    scene_events: list[SceneEventDefinition]
    state_switches: list[StateSwitch]