from dataclasses import dataclass

SELECTOR_TECHNIQUES = {
    "auth_failure": "T1110",
    "auth_success": "T1078",
    "privilege_change": "T1098",
}


@dataclass(frozen=True, slots=True)
class MappingCandidate:
    technique_external_id: str
    selector_codes: tuple[str, ...]


def map_credential_attack(
    rule_code: str, rule_version: str, selectors: tuple[str, ...]
) -> tuple[MappingCandidate, ...]:
    if (rule_code, rule_version) != ("credential-attack", "2"):
        return ()
    unique = set(selectors)
    return tuple(
        MappingCandidate(technique, (selector,))
        for selector, technique in SELECTOR_TECHNIQUES.items()
        if selector in unique
    )
