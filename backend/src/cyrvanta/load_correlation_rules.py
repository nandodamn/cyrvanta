"""Load and activate correlation rule versions.

Correlation rules are data, not code: a version lives in
`correlation_rule_versions` as a JSONB definition. Until the administration
service exists there is no API to publish one, and the alternative is pasting
raw SQL into psql -- which leaves no reviewable record of what was activated,
recomputes the canonical hash by hand, and can leave two ACTIVE versions of the
same rule behind if the transaction is written carelessly.

Every rule ID below was read off this deployment's own Wazuh ruleset and its
OpenSearch data on 2026-08-19. None of them is assumed. The verification that
mattered is recorded next to each rule, because a correlation rule that selects
an ID this Wazuh never emits is silently dead.

`--tenant-id` selects whose detection changes. Rules are scoped per tenant
(migration 0026), so activating one here affects that tenant and no other.

    python -m cyrvanta.load_correlation_rules --tenant-id <uuid> --list
    python -m cyrvanta.load_correlation_rules --tenant-id <uuid> --rule <code>
    python -m cyrvanta.load_correlation_rules --tenant-id <uuid> --rule <code> --apply
"""

import argparse
import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import select

from cyrvanta.modules.correlation.application.rule_admin import (
    CorrelationRuleAdminService,
    canonical,
)
from cyrvanta.modules.correlation.infrastructure.models import CorrelationRuleVersionModel
from cyrvanta.modules.identity.infrastructure.models import UserModel
from cyrvanta.shared.database import tenant_session

__all__ = ["RULES", "canonical"]

# `window_minutes` is the real window length: the engine reads it per rule
# since correlation moved to a sliding window.
_COMMON: dict[str, Any] = {
    "threshold": 85,
    "window_minutes": 10,
    "candidate_limit": 500,
    "member_limit": 32,
    "partial_issue_allowlist": [],
}


def _selector(code: str, value: str) -> dict[str, str]:
    return {
        "code": code,
        "field": "rule_reference",
        "value": value,
        "source_system": "wazuh",
    }


RULES: dict[str, dict[str, Any]] = {
    # The scenario the platform was first demonstrated with, minus four dead
    # selectors. Versions 2 and 3 still carried selectors for source_system
    # "cyrvanta-demo-v2" -- a synthetic feed with zero findings in this
    # deployment, inherited from the seed migration and never removed. They
    # could not match anything, and reading the rule suggested the demo feed
    # was still part of detection.
    #
    # 5760 (sshd authentication failed) and 5715 (sshd authentication success)
    # are the two that do the work, grouped by source IP: the same address
    # failing and then succeeding.
    "credential-attack": {
        "version": "4",
        "why": "failed logins then a success from one source address",
        "verified": "5760 and 5715 both emitted by lab-server-01; the removed "
        "cyrvanta-demo-v2 selectors match 0 of 18084 findings",
        "definition": {
            **_COMMON,
            "grouping": "source_ip",
            "selectors": [
                _selector("auth_failure", "5760"),
                _selector("auth_success", "5715"),
            ],
        },
    },
    # Two different kinds of file-integrity change on the same host inside one
    # window. Grouping by asset is what makes this possible at all: syscheck
    # findings carry no source IP, so before asset grouping existed no rule
    # could have correlated them.
    #
    # Registry syscheck (750/752/594/751/597/598) is deliberately excluded.
    # Those fire thousands of times on CYRVANTA-WINDOWS-LAB (750 alone: 2057
    # events) and all belong to one asset, so including them would open an
    # incident in nearly every window -- the rule would be a noise generator,
    # not a detection.
    "host-integrity-compromise": {
        "version": "1",
        "why": "FIM: two distinct file-integrity signals on the same host",
        "verified": "550/553/554 emitted by lab-server-01 and CYRVANTA-WINDOWS-LAB; "
        "592 present in the ruleset at level 8",
        "definition": {
            **_COMMON,
            "grouping": "asset",
            "selectors": [
                _selector("file_added", "554"),
                _selector("file_modified", "550"),
                _selector("file_deleted", "553"),
                _selector("log_tampering", "592"),
            ],
        },
    },
    # Wazuh has already done the aggregating here: 5763/5712/5551/5404 are
    # composite rules that only fire after 8 failures inside their own
    # timeframe. Waiting for a second, different signal before calling that an
    # incident would be waiting for an attack to succeed.
    #
    # All four are level 10, which the normalizer maps to severity 70
    # (level * 7), so min_severity is 70. Historical volume is zero: none of
    # them has ever fired in this deployment.
    "critical-single-signal": {
        "version": "1",
        "why": "one Wazuh composite alert grave enough to stand alone",
        "verified": "5763/5712 level 10 freq 8 timeframe 120, 5551 level 10 freq 8 "
        "timeframe 180, 5404 level 10 -- read from /var/ossec/ruleset/rules",
        "definition": {
            **_COMMON,
            "grouping": "asset",
            "min_severity": 70,
            "selectors": [
                _selector("brute_force_known_user", "5763"),
                _selector("brute_force_unknown_user", "5712"),
                _selector("pam_repeated_failure", "5551"),
                _selector("sudo_repeated_failure", "5404"),
            ],
        },
    },
    # Everything this Wazuh considers serious, without naming any of it.
    #
    # The enumerated rules above cover 13 of the ~70 IDs this deployment
    # actually emits, and a list like that rots: every ruleset update adds
    # detections nobody wrote down. In this data, 23506 (level 13) and 61061
    # (level 10) were passing unseen for exactly that reason.
    #
    # 84 is Wazuh level 12 (the normalizer maps level * 7), the point at which
    # Wazuh itself is claiming something serious rather than notable. Historic
    # volume at that level is 13 events, all one CVE, so this is not a flood --
    # but it is the rule most worth re-checking against `preview` after a
    # ruleset upgrade, since its whole purpose is to catch what nobody listed.
    "wazuh-critical-severity": {
        "version": "1",
        "why": "any alert Wazuh itself rates level 12 or higher",
        "verified": "level 12 = severity 84 via normalizer (level * 7); only 23506 "
        "(level 13, 13 events) currently qualifies in this deployment",
        "definition": {
            **_COMMON,
            "grouping": "asset",
            "min_severity": 84,
            "selectors": [
                {
                    "code": "wazuh_critical",
                    "field": "severity",
                    "value": "84",
                    "source_system": "wazuh",
                }
            ],
        },
    },
    # A remote login followed by escalation to root on the same host.
    #
    # The plan specified this rule over Windows logon events grouped by source
    # IP. That is not implementable here and would not be worth implementing:
    # 60118 and 67028 carry no data.srcip in any of the 3194 events checked, so
    # source_ip grouping can never match; and 67028 ("special privileges
    # assigned to new logon", Windows event 4672) fires on every administrator
    # logon, so pairing it with a logon success detects normal administration.
    # The sudo path below describes the same attacker behaviour with signals
    # that exist and mean something.
    #
    # Note this is deliberately sensitive: an administrator who legitimately
    # connects and runs sudo will match it. That is acceptable in the lab,
    # where no legitimate sudo traffic exists, but a production tenant would
    # want the sudo user allowlisted first.
    "privilege-escalation": {
        "version": "1",
        "why": "remote login plus privilege escalation on the same host",
        "verified": "5715 emitted by lab-server-01; 5401/5402/5403 present in the "
        "ruleset; /var/log/secure is monitored so authpriv reaches Wazuh",
        "definition": {
            **_COMMON,
            "grouping": "asset",
            "selectors": [
                _selector("remote_login", "5715"),
                _selector("sudo_to_root", "5402"),
                _selector("sudo_first_time", "5403"),
                _selector("sudo_failed", "5401"),
            ],
        },
    },
}


async def load(tenant_id: UUID, code: str, *, apply: bool) -> None:
    entry = RULES[code]
    definition = entry["definition"]
    _text, digest = canonical(definition)

    async with tenant_session(tenant_id) as session:
        active = (
            await session.scalars(
                select(CorrelationRuleVersionModel).where(
                    CorrelationRuleVersionModel.tenant_id == tenant_id,
                    CorrelationRuleVersionModel.rule_code == code,
                    CorrelationRuleVersionModel.status == "ACTIVE",
                )
            )
        ).all()

        print(f"Regla      : {code}")
        print(f"Version    : {entry['version']}")
        print(f"Motivo     : {entry['why']}")
        print(f"Verificado : {entry['verified']}")
        print(f"Agrupacion : {definition['grouping']}")
        if "min_severity" in definition:
            print(f"Severidad  : minimo {definition['min_severity']} (senal unica)")
        print(f"Selectores : {', '.join(s['value'] for s in definition['selectors'])}")
        print(f"sha256     : {digest}")

        if any(row.definition_sha256 == digest for row in active):
            print("\nYa esta activa con esta misma definicion. No hay nada que hacer.")
            return
        for row in active:
            print(f"\nSe retirara la version {row.version} actualmente ACTIVE.")

        if not apply:
            print("\nSimulacion. Volve a ejecutar con --apply para aplicarlo.")
            return

        actor_id = await session.scalar(
            select(UserModel.id).where(UserModel.tenant_id == tenant_id).limit(1)
        )
        if actor_id is None:
            raise SystemExit("No hay usuarios en el tenant; no se puede atribuir la operacion.")

        # The service owns validation, the canonical hash, the transactional
        # retire-then-activate and the audit trail. This script only decides
        # which catalogue entry to publish.
        service = CorrelationRuleAdminService(session)
        draft = await service.create_draft(
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            rule_code=code,
            version=entry["version"],
            definition=definition,
        )
        await service.activate(tenant_id=tenant_id, actor_user_id=actor_id, version_id=draft.id)
        print(f"\nActivada {code} v{entry['version']}. Registrado en auditoria.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--rule", choices=sorted(RULES))
    parser.add_argument("--list", action="store_true", help="Muestra las reglas disponibles.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios. Sin este argumento solo muestra que haria.",
    )
    args = parser.parse_args()
    if args.list or not args.rule:
        for code, entry in sorted(RULES.items()):
            print(f"{code:<28} v{entry['version']:<3} {entry['why']}")
        return
    asyncio.run(load(args.tenant_id, args.rule, apply=args.apply))


if __name__ == "__main__":
    main()
