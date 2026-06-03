"""HTTP-Endpoints fuer Eingangsrechnungen (tenant-isoliert + rate-limited)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.dependencies import TenantDep, TokenDep
from kontura.api.invoices.repository import InvoiceRepository
from kontura.api.invoices.schemas import (
    InvoiceCreate,
    InvoiceRead,
    InvoiceResponse,
    InvoiceUpdateRequest,
    ValidationWarning,
)
from kontura.api.rate_limit import limiter
from kontura.api.vendor_mappings.repository import VendorMappingRepository
from kontura.api.vendor_mappings.service import VendorMappingService
from kontura.core.config import settings
from kontura.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from kontura.infra.db import get_session

router = APIRouter(prefix="/invoices", tags=["Invoices"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_SUPPORTED_CURRENCIES = {"EUR", "USD", "CHF"}


@router.post(
    "",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Legt eine neue Eingangsrechnung an",
    responses={
        401: {"description": "JWT fehlt oder ungueltig"},
        409: {"description": "Rechnungsnummer existiert bereits fuer diesen Tenant"},
        429: {"description": "Rate-Limit ueberschritten"},
    },
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def create_invoice(
    request: Request,  # noqa: ARG001 - von slowapi gebraucht
    payload: InvoiceCreate,
    tenant: TenantDep,
    session: SessionDep,
) -> InvoiceRead:
    repo = InvoiceRepository(session)
    try:
        invoice = await repo.create(tenant, payload)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            f"Rechnungsnummer '{payload.invoice_number}' existiert bereits "
            f"fuer Tenant '{tenant.tenant_id}'."
        ) from exc
    await session.refresh(invoice)
    return InvoiceRead.model_validate(invoice)


@router.get(
    "",
    response_model=list[InvoiceRead],
    summary="Listet Eingangsrechnungen (sortiert nach Anlage-Datum)",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def list_invoices(
    request: Request,  # noqa: ARG001 - von slowapi gebraucht
    tenant: TenantDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[InvoiceRead]:
    repo = InvoiceRepository(session)
    invoices = await repo.list_all(tenant, limit=limit, offset=offset)
    return [InvoiceRead.model_validate(inv) for inv in invoices]


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Liefert eine einzelne Eingangsrechnung",
    responses={404: {"description": "Rechnung nicht gefunden (im Tenant)"}},
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def get_invoice(
    request: Request,  # noqa: ARG001 - von slowapi gebraucht
    response: Response,  # noqa: ARG001 - slowapi Header-Injection
    invoice_id: uuid.UUID,
    tenant: TenantDep,
    session: SessionDep,
) -> InvoiceResponse:
    repo = InvoiceRepository(session)
    invoice = await repo.get_by_id(tenant, invoice_id)
    if invoice is None:
        raise NotFoundError(f"Invoice mit id={invoice_id} nicht gefunden")
    return InvoiceResponse.from_invoice(invoice)


def _compute_warnings(invoice: object) -> list[ValidationWarning]:
    """Soft-Validation: berechnet Warnungen aus dem gespeicherten Invoice-Stand."""
    warnings: list[ValidationWarning] = []

    net = getattr(invoice, "net_amount", None)
    tax = getattr(invoice, "tax_amount", None)
    total = getattr(invoice, "total_amount", None)
    currency = getattr(invoice, "currency", None)

    if net is not None and tax is not None and total is not None:
        computed = Decimal(str(net)) + Decimal(str(tax))
        total_dec = Decimal(str(total))
        if abs(computed - total_dec) > Decimal("0.01"):
            warnings.append(
                ValidationWarning(
                    code="ust_total_mismatch",
                    message=(
                        f"Netto + Steuer ({computed:.2f} €) weicht vom "
                        f"Gesamtbetrag ({total_dec:.2f} €) ab. "
                        "Multi-Tax-Sätze sind möglich — bitte prüfen."
                    ),
                    field="total_amount",
                )
            )

    if currency and currency != "EUR":
        warnings.append(
            ValidationWarning(
                code="unusual_currency",
                message=(f"Währung {currency!r} ist für deutsche Steuerberater ungewöhnlich."),
                field="currency",
            )
        )

    return warnings


@router.patch(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Aktualisiert Felder einer Rechnung (Optimistic Locking + Audit-Trail)",
    responses={
        200: {"description": "Erfolgreich aktualisiert (inkl. validation_warnings)"},
        401: {"description": "JWT fehlt"},
        404: {"description": "Rechnung nicht gefunden oder anderer Tenant"},
        409: {"description": "Optimistic-Lock-Konflikt \u2014 Server-Version aktueller"},
        422: {"description": "Validation-Fehler (z.B. Datum in Zukunft)"},
        429: {"description": "Rate-Limit"},
    },
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def update_invoice(
    request: Request,  # noqa: ARG001 - slowapi
    response: Response,  # noqa: ARG001 - slowapi Header-Injection (PFLICHT, sonst 500!)
    invoice_id: uuid.UUID,
    payload: InvoiceUpdateRequest,
    tenant: TenantDep,
    token: TokenDep,
    session: SessionDep,
) -> InvoiceResponse:
    """PATCH /invoices/{invoice_id} - editiert Rechnungsfelder GoBD-konform.

    - Optimistic Locking via expected_version (409 bei Konflikt)
    - Hard-Validation: currency, invoice_date (422)
    - Soft-Validation: USt-Mismatch → ValidationWarning (NICHT 422, NICHT blockierend)
    - Audit-Trail: jedes geaenderte Feld → invoice_edits-Eintrag
    - is_reviewed=true speicherbar auch mit Warnings
    """
    repo = InvoiceRepository(session)
    user_id = uuid.UUID(token.sub)

    # 1. Laden (tenant-isoliert)
    invoice = await repo.get_by_id(tenant, invoice_id)
    if invoice is None:
        raise NotFoundError(f"Invoice {invoice_id} nicht gefunden")

    # 2. Optimistic Lock
    if payload.expected_version != invoice.version:
        current_response = InvoiceResponse.from_invoice(invoice, _compute_warnings(invoice))
        return JSONResponse(  # type: ignore[return-value]
            status_code=409,
            content={
                "detail": "Die Rechnung wurde zwischenzeitlich ge\u00e4ndert. Bitte lade neu.",
                "current_version": invoice.version,
                "current_state": current_response.model_dump(mode="json"),
            },
        )

    # 3. Hard-Validation
    if payload.currency is not None and payload.currency not in _SUPPORTED_CURRENCIES:
        raise DomainValidationError("Nicht unterst\u00fctzte W\u00e4hrung.")
    if payload.invoice_date is not None and payload.invoice_date > date.today():
        raise DomainValidationError("Rechnungsdatum darf nicht in der Zukunft liegen.")

    # 4. Diff berechnen (gesetzte Felder, ohne expected_version/is_reviewed)
    editable_fields = {
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "net_amount",
        "tax_amount",
        "total_amount",
        "currency",
        "line_items",
    }
    changes: dict[str, object] = {}
    for field in editable_fields:
        if field in payload.model_fields_set:
            new_val = getattr(payload, field)
            changes[field] = new_val

    # 5. is_reviewed-Sonderfall
    is_reviewed_change = None
    reviewed_at = None
    reviewed_by_user_id = None
    if "is_reviewed" in payload.model_fields_set and payload.is_reviewed is not None:
        is_reviewed_change = payload.is_reviewed
        if payload.is_reviewed:
            reviewed_at = datetime.now(tz=UTC)
            reviewed_by_user_id = user_id
        else:
            reviewed_at = None
            reviewed_by_user_id = None

    # 6. Atomarer Update + Audit-Inserts + version++ (alles in einer Transaktion)
    invoice = await repo.update_with_audit(
        invoice,
        changes,
        user_id=user_id,
        is_reviewed_change=is_reviewed_change,
        reviewed_at=reviewed_at,
        reviewed_by_user_id=reviewed_by_user_id,
    )
    if payload.creditor_account_number is not None and invoice.vendor_name:
        mapping_service = VendorMappingService(VendorMappingRepository(session))
        await mapping_service.record_mapping(
            tenant,
            vendor_name_raw=invoice.vendor_name,
            creditor_account_number=payload.creditor_account_number,
        )
    await session.commit()
    await session.refresh(invoice)

    # 7. Soft-Validation aus gespeichertem Stand
    warnings = _compute_warnings(invoice)

    return InvoiceResponse.from_invoice(invoice, warnings if warnings else None)
