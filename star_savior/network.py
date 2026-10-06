"""Per-sync HTTP proxy and TLS configuration without global side effects."""
import ssl
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, ProxyHandler, build_opener


def validate_proxy(value):
    value = value.strip()
    if not value:
        return ''
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Invalid proxy address') from exc
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or not port
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Use http://host:port or https://host:port without credentials')
    return value


def sync_opener(proxy_url='', verify_tls=True):
    proxy_url = validate_proxy(proxy_url)
    context = ssl.create_default_context()
    if not verify_tls:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    handlers = [HTTPSHandler(context=context)]
    if proxy_url:
        handlers.append(ProxyHandler({'http': proxy_url, 'https': proxy_url}))
    return build_opener(*handlers)
