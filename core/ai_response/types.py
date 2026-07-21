from dataclasses import dataclass, field
from typing import Mapping, Any
@dataclass(frozen=True, slots=True)
class RawAIResponse:
    provider:str=""; model:str=""; raw_text:str=""; raw_json:Mapping[str,Any]=field(default_factory=dict); finish_reason:str=""; input_tokens:int=0; output_tokens:int=0; response_id:str=""; created_at:str=""
@dataclass(frozen=True, slots=True)
class ParsedAIResponse:
    headline_suggestions:tuple[str,...]=(); short_summary:str=""; long_summary:str=""; seo_keywords:tuple[str,...]=(); hashtags:tuple[str,...]=(); entities:tuple[str,...]=(); topics:tuple[str,...]=(); category_guess:str=""; language:str=""; confidence:float=0.; editor_notes:str=""; translation:str=""; translation_status:str=""; en_title:str=""; en_body:str=""; ru_title:str=""; ru_body:str=""
