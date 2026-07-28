from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DirectoryConnection:
    server_uri: str
    use_starttls: bool
    bind_dn: str
    bind_password: str
    base_dn: str
    timeout_seconds: int
    ca_certificate_pem: str | None = None


@dataclass(frozen=True)
class DirectoryTestResult:
    success: bool
    detail_code: str


@dataclass(frozen=True)
class DirectoryAuthenticationRequest:
    configuration: DirectoryConnection
    base_dn: str
    user_filter: str
    username: str
    password: str
    subject_attribute: str
    email_attribute: str
    display_name_attribute: str
    group_attribute: str | None


@dataclass(frozen=True)
class DirectoryPrincipal:
    external_subject: str
    username: str
    email: str
    display_name: str
    groups: tuple[str, ...]


class DirectoryProvider(Protocol):
    async def test_connection(self, configuration: DirectoryConnection) -> DirectoryTestResult: ...

    async def authenticate(
        self, request: DirectoryAuthenticationRequest
    ) -> DirectoryPrincipal | None: ...
