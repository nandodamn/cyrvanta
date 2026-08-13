from email.headerregistry import Address


def contains_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def is_safe_single_mailbox(value: object) -> bool:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not 3 <= len(value) <= 254
        or contains_control_characters(value)
    ):
        return False
    try:
        address = Address(addr_spec=value)
    except ValueError:
        return False
    return bool(address.username and address.domain)
