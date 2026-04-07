"""
Greek Text Normalization for Hybrid Search.

Provides accent-insensitive text processing for Greek language search.
Enables matching "Δικηγορικό" with "δικηγορικο" or "ΔΙΚΗΓΟΡΙΚΟ".

Features:
- Greek diacritic/accent removal
- Case-insensitive normalization
- Greek stopwords filtering (optional)
- Unicode normalization
"""

import re
import unicodedata

# Greek accent mapping for normalization
GREEK_ACCENT_MAP = {
    # Lowercase with accents
    'ά': 'α', 'έ': 'ε', 'ή': 'η', 'ί': 'ι', 'ό': 'ο', 'ύ': 'υ', 'ώ': 'ω',
    # Uppercase with accents
    'Ά': 'α', 'Έ': 'ε', 'Ή': 'η', 'Ί': 'ι', 'Ό': 'ο', 'Ύ': 'υ', 'Ώ': 'ω',
    # Dialytika (dieresis)
    'ϊ': 'ι', 'ΐ': 'ι', 'ϋ': 'υ', 'ΰ': 'υ',
    'Ϊ': 'ι', 'Ϋ': 'υ',
}

# Greek stopwords (common words to optionally filter out)
GREEK_STOPWORDS: set[str] = {
    # Articles
    "ο", "η", "το", "οι", "τα", "των", "του", "της", "τον", "την",
    # Prepositions
    "σε", "από", "για", "με", "προς", "κατά", "μετά", "χωρίς", "στο", "στη", "στον", "στην",
    # Conjunctions
    "και", "ή", "αλλά", "ότι", "αν", "όταν", "ενώ", "επειδή",
    # Pronouns
    "αυτό", "αυτός", "αυτή", "εγώ", "εσύ", "εμείς", "εσείς",
    # Common verbs
    "είναι", "ήταν", "έχω", "έχει", "πρέπει", "μπορώ", "μπορεί",
    # Other common words
    "πως", "πώς", "πού", "που", "να", "θα", "δε", "δεν", "μη", "μην",
    # English stopwords (for mixed content)
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "and", "or", "but", "if", "of", "to", "in", "on", "for", "with",
}


def normalize_greek_text(text: str) -> str:
    """
    Normalize Greek text for accent-insensitive search.

    Transforms text to lowercase and removes Greek accents/diacritics.
    This enables matching "Δικηγορικό" with "δικηγορικο".

    Args:
        text: Input text (Greek, English, or mixed)

    Returns:
        Normalized lowercase text without accents

    Example:
        >>> normalize_greek_text("Δικηγορικό Γραφείο")
        'δικηγορικο γραφειο'
        >>> normalize_greek_text("ΚΏΣΤΑ & Συνεργάτες")
        'κωστα & συνεργατες'
    """
    if not text:
        return ""

    # Convert to lowercase first
    text = text.lower()

    # Remove Greek accents using mapping
    for accented, plain in GREEK_ACCENT_MAP.items():
        text = text.replace(accented, plain)

    # Additional Unicode normalization (NFD decomposition then remove combining marks)
    # This handles any remaining diacritics
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')

    return text


def tokenize_for_search(
    text: str,
    remove_stopwords: bool = False,
    min_token_length: int = 2
) -> list[str]:
    """
    Tokenize text for search with optional stopword removal.

    Args:
        text: Input text to tokenize
        remove_stopwords: Whether to remove common stopwords
        min_token_length: Minimum token length to include

    Returns:
        List of normalized tokens

    Example:
        >>> tokenize_for_search("Δικηγορικό Γραφείο Κ. Μάντζιου")
        ['δικηγορικο', 'γραφειο', 'μαντζιου']
    """
    if not text:
        return []

    # Normalize text first
    normalized = normalize_greek_text(text)

    # Split on non-word characters
    tokens = re.split(r'[^\w]+', normalized)

    # Filter tokens
    result = []
    for token in tokens:
        # Skip short tokens
        if len(token) < min_token_length:
            continue

        # Skip stopwords if requested
        if remove_stopwords and token in GREEK_STOPWORDS:
            continue

        result.append(token)

    return result


def extract_search_text(record_data: dict) -> str:
    """
    Extract searchable text from a record's extraction data.

    Combines relevant fields from forms, emails, and invoices
    into a single searchable string.

    Args:
        record_data: Dictionary containing extraction data

    Returns:
        Combined searchable text
    """
    parts = []

    # Form data
    if record_data.get("form_data"):
        form = record_data["form_data"]
        parts.extend([
            form.get("full_name", ""),
            form.get("company", ""),
            form.get("email", ""),
            form.get("message", ""),
            form.get("service_interest", ""),
        ])

    # Email data
    if record_data.get("email_data"):
        email = record_data["email_data"]
        parts.extend([
            email.get("sender_name", ""),
            email.get("sender_email", ""),
            email.get("subject", ""),
            email.get("body", ""),
            email.get("company", ""),
            email.get("vendor_name", ""),
        ])

    # Invoice data
    if record_data.get("invoice_data"):
        invoice = record_data["invoice_data"]
        parts.extend([
            invoice.get("client_name", ""),
            invoice.get("invoice_number", ""),
            invoice.get("client_address", ""),
            invoice.get("notes", ""),
        ])
        # Add item descriptions
        for item in invoice.get("items", []):
            parts.append(item.get("description", ""))

    # Filter empty parts and join
    text = " ".join(part for part in parts if part)
    return text


def create_search_vector_text(record_data: dict) -> str:
    """
    Create normalized text for tsvector storage.

    This text is stored in the database for full-text search
    and is normalized for accent-insensitive matching.

    Args:
        record_data: Dictionary containing extraction data

    Returns:
        Normalized searchable text for tsvector
    """
    raw_text = extract_search_text(record_data)
    return normalize_greek_text(raw_text)
