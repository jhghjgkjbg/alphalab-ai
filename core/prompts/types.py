from dataclasses import dataclass, field
from typing import Mapping, Any
@dataclass(frozen=True, slots=True)
class Prompt:
    system_prompt: str; user_prompt: str; metadata: Mapping[str,Any]=field(default_factory=dict); language: str="en"; version: str="v1"; context_hash: str=""
