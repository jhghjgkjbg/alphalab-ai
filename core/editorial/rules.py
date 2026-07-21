from dataclasses import replace
from typing import Protocol
from urllib.parse import urlsplit,urlunsplit
from core.publication.models import Publication
class Rule(Protocol):
    def apply(self, publication: Publication) -> Publication: ...
def _text(v):
    return " ".join(str(v or "").replace("\r\n","\n").replace("\r","\n").split())
class NormalizeWhitespaceRule:
    def apply(self,p): return replace(p, title=_text(p.title), summary=_text(p.summary), why_this_matters=_text(p.why_this_matters), target_audience=_text(p.target_audience))
class NormalizeUrlRule:
    def apply(self,p):
        x=urlsplit(p.canonical_url or p.url); c=urlunsplit((x.scheme.lower(),x.netloc.lower(),x.path.rstrip("/"),x.query,"")) if x.scheme else p.canonical_url
        return replace(p,canonical_url=c)
class CleanFieldsRule:
    def apply(self,p): return replace(p,category=_text(p.category),editorial_verdict=_text(p.editorial_verdict))
