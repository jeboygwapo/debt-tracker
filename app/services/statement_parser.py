"""AI-powered bank statement parser.

Accepts PDF or image bytes, converts to image if needed, sends to
gpt-4o-mini vision, returns structured extraction result.

File bytes are NEVER written to disk. Original content is discarded
after parsing — only the extracted data + SHA256 hash are kept.
"""
import base64
import hashlib
import io
import json
import re
from typing import Optional


SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
SUPPORTED_PDF_TYPE = "application/pdf"
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

_PARSE_PROMPT = """\
You are parsing a Philippine bank or financial account statement.
Extract ONLY these fields from the document:
- "balance": the closing/ending/available balance as a plain number (no currency symbols, no commas). Use the most recent balance shown. If ambiguous, use the highest balance on the page.
- "month": the statement period month as YYYY-MM (e.g. "2026-04"). Use the statement date or period end date.
- "account_hint": institution name and account type if visible (e.g. "BDO Savings", "BPI Checking", "PAG-IBIG MP2"), else null.

Return ONLY a JSON object with these three keys. No explanation. No markdown. Example:
{"balance": 125430.50, "month": "2026-04", "account_hint": "BDO Savings"}
"""


class ParseError(Exception):
    pass


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _pdf_to_image_bytes(pdf_bytes: bytes) -> bytes:
    """Convert first page of PDF to PNG bytes using pypdfium2."""
    try:
        import pypdfium2 as pdfium
    except ImportError as e:
        raise ParseError("pypdfium2 not installed — cannot parse PDF files.") from e

    doc = pdfium.PdfDocument(pdf_bytes)
    page = doc[0]
    bitmap = page.render(scale=2)  # 2x scale for legibility
    pil_image = bitmap.to_pil()
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return buf.getvalue()


def _to_base64_image(content: bytes, content_type: str) -> tuple[str, str]:
    """Return (base64_data, mime_type) ready for OpenAI vision API."""
    if content_type == SUPPORTED_PDF_TYPE:
        image_bytes = _pdf_to_image_bytes(content)
        mime = "image/png"
    elif content_type in SUPPORTED_IMAGE_TYPES:
        image_bytes = content
        mime = content_type
    else:
        raise ParseError(f"Unsupported file type: {content_type}. Upload PDF, JPG, PNG, or WEBP.")
    return base64.b64encode(image_bytes).decode(), mime


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise ParseError("AI response did not contain valid JSON.")
    try:
        return json.loads(m.group())
    except json.JSONDecodeError as e:
        raise ParseError(f"AI returned malformed JSON: {e}") from e


def _validate_result(data: dict) -> dict:
    balance = data.get("balance")
    month = data.get("month")

    if balance is None:
        raise ParseError("Could not extract balance from statement. Try a clearer image.")
    try:
        balance = float(str(balance).replace(",", ""))
    except (ValueError, TypeError) as e:
        raise ParseError(f"Balance value is not a number: {balance}") from e
    if balance < 0:
        raise ParseError("Extracted balance is negative — please verify the statement.")

    if month and not re.match(r"^\d{4}-\d{2}$", str(month)):
        month = None  # bad format, let user correct

    return {
        "balance": balance,
        "month": str(month) if month else None,
        "account_hint": str(data.get("account_hint") or "").strip() or None,
    }


async def parse_statement(
    content: bytes,
    content_type: str,
    api_key: str,
) -> dict:
    """Parse a statement file and return extracted data.

    Returns:
        {"balance": float, "month": str|None, "account_hint": str|None, "hash": str}

    Raises:
        ParseError on any failure.
    """
    if len(content) > MAX_FILE_BYTES:
        raise ParseError("File too large (max 10 MB).")

    file_hash = compute_file_hash(content)
    b64, mime = _to_base64_image(content, content_type)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PARSE_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
                        },
                    ],
                }
            ],
            max_tokens=200,
        )
    except Exception as e:
        raise ParseError(f"OpenAI API error: {e}") from e

    raw = resp.choices[0].message.content or ""
    data = _extract_json(raw)
    result = _validate_result(data)
    result["hash"] = file_hash
    return result
