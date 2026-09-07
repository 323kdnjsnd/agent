"""mineral-pdf-mcp: extract NI 43-101 resource estimates from public PDFs."""

from __future__ import annotations

import io
import os
import re

from mcp.server.fastmcp import FastMCP

from mcp_agent.common.http import HttpError, fetch_bytes
from mcp_agent.common.models import DataStatus, ResourceEstimate, ResourceResponse, SourceRef

mcp = FastMCP(
    "mineral-pdf-mcp", instructions="Extract Indicated and Inferred resources from NI 43-101 PDFs."
)

_DEMO_PDF_URL = "https://www.sedarplus.ca/"
_DEMO_TEXT = """NI 43-101 Technical Report - Pilbara Lithium Project
Effective Date: 2025-12-31
Mineral Resource Estimate
Indicated 245,000 tonnes at 1.20% Li2O
Inferred 89,000 tonnes at 1.05% Li2O
"""


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text with pdfplumber; kept separate for fixture-driven tests."""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise ValueError(f"PDF text extraction failed: {exc}") from exc


def parse_resource_text(text: str, pdf_url: str) -> ResourceResponse:
    standard = "NI 43-101" if re.search(r"NI\s*43[- ]?101", text, re.IGNORECASE) else "unknown"
    title_match = re.search(r"(?:technical report|project)\s*[-:–]\s*(.+)", text, re.IGNORECASE)
    report_title = title_match.group(0).strip() if title_match else "NI 43-101 resource report"
    date_match = re.search(
        r"(?:effective date|report date)\s*[:\-]?\s*(\d{4}[-/]\d{2}[-/]\d{2})", text, re.IGNORECASE
    )
    report_date = date_match.group(1).replace("/", "-") if date_match else ""
    estimates: list[ResourceEstimate] = []
    pattern = re.compile(
        r"\b(indicated|inferred)\b[^\n]{0,100}?([\d,.]+)\s*(million\s+)?(tonnes?|t)\b(?:[^\n]{0,80}?([\d,.]+)\s*%\s*(?:Li2O|Li))?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        quantity = float(match.group(2).replace(",", ""))
        if match.group(3):
            quantity *= 1_000_000
        estimates.append(
            ResourceEstimate(
                category=match.group(1).title(),
                quantity=quantity,
                unit="t",
                grade=f"{match.group(5)}% Li2O" if match.group(5) else "",
            )
        )
    warnings: list[str] = []
    if standard == "unknown":
        warnings.append("The document does not contain an explicit NI 43-101 marker.")
    if not estimates:
        warnings.append(
            "No Indicated/Inferred tonnage pattern was found; manual review is required."
        )
    total = sum(item.quantity for item in estimates) or None
    return ResourceResponse(
        pdf_url=pdf_url,
        report_title=report_title,
        report_date=report_date,
        standard=standard,
        data_status=DataStatus.LIVE if estimates else DataStatus.ERROR,
        estimates=estimates,
        total_quantity=total,
        warnings=warnings,
        source=SourceRef(title=report_title, url=pdf_url),
    )


def extract_resources_from_url(pdf_url: str) -> ResourceResponse:
    if not pdf_url.strip():
        raise ValueError("pdf_url must not be empty")
    if os.getenv("LIVE_DATA", "false").lower() != "true" and pdf_url == _DEMO_PDF_URL:
        result = parse_resource_text(_DEMO_TEXT, pdf_url)
        result.data_status = DataStatus.DEMO
        result.warnings.append(
            "Offline resource fixture used; verify against the issuer's current technical report."
        )
        return result
    try:
        text = extract_pdf_text(fetch_bytes(pdf_url))
        return parse_resource_text(text, pdf_url)
    except (HttpError, ValueError) as exc:
        return ResourceResponse(
            pdf_url=pdf_url,
            data_status=DataStatus.ERROR,
            warnings=[str(exc)],
            source=SourceRef(title="PDF source", url=pdf_url),
        )


@mcp.tool()
def extract_resources(pdf_url: str) -> dict:
    """Extract NI 43-101 Indicated and Inferred resources from a PDF URL."""
    return extract_resources_from_url(pdf_url).model_dump(mode="json")


if __name__ == "__main__":
    mcp.run(transport="stdio")
