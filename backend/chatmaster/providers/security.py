"""Validation for outbound, user-configurable provider endpoints."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeProviderUrl(ValueError):
    """A provider endpoint is not safe for the local service to call."""


def validate_provider_url(url: str | None, *, allow_private_network: bool = False) -> None:
    """Reject malformed endpoints and addresses unsafe for outbound requests.

    Loopback is intentionally allowed for local OpenAI-compatible runtimes such
    as Ollama. Private LAN ranges require an explicit opt-in.
    """
    if not url:
        return
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeProviderUrl("Provider URL must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.fragment:
        raise UnsafeProviderUrl("Provider URL must not contain credentials or a fragment.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, None)}
    except socket.gaierror as exc:
        raise UnsafeProviderUrl("Provider hostname could not be resolved.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_loopback:
            continue
        if ip.is_link_local or ip.is_unspecified or ip.is_multicast or ip.is_reserved:
            raise UnsafeProviderUrl("Provider URL resolves to a prohibited address.")
        if ip.is_private and not allow_private_network:
            raise UnsafeProviderUrl("Private-network provider URLs require explicit opt-in.")
