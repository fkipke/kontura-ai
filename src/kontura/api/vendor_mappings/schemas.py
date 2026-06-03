"""Schemas fuer Vendor→Kreditor-Mappings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UpsertMappingPayload(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=255)
    creditor_account_number: int = Field(..., ge=10000, le=999999)


class MappingSuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creditor_account_number: int
    vendor_name_raw: str
    usage_count: int
    last_used_at: datetime
    confidence: float
    match_type: Literal["exact", "fuzzy"]
    auto_apply: bool


class VendorMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    vendor_name_normalized: str
    vendor_name_raw: str
    creditor_account_number: int
    usage_count: int
    last_used_at: datetime
    created_at: datetime
    updated_at: datetime
