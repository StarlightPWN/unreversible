from typing import Optional
from dataclasses import dataclass

@dataclass
class Script:
    assembly: str
    cls: str

@dataclass
class MonoBehaviour:
    name: str
    script_guid: Optional[str]
    script: Optional[Script]
    gameobject_guid: Optional[str]
    data: dict

@dataclass
class UnityMeta:
    guid: str