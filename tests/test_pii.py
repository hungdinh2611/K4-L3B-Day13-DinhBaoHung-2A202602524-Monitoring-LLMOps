from app.pii import scrub_text
from app.logging_config import scrub_event


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_vietnamese_identity_card() -> None:
    out = scrub_text("CCCD: 001099012345")
    assert "001099012345" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card() -> None:
    out = scrub_text("Card: 4111 1111 1111 1111")
    assert "4111 1111 1111 1111" not in out
    assert "REDACTED_CREDIT_CARD" in out


def test_scrub_event_redacts_nested_string_fields() -> None:
    event = {
        "session_id": "student@example.com",
        "payload": {"detail": ["Call 0901234567"]},
    }

    scrub_event(None, "info", event)

    assert "student@example.com" not in str(event)
    assert "0901234567" not in str(event)
