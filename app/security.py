import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlsplit, urlunsplit

class PolicyError(Exception):
    pass

class Redactor:
    def __init__(self, secrets: dict[str, str], redaction_only: list[str] | None = None):
        self.aliases = {k: v for k, v in secrets.items() if v}
        self.secrets = self.aliases | {f"_redact_{i}": v for i, v in enumerate(redaction_only or []) if v}

    def clean(self, value: str) -> str:
        for secret in sorted(self.secrets.values(), key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)\b(?:sk-|gh[pousr]_)[a-z0-9_-]{8,}", "[REDACTED]", value)
        value = re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", "[EMAIL]", value)
        return value

    def data(self, value):
        if isinstance(value, str):
            return self.clean(value)
        if isinstance(value, dict):
            return {k: self.data(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.data(v) for v in value]
        return value

    def resolve(self, value: str) -> str:
        def replace(m):
            if m[1] not in self.aliases:
                raise PolicyError("Missing secret placeholder: " + m[1])
            return self.aliases[m[1]]
        return re.sub(r"\{\{([A-Z][A-Z0-9_]*)\}\}", replace, value)

def safe_url_text(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if ":" in host:
        host = "[" + host + "]"
    if parts.port:
        host += ":" + str(parts.port)
    return urlunsplit((parts.scheme, host, parts.path, "", ""))

class NavigationPolicy:
    def __init__(self, start_url: str, extra_hosts: str = "", allow_localhost: bool = False):
        self.hosts = {urlsplit(start_url).hostname}
        self.hosts.update(x.strip().lower() for x in extra_hosts.split(",") if x.strip())
        self.allow_localhost = allow_localhost

    async def validate(self, url: str, navigation: bool = True):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise PolicyError("Only HTTP(S) URLs without embedded credentials are allowed")
        host = parts.hostname.lower()
        if navigation and host not in self.hosts:
            raise PolicyError("Navigation host is outside this run's exact-host allowlist")
        addresses = await asyncio.to_thread(socket.getaddrinfo, host, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
        if not addresses:
            raise PolicyError("Host did not resolve")
        for entry in addresses:
            address = ipaddress.ip_address(entry[4][0])
            if address.is_loopback and self.allow_localhost and host in self.hosts:
                continue
            if not address.is_global:
                raise PolicyError("Private, loopback, link-local and reserved addresses are blocked")

DESTRUCTIVE = re.compile(r"\b(delete|remove|erase|purchase|buy|pay|checkout|order|book|send|submit|publish|transfer|unsubscribe|cancel|confirm)\b", re.I)

def needs_approval(action, metadata: dict) -> bool:
    if action.destructive:
        return True
    if action.kind != "click":
        return False
    # All form submission controls are gated, including ordinary login buttons.
    return bool(DESTRUCTIVE.search(metadata.get("name", ""))) or metadata.get("submits", False)