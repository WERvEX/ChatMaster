from __future__ import annotations

import pytest

from chatmaster.providers.security import UnsafeProviderUrl, validate_provider_url


def _addresses(*items: str):
    return [(2, 1, 6, "", (item, 0)) for item in items]


def test_provider_url_allows_loopback(monkeypatch) -> None:
    monkeypatch.setattr(
        "chatmaster.providers.security.socket.getaddrinfo", lambda *_: _addresses("127.0.0.1")
    )
    validate_provider_url("http://localhost:11434/v1")


@pytest.mark.parametrize("address", ["169.254.169.254", "0.0.0.0", "224.0.0.1"])
def test_provider_url_rejects_prohibited_addresses(monkeypatch, address: str) -> None:
    monkeypatch.setattr(
        "chatmaster.providers.security.socket.getaddrinfo", lambda *_: _addresses(address)
    )
    with pytest.raises(UnsafeProviderUrl):
        validate_provider_url("http://provider.test/v1")


def test_provider_url_requires_opt_in_for_private_lan(monkeypatch) -> None:
    monkeypatch.setattr(
        "chatmaster.providers.security.socket.getaddrinfo", lambda *_: _addresses("192.168.1.20")
    )
    with pytest.raises(UnsafeProviderUrl):
        validate_provider_url("http://provider.test/v1")
    validate_provider_url("http://provider.test/v1", allow_private_network=True)


@pytest.mark.parametrize(
    "url",
    ["ftp://provider.test", "https://user:secret@provider.test/v1", "https://provider.test/#x"],
)
def test_provider_url_rejects_unsafe_syntax(url: str) -> None:
    with pytest.raises(UnsafeProviderUrl):
        validate_provider_url(url)
