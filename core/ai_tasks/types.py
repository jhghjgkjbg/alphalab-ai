from dataclasses import dataclass, field
from typing import Mapping, Any
@dataclass(frozen=True, slots=True)
class AITask:
    name: str; enabled: bool=True; priority: int=10; requires_ai: bool=True; metadata: Mapping[str,Any]=field(default_factory=dict)
