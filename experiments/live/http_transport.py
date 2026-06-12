from __future__ import annotations

import urllib.request
import urllib.parse
import urllib.error
import socket
from dataclasses import dataclass
from typing import Protocol, Callable
from experiments.providers.models import (
    TransportRequest,
    TransportResponse,
    ProviderTransportError,
    ProviderAuthenticationError,
)

ALLOWED_RESPONSE_HEADERS = {
    "content-type",
    "content-length",
    "date",
    "server",
    "x-request-id",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "x-ratelimit-limit-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
    "retry-after",
}


@dataclass(frozen=True)
class LiveCredential:
    authorization_header: str

    def __repr__(self) -> str:
        return "LiveCredential(authorization_header=REDACTED)"

    def __str__(self) -> str:
        return "LiveCredential(authorization_header=REDACTED)"


class CredentialProvider(Protocol):
    def load_for_send(self) -> LiveCredential:
        """Loads the credential immediately before send. Must not leak secrets."""
        pass


class BlockRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, f"Redirect to {newurl} blocked", headers, fp)


class AttemptReservingTransport:
    def __init__(
        self,
        inner,
        reserve_attempt: Callable[[], None],
        limiter: object | None = None,
    ) -> None:
        if not callable(reserve_attempt):
            raise TypeError("reserve_attempt must be callable")
        self.inner = inner
        self.reserve_attempt = reserve_attempt
        self.limiter = limiter

    @property
    def no_auth_loopback(self) -> bool:
        return bool(getattr(self.inner, "no_auth_loopback", False))

    def send(self, request: TransportRequest, *, cancellation: object = None) -> TransportResponse:
        if self.limiter is not None and hasattr(self.limiter, "wait_before_attempt"):
            check_budget_fn = None
            if hasattr(self.reserve_attempt, "__self__"):
                tracker = self.reserve_attempt.__self__
                if hasattr(tracker, "_check_wall_clock"):
                    check_budget_fn = tracker._check_wall_clock
            self.limiter.wait_before_attempt(cancellation=cancellation, check_budget_fn=check_budget_fn)
        self.reserve_attempt()
        return self.inner.send(request, cancellation=cancellation)


class OpenAICompatibleHttpTransport:
    def __init__(
        self,
        api_base: str,
        credential_provider: CredentialProvider | None = None,
        *,
        timeout_seconds: float = 120.0,
        verify_tls: bool = True,
        max_response_bytes: int = 10 * 1024 * 1024,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> None:
        if isinstance(verify_tls, bool) and not verify_tls:
            raise ValueError("TLS verification cannot be disabled")
        if not verify_tls:
            raise ValueError("TLS verification cannot be disabled")

        self.api_base = api_base
        self.credential_provider = credential_provider
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.verify_tls = verify_tls

        # Fix the approved origin during initialization
        self.api_base_origin = self._parse_and_validate_origin(api_base, is_base=True)

        parsed_base = urllib.parse.urlparse(api_base)
        base_path = parsed_base.path.rstrip('/')
        base_scheme, base_host, base_port = self.api_base_origin

        # no_auth_loopback profile checks
        self.no_auth_loopback = (
            base_scheme == "http"
            and base_host == "127.0.0.1"
            and base_port == 8787
            and base_path == "/v1"
        )

        if opener is not None:
            self.opener = opener
        else:
            # Build secure opener
            self.opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                BlockRedirectHandler(),
            )

    def _parse_and_validate_origin(self, url_str: str, is_base: bool = False) -> tuple[str, str, int]:
        parsed = urllib.parse.urlparse(url_str)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise ValueError(f"Unsupported scheme: {scheme}")

        hostname = parsed.hostname
        if not hostname:
            raise ValueError("No hostname found in URL")
        hostname = hostname.lower()

        # Port normalization
        port = parsed.port
        if port is None:
            port = 443 if scheme == "https" else 80

        # Reject userinfo and fragment
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("UserInfo or Fragment is not allowed")

        # Localhost HTTP validation
        if scheme == "http":
            if hostname not in ("localhost", "127.0.0.1", "::1"):
                raise ValueError(f"Invalid localhost host: {hostname}")

        return (scheme, hostname, port)

    def send(
        self,
        request: TransportRequest,
        *,
        cancellation: object = None,
    ) -> TransportResponse:
        # 1. Validation happens BEFORE credential load
        req_origin = self._parse_and_validate_origin(request.url)
        if req_origin != self.api_base_origin:
            raise ValueError("Origin mismatch")

        parsed_req = urllib.parse.urlparse(request.url)
        req_path = parsed_req.path
        
        # 1. Reject dot segments and encoded slash/backslash/dot confusions
        path_lower = req_path.lower()
        
        # We must check percent-encoded variations for dot (.), dotdot (..), slash (/), and backslash (\)
        # %2e = . , %2f = / , %5c = \
        bad_patterns = [
            "..",
            "/./",
            "/%2e%2e",
            "/%2e/",
            "%2f",
            "%5c",
        ]
        
        # Check raw character confusion
        if "/../" in req_path or req_path.endswith("/..") or "/./" in req_path or req_path.endswith("/.") or "\\" in req_path:
            raise ValueError("Path traversal or backslash characters detected")
            
        # Check percent-encoded confusion
        for pattern in bad_patterns:
            if pattern in path_lower:
                raise ValueError(f"Prohibited path pattern detected: {pattern}")
                
        # Also check if it ends with encoded dot/dotdot
        if path_lower.endswith("/%2e%2e") or path_lower.endswith("/%2e") or path_lower.endswith("%2e%2e") or path_lower.endswith("%2e"):
            raise ValueError("Prohibited trailing encoded path pattern detected")

        # Exact segment check for /v1 namespace
        path_parts = [p for p in req_path.split("/") if p]
        if not path_parts or path_parts[0] != "v1":
            raise ValueError("Invalid path: must start with /v1 namespace")

        # 2. Check if cancellation is already triggered
        if cancellation is not None and getattr(cancellation, "is_cancelled", lambda: False)():
            raise RuntimeError("Request cancelled before send")

        headers = {}
        for k, v in request.public_headers:
            headers[k] = v

        if self.no_auth_loopback:
            # 若 caller 傳入 Authorization 或 authorization header，必須 fail closed
            for k, v in request.public_headers:
                if k.lower() == "authorization":
                    raise ValueError("Caller-supplied Authorization header is not allowed in no_auth_loopback mode")
            
            # no_auth_loopback 下不得加入 Authorization header
            auth_header = None
            raw_token = None
        else:
            # 非 no_auth_loopback profile 若缺少 approved credential，必須 fail closed
            if self.credential_provider is None:
                raise ValueError("Missing credential provider for authenticated profile")

            # 3. Load credentials only immediately before sending
            try:
                credential = self.credential_provider.load_for_send()
            except Exception as exc:
                # Wrap credential loading errors
                raise ValueError("Credential load failed (redacted)") from None

            # Ensure credential headers are valid
            if not credential or not credential.authorization_header:
                raise ValueError("Empty credential resolved")

            auth_header = credential.authorization_header
            if "{" in auth_header or "}" in auth_header or "private_key" in auth_header:
                raise ValueError("Service Account JSON structure is not allowed as Bearer token")

            # Extract raw token for exception message redaction
            raw_token = auth_header.replace("Bearer ", "").strip()
            headers["Authorization"] = auth_header

        req = urllib.request.Request(
            request.url,
            data=request.json_body,
            headers=headers,
            method=request.method,
        )

        try:
            # Enforce timeout and send
            response = self.opener.open(req, timeout=self.timeout_seconds)
            # Enforce max response bytes
            body = response.read(self.max_response_bytes + 1)
            if len(body) > self.max_response_bytes:
                raise ProviderTransportError("Response size limit exceeded")
            
            resp_headers = []
            for k, v in response.headers.items():
                if k.lower() in ALLOWED_RESPONSE_HEADERS:
                    resp_headers.append((k, v))

            return TransportResponse(
                status_code=response.status,
                body_bytes=body,
                allowlisted_headers=tuple(resp_headers),
                transport_request_id=None,
            )
        except urllib.error.HTTPError as exc:
            status = exc.code
            if status in (401, 403):
                raise ProviderAuthenticationError("Authentication failed")
            
            try:
                body = exc.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise ProviderTransportError("Response size limit exceeded")
            except Exception as e:
                if isinstance(e, ProviderTransportError):
                    raise
                body = b""

            resp_headers = []
            for k, v in exc.headers.items():
                if k.lower() in ALLOWED_RESPONSE_HEADERS:
                    resp_headers.append((k, v))

            return TransportResponse(
                status_code=exc.code,
                body_bytes=body,
                allowlisted_headers=tuple(resp_headers),
                transport_request_id=None,
            )
        except (urllib.error.URLError, socket.error, TimeoutError) as exc:
            clean_msg = str(exc)
            if auth_header and ("Authorization" in clean_msg or auth_header in clean_msg or (raw_token and raw_token in clean_msg)):
                clean_msg = "Network transport failed (redacted)"
            raise ProviderTransportError(clean_msg) from exc
        except Exception as exc:
            clean_msg = str(exc)
            if auth_header and ("Authorization" in clean_msg or auth_header in clean_msg or (raw_token and raw_token in clean_msg)):
                clean_msg = "Network transport failed (redacted)"
            raise ProviderTransportError(clean_msg) from exc
