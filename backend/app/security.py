import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUrlError(ValueError):
    pass


def _resolve_public_host(hostname: str) -> None:
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Не удалось разрешить адрес {hostname}") from exc

    if not addresses:
        raise UnsafeUrlError(f"Не найден IP-адрес для {hostname}")

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise UnsafeUrlError(f"Локальный или приватный адрес запрещён: {hostname}")


async def validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrlError("Разрешены только публичные HTTP/HTTPS адреса")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("Адреса со встроенными логином и паролем запрещены")
    await asyncio.to_thread(_resolve_public_host, parsed.hostname)

