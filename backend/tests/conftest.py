"""
Pytest configuration and fixtures.
"""

from pathlib import Path

import pytest


@pytest.fixture
def dummy_data_path() -> Path:
    """Get path to dummy data directory."""
    # Check Docker environment first
    docker_path = Path("/app/data")
    if docker_path.exists() and (docker_path / "forms").exists():
        return docker_path

    # Navigate from tests/ to the dummy_data folder (local development)
    # tests/ -> backend/ -> repo root
    current = Path(__file__).parent
    repo_root = current.parent.parent
    dummy_path = repo_root / "dummy_data"

    if not dummy_path.exists():
        pytest.skip(f"Dummy data directory not found: {dummy_path}")

    return dummy_path


@pytest.fixture
def forms_path(dummy_data_path: Path) -> Path:
    """Get path to forms directory."""
    return dummy_data_path / "forms"


@pytest.fixture
def emails_path(dummy_data_path: Path) -> Path:
    """Get path to emails directory."""
    return dummy_data_path / "emails"


@pytest.fixture
def invoices_path(dummy_data_path: Path) -> Path:
    """Get path to invoices directory."""
    return dummy_data_path / "invoices"


@pytest.fixture
def sample_form_html() -> str:
    """Sample HTML form content for testing."""
    return """<!DOCTYPE html>
<html lang="el">
<head><meta charset="UTF-8"><title>Test Form</title></head>
<body>
    <form>
        <input type="text" name="full_name" value="Τεστ Χρήστης">
        <input type="email" name="email" value="test@example.gr">
        <input type="tel" name="phone" value="210-1234567">
        <input type="text" name="company" value="Test Company">
        <select name="service"><option value="web_development" selected>Web</option></select>
        <textarea name="message">Test message</textarea>
        <input type="datetime-local" name="submission_date" value="2024-01-15T14:30">
        <select name="priority"><option value="high" selected>Υψηλή</option></select>
    </form>
</body>
</html>"""


@pytest.fixture
def sample_email_eml() -> str:
    """Sample EML content for testing."""
    return """From: Test User <test@example.gr>
To: info@ellincrm.gr
Subject: Test Request
Date: Mon, 20 Jan 2024 10:30:00 +0200
Content-Type: text/plain; charset=UTF-8

Καλησπέρα,

Είμαι ο Test User από την Test Company.

Στοιχεία Επικοινωνίας:
- Όνομα: Test User
- Email: test@example.gr
- Τηλέφωνο: 210-9876543
- Εταιρεία: Test Company

Χρειαζόμαστε CRM system.

Ευχαριστώ"""


@pytest.fixture
def sample_invoice_html() -> str:
    """Sample HTML invoice content for testing."""
    return """<!DOCTYPE html>
<html lang="el">
<head><meta charset="UTF-8"><title>Invoice</title></head>
<body>
    <h2>ΤΙΜΟΛΟΓΙΟ ΠΩΛΗΣΗΣ</h2>
    <div>
        <strong>Αριθμός:</strong> TF-2024-999<br>
        <strong>Ημερομηνία:</strong> 15/01/2024<br>
    </div>
    <div>
        <strong>Πελάτης:</strong><br>
        Test Client Ltd<br>
        ΑΦΜ: 123456789
    </div>
    <table class="invoice-table">
        <thead><tr><th>Περιγραφή</th><th>Ποσότητα</th><th>Τιμή</th><th>Σύνολο</th></tr></thead>
        <tbody>
            <tr><td>Item 1</td><td>10</td><td>€10.00</td><td>€100.00</td></tr>
        </tbody>
    </table>
    <div>
        <strong>Καθαρή Αξία:</strong> €100.00
        <strong>ΦΠΑ 24%:</strong> €24.00
        <strong>ΣΥΝΟΛΟ:</strong> €124.00
    </div>
</body>
</html>"""
