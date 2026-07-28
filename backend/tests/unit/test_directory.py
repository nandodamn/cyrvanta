import pytest

from cyrvanta.modules.directory.application.crypto import SecretCipher
from cyrvanta.modules.directory.application.schemas import DirectoryConfigurationWrite
from cyrvanta.modules.directory.domain.ports import DirectoryConnection
from cyrvanta.modules.directory.infrastructure.ldap_provider import LdapDirectoryProvider


def test_directory_secret_round_trip_does_not_expose_plaintext() -> None:
    cipher = SecretCipher("MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    encrypted = cipher.encrypt("directory-secret")
    assert "directory-secret" not in encrypted
    assert cipher.decrypt(encrypted) == "directory-secret"


def test_directory_configuration_requires_bounded_username_placeholder() -> None:
    with pytest.raises(ValueError):
        DirectoryConfigurationWrite(
            provider_type="ldap",
            server_uri="ldaps://ldap.example.test",
            base_dn="dc=example,dc=test",
            bind_dn="cn=service,dc=example,dc=test",
            bind_password="secret",
            user_filter="(uid=*)",
            login_attribute="uid",
            subject_attribute="entryUUID",
            email_attribute="mail",
            display_name_attribute="cn",
        )


@pytest.mark.asyncio
async def test_plain_ldap_without_starttls_fails_closed() -> None:
    result = await LdapDirectoryProvider().test_connection(
        DirectoryConnection(
            server_uri="ldap://ldap.example.test",
            use_starttls=False,
            bind_dn="cn=service,dc=example,dc=test",
            bind_password="secret",
            base_dn="dc=example,dc=test",
            timeout_seconds=1,
        )
    )
    assert result.success is False
    assert result.detail_code == "transport_security_required"
