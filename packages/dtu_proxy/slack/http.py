"""HTTP interceptors for Slack service traffic."""

from __future__ import annotations

from typing import Any, Dict
from urllib.parse import urlsplit

from ..registry import HTTPDispatch, HTTPInterceptor, ProxyContext


SLACK_HOSTS = {
    "slack.com",
    "api.slack.com",
    "hooks.slack.com",
}


class SlackHTTPInterceptor(HTTPInterceptor):
    service_name = "slack"

    def dispatch(
        self,
        method: str,
        url: str,
        kwargs: dict[str, Any],
        *,
        context: ProxyContext,
    ) -> HTTPDispatch:
        base = context.service_base(self.service_name)
        parsed = urlsplit(url)
        path = parsed.path.lstrip("/")
        proxied = f"{base}/{path}" if path else base
        if parsed.query:
            proxied = f"{proxied}?{parsed.query}"

        headers: Dict[str, Any] = kwargs.setdefault("headers", {})
        headers.setdefault("x-platform-api-key", context.api_key)
        return HTTPDispatch(url=proxied, kwargs=kwargs)


def register_slack_http(registry):
    for host in SLACK_HOSTS:
        registry.register_http(host, lambda ctx: SlackHTTPInterceptor())
