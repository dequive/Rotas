from uuid import uuid4

import pytest

from app.core.auth import Principal
from app.core.errors import ApiError
from app.modules.platform.service import require_platform_actor


def test_platform_actor_returns_auditable_identity():
    user_id = uuid4()
    principal = Principal(
        subject="test:platform",
        tenant_id=None,
        scope="platform",
        user_id=user_id,
        role="platform_admin",
    )

    assert require_platform_actor(principal) == (user_id, "platform_admin")


@pytest.mark.parametrize(
    "principal",
    [
        Principal(subject="test:tenant", tenant_id=uuid4(), scope="dashboard"),
        Principal(subject="test:platform", tenant_id=None, scope="platform"),
        Principal(
            subject="test:platform",
            tenant_id=None,
            scope="platform",
            user_id=uuid4(),
        ),
    ],
)
def test_platform_actor_rejects_incomplete_or_tenant_identity(principal: Principal):
    with pytest.raises(ApiError) as captured:
        require_platform_actor(principal)

    assert captured.value.code == "platform_identity_required"
    assert captured.value.status_code == 403
