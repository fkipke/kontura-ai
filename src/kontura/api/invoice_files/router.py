"""HTTP-Endpoints fuer Invoice-File-Uploads (tenant-isoliert).

Phase G2.0: Reine Dateispeicherung, Tenant-Isolation, Deduplication.
Phase G2.1: KI-Extraktion als BackgroundTask nach Upload + manuelle Trigger-Endpoints.

Extraction-Endpoints sind im selben Router, da sie logisch zu Invoice-Files gehoeren.
Eigene Datei waere sauberer fuer sehr grosse Teams - hier reicht eine Datei.

Sicherheitsschichten beim Upload (in dieser Reihenfolge):
1. Groesse: max INVOICE_FILE_MAX_BYTES (Standard: 10 MB)
2. MIME-Type: nur PDF, PNG, JPEG oder XML erlaubt
3. Datei-Signatur/XML-Header: verifiziert den echten Dateiinhalt
4. Filename-Sanitisierung: entfernt Pfad-Komponenten, truncated auf 255 Zeichen
"""

import hashlib
import json
import os
import uuid
from typing import Annotated

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from kontura.ai.extraction.service import ExtractionService
from kontura.api.dependencies import (
    AIProviderDep,
    EngineDep,
    FileStorageDep,
    TenantDep,
    TokenDep,
)
from kontura.api.invoice_files.repository import InvoiceFileRepository
from kontura.api.invoice_files.schemas import ExtractionStatusResponse, InvoiceFileResponse
from kontura.api.rate_limit import limiter
from kontura.core.config import settings
from kontura.core.exceptions import NotFoundError
from kontura.core.tenant import TenantContext, current_tenant_var
from kontura.infra.db import get_session
from kontura.infra.models.invoice_file import ExtractionStatus, InvoiceFile

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/invoice-files", tags=["invoice-files"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Erlaubte MIME-Types und ihre Magic-Bytes (erste Bytes der Datei)
_ALLOWED_MIME_TYPES = frozenset(
    [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "application/xml",
        "text/xml",
    ]
)
_XML_MIME_TYPES = frozenset(["application/xml", "text/xml"])

_MAGIC_BYTES: dict[str, bytes] = {
    "application/pdf": b"%PDF-",
    "image/png": b"\x89PNG",
    "image/jpeg": b"\xff\xd8\xff",
}


def _looks_like_xml_text(content: str) -> bool:
    stripped = content.lstrip()
    if stripped.startswith("<?xml"):
        return True
    if not stripped.startswith("<") or len(stripped) < 2:
        return False
    return stripped[1] in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_:"


def _looks_like_xml(content: bytes) -> bool:
    """Prueft defensiv auf XML-Header oder ein direktes Root-Element."""
    if content.startswith(b"\xef\xbb\xbf"):
        content = content[3:]
    elif content.startswith(b"\xff\xfe"):
        try:
            return _looks_like_xml_text(content[2:].decode("utf-16-le"))
        except UnicodeDecodeError:
            return False
    elif content.startswith(b"\xfe\xff"):
        try:
            return _looks_like_xml_text(content[2:].decode("utf-16-be"))
        except UnicodeDecodeError:
            return False

    stripped = content.lstrip()
    if stripped.startswith(b"<?xml"):
        return True
    if not stripped.startswith(b"<") or len(stripped) < 2:
        return False
    return stripped[1:2] in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_:"


def _sanitize_filename(filename: str) -> str:
    """Bereinigt den Dateinamen: entfernt Pfad-Komponenten, max 255 Zeichen."""
    safe = os.path.basename(filename.replace("\\", "/"))
    if not safe:
        safe = "upload"
    return safe[:255]


def _check_magic_bytes(content: bytes, mime_type: str) -> bool:
    """Prueft ob die ersten Bytes des Inhalts zum MIME-Type passen."""
    if mime_type in _XML_MIME_TYPES:
        return _looks_like_xml(content)
    magic = _MAGIC_BYTES.get(mime_type)
    if magic is None:
        return False
    return content[: len(magic)] == magic


def _build_extraction_status_response(invoice_file: InvoiceFile) -> ExtractionStatusResponse:
    """Erstellt den standardisierten Extraction-Status-Response."""
    return ExtractionStatusResponse(
        file_id=invoice_file.id,
        status=invoice_file.extraction_status.value,
        attempts=invoice_file.extraction_attempts,
        extracted_at=invoice_file.extracted_at,  # type: ignore[arg-type]
        error=invoice_file.extraction_error,
        result=invoice_file.extraction_result,
        linked_invoice_id=invoice_file.invoice_id,
    )


async def _run_extraction_in_background(
    engine: AsyncEngine,
    file_id: uuid.UUID,
    tenant: TenantContext,
    ai_provider: object,
    storage: object,
) -> None:
    """Fuehrt die Extraktion in einer eigenen DB-Session durch.

    Eigene Session notwendig, da die Request-Session nach Response-Ende geschlossen ist.
    Engine kommt per DI rein - so kann in Tests die Test-DB-Engine injiziert werden.
    Tenant wird explizit als ContextVar gesetzt (Request-Kontext existiert nicht mehr).
    """
    token = current_tenant_var.set(tenant)
    try:
        bg_session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with bg_session_factory() as bg_session:
            service = ExtractionService(
                ai_provider=ai_provider,  # type: ignore[arg-type]
                storage=storage,  # type: ignore[arg-type]
                session=bg_session,
            )
            await service.extract(tenant, file_id)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "background_extraction_unhandled_error",
            file_id=str(file_id),
            tenant_id=tenant.tenant_id,
            error=repr(exc),
        )
    finally:
        current_tenant_var.reset(token)


@router.post(
    "",
    response_model=InvoiceFileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Laedt eine Rechnungsdatei hoch (PDF/PNG/JPEG/XML)",
    responses={
        200: {"description": "Datei existierte bereits (Deduplication), kein neuer Upload"},
        201: {"description": "Datei erfolgreich hochgeladen, Extraction gestartet"},
        401: {"description": "JWT fehlt oder ungueltig"},
        413: {"description": "Datei zu gross (max 10 MB)"},
        415: {"description": "Nicht unterstuetzter MIME-Type oder Magic-Byte-Mismatch"},
        429: {"description": "Rate-Limit ueberschritten"},
    },
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def upload_invoice_file(
    request: Request,  # noqa: ARG001 - von slowapi benoetigt
    response: Response,  # noqa: ARG001 - von slowapi benoetigt (Header-Injection)
    file: UploadFile,
    tenant: TenantDep,
    token: TokenDep,
    session: SessionDep,
    storage: FileStorageDep,
    ai_provider: AIProviderDep,
    engine: EngineDep,
    background_tasks: BackgroundTasks,
) -> Response:
    """Validiert, dedupliziert und speichert eine Rechnungsdatei."""
    log = logger.bind(tenant_id=tenant.tenant_id)

    content = await file.read()
    if len(content) > settings.invoice_file_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Datei zu gross: {len(content)} Bytes. "
                f"Maximum: {settings.invoice_file_max_bytes} Bytes "
                f"({settings.invoice_file_max_bytes // (1024 * 1024)} MB)."
            ),
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"MIME-Type '{content_type}' nicht unterstuetzt. "
                f"Erlaubt: {sorted(_ALLOWED_MIME_TYPES)}"
            ),
        )

    if not _check_magic_bytes(content, content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Dateiinhalt passt nicht zum angegebenen MIME-Type '{content_type}'. "
                "Dateisignatur-/XML-Validierung fehlgeschlagen."
            ),
        )

    original_name = file.filename or "upload"
    safe_filename = _sanitize_filename(original_name)

    sha256 = hashlib.sha256(content).hexdigest()
    log = log.bind(sha256=sha256[:16], filename=safe_filename)

    repo = InvoiceFileRepository(session)
    existing = await repo.get_by_sha256(tenant, sha256)
    if existing is not None:
        log.info("invoice_file_deduplicated", file_id=str(existing.id))
        response_body = InvoiceFileResponse.from_model(existing)
        response_body = response_body.model_copy(update={"deduplicated": True})
        return Response(
            content=response_body.model_dump_json(),
            status_code=status.HTTP_200_OK,
            media_type="application/json",
            headers={"X-Deduplicated": "true"},
        )

    storage_path = await storage.save(tenant.tenant_id, sha256, content)

    try:
        user_uuid = uuid.UUID(token.sub)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        ) from exc

    invoice_file = await repo.create(
        tenant=tenant,
        uploaded_by_user_id=user_uuid,
        filename=safe_filename,
        mime_type=content_type,
        size_bytes=len(content),
        sha256=sha256,
        storage_path=storage_path,
    )
    await session.commit()
    await session.refresh(invoice_file)

    log.info("invoice_file_uploaded", file_id=str(invoice_file.id))

    # --- G4.1: Synchronous E-Invoice Fast-Path vor AI-BackgroundTask ---
    einvoice_handled = False
    try:
        from kontura.ai.einvoice.service import EinvoiceExtractionService  # noqa: PLC0415
        from kontura.api.invoices.repository import InvoiceRepository  # noqa: PLC0415

        invoice_repo = InvoiceRepository(session)
        einvoice_service = EinvoiceExtractionService(
            session=session,
            invoice_file_repo=repo,
            invoice_repo=invoice_repo,
        )
        result = await einvoice_service.try_extract(
            tenant=tenant,
            invoice_file=invoice_file,
            content_provider=lambda: storage.load(invoice_file.storage_path),
        )
        einvoice_handled = result is not None
        if result is not None:
            await session.refresh(invoice_file)
            log.info(
                "einvoice_extraction_succeeded",
                file_id=str(invoice_file.id),
                method=result.extraction_method,
                zugferd_profile=result.zugferd_profile.value if result.zugferd_profile else None,
            )
    except Exception as exc:  # noqa: BLE001
        log.exception(
            "einvoice_path_unexpected_error",
            file_id=str(invoice_file.id),
            error=repr(exc),
        )
        einvoice_handled = False

    if not einvoice_handled:
        background_tasks.add_task(
            _run_extraction_in_background,
            engine,
            invoice_file.id,
            tenant,
            ai_provider,
            storage,
        )

    response_body = InvoiceFileResponse.from_model(invoice_file)
    return Response(
        content=response_body.model_dump_json(),
        status_code=status.HTTP_201_CREATED,
        media_type="application/json",
        headers={"X-Deduplicated": "false"},
    )


@router.get(
    "",
    response_model=list[InvoiceFileResponse],
    summary="Listet alle Rechnungsdateien des Tenants (sortiert nach Upload-Datum)",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def list_invoice_files(
    request: Request,  # noqa: ARG001 - von slowapi benoetigt
    response: Response,  # noqa: ARG001 - von slowapi benoetigt (Header-Injection)
    tenant: TenantDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    """Listet alle Dateien des Tenants mit X-Total-Count fuer Client-Pagination."""
    repo = InvoiceFileRepository(session)
    files = await repo.list_all(tenant, limit=limit, offset=offset)
    total = await repo.count_all(tenant)

    response_items = [InvoiceFileResponse.from_model(f) for f in files]
    body = json.dumps([item.model_dump(mode="json") for item in response_items], default=str)
    return Response(
        content=body,
        status_code=status.HTTP_200_OK,
        media_type="application/json",
        headers={"X-Total-Count": str(total)},
    )


@router.post(
    "/{file_id}/extract",
    response_model=ExtractionStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Triggert die KI-Extraktion fuer eine Rechnungsdatei manuell",
    responses={
        202: {"description": "Extraktion gestartet oder abgeschlossen"},
        401: {"description": "JWT fehlt oder ungueltig"},
        404: {"description": "Datei nicht gefunden oder anderer Tenant"},
        429: {"description": "Rate-Limit ueberschritten"},
    },
)
@limiter.limit(settings.rate_limit_llm_per_tenant)
async def trigger_extraction(
    request: Request,  # noqa: ARG001 - von slowapi benoetigt
    response: Response,  # noqa: ARG001 - von slowapi benoetigt (Header-Injection)
    file_id: uuid.UUID,
    tenant: TenantDep,
    session: SessionDep,
    storage: FileStorageDep,
    ai_provider: AIProviderDep,
    force: Annotated[bool, Query(description="force=true erzwingt Re-Extraktion")] = False,
) -> ExtractionStatusResponse:
    """Triggert Re-Extraktion mit E-Invoice-Fast-Path vor AI-Fallback."""
    repo = InvoiceFileRepository(session)
    invoice_file = await repo.get_by_id(tenant, file_id)
    if invoice_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"InvoiceFile mit id={file_id} nicht gefunden",
        )

    einvoice_result = None
    try:
        from kontura.ai.einvoice.service import EinvoiceExtractionService  # noqa: PLC0415
        from kontura.api.invoices.repository import InvoiceRepository  # noqa: PLC0415

        invoice_repo = InvoiceRepository(session)
        einvoice_service = EinvoiceExtractionService(
            session=session,
            invoice_file_repo=repo,
            invoice_repo=invoice_repo,
        )
        storage_path = invoice_file.storage_path
        einvoice_result = await einvoice_service.try_extract(
            tenant=tenant,
            invoice_file=invoice_file,
            content_provider=lambda: storage.load(storage_path),
        )
        if einvoice_result is not None:
            await session.refresh(invoice_file)
            logger.info(
                "einvoice_re_extraction_succeeded",
                file_id=str(file_id),
                method=einvoice_result.extraction_method,
            )
            return _build_extraction_status_response(invoice_file)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "einvoice_re_extraction_unexpected_error",
            file_id=str(file_id),
            error=repr(exc),
        )

    if invoice_file.mime_type in _XML_MIME_TYPES and einvoice_result is None:
        invoice_file.extraction_status = ExtractionStatus.FAILED
        invoice_file.extraction_attempts = (invoice_file.extraction_attempts or 0) + 1
        invoice_file.extraction_error = (
            "XML konnte nicht als E-Rechnung interpretiert werden (kein UBL/CII-Root-Element)."
        )
        invoice_file.extraction_result = None
        invoice_file.invoice_id = None
        await session.commit()
        await session.refresh(invoice_file)
        return _build_extraction_status_response(invoice_file)

    service = ExtractionService(
        ai_provider=ai_provider,
        storage=storage,
        session=session,
    )
    try:
        invoice_file = await service.extract(tenant, file_id, force=force)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _build_extraction_status_response(invoice_file)


@router.get(
    "/{file_id}/extraction",
    response_model=ExtractionStatusResponse,
    summary="Liefert den aktuellen Extraktionsstatus einer Rechnungsdatei",
    responses={
        200: {"description": "Extraktionsstatus und -ergebnis"},
        401: {"description": "JWT fehlt oder ungueltig"},
        404: {"description": "Datei nicht gefunden oder anderer Tenant"},
        429: {"description": "Rate-Limit ueberschritten"},
    },
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def get_extraction_status(
    request: Request,  # noqa: ARG001 - von slowapi benoetigt
    response: Response,  # noqa: ARG001 - von slowapi benoetigt (Header-Injection)
    file_id: uuid.UUID,
    tenant: TenantDep,
    session: SessionDep,
) -> ExtractionStatusResponse:
    """Gibt den Extraktionsstatus zurueck."""
    repo = InvoiceFileRepository(session)
    invoice_file = await repo.get_by_id(tenant, file_id)
    if invoice_file is None:
        raise NotFoundError(f"InvoiceFile mit id={file_id} nicht gefunden")

    return ExtractionStatusResponse(
        file_id=invoice_file.id,
        status=invoice_file.extraction_status.value,
        attempts=invoice_file.extraction_attempts,
        extracted_at=invoice_file.extracted_at,  # type: ignore[arg-type]
        error=invoice_file.extraction_error,
        result=invoice_file.extraction_result,
        linked_invoice_id=invoice_file.invoice_id,
    )


@router.get(
    "/{file_id}",
    summary="Liefert den Dateiinhalt als Download",
    responses={
        200: {"description": "Dateiinhalt als Binary-Stream"},
        401: {"description": "JWT fehlt oder ungueltig"},
        404: {"description": "Datei nicht gefunden oder anderer Tenant"},
        429: {"description": "Rate-Limit ueberschritten"},
    },
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def get_invoice_file(
    request: Request,  # noqa: ARG001 - von slowapi benoetigt
    response: Response,  # noqa: ARG001 - von slowapi benoetigt (Header-Injection)
    file_id: uuid.UUID,
    tenant: TenantDep,
    session: SessionDep,
    storage: FileStorageDep,
) -> StreamingResponse:
    """Gibt den Dateiinhalt zurueck - 404 wenn nicht gefunden ODER anderer Tenant."""
    repo = InvoiceFileRepository(session)
    invoice_file = await repo.get_by_id(tenant, file_id)
    if invoice_file is None:
        raise NotFoundError(f"InvoiceFile mit id={file_id} nicht gefunden")

    content = await storage.load(invoice_file.storage_path)

    log = logger.bind(
        tenant_id=tenant.tenant_id,
        file_id=str(file_id),
        sha256=invoice_file.sha256[:16],
    )
    log.info("invoice_file_downloaded")

    return StreamingResponse(
        content=iter([content]),
        media_type=invoice_file.mime_type,
        headers={
            "Content-Disposition": (f'inline; filename="{invoice_file.filename}"'),
            "Content-Length": str(invoice_file.size_bytes),
        },
    )
