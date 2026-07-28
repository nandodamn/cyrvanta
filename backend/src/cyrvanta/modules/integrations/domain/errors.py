from enum import StrEnum


class ConnectorErrorCode(StrEnum):
    CONNECTOR_UNAVAILABLE = "CONNECTOR_UNAVAILABLE"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    TLS_ERROR = "TLS_ERROR"
    SOURCE_TIMEOUT = "SOURCE_TIMEOUT"
    SOURCE_SCHEMA_CHANGED = "SOURCE_SCHEMA_CHANGED"
    CURSOR_INVALID = "CURSOR_INVALID"
    SEARCH_FAILED = "SEARCH_FAILED"
    EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"


class ConnectorError(Exception):
    def __init__(self, code: ConnectorErrorCode, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(f"{code.value}: {safe_message}")


class UnsupportedCapabilityError(ConnectorError):
    def __init__(self, capability: str) -> None:
        super().__init__(
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            f"Connector capability is not available: {capability}",
        )

