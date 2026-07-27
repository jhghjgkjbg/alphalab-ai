from types import SimpleNamespace

class LinkedInPublisher:
    def __init__(self, access_token, author_urn, request, base_url="https://api.linkedin.com", api_version="202601", timeout_seconds=10):
        self._token, self._author, self._request = access_token, author_urn, request
        self._base_url, self._version, self._timeout = base_url.rstrip("/"), api_version, timeout_seconds
    async def publish(self, view):
        if not self._token: return SimpleNamespace(success=False, error="linkedin_missing_token")
        if not self._author: return SimpleNamespace(success=False, error="linkedin_missing_author")
        payload = {"author": self._author, "commentary": view.text, "visibility": "PUBLIC", "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []}, "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json", "LinkedIn-Version": self._version, "X-Restli-Protocol-Version": "2.0.0"}
        try:
            response = await self._request(f"{self._base_url}/rest/posts", payload, self._timeout, headers)
            status = getattr(response, "status_code", None)
            if status is not None and not 200 <= status < 300: return SimpleNamespace(success=False, error=f"linkedin_http_{status}")
            identifier = getattr(response, "headers", {}).get("x-restli-id")
            return SimpleNamespace(success=bool(identifier), external_id=identifier, error=None if identifier else "linkedin_invalid_response")
        except TimeoutError: return SimpleNamespace(success=False, error="linkedin_timeout")
        except ConnectionError: return SimpleNamespace(success=False, error="linkedin_network_error")
        except Exception: return SimpleNamespace(success=False, error="linkedin_request_failed")
