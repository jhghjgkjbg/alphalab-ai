from types import SimpleNamespace
import asyncio
import re
from urllib.parse import urlparse

PUBLISH_POST = "mutation ($input: PublishPostInput!) { publishPost(input: $input) { post { id slug url } } }"
CREATE_DRAFT = "mutation ($input: CreateDraftInput!) { createDraft(input: $input) { draft { id title } } }"

def _safe_graphql_code(value):
    if not isinstance(value, str) or not value.strip():
        return "none"
    value = re.sub(r"[^A-Za-z0-9_.-]", "_", value.strip())
    return value[:40] or "none"

def _graphql_path(error):
    path = error.get("path") if isinstance(error, dict) else None
    if not isinstance(path, (list, tuple)):
        return "none"
    parts = [str(part) for part in path if isinstance(part, (str, int))]
    return ".".join(parts)[:120] or "none"

def _graphql_category(message):
    text = message.lower() if isinstance(message, str) else ""
    patterns = (
        ("authentication", ("authentication", "unauthenticated", "invalid token", "token expired")),
        ("authorization", ("authorization", "forbidden", "not authorized", "permission")),
        ("publication_not_found", ("publication", "not found")),
        ("invalid_input", ("invalid input", "bad user input", "malformed input")),
        ("mutation_not_supported", ("mutation", "not supported", "unknown mutation")),
        ("rate_limited", ("rate limit", "too many requests", "throttl")),
        ("validation", ("validation", "required field", "invalid argument")),
    )
    for category, terms in patterns:
        if all(term in text for term in terms) if category == "publication_not_found" else any(term in text for term in terms):
            return category
    return "unknown_graphql"

class HashnodePublisher:
    def __init__(self, token, publication_id, request, api_url="https://gql-beta.hashnode.com/", timeout=10, publish=False):
        self.token, self.publication_id, self.request = token, publication_id, request
        self.api_url, self.timeout, self.publish_mode = api_url.rstrip("/"), timeout, publish
    async def publish(self, view):
        parsed = urlparse(self.api_url)
        if not self.token or not self.publication_id or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            print("hashnode_failure_kind=hashnode_config_missing")
            return SimpleNamespace(success=False, external_id=None, error="hashnode_config_missing", failure_kind="hashnode_config_missing")
        mutation = PUBLISH_POST if self.publish_mode else CREATE_DRAFT
        key = "publishPost" if self.publish_mode else "createDraft"
        inp = {"publicationId": self.publication_id, "title": view.title, "contentMarkdown": view.content_markdown}
        try:
            response = await self.request(self.api_url, {"query": mutation, "variables": {"input": inp}}, self.timeout, {"Authorization": f"Bearer {self.token}"})
            data = response.json() if hasattr(response, "json") else response
            if getattr(response, "status_code", 200) >= 400:
                print(f"hashnode_failure_kind=hashnode_http_error mutation_name={key}")
                return SimpleNamespace(success=False, external_id=None, error="hashnode_http_error", failure_kind="hashnode_http_error", mutation_name=key)
            if data.get("errors"):
                first_error = data.get("errors", [None])[0]
                extensions = first_error.get("extensions") if isinstance(first_error, dict) else {}
                code = _safe_graphql_code((extensions or {}).get("code"))
                path = _graphql_path(first_error)
                category = _graphql_category(first_error.get("message") if isinstance(first_error, dict) else "")
                print(f"hashnode_graphql_code={code}")
                print(f"hashnode_graphql_path={path}")
                print(f"hashnode_graphql_category={category}")
                codes = tuple(_safe_graphql_code((item.get("extensions") or {}).get("code")) for item in data.get("errors", []) if isinstance(item, dict) and (item.get("extensions") or {}).get("code"))
                return SimpleNamespace(success=False, external_id=None, error="graphql", failure_kind="graphql", graphql_error_codes=tuple(codes), mutation_name=key)
            obj = ((data.get("data") or {}).get(key) or {}).get("post" if self.publish_mode else "draft") or {}
            if not obj:
                print(f"hashnode_failure_kind=missing_response_path missing_response_path={key} mutation_name={key}")
                return SimpleNamespace(success=False, external_id=None, error="missing_response_path", failure_kind="missing_response_path", mutation_name=key)
            ext = obj.get("id")
            if not ext:
                print(f"hashnode_failure_kind=missing_response_id mutation_name={key}")
            return SimpleNamespace(success=bool(ext), external_id=str(ext) if ext else None, error=None if ext else "missing_response_id", failure_kind=None if ext else "missing_response_id", mutation_name=key, delivery_mode="published" if self.publish_mode else "draft")
        except asyncio.TimeoutError:
            print("hashnode_failure_kind=timeout")
            return SimpleNamespace(success=False, external_id=None, error="timeout", failure_kind="timeout")
        except Exception:
            print("hashnode_failure_kind=network")
            return SimpleNamespace(success=False, external_id=None, error="network", failure_kind="network")
