import asyncio
import ssl
from urllib.parse import urlparse

from ldap3 import ALL_ATTRIBUTES, Connection, Server, Tls  # type: ignore[import-untyped]
from ldap3.core.exceptions import LDAPException  # type: ignore[import-untyped]
from ldap3.utils.conv import escape_filter_chars  # type: ignore[import-untyped]

from cyrvanta.modules.directory.domain.ports import (
    DirectoryAuthenticationRequest,
    DirectoryConnection,
    DirectoryPrincipal,
    DirectoryProvider,
    DirectoryTestResult,
)


class LdapDirectoryProvider(DirectoryProvider):
    async def test_connection(self, configuration: DirectoryConnection) -> DirectoryTestResult:
        return await asyncio.to_thread(self._test_connection_sync, configuration)

    async def authenticate(
        self, request: DirectoryAuthenticationRequest
    ) -> DirectoryPrincipal | None:
        return await asyncio.to_thread(self._authenticate_sync, request)

    @staticmethod
    def _test_connection_sync(configuration: DirectoryConnection) -> DirectoryTestResult:
        parsed = urlparse(configuration.server_uri)
        if parsed.scheme not in {"ldap", "ldaps"} or not parsed.hostname:
            return DirectoryTestResult(False, "invalid_server_uri")
        if parsed.scheme == "ldap" and not configuration.use_starttls:
            return DirectoryTestResult(False, "transport_security_required")
        tls = Tls(
            validate=ssl.CERT_REQUIRED,
            ca_certs_data=configuration.ca_certificate_pem,
        )
        server = Server(
            parsed.hostname,
            port=parsed.port or (636 if parsed.scheme == "ldaps" else 389),
            use_ssl=parsed.scheme == "ldaps",
            tls=tls,
            connect_timeout=configuration.timeout_seconds,
        )
        connection: Connection | None = None
        try:
            connection = Connection(
                server,
                user=configuration.bind_dn,
                password=configuration.bind_password,
                receive_timeout=configuration.timeout_seconds,
                raise_exceptions=True,
            )
            connection.open()
            if configuration.use_starttls:
                connection.start_tls()
            connection.bind()
            return DirectoryTestResult(True, "connection_succeeded")
        except (LDAPException, OSError, ssl.SSLError):
            return DirectoryTestResult(False, "connection_failed")
        finally:
            if connection is not None:
                connection.unbind()

    @classmethod
    def _authenticate_sync(
        cls, request: DirectoryAuthenticationRequest
    ) -> DirectoryPrincipal | None:
        connection = cls._bound_connection(request.configuration)
        if connection is None:
            return None
        try:
            safe_username = escape_filter_chars(request.username)
            search_filter = request.user_filter.replace("{username}", safe_username)
            connection.search(
                search_base=request.base_dn,
                search_filter=search_filter,
                attributes=ALL_ATTRIBUTES,
                size_limit=2,
            )
            if len(connection.entries) != 1:
                return None
            entry = connection.entries[0]
            user_dn = str(entry.entry_dn)
            attributes = entry.entry_attributes_as_dict
            principal = cls._principal(request, attributes)
            if principal is None:
                return None
            user_connection = Connection(
                connection.server,
                user=user_dn,
                password=request.password,
                receive_timeout=request.configuration.timeout_seconds,
                raise_exceptions=True,
            )
            try:
                user_connection.open()
                if request.configuration.use_starttls:
                    user_connection.start_tls()
                if not user_connection.bind():
                    return None
            finally:
                user_connection.unbind()
            return principal
        except (LDAPException, OSError, ssl.SSLError):
            return None
        finally:
            connection.unbind()

    @staticmethod
    def _bound_connection(configuration: DirectoryConnection) -> Connection | None:
        parsed = urlparse(configuration.server_uri)
        if parsed.scheme not in {"ldap", "ldaps"} or not parsed.hostname:
            return None
        if parsed.scheme == "ldap" and not configuration.use_starttls:
            return None
        server = Server(
            parsed.hostname,
            port=parsed.port or (636 if parsed.scheme == "ldaps" else 389),
            use_ssl=parsed.scheme == "ldaps",
            tls=Tls(validate=ssl.CERT_REQUIRED, ca_certs_data=configuration.ca_certificate_pem),
            connect_timeout=configuration.timeout_seconds,
        )
        try:
            connection = Connection(
                server,
                user=configuration.bind_dn,
                password=configuration.bind_password,
                receive_timeout=configuration.timeout_seconds,
                raise_exceptions=True,
            )
            connection.open()
            if configuration.use_starttls:
                connection.start_tls()
            connection.bind()
            return connection
        except (LDAPException, OSError, ssl.SSLError):
            return None

    @staticmethod
    def _principal(
        request: DirectoryAuthenticationRequest, attributes: dict[str, object]
    ) -> DirectoryPrincipal | None:
        def first(name: str) -> str | None:
            value = attributes.get(name)
            if isinstance(value, list):
                value = value[0] if value else None
            return str(value) if value is not None else None

        subject = first(request.subject_attribute)
        email = first(request.email_attribute)
        display_name = first(request.display_name_attribute)
        if not subject or not email or not display_name:
            return None
        group_value = attributes.get(request.group_attribute or "")
        groups = tuple(str(item) for item in group_value) if isinstance(group_value, list) else ()
        return DirectoryPrincipal(
            external_subject=subject,
            username=request.username,
            email=email.lower(),
            display_name=display_name,
            groups=groups,
        )
