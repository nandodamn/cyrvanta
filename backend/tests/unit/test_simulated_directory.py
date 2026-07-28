from cyrvanta.modules.directory.domain.ports import (
    DirectoryAuthenticationRequest,
    DirectoryConnection,
)
from cyrvanta.modules.directory.infrastructure.simulated_provider import (
    SimulatedDirectoryProvider,
)


async def test_simulated_directory_disabled_by_default() -> None:
    request = DirectoryAuthenticationRequest(
        configuration=DirectoryConnection(
            server_uri="ldaps://simulated.invalid", use_starttls=False,
            bind_dn="cn=simulated", bind_password="ignored",
            base_dn="dc=cyrvanta,dc=demo", timeout_seconds=1,
        ),
        base_dn="dc=cyrvanta,dc=demo", user_filter="(uid={username})",
        username="ldap-demo", password="wrong", subject_attribute="subject",
        email_attribute="mail", display_name_attribute="displayName",
        group_attribute="memberOf",
    )
    assert await SimulatedDirectoryProvider().authenticate(request) is None
