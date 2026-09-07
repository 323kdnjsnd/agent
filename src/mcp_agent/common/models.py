"""Shared response models used by MCP tools and the report renderer."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class DataStatus(StrEnum):
    LIVE = "live"
    DEMO = "demo"
    ERROR = "error"


class SourceRef(BaseModel):
    title: str = ""
    url: HttpUrl | str
    publisher: str = ""
    accessed_at: date | None = None


class NewsItem(BaseModel):
    title: str
    summary: str = ""
    url: HttpUrl | str
    publisher: str = ""
    published_at: str = ""
    relevance: str = "medium"


class NewsSearchResponse(BaseModel):
    query: str
    days: int = Field(ge=1, le=30)
    data_status: DataStatus
    items: list[NewsItem] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ArticleResponse(BaseModel):
    url: HttpUrl | str
    title: str = ""
    publisher: str = ""
    published_at: str = ""
    text: str = ""
    data_status: DataStatus
    warnings: list[str] = Field(default_factory=list)


class ResourceEstimate(BaseModel):
    category: str
    quantity: float
    unit: str
    grade: str = ""
    mineral: str = "lithium"
    confidence: str = ""


class ResourceResponse(BaseModel):
    pdf_url: HttpUrl | str
    report_title: str = ""
    report_date: str = ""
    standard: str = "NI 43-101"
    data_status: DataStatus
    estimates: list[ResourceEstimate] = Field(default_factory=list)
    total_quantity: float | None = None
    unit: str = "t"
    warnings: list[str] = Field(default_factory=list)
    source: SourceRef | None = None


class PricePoint(BaseModel):
    date: date
    price: float
    currency: str = "USD"
    unit: str = "USD/t"

    @field_validator("price")
    @classmethod
    def finite_price(cls, value: float) -> float:
        if value < 0:
            raise ValueError("price cannot be negative")
        return value


class PriceResponse(BaseModel):
    commodity: str
    date: date
    data_status: DataStatus
    price: PricePoint | None = None
    source: SourceRef | None = None
    warnings: list[str] = Field(default_factory=list)


class TrendResponse(BaseModel):
    commodity: str
    days: int = Field(ge=2, le=90)
    data_status: DataStatus
    points: list[PricePoint] = Field(default_factory=list)
    start_price: float | None = None
    end_price: float | None = None
    change_percent: float | None = None
    direction: str = "unknown"
    source: SourceRef | None = None
    warnings: list[str] = Field(default_factory=list)


def model_payload(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe dict for MCP text content."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value
