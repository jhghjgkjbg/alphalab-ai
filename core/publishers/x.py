from types import SimpleNamespace

class XPublisher:
    def __init__(self, bearer_token, request, base_url="https://api.x.com", timeout_seconds=10):
        self._token = bearer_token
        self._request = request
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def publish(self, view):
        if not self._token:
            return SimpleNamespace(success=False, error="x_missing_token")
        try:
            response = await self._request(f"{self._base_url}/2/tweets", {"text": view.text}, self._timeout, {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"})
            status = getattr(response, "status_code", None)
            data = response.json() if hasattr(response, "json") else response
            if status is not None and not 200 <= status < 300:
                return SimpleNamespace(success=False, error=f"x_http_{status}")
            tweet_id = data.get("data", {}).get("id") if isinstance(data, dict) else None
            if not tweet_id:
                return SimpleNamespace(success=False, error="x_invalid_response")
            return SimpleNamespace(success=True, external_id=str(tweet_id))
        except TimeoutError:
            return SimpleNamespace(success=False, error="x_timeout")
        except ConnectionError:
            return SimpleNamespace(success=False, error="x_network_error")
        except Exception:
            return SimpleNamespace(success=False, error="x_request_failed")
