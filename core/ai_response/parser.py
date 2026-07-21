import json,re
from typing import Protocol
from .types import RawAIResponse, ParsedAIResponse
class ResponseParser(Protocol):
    def parse(self,response:RawAIResponse)->ParsedAIResponse: ...
class DefaultResponseParser:
    def parse(self,response):
        data=dict(response.raw_json) if isinstance(response.raw_json,dict) else {}
        if not data and response.raw_text:
            try:data=json.loads(response.raw_text)
            except Exception:
                m=re.search(r"```(?:json)?\s*(\{.*?\})\s*```",response.raw_text,re.S)
                if m:
                    try:data=json.loads(m.group(1))
                    except Exception:data={}
        def tup(k):
            v=data.get(k,()); return tuple(str(x) for x in v) if isinstance(v,(list,tuple)) else ((str(v),) if v else ())
        return ParsedAIResponse(tup("headline_suggestions"),str(data.get("short_summary", "")),str(data.get("long_summary", "")),tup("seo_keywords"),tup("hashtags"),tup("entities"),tup("topics"),str(data.get("category_guess", "")),str(data.get("language", "")),float(data.get("confidence",0) or 0),str(data.get("editor_notes", "")),str(data.get("translation", "")),str(data.get("translation_status", "")),str(data.get("en_title", "")),str(data.get("en_body", "")),str(data.get("ru_title", "")),str(data.get("ru_body", "")))
