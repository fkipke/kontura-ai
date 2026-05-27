from kontura.core.security.disposable_emails import is_disposable_email


def test_mailinator_is_disposable() -> None:
    assert is_disposable_email("user@mailinator.com") is True


def test_regular_provider_not_disposable() -> None:
    assert is_disposable_email("user@gmail.com") is False


def test_regular_provider_case_insensitive() -> None:
    assert is_disposable_email("user@GMAIL.com") is False


def test_invalid_email_without_at_is_not_disposable() -> None:
    assert is_disposable_email("not-an-email") is False
