from cyrvanta.modules.identity.application.administration_service import AdministrationService
from cyrvanta.modules.incident.application.service import IncidentService


def test_search_patterns_escape_sql_wildcards() -> None:
    expected = r"%50\%\_done\\safe%"
    assert IncidentService._search_pattern(r" 50%_done\safe ") == expected
    assert AdministrationService._search_pattern(r" 50%_done\safe ") == expected


def test_blank_search_patterns_are_ignored() -> None:
    assert IncidentService._search_pattern("   ") is None
    assert AdministrationService._search_pattern(None) is None
