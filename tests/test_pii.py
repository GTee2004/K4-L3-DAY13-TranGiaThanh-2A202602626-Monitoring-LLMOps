from app.pii import scrub_text, scrub_value


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


def test_scrub_phone_when_followed_by_other_numeric_pii() -> None:
    raw = "a@b.vn 0901234567 001099012345 4111 1111 1111 1111"

    out = scrub_text(raw)

    assert out == (
        "[REDACTED_EMAIL] "
        "[REDACTED_PHONE_VN] "
        "[REDACTED_CCCD] "
        "[REDACTED_CREDIT_CARD]"
    )
    for pii in ("a@b.vn", "0901234567", "001099012345", "4111 1111 1111 1111"):
        assert pii not in out


def test_scrub_cccd_12_digits() -> None:
    cccd = "001203012345"

    out = scrub_text(f"CCCD: {cccd}")

    assert cccd not in out
    assert "REDACTED_CCCD" in out


def test_scrub_payment_cards_with_spaces_or_hyphens() -> None:
    card_numbers = (
        "1234-5678-90123",
        "4111 1111 1111 1111",
        "5555-5555-5555-4444",
        "3782 822463 10005",
        "1234 5678 9012 3456 789",
    )

    for card_number in card_numbers:
        out = scrub_text(f"Card: {card_number}")
        assert card_number not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_scrub_nested_values_and_preserve_non_pii() -> None:
    raw_email = "student@vinuni.edu.vn"
    raw_phone = "84 90 123 4567"
    value = {
        "message": "Observability is useful",
        "metadata": {"contacts": [raw_email, raw_phone], "attempt": 2},
    }

    out = scrub_value(value)

    assert out["message"] == "Observability is useful"
    assert out["metadata"]["attempt"] == 2
    assert raw_email not in str(out)
    assert raw_phone not in str(out)
