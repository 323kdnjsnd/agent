"""lme-price-mcp: price and trend tools with an explicit offline fixture mode."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from urllib.parse import urlencode

from mcp.server.fastmcp import FastMCP

from mcp_agent.common.http import HttpError, fetch_text
from mcp_agent.common.models import DataStatus, PricePoint, PriceResponse, SourceRef, TrendResponse

mcp = FastMCP(
    "lme-price-mcp", instructions="Return commodity prices and trends with data provenance."
)

# Lithium carbonate is not an LME-traded contract. This fixture is labelled accordingly.
_DEMO_PRICES = {
    "lithium": 12_450.0,
    "lithium carbonate": 12_450.0,
    "copper": 9_650.0,
    "nickel": 15_820.0,
}


def _normalise(commodity: str) -> str:
    value = commodity.strip().lower()
    if not value:
        raise ValueError("commodity must not be empty")
    return value


def _fixture_points(commodity: str, days: int, end: date) -> list[PricePoint]:
    current = _DEMO_PRICES.get(commodity, 1_000.0)
    points = []
    for offset in range(days - 1, -1, -1):
        point_date = end - timedelta(days=offset)
        # Stable deterministic series, intentionally not presented as live market data.
        factor = 1 + ((days - offset) - 1) * 0.004
        points.append(PricePoint(date=point_date, price=round(current * factor, 2)))
    return points


def _api_points(commodity: str, days: int, end: date) -> list[PricePoint]:
    endpoint = os.getenv("PRICE_API_URL", "").strip()
    if not endpoint:
        return []
    query = urlencode({"commodity": commodity, "days": days, "end_date": end.isoformat()})
    url = f"{endpoint}{'&' if '?' in endpoint else '?'}{query}"
    raw = json.loads(fetch_text(url, max_bytes=1_000_000))
    records = raw.get("prices", raw) if isinstance(raw, dict) else raw
    points = []
    for row in records:
        points.append(
            PricePoint(
                date=date.fromisoformat(str(row["date"])),
                price=float(row["price"]),
                currency=str(row.get("currency", "USD")),
                unit=str(row.get("unit", "USD/t")),
            )
        )
    return sorted(points, key=lambda item: item.date)[-days:]


def get_price_value(commodity: str, when: date | None = None) -> PriceResponse:
    commodity = _normalise(commodity)
    when = when or date.today()
    if os.getenv("LIVE_DATA", "false").lower() == "true" and os.getenv("PRICE_API_URL", "").strip():
        try:
            points = _api_points(commodity, 1, when)
            if points:
                point = points[-1].model_copy(update={"date": when})
                return PriceResponse(
                    commodity=commodity,
                    date=when,
                    data_status=DataStatus.LIVE,
                    price=point,
                    source=SourceRef(
                        title="Configured price API", url=os.getenv("PRICE_API_URL", "")
                    ),
                )
        except (HttpError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return PriceResponse(
                commodity=commodity, date=when, data_status=DataStatus.ERROR, warnings=[str(exc)]
            )
    point = _fixture_points(commodity, 1, when)[0]
    warning = (
        "Offline fixture used; lithium is not an LME-traded contract. "
        "Configure PRICE_API_URL for live data."
    )
    return PriceResponse(
        commodity=commodity,
        date=when,
        data_status=DataStatus.DEMO,
        price=point,
        source=SourceRef(title="Offline commodity price fixture", url="https://www.lme.com/"),
        warnings=[warning],
    )


def get_trend_value(commodity: str, days: int = 7, end: date | None = None) -> TrendResponse:
    commodity = _normalise(commodity)
    if not 2 <= days <= 90:
        raise ValueError("days must be between 2 and 90")
    end = end or date.today()
    status = DataStatus.DEMO
    warnings = ["Offline fixture used; configure PRICE_API_URL and LIVE_DATA=true for live data."]
    try:
        points = (
            _api_points(commodity, days, end)
            if os.getenv("LIVE_DATA", "false").lower() == "true"
            else []
        )
        if points:
            status = DataStatus.LIVE
            warnings = []
        else:
            points = _fixture_points(commodity, days, end)
    except (HttpError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return TrendResponse(
            commodity=commodity, days=days, data_status=DataStatus.ERROR, warnings=[str(exc)]
        )
    start, finish = points[0].price, points[-1].price
    change = ((finish - start) / start * 100) if start else None
    direction = "up" if (change or 0) > 0.1 else "down" if (change or 0) < -0.1 else "flat"
    return TrendResponse(
        commodity=commodity,
        days=days,
        data_status=status,
        points=points,
        start_price=start,
        end_price=finish,
        change_percent=round(change, 2) if change is not None else None,
        direction=direction,
        source=SourceRef(
            title="Configured price API" if status == DataStatus.LIVE else "Offline price fixture",
            url=os.getenv("PRICE_API_URL", "https://www.lme.com/"),
        ),
        warnings=warnings,
    )


@mcp.tool()
def get_price(commodity: str, date: str | None = None) -> dict:
    """Get a commodity price for YYYY-MM-DD, with provenance and data status."""
    when = (
        __import__("datetime").date.fromisoformat(date)
        if date
        else __import__("datetime").date.today()
    )
    return get_price_value(commodity, when).model_dump(mode="json")


@mcp.tool()
def get_trend(commodity: str, days: int = 7) -> dict:
    """Get a deterministic or configured-provider commodity trend for 2-90 days."""
    return get_trend_value(commodity, days).model_dump(mode="json")


if __name__ == "__main__":
    mcp.run(transport="stdio")
