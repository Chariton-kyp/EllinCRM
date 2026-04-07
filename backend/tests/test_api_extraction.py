"""
Tests for the extraction API endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_list_files():
    """Test listing available files for extraction."""
    with patch("app.routers.extraction.settings") as mock_settings:
        from pathlib import Path
        import tempfile
        import os

        # Create temp directory with test files
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create subdirectories
            forms_dir = Path(tmpdir) / "forms"
            emails_dir = Path(tmpdir) / "emails"
            invoices_dir = Path(tmpdir) / "invoices"
            forms_dir.mkdir()
            emails_dir.mkdir()
            invoices_dir.mkdir()

            # Create test files
            (forms_dir / "contact_form_1.html").write_text("<html></html>")
            (emails_dir / "email_01.eml").write_text("From: test@test.com")
            (invoices_dir / "invoice_001.html").write_text("<html></html>")

            mock_settings.data_path = Path(tmpdir)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/extract/files")

            assert response.status_code == 200
            data = response.json()
            assert "files" in data
            assert "forms" in data["files"]
            assert "emails" in data["files"]
            assert "invoices" in data["files"]


@pytest.mark.anyio
async def test_health_endpoint():
    """Test health check endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data
    assert "version" in data


@pytest.mark.anyio
async def test_root_endpoint():
    """Test root endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "EllinCRM" in data["message"]


@pytest.mark.anyio
async def test_status_endpoint():
    """Test status endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/status")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data


@pytest.mark.integration
@pytest.mark.anyio
async def test_extract_form_file_not_found():
    """Test extracting a non-existent form file (requires DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/extract/form/nonexistent.html")

    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.anyio
async def test_extract_email_file_not_found():
    """Test extracting a non-existent email file (requires DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/extract/email/nonexistent.eml")

    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.anyio
async def test_extract_invoice_file_not_found():
    """Test extracting a non-existent invoice file (requires DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/extract/invoice/nonexistent.html")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_cors_headers():
    """Test CORS headers are present."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:7002",
                "Access-Control-Request-Method": "GET",
            },
        )

    # CORS should allow the request
    assert response.status_code == 200
