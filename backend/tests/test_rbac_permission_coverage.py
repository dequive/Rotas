"""F7.4: every declared permission must actually gate something.

A permission that no endpoint requires is worse than a missing permission: the
policy reads as if the capability were restricted, roles are granted or denied
it in `ROLE_PERMISSIONS`, reviewers reason about it — and none of it has any
effect, because the endpoint it was meant to protect is gated by a broader
permission that more roles already hold.

This module derives the set of enforced permissions from the source, so the
gap cannot be hidden by a stale hand-written list. The permissions known to be
unenforced today are recorded in `UNENFORCED_ON_PURPOSE` with the reason and
what actually gates the endpoint instead. Adding a new permission without
wiring it to a route fails this module immediately.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.rbac import ROLE_PERMISSIONS

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RBAC_SOURCE = BACKEND_ROOT / "app" / "core" / "rbac.py"
MODULES_ROOT = BACKEND_ROOT / "app" / "modules"


# Permission constant -> why it gates nothing yet, and what guards the surface
# instead. Every entry here is real RBAC debt, tracked in the F7.4 row of
# docs/FRONTEND_REFOUNDATION_PLAN.md — not a permanent exemption.
UNENFORCED_ON_PURPOSE: dict[str, str] = {
    "WORKSHOP_RELEASE": (
        "No vehicle-release endpoint exists yet; app/modules/workshop/router.py "
        "keeps the constant alive with an explicit reserved marker."
    ),
    "WORKSHOP_QUOTE": (
        "Quote creation is gated by WORKSHOP_WRITE in workshop/quote_router.py."
    ),
    "WORKSHOP_QUOTE_APPROVE": (
        "Quote approval is gated by WORKSHOP_WRITE, so mechanic and receptionist "
        "can approve quotes they were never granted approval rights over."
    ),
    "WORKSHOP_RECEPTION": (
        "Vehicle reception is gated by WORKSHOP_WRITE in workshop/reception_router.py."
    ),
    "CARGO_VALIDATE": (
        "Delivery-proof validate/dispute/resolve are gated by CARGO_WRITE, so the "
        "same principal that records a delivery can validate it — the separation "
        "of duties this permission exists for is not enforced."
    ),
    "HR_SALARY_VIEW": (
        "GET /api/v1/hr/payroll is gated by HR_READ and returns gross_salary and "
        "net_salary, so manager and viewer read payroll despite not holding this "
        "permission — and the viewer block in rbac.py states 'no salary visibility'."
    ),
    "ACCOUNTING_REVERSE": "No reversal endpoint requires it yet.",
    "PAYABLES_APPROVE": "No approval endpoint requires it yet.",
    "ADMIN_TENANT": "Tenant administration is guarded by scope, not by this permission.",
}


def declared_permissions() -> set[str]:
    """Permission constants declared in rbac.py, by name."""
    source = RBAC_SOURCE.read_text(encoding="utf-8")
    return set(re.findall(r'^([A-Z][A-Z0-9_]*)\s*=\s*"', source, re.M))


def enforced_permissions() -> set[str]:
    """Permission constants named inside a require_permission/require_platform_role call."""
    enforced: set[str] = set()
    for path in MODULES_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        for call in re.findall(r"require_(?:permission|platform_role)\(([^)]*)\)", source):
            enforced.update(re.findall(r"[A-Z][A-Z0-9_]*", call))
    return enforced


def test_no_new_permission_is_declared_without_gating_a_route() -> None:
    declared = declared_permissions()
    enforced = enforced_permissions()

    unenforced = declared - enforced - set(UNENFORCED_ON_PURPOSE)

    assert not unenforced, (
        "Permissoes declaradas que nao protegem nenhuma rota: "
        f"{sorted(unenforced)}.\n"
        "Uma permissao que nenhum endpoint exige nao restringe nada, mas faz a "
        "politica parecer mais apertada do que e. Ligue-a a uma rota, ou "
        "declare-a em UNENFORCED_ON_PURPOSE com o motivo e o que guarda a "
        "superficie entretanto."
    )


def test_recorded_debt_is_still_real() -> None:
    """The allowlist must shrink, never rot.

    If a permission in `UNENFORCED_ON_PURPOSE` starts gating a route, the entry
    is stale and has to go — otherwise the list slowly becomes a place where
    permissions hide forever.
    """
    enforced = enforced_permissions()
    now_enforced = sorted(name for name in UNENFORCED_ON_PURPOSE if name in enforced)

    assert not now_enforced, (
        f"Estas permissoes ja protegem rotas e devem sair de UNENFORCED_ON_PURPOSE: "
        f"{now_enforced}"
    )


def test_allowlisted_permissions_still_exist() -> None:
    """Guard against the allowlist outliving the constant it names."""
    declared = declared_permissions()
    missing = sorted(name for name in UNENFORCED_ON_PURPOSE if name not in declared)

    assert not missing, (
        f"UNENFORCED_ON_PURPOSE refere permissoes que ja nao existem em rbac.py: {missing}"
    )


def test_every_role_permission_is_a_declared_constant() -> None:
    """Roles must not be granted permission strings that no constant backs.

    A typo in a role's frozenset would grant a permission no endpoint checks —
    silently removing the capability from that role rather than adding it.
    """
    source = RBAC_SOURCE.read_text(encoding="utf-8")
    declared_values = set(re.findall(r'^[A-Z][A-Z0-9_]*\s*=\s*"([^"]+)"', source, re.M))

    granted: set[str] = set()
    for perms in ROLE_PERMISSIONS.values():
        granted.update(perms)

    unknown = sorted(granted - declared_values)
    assert not unknown, (
        f"Papeis recebem permissoes sem constante correspondente em rbac.py: {unknown}"
    )
