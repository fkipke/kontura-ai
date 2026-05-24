"""HTTP-Endpoints fuer Invoice-File-Uploads (tenant-isoliert).

Phase G2.0: Reine Dateispeicherung, keine KI-Extraktion.
G2.1 wird diesen Router mit AI-Extraktion verbinden.

Sicherheitsschichten beim Upload (in dieser Reihenfolge):
1. Groesse: max INVOICE_FILE_MAX_BYTES (Standard: 10 MB)
2. MIME-Type: nur PDF, PNG, JPEG erlaubt
3. Magic-Bytes: verifiziert den echten Dateiinhalt (verhindert Extension-Spoofing)
4. Filename-Sanitisierung: entfernt Pfad-Komponenten, truncated auf 255 Zeichen
"""

import hashlib
import json
import os
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.dependencies import FileStorageDep, TenantDep, TokenDep
from kontura.api.invoice_files.repository import InvoiceFileRepository
from kontura.api.invoice_files.schemas import InvoiceFileResponse
from kontura.api.rate_limit import limiter
from kontura.core.config import settings
from kontura.core.exceptions import NotFoundError
from kontura.infra.db import get_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/invoice-files", tags=["invoice-files"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Erlaubte MIME-Types und ihre Magic-Bytes (erste Bytes der Datei)
_ALLOWED_MIME_TYPES = frozenset(["application/pdf", "image/png", "image/jpeg"])

_MAGIC_BYTES: dict[str, bytes] = {
    "application/pdf": b"%PDF-",
    "image/png": b"\x89PNG",
    "image/jpeg": b"\xff\xd8\xff",
}


def _sanitize_filename(filename: str) -> str:
    """Bereinigt den Dateinamen: entfernt Pfad-Komponenten, max 255 Zeichen.

    Verhindert Path-Traversal-Angriffe (z.B. '../../etc/passwd').
    os.path.basename extrahiert nur den letzten Komponenten.
    """
    # Entfernt Pfad-Komponenten auf beiden Plattformen
    safe = os.path.basename(filename.replace("\\", "/"))
    # Fallback wenn nur Slashes kommen
    if not safe:
        safe = "upload"
    # Max 255 Zeichen (Dateisystem-Limit)
    return safe[:255]


def _check_magic_bytes(content: bytes, mime_type: str) -> bool:
    """Prueft ob die ersten Bytes des Inhalts zum MIME-Type passen.

    Verhindert Extension-Spoofing: jemand benennt eine .txt-Datei in .pdf um.
    Der MIME-Type im Content-Type-Header ist Client-seitig manipulierbar -
    die Magic-Bytes im Dateiinhalt nicht.
    """
    magic = _MAGIC_BYTES.get(mime_type)
    if magic is None:
        return False
    return content[: len(magic)] == magic


@router.post(
    "",
    response_model=InvoiceFileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Laedt eine Rechnungsdatei hoch (PDF/PNG/JPEG)",
    responses={
        200: {"description": "Datei existierte bereits (Deduplication), kein neuer Upload"},
        201: {"description": "Datei erfolgreich hochgeladen"},
        401: {"description": "JWT fehlt oder ungueltig"},
        413: {"description": "Datei zu gross (max 10 MB)"},
        415: {"description": "Nicht unterstuetzter MIME-Type oder Magic-Byte-Mismatch"},
        429: {"description": "Rate-Limit ueberschritten"},
    },
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def upload_invoice_file(
    request: Request,  # noqa: ARG001 - von slowapi benoetigt
    file: UploadFile,
    tenant: TenantDep,
    token: TokenDep,
    session: SessionDep,
    storage: FileStorageDep,
) -> Response:
    """Validiert, dedupliziert und speichert eine Rechnungsdatei.

    Gibt HTTP 201 zurueck wenn die Datei neu ist, HTTP 200 wenn sie schon existierte.
    X-Deduplicated: true Header zeigt dem Client, ob es ein Duplikat war.
    """
    log = logger.bind(tenant_id=tenant.tenant_id)

    # --- 1. Groessen-Check ---
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

    # --- 2. MIME-Type-Check ---
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"MIME-Type '{content_type}' nicht unterstuetzt. "
                f"Erlaubt: {sorted(_ALLOWED_MIME_TYPES)}"
            ),
        )

    # --- 3. Magic-Bytes-Check (verhindert Extension-Spoofing) ---
    if not _check_magic_bytes(content, content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Dateiinhalt passt nicht zum angegebenen MIME-Type '{content_type}'. "
                "Magic-Byte-Validierung fehlgeschlagen."
            ),
        )

    # --- 4. Filename-Sanitisierung ---
    original_name = file.filename or "upload"
    safe_filename = _sanitize_filename(original_name)

    # --- SHA-256 berechnen ---
    sha256 = hashlib.sha256(content).hexdigest()
    log = log.bind(sha256=sha256[:16], filename=safe_filename)

    # --- Deduplication-Check ---
    repo = InvoiceFileRepository(session)
    existing = await repo.get_by_sha256(tenant, sha256)
    if existing is not None:
        log.info("invoice_file_deduplicated", file_id=str(existing.id))
        response_body = InvoiceFileResponse.model_validate(existing)
        response_body = response_body.model_copy(update={"deduplicated": True})
        return Response(
            content=response_body.model_dump_json(),
            status_code=status.HTTP_200_OK,
            media_type="application/json",
            headers={"X-Deduplicated": "true"},
        )

    # --- Datei speichern ---
    storage_path = await storage.save(tenant.tenant_id, sha256, content)

    # --- Datenbankzeile anlegen ---
    # sub aus JWT ist die User-ID (UUID als String)
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

    response_body = InvoiceFileResponse.model_validate(invoice_file)
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
    tenant: TenantDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    """Listet alle Dateien des Tenants mit X-Total-Count fuer Client-Pagination."""
    repo = InvoiceFileRepository(session)
    files = await repo.list_all(tenant, limit=limit, offset=offset)
    total = await repo.count_all(tenant)

    response_items = [InvoiceFileResponse.model_validate(f) for f in files]
    body = json.dumps([item.model_dump(mode="json") for item in response_items], default=str)
    return Response(
        content=body,
        status_code=status.HTTP_200_OK,
        media_type="application/json",
        headers={"X-Total-Count": str(total)},
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
    file_id: uuid.UUID,
    tenant: TenantDep,
    session: SessionDep,
    storage: FileStorageDep,
) -> StreamingResponse:
    """Gibt den Dateiinhalt zurueck - 404 wenn nicht gefunden ODER anderer Tenant.

    Kein Info-Leak: Wir sagen nicht ob die Datei existiert aber einem anderen Tenant
    gehoert. 404 in beiden Faellen.
    """
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
