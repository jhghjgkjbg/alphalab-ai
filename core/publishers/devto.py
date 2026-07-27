from types import SimpleNamespace
class DevToPublisher:
    def __init__(self, api_key, request, base_url="https://dev.to", timeout_seconds=10): self.key,self.request,self.base_url,self.timeout=api_key,request,base_url.rstrip("/"),timeout_seconds
    async def publish(self, view):
        if not self.key: return SimpleNamespace(success=False,error="devto_missing_api_key")
        article={"title":view.title,"body_markdown":view.body_markdown,"published":view.published,"canonical_url":view.canonical_url,"tags":list(view.tags)}
        if view.organization_id is not None: article["organization_id"]=view.organization_id
        try:
            response=await self.request(f"{self.base_url}/api/articles", {"article":article}, self.timeout, {"api-key":self.key,"Content-Type":"application/json","Accept":"application/vnd.forem.api-v1+json"})
            status=getattr(response,"status_code",None)
            if status is not None and not 200<=status<300:return SimpleNamespace(success=False,error=f"devto_http_{status}")
            data=response.json() if hasattr(response,"json") else response; ident=data.get("id") if isinstance(data,dict) else None
            return SimpleNamespace(success=bool(ident),external_id=str(ident) if ident else None,error=None if ident else "devto_invalid_response")
        except TimeoutError:return SimpleNamespace(success=False,error="devto_timeout")
        except ConnectionError:return SimpleNamespace(success=False,error="devto_network_error")
        except Exception:return SimpleNamespace(success=False,error="devto_invalid_response")
