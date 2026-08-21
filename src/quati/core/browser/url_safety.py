from __future__ import annotations

import socket
from collections.abc import Callable, Collection, Sequence
from ipaddress import ip_address
from urllib.parse import urlsplit, urlunsplit

AddressInfo = Sequence[tuple[int, int, int, str, tuple[object, ...]]]


def host_is_allowed(host: str, allowed_hosts: Collection[str]) -> bool:
    normalized_host = host.lower().rstrip(".")
    return any(
        normalized_host == allowed.lower().rstrip(".")
        or normalized_host.endswith(f".{allowed.lower().rstrip('.')}")
        for allowed in allowed_hosts
    )


def validate_public_https_url(url: str, allowed_hosts: Collection[str] | None = None) -> str:
    """Aceita somente URLs HTTPS públicas, sem usuário, senha, porta ou fragmento."""
    if not isinstance(url, str) or len(url) > 2_048:
        raise ValueError("URL inválida.")

    parsed = urlsplit(url.strip())
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Use uma URL HTTPS pública, sem credenciais ou porta personalizada.")

    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".local"):
        raise ValueError("Endereço de rede privada não é permitido.")
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise ValueError("Endereço de rede privada não é permitido.")

    if allowed_hosts and not host_is_allowed(host, allowed_hosts):
        raise ValueError("O domínio não é permitido para esta fonte.")

    return urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def validate_public_hostname_resolution(
    host: str,
    *,
    resolver: Callable[..., AddressInfo] = socket.getaddrinfo,
) -> None:
    """Bloqueia SSRF por DNS que aponta um domínio externo para uma rede privada."""
    try:
        answers = resolver(host, 443, type=socket.SOCK_STREAM)
        addresses = {ip_address(str(answer[4][0])) for answer in answers}
    except (OSError, ValueError, IndexError) as exc:
        raise ValueError("Não foi possível validar o domínio externo.") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("O domínio externo aponta para uma rede não pública.")
