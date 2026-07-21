from datetime import datetime, UTC
from urllib.parse import urlsplit, urlunsplit
from .models import Publication, LanguageVariant

class PublicationBuilder:
    def build(self, item, language="en") -> Publication:
        payload = getattr(item, "payload", None) or (item if isinstance(item, dict) else {})
        def value(name, default=""):
            return payload.get(name, default) if isinstance(payload, dict) else getattr(item, name, default)
        article_id = str(getattr(item, "external_id", None) or value("article_id") or value("id") or value("url"))
        url = str(value("url"))
        parts=urlsplit(url); canonical=urlunsplit((parts.scheme.lower(),parts.netloc.lower(),parts.path.rstrip("/"),parts.query,"")) if parts.scheme else url
        title, summary = str(value("title")), str(value("summary")); variant=LanguageVariant(language,title,summary,summary,summary,tuple(value("keywords",()) or ()),canonical)
        variants={language:variant}; variants.setdefault("en",variant); variants.setdefault("ru",variant)
        return Publication(str(value("publication_id", article_id)), article_id, language, title, summary, url, canonical, str(getattr(item,"source",None) or value("source")), str(value("category")), str(value("published_at")), float(getattr(item,"final_score",value("score",0)) or 0), float(value("trend_bonus",0) or 0), float(value("editorial_score",0) or 0), str(value("editorial_verdict")), str(value("why_this_matters")), str(value("target_audience")), datetime.now(UTC).isoformat(), dict(payload) if isinstance(payload,dict) else {}, variants)
