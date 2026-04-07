"""
Tests for the records API endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.main import app
from app.db.models import ExtractionRecordDB


@pytest.fixture
def sample_record():
    """Create a sample extraction record."""
    return ExtractionRecordDB(
        id=uuid4(),
        source_file="/app/data/forms/contact_form_1.html",
        record_type="FORM",
        extracted_data={
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "123-456-7890",
            "company": "Test Company",
            "service_interest": "web_development",
            "message": "Test message",
            "priority": "high",
        },
        confidence_score=0.95,
        warnings=[],
        errors=[],
        status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_list_records_empty():
    """Test listing records when database is empty."""
    from app.routers.records import get_record_service

    mock_service = AsyncMock()
    mock_service.list_records.return_value = ([], 0)

    async def override_get_record_service():
        return mock_service

    app.dependency_overrides[get_record_service] = override_get_record_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/records")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["records"] == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_list_records_with_filters():
    """Test listing records with status and type filters."""
    from app.routers.records import get_record_service

    mock_service = AsyncMock()
    mock_service.list_records.return_value = ([], 0)

    async def override_get_record_service():
        return mock_service

    app.dependency_overrides[get_record_service] = override_get_record_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/records",
                params={"status": "pending", "record_type": "FORM"},
            )

        # Should return 200 regardless of data
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
@pytest.mark.anyio
async def test_get_stats():
    """Test getting dashboard statistics (requires DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/records/stats")

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "pending_count" in data
    assert "approved_count" in data
    assert "rejected_count" in data


@pytest.mark.anyio
async def test_get_record_not_found():
    """Test getting a non-existent record."""
    from app.routers.records import get_record_service

    mock_service = AsyncMock()
    mock_service.get_record.return_value = None  # Router checks for None

    async def override_get_record_service():
        return mock_service

    app.dependency_overrides[get_record_service] = override_get_record_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/records/{uuid4()}")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_approve_record_not_found():
    """Test approving a non-existent record."""
    from app.routers.records import get_record_service

    mock_service = AsyncMock()
    mock_service.approve.side_effect = ValueError("Record not found")

    async def override_get_record_service():
        return mock_service

    app.dependency_overrides[get_record_service] = override_get_record_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/records/{uuid4()}/approve",
                json={"notes": "Test approval"},
            )

        assert response.status_code in [400, 404]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_reject_record_not_found():
    """Test rejecting a non-existent record."""
    from app.routers.records import get_record_service

    mock_service = AsyncMock()
    mock_service.reject.side_effect = ValueError("Record not found")

    async def override_get_record_service():
        return mock_service

    app.dependency_overrides[get_record_service] = override_get_record_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/records/{uuid4()}/reject",
                json={"reason": "Test rejection"},
            )

        assert response.status_code in [400, 404]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
@pytest.mark.anyio
async def test_reject_record_missing_reason():
    """Test rejecting without providing a reason (requires DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/records/{uuid4()}/reject",
            json={},  # Missing reason
        )

    # Should return 422 (validation error) since reason is required
    assert response.status_code == 422


@pytest.mark.anyio
async def test_edit_record_not_found():
    """Test editing a non-existent record."""
    from app.routers.records import get_record_service

    mock_service = AsyncMock()
    mock_service.edit.side_effect = ValueError("Record not found")

    async def override_get_record_service():
        return mock_service

    app.dependency_overrides[get_record_service] = override_get_record_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/records/{uuid4()}",
                json={"data": {"full_name": "Updated Name"}},
            )

        assert response.status_code in [400, 404]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_export_no_records():
    """Test exporting when no records available."""
    from app.routers.records import get_export_service

    mock_service = AsyncMock()
    mock_service.export_records.side_effect = ValueError("No records to export")

    async def override_get_export_service():
        return mock_service

    app.dependency_overrides[get_export_service] = override_get_export_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/records/export",
                json={"format": "csv"},
            )

        # Should return 400 when no records to export
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
@pytest.mark.anyio
async def test_export_invalid_format():
    """Test exporting with invalid format (requires DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/records/export",
            json={"format": "invalid_format"},
        )

    # Should return validation error
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.anyio
async def test_batch_approve_empty():
    """Test batch approve with empty list returns validation error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/records/approve-batch",
            json=[],
        )

    # Empty list is correctly rejected with 422 validation error
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.anyio
async def test_batch_reject_empty():
    """Test batch reject with empty list returns validation error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/records/reject-batch",
            json=[],
            params={"reason": "Test reason"},
        )

    # Empty list is correctly rejected with 422 validation error
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.anyio
async def test_google_sheets_status():
    """Test Google Sheets status endpoint (requires DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/records/sheets/status")

    assert response.status_code == 200
    data = response.json()
    assert "configured" in data
    assert "message" in data


@pytest.mark.integration
@pytest.mark.anyio
async def test_google_sheets_create_not_configured():
    """Test creating spreadsheet when not configured (requires DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/records/sheets/create")

    # Should return 400 when not configured
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.anyio
async def test_google_sheets_sync_not_configured():
    """Test syncing to spreadsheet when not configured (requires DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/records/sheets/sync",
            params={"spreadsheet_id": "test_id"},
        )

    # Should return error when not configured (400 or 500 depending on setup)
    assert response.status_code in (400, 500)
