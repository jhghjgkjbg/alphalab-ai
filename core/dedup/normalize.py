import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source", "rss"}

def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith("utm_") and k.lower() not in _TRACKING]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))

def normalize_title(title: str) -> str:
    value = re.sub(r"\s+", " ", title.strip().lower())
    return re.sub(r"([!?.,:;])\1+", r"\1", value)
