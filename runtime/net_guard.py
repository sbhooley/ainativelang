"""SSRF checks for fetches whose URL can come from a document.

Refuse loopback, link-local (including the cloud metadata address), private,
reserved, multicast, and unspecified addresses. Hostnames are resolved and
every answer is checked. DNS failure is a refusal.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Iterable, List
from urllib.parse import urlparse

METADATA_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
        "metadata",
    }
)

# Cloud instance metadata addresses that are not always classified the way
# a defender expects across address families.
METADATA_IPS = frozenset(
    {
        "169.254.169.254",  # AWS, Azure, GCP, Oracle IMDS
        "169.254.170.2",  # ECS task role
        "169.254.170.23",  # EKS Pod Identity
        "100.100.100.200",  # Alibaba
        "fd00:ec2::254",  # AWS IPv6 IMDS
        "168.63.129.16",  # Azure Wire Server
        "192.0.0.192",  # Oracle IMDS
    }
)
_NAT64 = ipaddress.IPv6Network("64:ff9b::/96")


class AddressRejected(ValueError):
    """The URL is not an acceptable public HTTPS/HTTP target."""


def _is_metadata_ip(ip: ipaddress._BaseAddress) -> bool:
    """Metadata stays closed, including mapped, 6to4, NAT64, and link-local."""
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None and _is_metadata_ip(mapped):
        return True
    six = getattr(ip, "sixtofour", None)
    if six is not None and _is_metadata_ip(six):
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip in _NAT64:
        embedded = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if _is_metadata_ip(embedded):
            return True
    if ip.is_link_local:
        return True
    text = ip.compressed
    return text in METADATA_IPS or str(ip) in METADATA_IPS


def _ip_blocked(ip: ipaddress._BaseAddress) -> bool:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None and _ip_blocked(mapped):
        return True
    if _is_metadata_ip(ip):
        return True
    return bool(
        ip.is_loopback
        or ip.is_private
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _is_metadata_host(host: str) -> bool:
    name = (host or "").strip().rstrip(".").lower()
    if name.startswith("[") and name.endswith("]"):
        name = name[1:-1]
    if name in METADATA_HOSTS or name in METADATA_IPS:
        return True
    try:
        ip = ipaddress.ip_address(name)
    except ValueError:
        return False
    return _is_metadata_ip(ip)


def host_is_blocked(host: str) -> bool:
    name = (host or "").strip().rstrip(".").lower()
    if name.startswith("[") and name.endswith("]"):
        name = name[1:-1]
    if name in METADATA_HOSTS or name in {"localhost", "ip6-localhost", "ip6-loopback"}:
        return True
    if name.endswith(".localhost") or name.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(name)
    except ValueError:
        return False
    return _ip_blocked(ip)


def resolve_blocked(host: str) -> bool:
    """True when any DNS answer is a blocked address. DNS failure refuses."""
    name = (host or "").strip().rstrip(".")
    if name.startswith("[") and name.endswith("]"):
        name = name[1:-1]
    if host_is_blocked(name):
        return True
    try:
        ipaddress.ip_address(name)
        return False
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(name, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AddressRejected(f"dns lookup failed for host") from exc
    if not infos:
        raise AddressRejected("dns lookup returned no addresses")
    for info in infos:
        sockaddr = info[4] if len(info) > 4 else None
        if not sockaddr:
            continue
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if _ip_blocked(ip):
            return True
    return False


def approved_ips(host: str, *, allow_private: bool = False) -> List[str]:
    """Addresses the caller may connect to. Metadata never passes.

    Every answer is checked. One private answer rejects the name, so a
    mixed DNS response cannot be used. The returned addresses are the ones
    the check saw. The caller connects to one of them instead of resolving
    again.
    """
    name = (host or "").strip().rstrip(".").lower()
    if name.startswith("[") and name.endswith("]"):
        name = name[1:-1]
    if not name:
        raise AddressRejected("url is missing a host")
    if _is_metadata_host(name):
        raise AddressRejected("url host is not a public address")
    try:
        ipaddress.ip_address(name)
        literal = True
    except ValueError:
        literal = False
    if literal:
        if not allow_private and host_is_blocked(name):
            raise AddressRejected("url host is not a public address")
        return [name]
    if not allow_private and host_is_blocked(name):
        raise AddressRejected("url host is not a public address")
    try:
        infos = socket.getaddrinfo(name, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AddressRejected("dns lookup failed for host") from exc
    found: List[str] = []
    if not infos:
        raise AddressRejected("dns lookup returned no addresses")
    for info in infos:
        sockaddr = info[4] if len(info) > 4 else None
        if not sockaddr:
            continue
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if _is_metadata_host(ip.compressed) or (not allow_private and _ip_blocked(ip)):
            raise AddressRejected("url host resolves to a non-public address")
        text = ip.compressed
        if text not in found:
            found.append(text)
    if not found:
        raise AddressRejected("dns lookup returned no addresses")
    return found


def require_allowed_public_url(
    url: str,
    *,
    allow_hosts: Iterable[str],
    https_only: bool = True,
    allow_private: bool = False,
) -> List[str]:
    """Deny unless the host is one exact allowlist entry.

    An empty list denies every host. ``*`` is not an entry. A listed
    loopback or private host may be fetched. A metadata address may not,
    even when it is written in the allowlist.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    allowed = {
        str(item).strip().lower()
        for item in allow_hosts
        if str(item).strip() and str(item).strip() != "*"
    }
    if not host or host not in allowed:
        raise AddressRejected("host blocked by allowlist")
    private_ok = bool(allow_private) or (
        host_is_blocked(host) and not _is_metadata_host(host)
    )
    return check_fetch_url(
        url,
        https_only=https_only,
        allow_private=private_ok,
        resolve=True,
    )


def check_fetch_url(
    url: str,
    *,
    https_only: bool = False,
    allow_private: bool = False,
    resolve: bool = True,
) -> List[str]:
    """Refuse a bad URL and return the addresses that were checked.

    ``resolve=False`` skips DNS and returns an empty list. Callers that
    connect must resolve so they can pin the socket to one of these
    addresses.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise AddressRejected("url scheme is not http or https")
    if https_only and scheme != "https":
        raise AddressRejected("url scheme must be https")
    host = parsed.hostname or ""
    if not host:
        raise AddressRejected("url is missing a host")
    if parsed.username or parsed.password:
        raise AddressRejected("url must not carry userinfo")
    if not resolve:
        if _is_metadata_host(host) or (not allow_private and host_is_blocked(host)):
            raise AddressRejected("url host is not a public address")
        return []
    return approved_ips(host, allow_private=allow_private)


def check_each(urls: Iterable[str], **kwargs: object) -> None:
    for url in urls:
        check_fetch_url(str(url), **kwargs)  # type: ignore[arg-type]
