from types import SimpleNamespace

class MediumPublisher:
    def __init__(self, token, author_id, request, base_url="https://api.medium.com", timeout_seconds=10, publish_status="draft"):
        self.token, self.author_id, self.request = token, author_id, request
        self.base_url, self.timeout, self.publish_status = base_url.rstrip("/"), timeout_seconds, publish_status
    async def publish(self, view):
        if not self.token: return SimpleNamespace(success=False, error="medium_missing_token")
        if not self.author_id: return SimpleNamespace(success=False, error="medium_missing_author")
        if self.publish_status not in {"draft", "public", "unlisted"}: return SimpleNamespace(success=False, error="medium_invalid_publish_status")
        payload={"title":view.title,"contentFormat":"html","content":view.content_html,"canonicalUrl":view.canonical_url,"tags":list(view.tags),"publishStatus":view.publish_status}
        headers={"Authorization":f"Bearer {self.token}","Content-Type":"application/json","Accept":"application/json","Accept-Charset":"utf-8"}
        try:
            response=await self.request(f"{self.base_url}/v1/users/{self.author_id}/posts",payload,self.timeout,headers)
            status=getattr(response,"status_code",None)
            if status is not None and not 200 <= status < 300: return SimpleNamespace(success=False,error=f"medium_http_{status}")
            data=response.json() if hasattr(response,"json") else response
            ident=data.get("data",{}).get("id") if isinstance(data,dict) else None
            return SimpleNamespace(success=bool(ident),external_id=str(ident) if ident else None,error=None if ident else "medium_invalid_response")
        except TimeoutError: return SimpleNamespace(success=False,error="medium_timeout")
        except ConnectionError: return SimpleNamespace(success=False,error="medium_network_error")
        except Exception: return SimpleNamespace(success=False,error="medium_invalid_response")
