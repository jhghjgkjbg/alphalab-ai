from types import SimpleNamespace

class XOAuthTokenProvider:
    """Small injectable OAuth 2 user-context token provider."""
    def __init__(self, access_token="", refresh_token="", client_id="", client_secret="", token_url="https://api.x.com/2/oauth2/token", request=None, persist=None, timeout_seconds=10, state_store=None):
        self.access_token = access_token or ""
        self.refresh_token = refresh_token or ""
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self.token_url = token_url
        self._request = request
        self._persist = persist
        self.timeout_seconds = timeout_seconds
        self._state_store = state_store
        if state_store:
            try:
                state = state_store.load()
                if state:
                    self.access_token, self.refresh_token = state.access_token, state.refresh_token
            except RuntimeError:
                pass

    async def get_access_token(self):
        return self.access_token

    async def refresh_access_token(self):
        if not self._request or not self.refresh_token or not self.client_id:
            return SimpleNamespace(success=False, error="x_token_refresh_failed")
        payload = {"grant_type": "refresh_token", "refresh_token": self.refresh_token, "client_id": self.client_id}
        if self.client_secret:
            payload["client_secret"] = self.client_secret
        try:
            response = await self._request(self.token_url, payload, self.timeout_seconds, {"Content-Type": "application/x-www-form-urlencoded"})
            status = getattr(response, "status_code", 200)
            data = response.json() if hasattr(response, "json") else response
            token = data.get("access_token") if isinstance(data, dict) else None
            if status < 200 or status >= 300 or not token:
                return SimpleNamespace(success=False, error="x_token_refresh_failed")
            self.access_token = str(token)
            if isinstance(data, dict) and data.get("refresh_token"):
                self.refresh_token = str(data["refresh_token"])
            if self._state_store:
                from core.credentials.x_token_store import XTokenState
                try: self._state_store.save(XTokenState(self.access_token, self.refresh_token))
                except Exception: return SimpleNamespace(success=False, error="x_token_state_write_failed")
            if self._persist:
                self._persist(self.access_token, self.refresh_token)
            return SimpleNamespace(success=True, access_token=self.access_token)
        except TimeoutError:
            return SimpleNamespace(success=False, error="x_token_refresh_timeout")
        except ConnectionError:
            return SimpleNamespace(success=False, error="x_token_refresh_network_error")
        except Exception:
            return SimpleNamespace(success=False, error="x_token_refresh_failed")

class XPublisher:
    def __init__(self, bearer_token="", request=None, base_url="https://api.x.com", timeout_seconds=10, token_provider=None):
        self._token = bearer_token
        self._request = request
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._token_provider = token_provider

    async def publish(self, view):
        token = await self._token_provider.get_access_token() if self._token_provider else self._token
        if not token:
            return SimpleNamespace(success=False, error="x_missing_token")
        try:
            response = await self._request(f"{self._base_url}/2/tweets", {"text": view.text}, self._timeout, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            status = getattr(response, "status_code", None)
            data = response.json() if hasattr(response, "json") else response
            if status == 401 and self._token_provider:
                refreshed = await self._token_provider.refresh_access_token()
                if getattr(refreshed, "success", False):
                    token = await self._token_provider.get_access_token()
                    response = await self._request(f"{self._base_url}/2/tweets", {"text": view.text}, self._timeout, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
                    status = getattr(response, "status_code", None)
                    data = response.json() if hasattr(response, "json") else response
            if status is not None and not 200 <= status < 300:
                if status == 401: return SimpleNamespace(success=False, error="x_auth_failed")
                if status == 402: return SimpleNamespace(success=False, error="x_payment_required")
                if status == 403: return SimpleNamespace(success=False, error="x_insufficient_scope")
                if status == 429: return SimpleNamespace(success=False, error="x_rate_limited")
                if status >= 500: return SimpleNamespace(success=False, error="x_http_5xx")
                return SimpleNamespace(success=False, error=f"x_http_{status}")
            tweet_id = data.get("data", {}).get("id") if isinstance(data, dict) else None
            if not tweet_id:
                return SimpleNamespace(success=False, error="x_invalid_response")
            return SimpleNamespace(success=True, external_id=str(tweet_id))
        except TimeoutError:
            return SimpleNamespace(success=False, error="x_unknown_outcome")
        except ConnectionError:
            return SimpleNamespace(success=False, error="x_network_error")
        except Exception:
            return SimpleNamespace(success=False, error="x_request_failed")
