from cyrvanta.modules.directory.domain.ports import (
    DirectoryAuthenticationRequest,
    DirectoryConnection,
    DirectoryPrincipal,
    DirectoryTestResult,
)
from cyrvanta.shared.config import get_settings


class SimulatedDirectoryProvider:
    """Isolated development provider. It never performs a network request."""

    async def test_connection(self, configuration: DirectoryConnection) -> DirectoryTestResult:
        enabled = get_settings().directory_demo_enabled
        return DirectoryTestResult(enabled, "simulated_directory_ready" if enabled else "disabled")

    async def authenticate(
        self, request: DirectoryAuthenticationRequest
    ) -> DirectoryPrincipal | None:
        settings = get_settings()
        valid = (
            settings.environment != "production"
            and settings.directory_demo_enabled
            and request.username == settings.directory_demo_username
            and request.password == settings.directory_demo_password
            and bool(settings.directory_demo_password)
        )
        if not valid:
            return None
        return DirectoryPrincipal(
            external_subject="cyrvanta-directory-demo-subject-v1",
            username=request.username,
            email="ldap-demo@cyrvanta.uy",
            display_name="LDAP Demo Analyst",
            groups=("cyrvanta-demo-analysts",),
        )
