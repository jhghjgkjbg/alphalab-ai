import hashlib

def _norm(value):
    return " ".join(str(value or "").strip().casefold().split())

def build_campaign_id(article_id, campaign="content_distribution"):
    return hashlib.sha256(f"article-distribution:v1:{_norm(article_id)}:{_norm(campaign)}".encode()).hexdigest()

def build_link_id(article_id, destination_id, campaign_id, content_variant):
    raw = "|".join((_norm(article_id), _norm(destination_id), _norm(campaign_id), _norm(content_variant)))
    return hashlib.sha256(raw.encode()).hexdigest()
