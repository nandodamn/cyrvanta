"""Read numbers out of configuration that arrives as untyped JSON.

Integration configuration is stored encrypted and decrypted into
`dict[str, object]`, which is the honest type: the values come from JSON an
operator supplied, so nothing in the type system knows a timeout is a number.
Calling `int(value)` on that is a type error, and typing the dictionaries as
`Any` would silence the checks that *are* meaningful on the same values -- the
`str(...)` coercions right next to them.

These keep the existing behaviour deliberately: a malformed value raises rather
than falling back to a default. A timeout of "abc" is a misconfiguration, and
quietly substituting ten seconds would hide it until someone wondered why a
connector behaves differently from what its configuration says.
"""

from __future__ import annotations


def as_int(value: object, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise TypeError("configuration value must be a number, not a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(float(value))
    raise TypeError(f"configuration value cannot be read as a number: {type(value).__name__}")


def as_float(value: object, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        raise TypeError("configuration value must be a number, not a boolean")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError(f"configuration value cannot be read as a number: {type(value).__name__}")
