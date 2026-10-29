import asyncio
import socket

import pytest

from app.security import UnsafeUrlError, validate_public_url


def test_public_url_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))],
    )

    asyncio.run(validate_public_url("https://jobs.example.com/openings"))


def test_private_url_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))],
    )

    with pytest.raises(UnsafeUrlError, match="приватный"):
        asyncio.run(validate_public_url("http://localhost/jobs"))


def test_url_with_credentials_is_rejected() -> None:
    with pytest.raises(UnsafeUrlError, match="логином"):
        asyncio.run(validate_public_url("https://user:secret@example.com/jobs"))

