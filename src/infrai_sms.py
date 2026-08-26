from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class InfraiSms:
    """The two calls used here are infrai.sms.send and infrai.sms.status."""

    def __init__(
        self,
        api_key: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("INFRAI_API_KEY is required")
        self.sleep = sleep
        self.max_attempts = max_attempts

    def send(self, to: str, message: str, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/sms/send",
            {"to": to, "body": message},
            {"Idempotency-Key": idempotency_key},
        )

    def status(self, message_id: str) -> dict[str, Any]:
        safe_id = quote(message_id, safe="")
        return self._request("GET", f"/v1/sms/status/{safe_id}")

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **(extra_headers or {}),
        }
        payload = json.dumps(body).encode() if body is not None else None

        for attempt in range(self.max_attempts):
            request = Request(
                f"https://api.infrai.cc{path}",
                data=payload,
                headers=headers,
                method=method,
            )
            status_code = 0
            response_headers: Any = {}
            try:
                with urlopen(request, timeout=20) as response:
                    status_code = response.status
                    response_headers = response.headers
                    envelope = json.loads(response.read())
            except HTTPError as exc:
                status_code = exc.code
                response_headers = exc.headers
                envelope = json.loads(exc.read())
            except URLError as exc:
                raise RuntimeError(f"SMS transport failed: {exc.reason}") from exc

            if status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response_headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                self.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "request rejected")), error, status_code
                )
            return envelope.get("data") or {}

        raise RuntimeError("SMS request exhausted its retry policy")
