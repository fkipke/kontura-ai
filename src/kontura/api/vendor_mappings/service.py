"""Service fuer Vendor→Kreditor-Mappings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import structlog

from kontura.api.vendor_mappings.normalize import normalize_vendor_name
from kontura.api.vendor_mappings.repository import VendorMappingRepository
from kontura.core.tenant import TenantContext
from kontura.infra.models.vendor_account_mapping import VendorAccountMapping

logger = structlog.get_logger(__name__)

_AUTO_APPLY_THRESHOLD = 0.8
_FUZZY_MAX_DISTANCE = 2
_FUZZY_LIST_LIMIT = 5000


@dataclass(frozen=True)
class MappingSuggestion:
    """Ein Vorschlag fuer ein Kreditor-Konto basierend auf einem Vendor-Namen."""

    creditor_account_number: int
    vendor_name_raw: str
    usage_count: int
    last_used_at: datetime
    confidence: float
    match_type: Literal["exact", "fuzzy"]
    auto_apply: bool


def calculate_confidence(usage_count: int) -> float:
    """Confidence-Score basierend auf Usage."""
    if usage_count <= 0:
        return 0.0
    if usage_count >= 5:
        return 1.0
    return usage_count / 5.0


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            cost = 0 if left_char == right_char else 1
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + cost,
                )
            )
        previous = current
    return previous[-1]


def _length_difference_ratio(left: str, right: str) -> float:
    longest = max(len(left), len(right), 1)
    return abs(len(left) - len(right)) / longest


class VendorMappingService:
    def __init__(self, repository: VendorMappingRepository) -> None:
        self._repository = repository

    async def suggest_for_vendor(
        self, tenant: TenantContext, vendor_name_raw: str
    ) -> MappingSuggestion | None:
        normalized = normalize_vendor_name(vendor_name_raw)
        if not normalized:
            return None

        exact = await self._repository.get_exact(tenant, normalized)
        if exact is not None:
            confidence = calculate_confidence(exact.usage_count)
            return MappingSuggestion(
                creditor_account_number=exact.creditor_account_number,
                vendor_name_raw=exact.vendor_name_raw,
                usage_count=exact.usage_count,
                last_used_at=exact.last_used_at,
                confidence=confidence,
                match_type="exact",
                auto_apply=confidence >= _AUTO_APPLY_THRESHOLD,
            )

        mappings = await self._repository.list_for_tenant(tenant, limit=_FUZZY_LIST_LIMIT)
        best_match: VendorAccountMapping | None = None
        best_distance: int | None = None

        for mapping in mappings:
            ratio = _length_difference_ratio(normalized, mapping.vendor_name_normalized)
            if ratio > 0.3:
                continue

            distance = _levenshtein_distance(normalized, mapping.vendor_name_normalized)
            if distance > _FUZZY_MAX_DISTANCE:
                continue

            if (
                best_match is None
                or best_distance is None
                or distance < best_distance
                or (distance == best_distance and mapping.last_used_at > best_match.last_used_at)
            ):
                best_match = mapping
                best_distance = distance

        if best_match is None:
            logger.info(
                "vendor_mapping_suggestion_missing",
                tenant_id=tenant.tenant_id,
                vendor_name_raw=vendor_name_raw,
                vendor_name_normalized=normalized,
            )
            return None

        confidence = calculate_confidence(best_match.usage_count) / 2
        return MappingSuggestion(
            creditor_account_number=best_match.creditor_account_number,
            vendor_name_raw=best_match.vendor_name_raw,
            usage_count=best_match.usage_count,
            last_used_at=best_match.last_used_at,
            confidence=confidence,
            match_type="fuzzy",
            auto_apply=confidence >= _AUTO_APPLY_THRESHOLD,
        )

    async def record_mapping(
        self,
        tenant: TenantContext,
        *,
        vendor_name_raw: str,
        creditor_account_number: int,
    ) -> VendorAccountMapping:
        normalized = normalize_vendor_name(vendor_name_raw)
        mapping = await self._repository.upsert(
            tenant,
            vendor_name_raw=vendor_name_raw,
            vendor_name_normalized=normalized,
            creditor_account_number=creditor_account_number,
        )
        logger.info(
            "vendor_mapping_recorded",
            tenant_id=tenant.tenant_id,
            vendor_name_raw=vendor_name_raw,
            vendor_name_normalized=normalized,
            creditor_account_number=creditor_account_number,
            usage_count=mapping.usage_count,
        )
        return mapping

    async def resolve_for_export(
        self, tenant: TenantContext, vendor_name_raw: str, default: int
    ) -> int:
        suggestion = await self.suggest_for_vendor(tenant, vendor_name_raw)
        if suggestion is None or not suggestion.auto_apply:
            return default
        return suggestion.creditor_account_number
