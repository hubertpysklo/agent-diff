"""Client-facing exports for dtu_proxy."""

from .http_proxy import http_proxy
from .registry import GLOBAL_REGISTRY, InterceptorRegistry, ProxyContext
from .service_proxy import service_proxy

from .linear.http import register_linear_http
from .slack.http import register_slack_http
from .mcp.linear import LinearMCPInterceptor

register_linear_http(GLOBAL_REGISTRY)
register_slack_http(GLOBAL_REGISTRY)
GLOBAL_REGISTRY.register_mcp(
    LinearMCPInterceptor.endpoint, lambda ctx: LinearMCPInterceptor()
)

__all__ = [
    "ProxyContext",
    "http_proxy",
    "service_proxy",
    "GLOBAL_REGISTRY",
    "InterceptorRegistry",
]
