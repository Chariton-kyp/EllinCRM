"""
Extraction router for file processing endpoints.
Handles form, email, and invoice extraction with optional database persistence.
Integrates with AI embedding service for semantic search.

Uses LLM-first extraction (Gemini Flash) with automatic regex fallback when
LLM is unavailable or fails.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ai_router import get_ai_router
from app.ai.similarity import SimilaritySearchService
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import get_db
from app.db.repositories import RecordRepository
from app.extractors import EmailExtractor, FormExtractor, InvoiceExtractor, PDFInvoiceExtractor
from app.models.schemas import ExtractionResult
from app.services.llm_extractor import LLMExtractor
from app.services.record_service import RecordService

logger = get_logger(__name__)

router = APIRouter(prefix="/extract", tags=["extraction"])


# Dependency for RecordService with AI integration
async def get_record_service(db: AsyncSession = Depends(get_db)) -> RecordService:
    """Get RecordService with database session and AI embedding service."""
    repository = RecordRepository(db)
    similarity_service = SimilaritySearchService(db)
    return RecordService(repository, similarity_service)


async def _extract_with_fallback(
    file_path: Path,
    doc_type: str,
    regex_extractor,
) -> tuple[ExtractionResult, str]:
    """Try LLM extraction first, fall back to regex if LLM unavailable or fails.

    Args:
        file_path: Path to the document file.
        doc_type: One of "form", "email", "invoice".
        regex_extractor: Instance of the matching regex-based extractor.

    Returns:
        Tuple of (ExtractionResult, extraction_method) where method is "llm" or "regex".
    """
    # Try LLM extraction if AI router is available
    if get_ai_router() is not None:
        try:
            content = file_path.read_text(encoding="utf-8")
            llm = LLMExtractor()
            if doc_type == "form":
                result = await llm.extract_form(content, file_path.name)
            elif doc_type == "email":
                result = await llm.extract_email(content, file_path.name)
            else:
                result = await llm.extract_invoice(content, file_path.name)

            if not result.has_errors:
                logger.info(
                    "llm_extraction_success",
                    file=file_path.name,
                    type=doc_type,
                    confidence=result.confidence_score,
                )
                return result, "llm"
            else:
                logger.warning(
                    "llm_extraction_had_errors",
                    file=file_path.name,
                    errors=result.errors,
                )
                # Fall through to regex
        except Exception as e:
            logger.warning(
                "llm_extraction_failed_falling_back",
                file=file_path.name,
                error=str(e),
            )
            # Fall through to regex

    # Fallback: regex extraction
    logger.info("using_regex_extraction", file=file_path.name, type=doc_type)
    return regex_extractor.extract(file_path), "regex"


@router.get("/files")
async def list_available_files() -> dict[str, Any]:
    """
    List all available files for processing.

    Returns:
        Dictionary with file lists by type and total count.
    """
    data_path = settings.data_path
    files: dict[str, list[str]] = {
        "forms": [],
        "emails": [],
        "invoices": [],
    }

    forms_path = data_path / "forms"
    emails_path = data_path / "emails"
    invoices_path = data_path / "invoices"

    if forms_path.exists():
        files["forms"] = sorted([f.name for f in forms_path.glob("*.html")])

    if emails_path.exists():
        files["emails"] = sorted([f.name for f in emails_path.glob("*.eml")])

    if invoices_path.exists():
        # Support both HTML and PDF invoices
        html_invoices = [f.name for f in invoices_path.glob("*.html")]
        pdf_invoices = [f.name for f in invoices_path.glob("*.pdf")]
        files["invoices"] = sorted(html_invoices + pdf_invoices)

    return {
        "data_path": str(data_path),
        "files": files,
        "total_count": sum(len(f) for f in files.values()),
    }


@router.post("/form/{filename}")
async def extract_form(
    filename: str,
    save_record: bool = Query(False, description="Save to database for approval"),
    service: RecordService = Depends(get_record_service),
) -> dict[str, Any]:
    """
    Extract data from a contact form.

    Args:
        filename: Name of the HTML form file.
        save_record: If True, save extraction to database for approval workflow.
        service: RecordService dependency.

    Returns:
        Extraction result with optional record_id.
    """
    file_path = settings.data_path / "forms" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Form file not found: {filename}")

    extractor = FormExtractor()
    result, method = await _extract_with_fallback(file_path, "form", extractor)

    if result.has_errors:
        raise HTTPException(status_code=422, detail=result.errors)

    response: dict[str, Any] = {"extraction": result, "extraction_method": method}

    if save_record:
        record = await service.create_from_extraction(result)
        response["record_id"] = str(record.id)
        response["message"] = "Record created and pending approval"

    return response


@router.post("/email/{filename}")
async def extract_email(
    filename: str,
    save_record: bool = Query(False, description="Save to database for approval"),
    service: RecordService = Depends(get_record_service),
) -> dict[str, Any]:
    """
    Extract data from an email file.

    Args:
        filename: Name of the EML email file.
        save_record: If True, save extraction to database for approval workflow.
        service: RecordService dependency.

    Returns:
        Extraction result with optional record_id.
    """
    file_path = settings.data_path / "emails" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Email file not found: {filename}")

    extractor = EmailExtractor()
    result, method = await _extract_with_fallback(file_path, "email", extractor)

    if result.has_errors:
        raise HTTPException(status_code=422, detail=result.errors)

    response: dict[str, Any] = {"extraction": result, "extraction_method": method}

    if save_record:
        record = await service.create_from_extraction(result)
        response["record_id"] = str(record.id)
        response["message"] = "Record created and pending approval"

    return response


@router.post("/invoice/{filename}")
async def extract_invoice(
    filename: str,
    save_record: bool = Query(False, description="Save to database for approval"),
    service: RecordService = Depends(get_record_service),
) -> dict[str, Any]:
    """
    Extract data from an invoice file (HTML or PDF).

    Args:
        filename: Name of the invoice file (HTML or PDF).
        save_record: If True, save extraction to database for approval workflow.
        service: RecordService dependency.

    Returns:
        Extraction result with optional record_id.
    """
    file_path = settings.data_path / "invoices" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Invoice file not found: {filename}")

    # PDF invoices remain regex-only for now
    if file_path.suffix.lower() == ".pdf":
        if not PDFInvoiceExtractor.is_supported():
            raise HTTPException(
                status_code=501, detail="PDF extraction not supported - pdfplumber not installed"
            )
        pdf_extractor = PDFInvoiceExtractor()
        result = pdf_extractor.extract(file_path)
        method = "regex"
    else:
        extractor = InvoiceExtractor()
        result, method = await _extract_with_fallback(file_path, "invoice", extractor)

    if result.has_errors:
        raise HTTPException(status_code=422, detail=result.errors)

    response: dict[str, Any] = {"extraction": result, "extraction_method": method}

    if save_record:
        record = await service.create_from_extraction(result)
        response["record_id"] = str(record.id)
        response["message"] = "Record created and pending approval"

    return response


@router.post("/all")
async def extract_all_files(
    save_records: bool = Query(False, description="Save all to database for approval"),
    service: RecordService = Depends(get_record_service),
) -> dict[str, Any]:
    """
    Extract data from all available files.

    Args:
        save_records: If True, save all extractions to database.
        service: RecordService dependency.

    Returns:
        Results for all files with summary statistics.
    """
    results: dict[str, list[dict[str, Any]]] = {
        "forms": [],
        "emails": [],
        "invoices": [],
    }
    errors: list[dict[str, Any]] = []
    records_created = 0

    data_path = settings.data_path

    # Process forms
    form_extractor = FormExtractor()
    forms_path = data_path / "forms"
    if forms_path.exists():
        for form_file in sorted(forms_path.glob("*.html")):
            try:
                result, method = await _extract_with_fallback(form_file, "form", form_extractor)
                entry: dict[str, Any] = {
                    "file": form_file.name,
                    "success": not result.has_errors,
                    "confidence": result.confidence_score,
                    "extraction_method": method,
                    "data": result.form_data.model_dump() if result.form_data else None,
                    "warnings": result.warnings,
                }

                if save_records and not result.has_errors:
                    record = await service.create_from_extraction(result)
                    entry["record_id"] = str(record.id)
                    records_created += 1

                results["forms"].append(entry)
            except Exception as e:
                logger.error("form_extraction_failed", file=form_file.name, error=str(e))
                errors.append({"file": form_file.name, "error": str(e)})

    # Process emails
    email_extractor = EmailExtractor()
    emails_path = data_path / "emails"
    if emails_path.exists():
        for email_file in sorted(emails_path.glob("*.eml")):
            try:
                result, method = await _extract_with_fallback(email_file, "email", email_extractor)
                entry = {
                    "file": email_file.name,
                    "success": not result.has_errors,
                    "confidence": result.confidence_score,
                    "extraction_method": method,
                    "data": result.email_data.model_dump() if result.email_data else None,
                    "warnings": result.warnings,
                }

                if save_records and not result.has_errors:
                    record = await service.create_from_extraction(result)
                    entry["record_id"] = str(record.id)
                    records_created += 1

                results["emails"].append(entry)
            except Exception as e:
                logger.error("email_extraction_failed", file=email_file.name, error=str(e))
                errors.append({"file": email_file.name, "error": str(e)})

    # Process invoices (HTML and PDF)
    html_invoice_extractor = InvoiceExtractor()
    pdf_invoice_extractor = PDFInvoiceExtractor() if PDFInvoiceExtractor.is_supported() else None
    invoices_path = data_path / "invoices"
    if invoices_path.exists():
        # Process both HTML and PDF invoices
        invoice_files = list(invoices_path.glob("*.html")) + list(invoices_path.glob("*.pdf"))
        for invoice_file in sorted(invoice_files):
            try:
                # PDF invoices remain regex-only
                if invoice_file.suffix.lower() == ".pdf":
                    if not pdf_invoice_extractor:
                        errors.append(
                            {"file": invoice_file.name, "error": "PDF extraction not supported"}
                        )
                        continue
                    result = pdf_invoice_extractor.extract(invoice_file)
                    method = "regex"
                else:
                    result, method = await _extract_with_fallback(
                        invoice_file, "invoice", html_invoice_extractor
                    )
                entry = {
                    "file": invoice_file.name,
                    "success": not result.has_errors,
                    "confidence": result.confidence_score,
                    "extraction_method": method,
                    "data": result.invoice_data.model_dump() if result.invoice_data else None,
                    "warnings": result.warnings,
                }

                if save_records and not result.has_errors:
                    record = await service.create_from_extraction(result)
                    entry["record_id"] = str(record.id)
                    records_created += 1

                results["invoices"].append(entry)
            except Exception as e:
                logger.error("invoice_extraction_failed", file=invoice_file.name, error=str(e))
                errors.append({"file": invoice_file.name, "error": str(e)})

    return {
        "results": results,
        "summary": {
            "forms_processed": len(results["forms"]),
            "emails_processed": len(results["emails"]),
            "invoices_processed": len(results["invoices"]),
            "total_errors": len(errors),
            "records_created": records_created if save_records else None,
        },
        "errors": errors if errors else None,
    }
