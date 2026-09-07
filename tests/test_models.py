from datetime import date

import pytest
from pydantic import ValidationError

from mcp_agent.common.models import PricePoint, ResourceResponse


def test_price_point_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        PricePoint(date=date.today(), price=-1)


def test_resource_response_serializes_nested_source() -> None:
    result = ResourceResponse(pdf_url="https://example.com/report.pdf", data_status="demo")
    assert result.model_dump(mode="json")["data_status"] == "demo"
