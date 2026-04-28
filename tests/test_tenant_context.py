"""Unit-Tests fuer TenantContext-Validierung."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kontura.core.tenant import TenantContext


def test_valid_tenant_id_accepted() -> None:
    ctx = TenantContext(tenant_id="acme-corp")
    assert ctx.tenant_id == "acme-corp"


def test_valid_tenant_id_with_underscores_and_digits() -> None:
    ctx = TenantContext(tenant_id="customer_42")
    assert ctx.tenant_id == "customer_42"


def test_uppercase_tenant_id_rejected() -> None:
    with pytest.raises(ValidationError):
        TenantContext(tenant_id="ACME")


def test_tenant_id_with_special_chars_rejected() -> None:
    with pytest.raises(ValidationError):
        TenantContext(tenant_id="acme.corp")


def test_too_short_tenant_id_rejected() -> None:
    with pytest.raises(ValidationError):
        TenantContext(tenant_id="a")


def test_too_long_tenant_id_rejected() -> None:
    with pytest.raises(ValidationError):
        TenantContext(tenant_id="x" * 65)


def test_tenant_context_is_frozen() -> None:
    ctx = TenantContext(tenant_id="acme")
    with pytest.raises(ValidationError):
        ctx.tenant_id = "evil"


def test_tenant_context_str_returns_id() -> None:
    ctx = TenantContext(tenant_id="acme-corp")
    assert str(ctx) == "acme-corp"
