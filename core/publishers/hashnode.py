from types import SimpleNamespace
import asyncio

PUBLISH_POST = "mutation ($input: PublishPostInput!) { publishPost(input: $input) { post { id slug url } } }"
CREATE_DRAFT = "mutation ($input: CreateDraftInput!) { createDraft(input: $input) { draft { id title } } }"

class HashnodePublisher:
    def __init__(self, token, publication_id, request, api_url="https://gql-beta.hashnode.com/", timeout=10, publish=False):
        self.token, self.publication_id, self.request = token, publication_id, request
        self.api_url, self.timeout, self.publish_mode = api_url.rstrip("/"), timeout, publish
    async def publish(self, view):
        if not self.token or not self.publication_id: return SimpleNamespace(success=False, external_id=None, error="configuration")
        mutation = PUBLISH_POST if self.publish_mode else CREATE_DRAFT
        key = "publishPost" if self.publish_mode else "createDraft"
        inp = {"publicationId": self.publication_id, "title": view.title, "contentMarkdown": view.content_markdown}
        try:
            response = await self.request(self.api_url, {"query": mutation, "variables": {"input": inp}}, self.timeout, {"Authorization": f"Bearer {self.token}"})
            data = response.json() if hasattr(response, "json") else response
            if getattr(response, "status_code", 200) >= 400 or data.get("errors"):
                return SimpleNamespace(success=False, external_id=None, error="graphql")
            obj = ((data.get("data") or {}).get(key) or {}).get("post" if self.publish_mode else "draft") or {}
            ext = obj.get("id")
            return SimpleNamespace(success=bool(ext), external_id=str(ext) if ext else None, error=None if ext else "invalid_response", delivery_mode="published" if self.publish_mode else "draft")
        except asyncio.TimeoutError:
            return SimpleNamespace(success=False, external_id=None, error="timeout")
        except Exception:
            return SimpleNamespace(success=False, external_id=None, error="network")
